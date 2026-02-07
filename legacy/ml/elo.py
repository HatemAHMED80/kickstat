"""
ELO Rating System for Football Teams

The ELO system is one of the best predictors for match outcomes.
Originally designed for chess, adapted for football with:
- Home advantage factor
- Goal difference impact
- Match importance weighting
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from loguru import logger

from app.models import Team, Match, EloHistory


# Default parameters (tuned for football)
DEFAULT_K = 32  # K-factor: how much ratings change per match
HOME_ADVANTAGE = 100  # ELO points advantage for home team
INITIAL_ELO = 1500  # Starting ELO for new teams


@dataclass
class EloResult:
    """Result of an ELO calculation."""

    home_elo_before: float
    away_elo_before: float
    home_elo_after: float
    away_elo_after: float
    home_expected: float
    away_expected: float
    home_change: float
    away_change: float


class EloCalculator:
    """
    Calculate and update ELO ratings for teams.

    Usage:
        calculator = EloCalculator(db_session)
        calculator.initialize_teams()  # Set initial ELO
        calculator.process_all_matches()  # Calculate from history
    """

    def __init__(
        self,
        db: Session,
        k_factor: float = DEFAULT_K,
        home_advantage: float = HOME_ADVANTAGE,
    ):
        self.db = db
        self.k_factor = k_factor
        self.home_advantage = home_advantage

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """
        Calculate expected score for team A against team B.

        Returns probability between 0 and 1.
        """
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

    def actual_score(self, goals_a: int, goals_b: int) -> float:
        """
        Convert match result to score.

        Win = 1.0, Draw = 0.5, Loss = 0.0
        """
        if goals_a > goals_b:
            return 1.0
        elif goals_a < goals_b:
            return 0.0
        else:
            return 0.5

    def goal_difference_multiplier(self, goal_diff: int) -> float:
        """
        Adjust K-factor based on goal difference.

        Bigger wins should have more impact on ratings.
        Formula from World Football Elo Ratings.
        """
        goal_diff = abs(goal_diff)
        if goal_diff <= 1:
            return 1.0
        elif goal_diff == 2:
            return 1.5
        else:
            return (11 + goal_diff) / 8

    def calculate_match(
        self,
        home_elo: float,
        away_elo: float,
        home_goals: int,
        away_goals: int,
        k_factor: Optional[float] = None,
    ) -> EloResult:
        """
        Calculate new ELO ratings after a match.

        Args:
            home_elo: Home team's current ELO
            away_elo: Away team's current ELO
            home_goals: Goals scored by home team
            away_goals: Goals scored by away team
            k_factor: Optional custom K-factor

        Returns:
            EloResult with before/after ratings
        """
        k = k_factor or self.k_factor

        # Adjust for home advantage
        adjusted_home_elo = home_elo + self.home_advantage

        # Expected scores
        home_expected = self.expected_score(adjusted_home_elo, away_elo)
        away_expected = 1 - home_expected

        # Actual scores
        home_actual = self.actual_score(home_goals, away_goals)
        away_actual = 1 - home_actual

        # Goal difference multiplier
        goal_diff = abs(home_goals - away_goals)
        multiplier = self.goal_difference_multiplier(goal_diff)

        # Calculate changes
        home_change = k * multiplier * (home_actual - home_expected)
        away_change = k * multiplier * (away_actual - away_expected)

        return EloResult(
            home_elo_before=home_elo,
            away_elo_before=away_elo,
            home_elo_after=home_elo + home_change,
            away_elo_after=away_elo + away_change,
            home_expected=home_expected,
            away_expected=away_expected,
            home_change=home_change,
            away_change=away_change,
        )

    def predict_match(
        self,
        home_elo: float,
        away_elo: float,
    ) -> dict:
        """
        Predict match outcome based on ELO ratings.

        Returns probabilities for home win, draw, away win.
        """
        # Adjust for home advantage
        adjusted_home_elo = home_elo + self.home_advantage

        # Expected score (probability of home team winning)
        home_expected = self.expected_score(adjusted_home_elo, away_elo)

        # Convert to 1X2 probabilities
        # Draw probability is estimated based on rating difference
        elo_diff = abs(adjusted_home_elo - away_elo)

        # Draw probability decreases as rating difference increases
        # Typical draw rate in football is ~25%
        base_draw_prob = 0.25
        draw_prob = base_draw_prob * (1 - elo_diff / 1000)
        draw_prob = max(0.10, min(0.35, draw_prob))  # Clamp between 10-35%

        # Distribute remaining probability
        remaining = 1 - draw_prob

        if home_expected > 0.5:
            home_win = remaining * home_expected
            away_win = remaining * (1 - home_expected)
        else:
            home_win = remaining * home_expected
            away_win = remaining * (1 - home_expected)

        # Normalize to ensure sum = 1
        total = home_win + draw_prob + away_win

        return {
            "home_win": round(home_win / total, 3),
            "draw": round(draw_prob / total, 3),
            "away_win": round(away_win / total, 3),
        }

    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================

    def initialize_teams(self, initial_elo: float = INITIAL_ELO) -> int:
        """Set initial ELO for all teams without a rating."""
        teams = self.db.execute(
            select(Team).where(Team.elo_rating == None)
        ).scalars().all()

        for team in teams:
            team.elo_rating = initial_elo

        self.db.commit()
        logger.info(f"Initialized {len(teams)} teams with ELO {initial_elo}")
        return len(teams)

    def process_match(self, match: Match, save_history: bool = True) -> Optional[EloResult]:
        """
        Process a single match and update team ratings.

        Args:
            match: Match object (must be finished with scores)
            save_history: Whether to save ELO history

        Returns:
            EloResult or None if match can't be processed
        """
        if match.status != "finished" or match.home_score is None:
            return None

        home_team = self.db.get(Team, match.home_team_id)
        away_team = self.db.get(Team, match.away_team_id)

        if not home_team or not away_team:
            return None

        # Get current ratings (or initialize)
        home_elo = home_team.elo_rating or INITIAL_ELO
        away_elo = away_team.elo_rating or INITIAL_ELO

        # Calculate new ratings
        result = self.calculate_match(
            home_elo=home_elo,
            away_elo=away_elo,
            home_goals=match.home_score,
            away_goals=match.away_score,
        )

        # Update teams
        home_team.elo_rating = result.home_elo_after
        away_team.elo_rating = result.away_elo_after

        # Save history
        if save_history:
            self.db.add(EloHistory(
                team_id=home_team.id,
                match_id=match.id,
                elo_before=result.home_elo_before,
                elo_after=result.home_elo_after,
                elo_change=result.home_change,
                recorded_at=match.kickoff,
            ))
            self.db.add(EloHistory(
                team_id=away_team.id,
                match_id=match.id,
                elo_before=result.away_elo_before,
                elo_after=result.away_elo_after,
                elo_change=result.away_change,
                recorded_at=match.kickoff,
            ))

        return result

    def process_all_matches(self, save_history: bool = True) -> int:
        """
        Process all finished matches in chronological order.

        This recalculates all ELO ratings from scratch.
        """
        # Initialize all teams first
        self.initialize_teams()

        # Get all finished matches ordered by date
        matches = self.db.execute(
            select(Match)
            .where(Match.status == "finished")
            .order_by(Match.kickoff)
        ).scalars().all()

        processed = 0
        for match in matches:
            result = self.process_match(match, save_history=save_history)
            if result:
                processed += 1

        self.db.commit()
        logger.info(f"Processed {processed} matches for ELO calculation")
        return processed

    def get_team_elo(self, team_id: int) -> float:
        """Get current ELO for a team."""
        team = self.db.get(Team, team_id)
        return team.elo_rating if team else INITIAL_ELO

    def get_rankings(self, limit: int = 20) -> list[tuple[Team, float]]:
        """Get teams ranked by ELO rating."""
        teams = self.db.execute(
            select(Team)
            .where(Team.elo_rating != None)
            .order_by(Team.elo_rating.desc())
            .limit(limit)
        ).scalars().all()

        return [(team, team.elo_rating) for team in teams]

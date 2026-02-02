"""
Feature Engineering for Match Prediction

Combines all features into a single feature vector for ML models.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from loguru import logger

from app.models import Team, Match, Standing, Player
from app.services.ml.elo import EloCalculator, INITIAL_ELO
from app.services.ml.form import FormCalculator


@dataclass
class MatchFeatures:
    """
    Feature vector for a single match.

    All features are numeric for ML model input.
    """

    match_id: int
    home_team_id: int
    away_team_id: int
    kickoff: datetime

    # === ELO Features ===
    home_elo: float = INITIAL_ELO
    away_elo: float = INITIAL_ELO
    elo_diff: float = 0.0  # home - away
    elo_home_expected: float = 0.5  # Expected score from ELO

    # === Standing Features ===
    home_position: int = 10
    away_position: int = 10
    position_diff: int = 0  # away - home (positive = home is better)
    home_points: int = 0
    away_points: int = 0
    points_diff: int = 0

    # === Form Features (last 5 matches) ===
    home_form_points: int = 0  # Points in last 5
    away_form_points: int = 0
    home_form_goals: int = 0
    away_form_goals: int = 0
    home_form_conceded: int = 0
    away_form_conceded: int = 0
    home_form_win_rate: float = 0.0
    away_form_win_rate: float = 0.0

    # === Home/Away Specific Form ===
    home_home_form_points: int = 0  # Home team's home form
    away_away_form_points: int = 0  # Away team's away form

    # === Goal Stats ===
    home_goals_per_match: float = 0.0
    away_goals_per_match: float = 0.0
    home_conceded_per_match: float = 0.0
    away_conceded_per_match: float = 0.0

    # === Streaks ===
    home_unbeaten_run: int = 0
    away_unbeaten_run: int = 0
    home_winless_run: int = 0
    away_winless_run: int = 0

    # === Head to Head ===
    h2h_matches: int = 0
    h2h_home_wins: int = 0
    h2h_draws: int = 0
    h2h_away_wins: int = 0
    h2h_home_goals: int = 0
    h2h_away_goals: int = 0

    # === Rest Days ===
    home_rest_days: int = 7
    away_rest_days: int = 7

    # === Squad Availability ===
    home_injuries: int = 0
    away_injuries: int = 0

    # === Target (for training) ===
    result: Optional[str] = None  # "H", "D", "A"
    home_score: Optional[int] = None
    away_score: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame."""
        return {k: v for k, v in self.__dict__.items()}

    def get_feature_vector(self) -> list[float]:
        """
        Get numeric feature vector for ML model.

        Returns list of features in consistent order.
        """
        return [
            self.home_elo,
            self.away_elo,
            self.elo_diff,
            self.elo_home_expected,
            float(self.home_position),
            float(self.away_position),
            float(self.position_diff),
            float(self.home_points),
            float(self.away_points),
            float(self.points_diff),
            float(self.home_form_points),
            float(self.away_form_points),
            float(self.home_form_goals),
            float(self.away_form_goals),
            float(self.home_form_conceded),
            float(self.away_form_conceded),
            self.home_form_win_rate,
            self.away_form_win_rate,
            float(self.home_home_form_points),
            float(self.away_away_form_points),
            self.home_goals_per_match,
            self.away_goals_per_match,
            self.home_conceded_per_match,
            self.away_conceded_per_match,
            float(self.home_unbeaten_run),
            float(self.away_unbeaten_run),
            float(self.home_winless_run),
            float(self.away_winless_run),
            float(self.h2h_matches),
            float(self.h2h_home_wins),
            float(self.h2h_draws),
            float(self.h2h_away_wins),
            float(self.home_rest_days),
            float(self.away_rest_days),
            float(self.home_injuries),
            float(self.away_injuries),
        ]

    @staticmethod
    def get_feature_names() -> list[str]:
        """Get names of features in order."""
        return [
            "home_elo",
            "away_elo",
            "elo_diff",
            "elo_home_expected",
            "home_position",
            "away_position",
            "position_diff",
            "home_points",
            "away_points",
            "points_diff",
            "home_form_points",
            "away_form_points",
            "home_form_goals",
            "away_form_goals",
            "home_form_conceded",
            "away_form_conceded",
            "home_form_win_rate",
            "away_form_win_rate",
            "home_home_form_points",
            "away_away_form_points",
            "home_goals_per_match",
            "away_goals_per_match",
            "home_conceded_per_match",
            "away_conceded_per_match",
            "home_unbeaten_run",
            "away_unbeaten_run",
            "home_winless_run",
            "away_winless_run",
            "h2h_matches",
            "h2h_home_wins",
            "h2h_draws",
            "h2h_away_wins",
            "home_rest_days",
            "away_rest_days",
            "home_injuries",
            "away_injuries",
        ]


class FeatureEngineer:
    """
    Generate features for match prediction.

    Usage:
        engineer = FeatureEngineer(db_session)
        features = engineer.extract_features(match)
        training_data = engineer.prepare_training_data()
    """

    def __init__(self, db: Session):
        self.db = db
        self.elo_calc = EloCalculator(db)
        self.form_calc = FormCalculator(db)

    def extract_features(self, match: Match) -> MatchFeatures:
        """
        Extract all features for a match.

        For training: use match kickoff date to avoid data leakage
        For prediction: use current date
        """
        features = MatchFeatures(
            match_id=match.id,
            home_team_id=match.home_team_id,
            away_team_id=match.away_team_id,
            kickoff=match.kickoff,
        )

        # Get teams
        home_team = self.db.get(Team, match.home_team_id)
        away_team = self.db.get(Team, match.away_team_id)

        if not home_team or not away_team:
            return features

        # === ELO Features ===
        features.home_elo = home_team.elo_rating or INITIAL_ELO
        features.away_elo = away_team.elo_rating or INITIAL_ELO
        features.elo_diff = features.home_elo - features.away_elo

        prediction = self.elo_calc.predict_match(features.home_elo, features.away_elo)
        features.elo_home_expected = prediction["home_win"]

        # === Standing Features ===
        self._add_standing_features(features, home_team, away_team)

        # === Form Features ===
        self._add_form_features(features, match)

        # === H2H Features ===
        self._add_h2h_features(features, home_team.id, away_team.id)

        # === Rest Days ===
        self._add_rest_days(features, match)

        # === Injuries ===
        self._add_injury_features(features, home_team.id, away_team.id)

        # === Target (if match is finished) ===
        if match.status == "finished" and match.home_score is not None:
            features.home_score = match.home_score
            features.away_score = match.away_score

            if match.home_score > match.away_score:
                features.result = "H"
            elif match.home_score < match.away_score:
                features.result = "A"
            else:
                features.result = "D"

        return features

    def _add_standing_features(
        self,
        features: MatchFeatures,
        home_team: Team,
        away_team: Team,
    ) -> None:
        """Add league standing features."""
        # Get standings for both teams
        home_standing = self.db.execute(
            select(Standing).where(Standing.team_id == home_team.id)
        ).scalar_one_or_none()

        away_standing = self.db.execute(
            select(Standing).where(Standing.team_id == away_team.id)
        ).scalar_one_or_none()

        if home_standing:
            features.home_position = home_standing.position
            features.home_points = home_standing.points

        if away_standing:
            features.away_position = away_standing.position
            features.away_points = away_standing.points

        features.position_diff = features.away_position - features.home_position
        features.points_diff = features.home_points - features.away_points

    def _add_form_features(self, features: MatchFeatures, match: Match) -> None:
        """Add recent form features."""
        # Use match date to avoid data leakage
        before_date = match.kickoff

        # Overall form
        home_form = self.form_calc.get_team_form(
            match.home_team_id, last_n=5, before_date=before_date
        )
        away_form = self.form_calc.get_team_form(
            match.away_team_id, last_n=5, before_date=before_date
        )

        features.home_form_points = home_form.points
        features.away_form_points = away_form.points
        features.home_form_goals = home_form.goals_scored
        features.away_form_goals = away_form.goals_scored
        features.home_form_conceded = home_form.goals_conceded
        features.away_form_conceded = away_form.goals_conceded
        features.home_form_win_rate = home_form.win_rate
        features.away_form_win_rate = away_form.win_rate

        features.home_goals_per_match = home_form.goals_per_match
        features.away_goals_per_match = away_form.goals_per_match
        features.home_conceded_per_match = home_form.conceded_per_match
        features.away_conceded_per_match = away_form.conceded_per_match

        features.home_unbeaten_run = home_form.unbeaten_run
        features.away_unbeaten_run = away_form.unbeaten_run
        features.home_winless_run = home_form.winless_run
        features.away_winless_run = away_form.winless_run

        # Home/Away specific form
        home_home_form = self.form_calc.get_home_form(
            match.home_team_id, last_n=5, before_date=before_date
        )
        away_away_form = self.form_calc.get_away_form(
            match.away_team_id, last_n=5, before_date=before_date
        )

        features.home_home_form_points = home_home_form.points
        features.away_away_form_points = away_away_form.points

    def _add_h2h_features(
        self,
        features: MatchFeatures,
        home_team_id: int,
        away_team_id: int,
    ) -> None:
        """Add head-to-head features."""
        h2h = self.form_calc.get_h2h_record(home_team_id, away_team_id, last_n=10)

        features.h2h_matches = h2h["matches"]
        features.h2h_home_wins = h2h["team1_wins"]
        features.h2h_draws = h2h["draws"]
        features.h2h_away_wins = h2h["team2_wins"]
        features.h2h_home_goals = h2h["team1_goals"]
        features.h2h_away_goals = h2h["team2_goals"]

    def _add_rest_days(self, features: MatchFeatures, match: Match) -> None:
        """Calculate rest days since last match."""
        # Home team's last match
        home_last = self.db.execute(
            select(Match)
            .where(
                Match.status == "finished",
                Match.kickoff < match.kickoff,
                (Match.home_team_id == match.home_team_id) |
                (Match.away_team_id == match.home_team_id),
            )
            .order_by(Match.kickoff.desc())
            .limit(1)
        ).scalar_one_or_none()

        if home_last:
            delta = match.kickoff - home_last.kickoff
            features.home_rest_days = min(delta.days, 30)  # Cap at 30

        # Away team's last match
        away_last = self.db.execute(
            select(Match)
            .where(
                Match.status == "finished",
                Match.kickoff < match.kickoff,
                (Match.home_team_id == match.away_team_id) |
                (Match.away_team_id == match.away_team_id),
            )
            .order_by(Match.kickoff.desc())
            .limit(1)
        ).scalar_one_or_none()

        if away_last:
            delta = match.kickoff - away_last.kickoff
            features.away_rest_days = min(delta.days, 30)

    def _add_injury_features(
        self,
        features: MatchFeatures,
        home_team_id: int,
        away_team_id: int,
    ) -> None:
        """Count injured players per team."""
        home_injuries = self.db.execute(
            select(func.count(Player.id))
            .where(
                Player.team_id == home_team_id,
                Player.injury_status == "injured",
            )
        ).scalar()

        away_injuries = self.db.execute(
            select(func.count(Player.id))
            .where(
                Player.team_id == away_team_id,
                Player.injury_status == "injured",
            )
        ).scalar()

        features.home_injuries = home_injuries or 0
        features.away_injuries = away_injuries or 0

    # =========================================================================
    # TRAINING DATA PREPARATION
    # =========================================================================

    def prepare_training_data(
        self,
        min_matches: int = 5,
    ) -> tuple[list[list[float]], list[str]]:
        """
        Prepare training data from all finished matches.

        Args:
            min_matches: Minimum matches before a team's games are included

        Returns:
            (X, y) tuple where X is feature matrix and y is results
        """
        logger.info("Preparing training data...")

        # Get all finished matches
        matches = self.db.execute(
            select(Match)
            .where(Match.status == "finished", Match.home_score != None)
            .order_by(Match.kickoff)
        ).scalars().all()

        X = []
        y = []

        for i, match in enumerate(matches):
            # Skip early matches (not enough history)
            if i < min_matches * 2:  # Need history for both teams
                continue

            try:
                features = self.extract_features(match)

                if features.result:
                    X.append(features.get_feature_vector())
                    y.append(features.result)

            except Exception as e:
                logger.warning(f"Failed to extract features for match {match.id}: {e}")
                continue

        logger.info(f"Prepared {len(X)} samples for training")
        return X, y

    def get_prediction_features(self, match: Match) -> MatchFeatures:
        """
        Get features for a future match prediction.

        Uses current data (not historical) for standings, form, etc.
        """
        return self.extract_features(match)

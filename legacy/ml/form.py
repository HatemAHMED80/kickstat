"""
Team Form Calculator

Analyzes recent match results to compute form metrics.
Form is a strong predictor of short-term performance.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, and_, desc
from loguru import logger

from app.models import Team, Match


@dataclass
class FormStats:
    """Team form statistics."""

    team_id: int
    team_name: str
    matches_played: int

    # Results
    wins: int
    draws: int
    losses: int
    points: int  # 3 for win, 1 for draw

    # Goals
    goals_scored: int
    goals_conceded: int
    goal_difference: int
    clean_sheets: int

    # Streaks
    current_streak: str  # "W3", "D1", "L2"
    unbeaten_run: int
    winless_run: int

    # Derived metrics
    points_per_match: float
    goals_per_match: float
    conceded_per_match: float
    win_rate: float

    # Form string (last 5 results)
    form_string: str  # "WWDLW"


class FormCalculator:
    """
    Calculate team form from recent matches.

    Usage:
        calculator = FormCalculator(db_session)
        form = calculator.get_team_form(team_id, last_n=5)
        home_form = calculator.get_home_form(team_id, last_n=5)
    """

    def __init__(self, db: Session):
        self.db = db

    def get_team_matches(
        self,
        team_id: int,
        last_n: int = 5,
        home_only: bool = False,
        away_only: bool = False,
        before_date: Optional[datetime] = None,
    ) -> list[Match]:
        """
        Get recent finished matches for a team.

        Args:
            team_id: Team database ID
            last_n: Number of matches to retrieve
            home_only: Only home matches
            away_only: Only away matches
            before_date: Only matches before this date
        """
        query = select(Match).where(
            Match.status == "finished",
            Match.home_score != None,
        )

        if home_only:
            query = query.where(Match.home_team_id == team_id)
        elif away_only:
            query = query.where(Match.away_team_id == team_id)
        else:
            query = query.where(
                or_(
                    Match.home_team_id == team_id,
                    Match.away_team_id == team_id,
                )
            )

        if before_date:
            query = query.where(Match.kickoff < before_date)

        query = query.order_by(desc(Match.kickoff)).limit(last_n)

        return list(self.db.execute(query).scalars().all())

    def calculate_form(
        self,
        team_id: int,
        matches: list[Match],
    ) -> FormStats:
        """
        Calculate form statistics from a list of matches.

        Args:
            team_id: Team database ID
            matches: List of Match objects
        """
        team = self.db.get(Team, team_id)
        team_name = team.name if team else f"Team {team_id}"

        if not matches:
            return FormStats(
                team_id=team_id,
                team_name=team_name,
                matches_played=0,
                wins=0, draws=0, losses=0, points=0,
                goals_scored=0, goals_conceded=0, goal_difference=0, clean_sheets=0,
                current_streak="", unbeaten_run=0, winless_run=0,
                points_per_match=0.0, goals_per_match=0.0, conceded_per_match=0.0,
                win_rate=0.0, form_string="",
            )

        wins = draws = losses = 0
        goals_scored = goals_conceded = 0
        clean_sheets = 0
        results = []

        for match in matches:
            is_home = match.home_team_id == team_id

            if is_home:
                scored = match.home_score
                conceded = match.away_score
            else:
                scored = match.away_score
                conceded = match.home_score

            goals_scored += scored
            goals_conceded += conceded

            if conceded == 0:
                clean_sheets += 1

            if scored > conceded:
                wins += 1
                results.append("W")
            elif scored < conceded:
                losses += 1
                results.append("L")
            else:
                draws += 1
                results.append("D")

        # Calculate streaks (from most recent)
        current_streak = self._calculate_streak(results)
        unbeaten_run = self._calculate_unbeaten_run(results)
        winless_run = self._calculate_winless_run(results)

        # Points and derived stats
        points = wins * 3 + draws
        n = len(matches)

        return FormStats(
            team_id=team_id,
            team_name=team_name,
            matches_played=n,
            wins=wins,
            draws=draws,
            losses=losses,
            points=points,
            goals_scored=goals_scored,
            goals_conceded=goals_conceded,
            goal_difference=goals_scored - goals_conceded,
            clean_sheets=clean_sheets,
            current_streak=current_streak,
            unbeaten_run=unbeaten_run,
            winless_run=winless_run,
            points_per_match=round(points / n, 2),
            goals_per_match=round(goals_scored / n, 2),
            conceded_per_match=round(goals_conceded / n, 2),
            win_rate=round(wins / n, 2),
            form_string="".join(results),  # Most recent first
        )

    def _calculate_streak(self, results: list[str]) -> str:
        """Calculate current streak (e.g., 'W3', 'D1', 'L2')."""
        if not results:
            return ""

        current = results[0]
        count = 1

        for r in results[1:]:
            if r == current:
                count += 1
            else:
                break

        return f"{current}{count}"

    def _calculate_unbeaten_run(self, results: list[str]) -> int:
        """Count consecutive matches without a loss."""
        count = 0
        for r in results:
            if r != "L":
                count += 1
            else:
                break
        return count

    def _calculate_winless_run(self, results: list[str]) -> int:
        """Count consecutive matches without a win."""
        count = 0
        for r in results:
            if r != "W":
                count += 1
            else:
                break
        return count

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def get_team_form(
        self,
        team_id: int,
        last_n: int = 5,
        before_date: Optional[datetime] = None,
    ) -> FormStats:
        """Get overall form for a team."""
        matches = self.get_team_matches(team_id, last_n, before_date=before_date)
        return self.calculate_form(team_id, matches)

    def get_home_form(
        self,
        team_id: int,
        last_n: int = 5,
        before_date: Optional[datetime] = None,
    ) -> FormStats:
        """Get home form for a team."""
        matches = self.get_team_matches(
            team_id, last_n, home_only=True, before_date=before_date
        )
        return self.calculate_form(team_id, matches)

    def get_away_form(
        self,
        team_id: int,
        last_n: int = 5,
        before_date: Optional[datetime] = None,
    ) -> FormStats:
        """Get away form for a team."""
        matches = self.get_team_matches(
            team_id, last_n, away_only=True, before_date=before_date
        )
        return self.calculate_form(team_id, matches)

    def get_h2h_record(
        self,
        team1_id: int,
        team2_id: int,
        last_n: int = 10,
    ) -> dict:
        """
        Get head-to-head record between two teams.

        Returns stats from team1's perspective.
        """
        query = select(Match).where(
            Match.status == "finished",
            Match.home_score != None,
            or_(
                and_(Match.home_team_id == team1_id, Match.away_team_id == team2_id),
                and_(Match.home_team_id == team2_id, Match.away_team_id == team1_id),
            ),
        ).order_by(desc(Match.kickoff)).limit(last_n)

        matches = list(self.db.execute(query).scalars().all())

        if not matches:
            return {
                "matches": 0,
                "team1_wins": 0,
                "draws": 0,
                "team2_wins": 0,
                "team1_goals": 0,
                "team2_goals": 0,
            }

        team1_wins = draws = team2_wins = 0
        team1_goals = team2_goals = 0

        for match in matches:
            if match.home_team_id == team1_id:
                t1_scored = match.home_score
                t2_scored = match.away_score
            else:
                t1_scored = match.away_score
                t2_scored = match.home_score

            team1_goals += t1_scored
            team2_goals += t2_scored

            if t1_scored > t2_scored:
                team1_wins += 1
            elif t1_scored < t2_scored:
                team2_wins += 1
            else:
                draws += 1

        return {
            "matches": len(matches),
            "team1_wins": team1_wins,
            "draws": draws,
            "team2_wins": team2_wins,
            "team1_goals": team1_goals,
            "team2_goals": team2_goals,
        }

    def compare_form(
        self,
        team1_id: int,
        team2_id: int,
        last_n: int = 5,
    ) -> dict:
        """Compare recent form between two teams."""
        form1 = self.get_team_form(team1_id, last_n)
        form2 = self.get_team_form(team2_id, last_n)

        return {
            "team1": form1,
            "team2": form2,
            "points_diff": form1.points - form2.points,
            "goal_diff_diff": form1.goal_difference - form2.goal_difference,
            "win_rate_diff": round(form1.win_rate - form2.win_rate, 2),
        }

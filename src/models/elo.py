"""ELO rating system for football teams.

Based on World Football Elo Ratings methodology with goal difference adjustment.
"""

from dataclasses import dataclass


@dataclass
class EloMatch:
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int


class EloRating:
    """ELO rating system with home advantage and goal difference scaling."""

    def __init__(
        self,
        k_factor: float = 32,
        home_advantage: float = 100,
        initial_rating: float = 1500,
    ):
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.ratings: dict[str, float] = {}

    def _expected_score(self, rating_a: float, rating_b: float) -> float:
        """Expected score for team A vs team B."""
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))

    def _goal_multiplier(self, goal_diff: int) -> float:
        """Scale K-factor by goal difference."""
        abs_diff = abs(goal_diff)
        if abs_diff <= 1:
            return 1.0
        elif abs_diff == 2:
            return 1.5
        else:
            return (11 + abs_diff) / 8

    def get_rating(self, team: str) -> float:
        return self.ratings.get(team, self.initial_rating)

    def update(self, match: EloMatch) -> tuple[float, float]:
        """Update ratings after a match. Returns (new_home_elo, new_away_elo)."""
        home_elo = self.get_rating(match.home_team)
        away_elo = self.get_rating(match.away_team)

        # Home advantage added to expected score calculation
        expected_home = self._expected_score(
            home_elo + self.home_advantage, away_elo
        )
        expected_away = 1.0 - expected_home

        # Actual scores
        if match.home_goals > match.away_goals:
            actual_home, actual_away = 1.0, 0.0
        elif match.home_goals < match.away_goals:
            actual_home, actual_away = 0.0, 1.0
        else:
            actual_home, actual_away = 0.5, 0.5

        goal_diff = match.home_goals - match.away_goals
        mult = self._goal_multiplier(goal_diff)

        new_home = home_elo + self.k_factor * mult * (actual_home - expected_home)
        new_away = away_elo + self.k_factor * mult * (actual_away - expected_away)

        self.ratings[match.home_team] = new_home
        self.ratings[match.away_team] = new_away

        return new_home, new_away

    def process_season(self, matches: list[EloMatch]) -> None:
        """Process a list of matches chronologically."""
        for match in matches:
            self.update(match)

    def predict_1x2(self, home_team: str, away_team: str) -> dict:
        """Predict 1X2 probabilities from ELO ratings."""
        home_elo = self.get_rating(home_team)
        away_elo = self.get_rating(away_team)

        expected_home = self._expected_score(
            home_elo + self.home_advantage, away_elo
        )

        # Convert expected score to 1X2
        # Draw probability modeled as function of elo difference
        elo_diff = abs(home_elo - away_elo)
        draw_prob = max(0.10, min(0.35, 0.28 - elo_diff / 2500))

        remaining = 1.0 - draw_prob
        home_win = remaining * expected_home
        away_win = remaining * (1.0 - expected_home)

        return {
            "home": round(home_win, 4),
            "draw": round(draw_prob, 4),
            "away": round(away_win, 4),
        }

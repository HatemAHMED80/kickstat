"""ELO rating system for football teams.

Based on World Football Elo Ratings methodology with goal difference adjustment.
Supports dual home/away ratings with progressive seasonal decay.
"""

from dataclasses import dataclass


@dataclass
class EloMatch:
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int


class EloRating:
    """ELO rating system with home advantage, goal difference scaling,
    and dual home/away contextual ratings.

    Each team has 3 ratings:
    - global: updated on every match (original behavior)
    - home_elo: updated only when playing at home
    - away_elo: updated only when playing away

    Contextual ratings blend with global via match count:
    weight = min(1.0, context_matches / blend_threshold)
    effective = weight * contextual + (1 - weight) * global
    """

    def __init__(
        self,
        k_factor: float = 32,
        home_advantage: float = 100,
        initial_rating: float = 1500,
        blend_threshold: int = 10,
    ):
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.blend_threshold = blend_threshold

        # Global ratings (original)
        self.ratings: dict[str, float] = {}

        # Contextual ratings
        self.home_ratings: dict[str, float] = {}
        self.away_ratings: dict[str, float] = {}

        # Match counts per context (for blend weight)
        self.home_match_count: dict[str, int] = {}
        self.away_match_count: dict[str, int] = {}

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
        """Get global rating for a team."""
        return self.ratings.get(team, self.initial_rating)

    def get_contextual_rating(self, team: str, context: str) -> float:
        """Get blended contextual rating (home or away).

        Blends contextual rating with global based on how many matches
        the team has played in that context. More context matches =
        more weight on contextual rating.
        """
        global_r = self.get_rating(team)

        if context == "home":
            ctx_ratings = self.home_ratings
            ctx_counts = self.home_match_count
        elif context == "away":
            ctx_ratings = self.away_ratings
            ctx_counts = self.away_match_count
        else:
            return global_r

        if team not in ctx_ratings:
            return global_r

        ctx_r = ctx_ratings[team]
        n = ctx_counts.get(team, 0)
        weight = min(1.0, n / self.blend_threshold)
        return weight * ctx_r + (1.0 - weight) * global_r

    def update(self, match: EloMatch) -> tuple[float, float]:
        """Update ratings after a match. Returns (new_home_elo, new_away_elo).

        Updates both global and contextual ratings.
        """
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

        delta_home = self.k_factor * mult * (actual_home - expected_home)
        delta_away = self.k_factor * mult * (actual_away - expected_away)

        new_home = home_elo + delta_home
        new_away = away_elo + delta_away

        # Update global ratings
        self.ratings[match.home_team] = new_home
        self.ratings[match.away_team] = new_away

        # Update contextual ratings
        # Home team's home_elo
        prev_home_ctx = self.home_ratings.get(match.home_team, home_elo)
        self.home_ratings[match.home_team] = prev_home_ctx + delta_home
        self.home_match_count[match.home_team] = self.home_match_count.get(match.home_team, 0) + 1

        # Away team's away_elo
        prev_away_ctx = self.away_ratings.get(match.away_team, away_elo)
        self.away_ratings[match.away_team] = prev_away_ctx + delta_away
        self.away_match_count[match.away_team] = self.away_match_count.get(match.away_team, 0) + 1

        return new_home, new_away

    def seed_from_previous_season(self, matches: list[EloMatch], last_n: int = 10) -> None:
        """Seed contextual ratings from previous season's last N home/away matches.

        Call this before processing a new season. The contextual ratings
        will naturally decay as new season matches accumulate (blend_threshold
        controls how quickly new data takes over).
        """
        # Collect last N home matches and last N away matches per team
        home_matches: dict[str, list[EloMatch]] = {}
        away_matches: dict[str, list[EloMatch]] = {}

        for m in matches:
            home_matches.setdefault(m.home_team, []).append(m)
            away_matches.setdefault(m.away_team, []).append(m)

        # Process last N matches per context to build seed ratings
        temp_elo = EloRating(
            k_factor=self.k_factor,
            home_advantage=self.home_advantage,
            initial_rating=self.initial_rating,
        )

        # Process all matches to get proper ratings
        for m in matches:
            temp_elo.update(m)

        # Seed contextual ratings from temp elo
        # Use last_n matches count as the blend starting point
        regression_factor = 0.8  # Regress 20% toward mean for season transition

        for team in temp_elo.ratings:
            global_r = temp_elo.get_rating(team)

            if team in home_matches:
                recent_home = home_matches[team][-last_n:]
                if len(recent_home) >= 3:
                    # Regress toward global to account for transfers/changes
                    seed_r = regression_factor * global_r + (1 - regression_factor) * self.initial_rating
                    self.home_ratings[team] = seed_r
                    # Start with low count so new season data takes over quickly
                    self.home_match_count[team] = min(len(recent_home), 3)

            if team in away_matches:
                recent_away = away_matches[team][-last_n:]
                if len(recent_away) >= 3:
                    seed_r = regression_factor * global_r + (1 - regression_factor) * self.initial_rating
                    self.away_ratings[team] = seed_r
                    self.away_match_count[team] = min(len(recent_away), 3)

    def apply_seasonal_decay(self, regression: float = 0.8, max_carry: int = 3) -> None:
        """Apply seasonal decay to contextual ratings at season transitions.

        For walk-forward use: regresses contextual ratings toward global
        and caps match counts so new-season data takes over quickly.

        Args:
            regression: How much of the contextual rating to keep (0.8 = 80%
                contextual + 20% global). Accounts for transfers/changes.
            max_carry: Cap on match counts carried into new season.
                With blend_threshold=10, max_carry=3 means initial blend
                weight is 30%, growing as new matches accumulate.
        """
        for team in list(self.home_ratings):
            global_r = self.get_rating(team)
            self.home_ratings[team] = (
                regression * self.home_ratings[team]
                + (1 - regression) * global_r
            )
            self.home_match_count[team] = min(
                self.home_match_count.get(team, 0), max_carry
            )

        for team in list(self.away_ratings):
            global_r = self.get_rating(team)
            self.away_ratings[team] = (
                regression * self.away_ratings[team]
                + (1 - regression) * global_r
            )
            self.away_match_count[team] = min(
                self.away_match_count.get(team, 0), max_carry
            )

    def process_season(self, matches: list[EloMatch]) -> None:
        """Process a list of matches chronologically."""
        for match in matches:
            self.update(match)

    def predict_1x2(self, home_team: str, away_team: str) -> dict:
        """Predict 1X2 probabilities using contextual ELO ratings.

        Uses home team's home_elo vs away team's away_elo for more
        accurate context-specific predictions.
        """
        home_elo = self.get_contextual_rating(home_team, "home")
        away_elo = self.get_contextual_rating(away_team, "away")

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

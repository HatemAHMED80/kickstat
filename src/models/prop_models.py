"""Prop market prediction models: corners, over/under goals.

Uses Poisson distributions on rolling team statistics.
No ML complexity — just direct statistical modeling on team averages,
which is appropriate for less efficiently priced secondary markets.
"""

from collections import defaultdict

import numpy as np
from scipy.stats import poisson
from loguru import logger


class CornerModel:
    """Predict corner outcomes using team-level Poisson model.

    Tracks rolling corner stats per team and uses independent Poisson
    distributions for home/away corners. From the convolution, derives:
    - Corner 1X2 (home wins corners / draw / away wins corners)
    - Over/Under total corners at any line
    """

    LEAGUE_AVG_HOME_CORNERS = 5.5
    LEAGUE_AVG_AWAY_CORNERS = 4.3
    MAX_CORNERS = 20

    def __init__(self, window: int = 10):
        self.window = window
        # team -> list of (corners_for, corners_against, is_home)
        self._team_history: dict[str, list[tuple[int, int, bool]]] = defaultdict(list)

    def update(self, match: dict) -> None:
        """Add a completed match to the history."""
        home = match["home_team"]
        away = match["away_team"]
        hc = match.get("hc", 0)
        ac = match.get("ac", 0)

        if hc == 0 and ac == 0:
            return  # no corner data

        self._team_history[home].append((hc, ac, True))
        self._team_history[away].append((ac, hc, False))

    def _get_lambda(self, team: str, is_home: bool) -> float:
        """Get expected corners for a team based on rolling history."""
        history = self._team_history.get(team, [])
        if not history:
            return self.LEAGUE_AVG_HOME_CORNERS if is_home else self.LEAGUE_AVG_AWAY_CORNERS

        recent = history[-self.window:]
        # Filter by venue if enough data
        venue_matches = [h for h in recent if h[2] == is_home]
        if len(venue_matches) >= 3:
            avg = np.mean([h[0] for h in venue_matches])
        else:
            avg = np.mean([h[0] for h in recent])

        return max(float(avg), 1.0)

    def predict(self, home_team: str, away_team: str) -> dict:
        """Predict corner outcomes for a match.

        Returns dict with:
            lambda_home, lambda_away: expected corners per team
            home_more_prob, draw_prob, away_more_prob: corner 1X2
            total_expected: expected total corners
            over_X_prob: probability of over X total corners (various lines)
        """
        lh = self._get_lambda(home_team, is_home=True)
        la = self._get_lambda(away_team, is_home=False)

        n = self.MAX_CORNERS + 1

        # Build joint probability matrix (independent Poisson)
        ph = poisson.pmf(np.arange(n), lh)
        pa = poisson.pmf(np.arange(n), la)
        matrix = np.outer(ph, pa)
        matrix /= matrix.sum()  # normalize

        # Corner 1X2
        home_more = float(np.tril(matrix, k=-1).sum())
        draw = float(np.trace(matrix))
        away_more = float(np.triu(matrix, k=1).sum())

        # Total corners distribution
        total_probs = np.zeros(2 * n)
        for i in range(n):
            for j in range(n):
                total_probs[i + j] += matrix[i, j]

        # Over/Under at various lines
        over = {}
        for line in [7.5, 8.5, 9.5, 10.5, 11.5]:
            over[line] = float(sum(total_probs[int(line) + 1:]))

        return {
            "lambda_home": lh,
            "lambda_away": la,
            "home_more_prob": home_more,
            "draw_prob": draw,
            "away_more_prob": away_more,
            "total_expected": lh + la,
            "over_probs": over,
        }


class OverUnderGoalsModel:
    """Predict Over/Under 2.5 goals using team-level Poisson model.

    Uses rolling scoring/conceding averages per team, combined with
    Dixon-Coles lambdas when available for better estimates.
    """

    LEAGUE_AVG_GOALS = 1.35
    MAX_GOALS = 8

    def __init__(self, window: int = 10):
        self.window = window
        self._team_history: dict[str, list[tuple[int, int, bool]]] = defaultdict(list)

    def update(self, match: dict) -> None:
        """Add a completed match."""
        home = match["home_team"]
        away = match["away_team"]
        hg = match["home_score"]
        ag = match["away_score"]
        self._team_history[home].append((hg, ag, True))
        self._team_history[away].append((ag, hg, False))

    def _get_lambda(self, team: str, is_home: bool, scoring: bool = True) -> float:
        """Get expected goals scored or conceded."""
        history = self._team_history.get(team, [])
        if not history:
            return self.LEAGUE_AVG_GOALS

        recent = history[-self.window:]
        idx = 0 if scoring else 1
        avg = np.mean([h[idx] for h in recent])
        return max(float(avg), 0.2)

    def predict(
        self,
        home_team: str,
        away_team: str,
        dc_lambda_h: float | None = None,
        dc_lambda_a: float | None = None,
    ) -> dict:
        """Predict goal outcomes.

        If DC lambdas provided, blends them with rolling averages.
        """
        # Rolling stat lambdas
        home_scored = self._get_lambda(home_team, True, scoring=True)
        away_conceded = self._get_lambda(away_team, False, scoring=False)
        away_scored = self._get_lambda(away_team, False, scoring=True)
        home_conceded = self._get_lambda(home_team, True, scoring=False)

        roll_lh = (home_scored + away_conceded) / 2
        roll_la = (away_scored + home_conceded) / 2

        # Blend with DC lambdas if available (60% DC, 40% rolling)
        if dc_lambda_h is not None and dc_lambda_a is not None:
            lh = 0.6 * dc_lambda_h + 0.4 * roll_lh
            la = 0.6 * dc_lambda_a + 0.4 * roll_la
        else:
            lh = roll_lh
            la = roll_la

        n = self.MAX_GOALS + 1
        ph = poisson.pmf(np.arange(n), lh)
        pa = poisson.pmf(np.arange(n), la)
        matrix = np.outer(ph, pa)
        matrix /= matrix.sum()

        # Over/Under at various lines
        total_probs = np.zeros(2 * n)
        for i in range(n):
            for j in range(n):
                total_probs[i + j] += matrix[i, j]

        over_25 = float(sum(total_probs[3:]))
        over_15 = float(sum(total_probs[2:]))
        over_35 = float(sum(total_probs[4:]))

        return {
            "lambda_home": lh,
            "lambda_away": la,
            "total_expected": lh + la,
            "over_15": over_15,
            "over_25": over_25,
            "under_25": 1.0 - over_25,
            "over_35": over_35,
        }


def remove_margin_2way(odds_a: float, odds_b: float) -> tuple[float, float]:
    """Remove bookmaker margin from a 2-way market (O/U, AH).

    Returns (fair_prob_a, fair_prob_b).
    """
    if odds_a <= 1.0 or odds_b <= 1.0:
        return 0.0, 0.0
    raw_a = 1.0 / odds_a
    raw_b = 1.0 / odds_b
    total = raw_a + raw_b
    return raw_a / total, raw_b / total


def remove_margin_3way(odds_h: float, odds_d: float, odds_a: float) -> tuple[float, float, float]:
    """Remove bookmaker margin from a 3-way market (1X2, corner 1X2).

    Returns (fair_home, fair_draw, fair_away).
    """
    if odds_h <= 1.0 or odds_d <= 1.0 or odds_a <= 1.0:
        return 0.0, 0.0, 0.0
    raw_h = 1.0 / odds_h
    raw_d = 1.0 / odds_d
    raw_a = 1.0 / odds_a
    total = raw_h + raw_d + raw_a
    return raw_h / total, raw_d / total, raw_a / total

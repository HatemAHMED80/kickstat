"""Feature engineering for XGBoost stacking model.

Computes rolling form, shot stats, dominance, and head-to-head features
from historical match data. All features are strictly walk-forward safe.
"""

from collections import defaultdict
from datetime import datetime

import numpy as np
from loguru import logger


FEATURE_NAMES: list[str] = [
    # Base model probabilities (6)
    "dc_home_prob", "dc_draw_prob", "dc_away_prob",
    "elo_home_prob", "elo_draw_prob", "elo_away_prob",
    # DC team strength (4)
    "dc_home_attack", "dc_home_defense", "dc_away_attack", "dc_away_defense",
    # ELO ratings (3 global + 4 contextual)
    "elo_home_rating", "elo_away_rating", "elo_diff",
    "elo_home_at_home", "elo_away_at_away", "elo_contextual_diff", "elo_home_away_ratio",
    # Form - rolling 5 (8)
    "home_ppg_5", "away_ppg_5",
    "home_goals_scored_5", "away_goals_scored_5",
    "home_goals_conceded_5", "away_goals_conceded_5",
    "home_home_ppg_5", "away_away_ppg_5",
    # Shot stats - rolling 5 (8)
    "home_shots_pg_5", "away_shots_pg_5",
    "home_sot_pg_5", "away_sot_pg_5",
    "home_shot_accuracy_5", "away_shot_accuracy_5",
    "home_sot_ratio_5", "away_sot_ratio_5",
    # Dominance - rolling 5 (6)
    "home_corners_pg_5", "away_corners_pg_5",
    "home_fouls_pg_5", "away_fouls_pg_5",
    "home_dominance_5", "away_dominance_5",
    # Differentials (5)
    "ppg_diff", "goals_diff", "sot_diff", "corner_diff", "dominance_diff",
    # Head-to-head (4)
    "h2h_matches", "h2h_home_win_rate", "h2h_goals_pg", "h2h_over25_rate",
    # Rest days (2)
    "home_rest_days", "away_rest_days",
]


class MatchHistory:
    """Accumulator for historical match data with team-indexed lookups."""

    def __init__(self):
        self.matches: list[dict] = []
        self._team_index: dict[str, list[tuple[int, bool]]] = defaultdict(list)

    def add_match(self, match: dict) -> None:
        idx = len(self.matches)
        self.matches.append(match)
        self._team_index[match["home_team"]].append((idx, True))
        self._team_index[match["away_team"]].append((idx, False))

    def add_matches(self, matches: list[dict]) -> None:
        for m in matches:
            self.add_match(m)

    def get_team_matches(
        self,
        team: str,
        before_date,
        last_n: int = 5,
        home_only: bool = False,
        away_only: bool = False,
    ) -> list[tuple[dict, bool]]:
        """Get last N matches for a team before a date. Returns (match, is_home) tuples."""
        results = []
        for idx, is_home in reversed(self._team_index.get(team, [])):
            m = self.matches[idx]
            if m["kickoff"] >= before_date:
                continue
            if home_only and not is_home:
                continue
            if away_only and is_home:
                continue
            results.append((m, is_home))
            if len(results) >= last_n:
                break
        return results

    def get_h2h_matches(
        self,
        home_team: str,
        away_team: str,
        before_date,
        last_n: int = 10,
    ) -> list[dict]:
        """Get head-to-head matches (both directions) before date."""
        h2h = []
        for idx, _ in reversed(self._team_index.get(home_team, [])):
            m = self.matches[idx]
            if m["kickoff"] >= before_date:
                continue
            other = m["away_team"] if m["home_team"] == home_team else m["home_team"]
            if other == away_team:
                h2h.append(m)
                if len(h2h) >= last_n:
                    break
        return h2h


def compute_features(
    home_team: str,
    away_team: str,
    match_date,
    history: MatchHistory,
    dc_model=None,
    elo_model=None,
) -> dict[str, float]:
    """Compute all features for a match prediction.

    All features use only data strictly before match_date.
    """
    f: dict[str, float] = {}

    # === Base model probabilities ===
    if dc_model and dc_model.is_fitted:
        dc_pred = dc_model.predict(home_team, away_team)
        f["dc_home_prob"] = dc_pred.home_win
        f["dc_draw_prob"] = dc_pred.draw
        f["dc_away_prob"] = dc_pred.away_win
        home_r = dc_model.teams.get(home_team)
        away_r = dc_model.teams.get(away_team)
        f["dc_home_attack"] = home_r.attack if home_r else 1.0
        f["dc_home_defense"] = home_r.defense if home_r else 1.0
        f["dc_away_attack"] = away_r.attack if away_r else 1.0
        f["dc_away_defense"] = away_r.defense if away_r else 1.0
    else:
        for k in ["dc_home_prob", "dc_draw_prob", "dc_away_prob"]:
            f[k] = 1 / 3
        for k in ["dc_home_attack", "dc_home_defense", "dc_away_attack", "dc_away_defense"]:
            f[k] = 1.0

    if elo_model:
        elo_pred = elo_model.predict_1x2(home_team, away_team)
        f["elo_home_prob"] = elo_pred["home"]
        f["elo_draw_prob"] = elo_pred["draw"]
        f["elo_away_prob"] = elo_pred["away"]
        f["elo_home_rating"] = elo_model.get_rating(home_team)
        f["elo_away_rating"] = elo_model.get_rating(away_team)
        f["elo_diff"] = f["elo_home_rating"] - f["elo_away_rating"]
        # Contextual ELO duo features
        if hasattr(elo_model, "get_contextual_rating"):
            f["elo_home_at_home"] = elo_model.get_contextual_rating(home_team, "home")
            f["elo_away_at_away"] = elo_model.get_contextual_rating(away_team, "away")
            f["elo_contextual_diff"] = f["elo_home_at_home"] - f["elo_away_at_away"]
            # Ratio: how much does context deviate from global (>1 = better at home/away than average)
            global_avg = (f["elo_home_rating"] + f["elo_away_rating"]) / 2
            if global_avg > 0:
                f["elo_home_away_ratio"] = f["elo_home_at_home"] / f["elo_away_at_away"] if f["elo_away_at_away"] > 0 else 1.0
            else:
                f["elo_home_away_ratio"] = 1.0
        else:
            f["elo_home_at_home"] = f["elo_home_rating"]
            f["elo_away_at_away"] = f["elo_away_rating"]
            f["elo_contextual_diff"] = f["elo_diff"]
            f["elo_home_away_ratio"] = 1.0
    else:
        for k in ["elo_home_prob", "elo_draw_prob", "elo_away_prob"]:
            f[k] = 1 / 3
        f["elo_home_rating"] = f["elo_away_rating"] = 1500.0
        f["elo_diff"] = 0.0
        f["elo_home_at_home"] = f["elo_away_at_away"] = 1500.0
        f["elo_contextual_diff"] = 0.0
        f["elo_home_away_ratio"] = 1.0

    # === Form + shot stats (rolling 5) ===
    home_recent = history.get_team_matches(home_team, match_date, last_n=5)
    away_recent = history.get_team_matches(away_team, match_date, last_n=5)
    _compute_rolling_stats(f, "home", home_recent)
    _compute_rolling_stats(f, "away", away_recent)

    # Venue-specific form
    home_home = history.get_team_matches(home_team, match_date, last_n=5, home_only=True)
    away_away = history.get_team_matches(away_team, match_date, last_n=5, away_only=True)
    f["home_home_ppg_5"] = _ppg(home_home) if home_home else f.get("home_ppg_5", 1.0)
    f["away_away_ppg_5"] = _ppg(away_away) if away_away else f.get("away_ppg_5", 1.0)

    # === Differentials ===
    f["ppg_diff"] = f["home_ppg_5"] - f["away_ppg_5"]
    f["goals_diff"] = f["home_goals_scored_5"] - f["away_goals_scored_5"]
    f["sot_diff"] = f["home_sot_pg_5"] - f["away_sot_pg_5"]
    f["corner_diff"] = f["home_corners_pg_5"] - f["away_corners_pg_5"]
    f["dominance_diff"] = f["home_dominance_5"] - f["away_dominance_5"]

    # === Head-to-head ===
    h2h = history.get_h2h_matches(home_team, away_team, match_date, last_n=10)
    _compute_h2h(f, h2h, home_team)

    # === Rest days ===
    for team, prefix in [(home_team, "home"), (away_team, "away")]:
        last = history.get_team_matches(team, match_date, last_n=1)
        if last:
            delta = (match_date - last[0][0]["kickoff"]).days
            f[f"{prefix}_rest_days"] = min(float(delta), 30.0)
        else:
            f[f"{prefix}_rest_days"] = 7.0

    return {name: f.get(name, 0.0) for name in FEATURE_NAMES}


def features_to_array(features: dict[str, float]) -> np.ndarray:
    """Convert features dict to numpy array in FEATURE_NAMES order."""
    return np.array([features[name] for name in FEATURE_NAMES], dtype=np.float32)


def _ppg(matches: list[tuple[dict, bool]]) -> float:
    if not matches:
        return 0.0
    pts = 0
    for m, is_home in matches:
        gs = m["home_score"] if is_home else m["away_score"]
        gc = m["away_score"] if is_home else m["home_score"]
        pts += 3 if gs > gc else (1 if gs == gc else 0)
    return pts / len(matches)


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b > 0 else default


def _compute_rolling_stats(
    f: dict, prefix: str, matches: list[tuple[dict, bool]]
) -> None:
    """Compute rolling form + shot + dominance stats for a team."""
    n = len(matches)
    if n == 0:
        f[f"{prefix}_ppg_5"] = 1.0
        f[f"{prefix}_goals_scored_5"] = 1.2
        f[f"{prefix}_goals_conceded_5"] = 1.2
        f[f"{prefix}_shots_pg_5"] = 11.0
        f[f"{prefix}_sot_pg_5"] = 4.0
        f[f"{prefix}_shot_accuracy_5"] = 0.36
        f[f"{prefix}_sot_ratio_5"] = 0.5
        f[f"{prefix}_corners_pg_5"] = 5.0
        f[f"{prefix}_fouls_pg_5"] = 13.0
        f[f"{prefix}_dominance_5"] = 0.5
        return

    pts = gs = gc = shots = sot = opp_sot = corners = opp_corners = fouls = 0.0
    for m, is_home in matches:
        _gs = m["home_score"] if is_home else m["away_score"]
        _gc = m["away_score"] if is_home else m["home_score"]
        gs += _gs
        gc += _gc
        pts += 3 if _gs > _gc else (1 if _gs == _gc else 0)

        shots += m.get("hs" if is_home else "as", 0)
        sot += m.get("hst" if is_home else "ast", 0)
        opp_sot += m.get("ast" if is_home else "hst", 0)
        corners += m.get("hc" if is_home else "ac", 0)
        opp_corners += m.get("ac" if is_home else "hc", 0)
        fouls += m.get("hf" if is_home else "af", 0)

    f[f"{prefix}_ppg_5"] = pts / n
    f[f"{prefix}_goals_scored_5"] = gs / n
    f[f"{prefix}_goals_conceded_5"] = gc / n
    f[f"{prefix}_shots_pg_5"] = shots / n
    f[f"{prefix}_sot_pg_5"] = sot / n
    f[f"{prefix}_shot_accuracy_5"] = _safe_div(sot, shots, 0.36)
    f[f"{prefix}_sot_ratio_5"] = _safe_div(sot, sot + opp_sot, 0.5)
    f[f"{prefix}_corners_pg_5"] = corners / n
    f[f"{prefix}_fouls_pg_5"] = fouls / n
    f[f"{prefix}_dominance_5"] = _safe_div(
        sot + corners, sot + opp_sot + corners + opp_corners, 0.5
    )


def _compute_h2h(f: dict, h2h_matches: list[dict], home_team: str) -> None:
    """Compute head-to-head features."""
    n = len(h2h_matches)
    if n == 0:
        f["h2h_matches"] = 0.0
        f["h2h_home_win_rate"] = 0.33
        f["h2h_goals_pg"] = 2.5
        f["h2h_over25_rate"] = 0.5
        return

    home_wins = 0
    total_goals = 0
    over25 = 0
    for m in h2h_matches:
        hg = m["home_score"] if m["home_team"] == home_team else m["away_score"]
        ag = m["away_score"] if m["home_team"] == home_team else m["home_score"]
        if hg > ag:
            home_wins += 1
        total_goals += m["home_score"] + m["away_score"]
        if m["home_score"] + m["away_score"] > 2:
            over25 += 1

    f["h2h_matches"] = float(n)
    f["h2h_home_win_rate"] = home_wins / n
    f["h2h_goals_pg"] = total_goals / n
    f["h2h_over25_rate"] = over25 / n

#!/usr/bin/env python3
"""Grid-search optimizer for a single league × market.

Runs the walk-forward backtest ONCE to collect raw probability data for all
4 strategies, then sweeps (strategy × edge_threshold × min_prob) in
post-processing to find the optimal combination.

Usage:
    python scripts/optimize_market.py --league bundesliga --market home
    python scripts/optimize_market.py --league bundesliga --market draw
    python scripts/optimize_market.py --league la_liga --market home --top 20
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.football_data_uk import load_historical_data, build_multi_market_odds
from src.data.odds_api import remove_margin
from src.models.prop_models import remove_margin_2way
from src.models.dixon_coles import DixonColesModel, MatchResult
from src.models.elo import EloRating, EloMatch
from src.models.ensemble import EnsemblePredictor
from src.models.features import MatchHistory, compute_features, features_to_array
from src.models.xgb_model import XGBStackingModel
from src.models.xgb_props import XGBPropModel
from src.models.calibrator import ProbabilityCalibrator


# ---------------------------------------------------------------------------
# Data collection: walk-forward loop (runs ONCE)
# ---------------------------------------------------------------------------

def collect_raw_data(
    matches: list[dict],
    odds_data: dict,
    target_market: str,
    min_training: int = 120,
    dc_weight: float = 0.65,
    elo_weight: float = 0.35,
    refit_interval: int = 30,
    xgb_retrain_interval: int = 60,
    calibrator_retrain_interval: int = 100,
    kelly_fraction: float = 0.15,
) -> list[dict]:
    """Run walk-forward and collect raw probabilities for target_market.

    Returns a list of dicts, one per match with odds, containing:
      - prob_baseline, prob_xgb, prob_xgb_draw, prob_xgb_cal
      - fair_prob, best_odds, outcome (bool: True if target won)
    For O/U markets: prob_dc_ou, prob_xgb_ou instead of 4 strategies.
    """
    matches = sorted(matches, key=lambda m: m["kickoff"])
    n = len(matches)

    # Models
    elo = EloRating()
    history = MatchHistory()
    dc = None
    xgb_model = XGBStackingModel()
    calibrator = ProbabilityCalibrator(method="isotonic")
    xgb_over25 = XGBPropModel(market_name="over25")

    # Training data for XGB and calibrator
    X_train, y_train = [], []
    cal_probs, cal_outcomes = [], []
    xgb_ou_X, xgb_ou_y = [], []

    raw_data = []
    current_season = None

    for i in range(n):
        test = matches[i]
        date_str = str(test["kickoff"])[:10]

        # Detect season transitions for ELO decay
        test_season = test.get("season")
        if test_season and current_season and test_season != current_season:
            elo.apply_seasonal_decay()
        current_season = test_season

        # --- Training phase (all matches before current) ---
        if i < min_training:
            # Feed ELO + history
            elo.update(EloMatch(
                home_team=test["home_team"], away_team=test["away_team"],
                home_goals=int(test["home_score"]), away_goals=int(test["away_score"]),
            ))
            history.add_match(test)

            # Fit DC periodically (needs >= 50 matches)
            if i >= 50 and i % refit_interval == 0:
                train_matches = [MatchResult(
                    date=m["kickoff"], home_team=m["home_team"], away_team=m["away_team"],
                    home_goals=int(m["home_score"]), away_goals=int(m["away_score"]),
                ) for m in matches[:i]]
                dc = DixonColesModel()
                dc.fit(train_matches)

            # Accumulate XGB training data
            if dc is not None and i >= 80:
                try:
                    features = compute_features(
                        test["home_team"], test["away_team"],
                        test["kickoff"], history, dc, elo,
                    )
                    hs, aws = int(test["home_score"]), int(test["away_score"])
                    outcome = 0 if hs > aws else (1 if hs == aws else 2)
                    X_train.append(features_to_array(features))
                    y_train.append(outcome)

                    # O/U data
                    total_goals = hs + aws
                    xgb_ou_X.append(features_to_array(features))
                    xgb_ou_y.append(1 if total_goals > 2 else 0)

                    # Calibration data
                    dc_pred = dc.predict(test["home_team"], test["away_team"])
                    cal_probs.append([dc_pred.home_win, dc_pred.draw, dc_pred.away_win])
                    cal_outcomes.append(outcome)
                except Exception:
                    pass

            continue

        # --- Periodic refitting ---
        train_idx = i
        if i == min_training or (i - min_training) % refit_interval == 0:
            train_matches = [MatchResult(
                date=m["kickoff"], home_team=m["home_team"], away_team=m["away_team"],
                home_goals=int(m["home_score"]), away_goals=int(m["away_score"]),
            ) for m in matches[:train_idx]]
            dc = DixonColesModel()
            dc.fit(train_matches)

        if (i == min_training or (i - min_training) % xgb_retrain_interval == 0) and len(X_train) >= 100:
            X = np.vstack(X_train)
            y = np.array(y_train)
            split = max(int(len(X) * 0.8), len(X) - 200)
            xgb_model = XGBStackingModel()
            xgb_model.fit(X[:split], y[:split], X[split:], y[split:])

            # O/U XGB
            if len(xgb_ou_X) >= 100:
                X_ou = np.vstack(xgb_ou_X)
                y_ou = np.array(xgb_ou_y)
                xgb_over25 = XGBPropModel(market_name="over25")
                xgb_over25.fit(X_ou[:split], y_ou[:split], X_ou[split:], y_ou[split:])

        if (i == min_training or (i - min_training) % calibrator_retrain_interval == 0) and len(cal_probs) >= 80:
            calibrator = ProbabilityCalibrator(method="isotonic")
            calibrator.fit(np.array(cal_probs), np.array(cal_outcomes))

        # --- Compute features for this match ---
        match_features = None
        if dc is not None:
            try:
                match_features = compute_features(
                    test["home_team"], test["away_team"],
                    test["kickoff"], history, dc, elo,
                )
            except Exception:
                pass

        # --- Compute all probability sources ---
        if dc is None:
            # Feed ELO + history and skip
            elo.update(EloMatch(
                home_team=test["home_team"], away_team=test["away_team"],
                home_goals=int(test["home_score"]), away_goals=int(test["away_score"]),
            ))
            history.add_match(test)
            continue

        # Baseline: DC + ELO
        ens_base = EnsemblePredictor(
            dc_model=dc, elo_model=elo,
            dc_weight=dc_weight, elo_weight=elo_weight,
        )
        pred_base = ens_base.predict(test["home_team"], test["away_team"])
        probs_base = np.array([pred_base.home_prob, pred_base.draw_prob, pred_base.away_prob])

        # XGB variants
        if xgb_model.is_fitted and match_features is not None:
            ens_xgb = EnsemblePredictor(
                dc_model=dc, elo_model=elo,
                dc_weight=dc_weight, elo_weight=elo_weight,
                xgb_model=xgb_model,
            )
            pred_xgb = ens_xgb.predict(test["home_team"], test["away_team"], match_features=match_features)
            probs_xgb = np.array([pred_xgb.home_prob, pred_xgb.draw_prob, pred_xgb.away_prob])

            ens_draw = EnsemblePredictor(
                dc_model=dc, elo_model=elo,
                dc_weight=dc_weight, elo_weight=elo_weight,
                xgb_model=xgb_model, xgb_markets={"draw"},
            )
            pred_draw = ens_draw.predict(test["home_team"], test["away_team"], match_features=match_features)
            probs_xgb_draw = np.array([pred_draw.home_prob, pred_draw.draw_prob, pred_draw.away_prob])

            # Calibrated XGB
            if calibrator.is_fitted:
                raw = np.array([pred_xgb.home_prob, pred_xgb.draw_prob, pred_xgb.away_prob])
                cal_p = calibrator.calibrate(raw)
                probs_cal = cal_p / cal_p.sum() if cal_p.sum() > 0 else raw
            else:
                probs_cal = probs_xgb.copy()
        else:
            probs_xgb = probs_base.copy()
            probs_xgb_draw = probs_base.copy()
            probs_cal = probs_base.copy()

        # DC prediction for O/U
        dc_pred = dc.predict(test["home_team"], test["away_team"])
        dc_over25_p = dc_pred.over_25 if dc_pred is not None else None
        xgb_over25_p = None
        if xgb_over25.is_fitted and match_features is not None:
            xgb_over25_p = xgb_over25.predict_proba(match_features)

        # AH probabilities
        ah_home_p = None
        ah_away_p = None
        ah_line = None
        if dc_pred is not None and dc_pred.score_matrix is not None:
            match_key = f"{test['home_team']}_vs_{test['away_team']}_{date_str}"
            odds = odds_data.get(match_key, {})
            is_multi = any(isinstance(odds.get(k), dict) for k in ("1x2", "ou25", "ah"))
            odds_ah = odds.get("ah") if is_multi else None
            if odds_ah:
                ah_line = odds_ah.get("line", 0)
                matrix = dc_pred.score_matrix
                n_goals = matrix.shape[0]
                ah_home_p = 0.0
                for gi in range(n_goals):
                    for gj in range(n_goals):
                        if gi + ah_line > gj:
                            ah_home_p += float(matrix[gi, gj])
                ah_away_p = 1.0 - ah_home_p

        # --- Get odds ---
        match_key = f"{test['home_team']}_vs_{test['away_team']}_{date_str}"
        if match_key not in odds_data:
            # Still feed models
            elo.update(EloMatch(
                home_team=test["home_team"], away_team=test["away_team"],
                home_goals=int(test["home_score"]), away_goals=int(test["away_score"]),
            ))
            history.add_match(test)
            # Accumulate training data
            if match_features is not None:
                hs, aws = int(test["home_score"]), int(test["away_score"])
                outcome = 0 if hs > aws else (1 if hs == aws else 2)
                X_train.append(features_to_array(match_features))
                y_train.append(outcome)
                total_goals = hs + aws
                xgb_ou_X.append(features_to_array(match_features))
                xgb_ou_y.append(1 if total_goals > 2 else 0)
                cal_probs.append([probs_base[0], probs_base[1], probs_base[2]])
                cal_outcomes.append(outcome)
            continue

        odds = odds_data[match_key]
        is_multi = any(isinstance(odds.get(k), dict) for k in ("1x2", "ou25", "ah"))

        # Actual result
        hs = int(test["home_score"])
        aws = int(test["away_score"])
        outcome = 0 if hs > aws else (1 if hs == aws else 2)
        total_goals = hs + aws

        # --- Extract market-specific data ---
        if target_market in ("home", "draw", "away"):
            market_idx = {"home": 0, "draw": 1, "away": 2}[target_market]
            won = outcome == market_idx

            # 1X2 odds
            odds_1x2 = odds.get("1x2", {}) if is_multi else None
            has_1x2 = odds_1x2 and odds_1x2.get("pin_home", 0) > 1.0

            if has_1x2:
                fair = remove_margin(
                    odds_1x2.get("pin_home", 0), odds_1x2.get("pin_draw", 0), odds_1x2.get("pin_away", 0)
                )
                best_odds_map = {
                    "home": odds_1x2.get("best_home", odds_1x2.get("pin_home", 0)),
                    "draw": odds_1x2.get("best_draw", odds_1x2.get("pin_draw", 0)),
                    "away": odds_1x2.get("best_away", odds_1x2.get("pin_away", 0)),
                }
            elif not is_multi:
                fair = remove_margin(
                    odds.get("home_odds", 0), odds.get("draw_odds", 0), odds.get("away_odds", 0)
                )
                best_odds_map = {
                    "home": odds.get("best_home", odds.get("home_odds", 0)),
                    "draw": odds.get("best_draw", odds.get("draw_odds", 0)),
                    "away": odds.get("best_away", odds.get("away_odds", 0)),
                }
            else:
                fair = {"home": 0, "draw": 0, "away": 0}
                best_odds_map = {"home": 0, "draw": 0, "away": 0}

            fair_p = fair[target_market]
            best_o = best_odds_map[target_market]

            if fair_p <= 0 or best_o <= 1.0:
                elo.update(EloMatch(
                    home_team=test["home_team"], away_team=test["away_team"],
                    home_goals=hs, away_goals=aws,
                ))
                history.add_match(test)
                if match_features is not None:
                    X_train.append(features_to_array(match_features))
                    y_train.append(outcome)
                    xgb_ou_X.append(features_to_array(match_features))
                    xgb_ou_y.append(1 if total_goals > 2 else 0)
                    cal_probs.append([probs_base[0], probs_base[1], probs_base[2]])
                    cal_outcomes.append(outcome)
                continue

            raw_data.append({
                "date": date_str,
                "home": test["home_team"],
                "away": test["away_team"],
                "prob_baseline": float(probs_base[market_idx]),
                "prob_xgb": float(probs_xgb[market_idx]),
                "prob_xgb_draw": float(probs_xgb_draw[market_idx]),
                "prob_xgb_cal": float(probs_cal[market_idx]),
                "fair_prob": float(fair_p),
                "best_odds": float(best_o),
                "won": won,
            })

        elif target_market in ("over25", "under25"):
            odds_ou = odds.get("ou25") if is_multi else None
            if not odds_ou:
                elo.update(EloMatch(
                    home_team=test["home_team"], away_team=test["away_team"],
                    home_goals=hs, away_goals=aws,
                ))
                history.add_match(test)
                if match_features is not None:
                    X_train.append(features_to_array(match_features))
                    y_train.append(outcome)
                    xgb_ou_X.append(features_to_array(match_features))
                    xgb_ou_y.append(1 if total_goals > 2 else 0)
                    cal_probs.append([probs_base[0], probs_base[1], probs_base[2]])
                    cal_outcomes.append(outcome)
                continue

            pin_over = odds_ou.get("pin_over", 0)
            pin_under = odds_ou.get("pin_under", 0)
            if pin_over <= 1.0 or pin_under <= 1.0:
                elo.update(EloMatch(
                    home_team=test["home_team"], away_team=test["away_team"],
                    home_goals=hs, away_goals=aws,
                ))
                history.add_match(test)
                if match_features is not None:
                    X_train.append(features_to_array(match_features))
                    y_train.append(outcome)
                    xgb_ou_X.append(features_to_array(match_features))
                    xgb_ou_y.append(1 if total_goals > 2 else 0)
                    cal_probs.append([probs_base[0], probs_base[1], probs_base[2]])
                    cal_outcomes.append(outcome)
                continue

            fair_over_p, fair_under_p = remove_margin_2way(pin_over, pin_under)
            best_over = odds_ou.get("best_over", pin_over)
            best_under = odds_ou.get("best_under", pin_under)

            is_over = target_market == "over25"
            won = total_goals > 2 if is_over else total_goals < 3
            fair_p = fair_over_p if is_over else fair_under_p
            best_o = best_over if is_over else best_under

            dc_p = dc_over25_p if dc_over25_p is not None else 0.5
            xgb_p = xgb_over25_p if xgb_over25_p is not None else dc_p

            if not is_over:
                dc_p = 1.0 - dc_p
                xgb_p = 1.0 - xgb_p

            raw_data.append({
                "date": date_str,
                "home": test["home_team"],
                "away": test["away_team"],
                "prob_baseline": float(dc_p),
                "prob_xgb": float(xgb_p),
                "prob_xgb_draw": float(dc_p),  # same as baseline for O/U
                "prob_xgb_cal": float(xgb_p),  # same as xgb for O/U
                "fair_prob": float(fair_p),
                "best_odds": float(best_o),
                "won": won,
            })

        elif target_market in ("ah_home", "ah_away"):
            odds_ah_data = odds.get("ah") if is_multi else None
            if not odds_ah_data or ah_home_p is None:
                elo.update(EloMatch(
                    home_team=test["home_team"], away_team=test["away_team"],
                    home_goals=hs, away_goals=aws,
                ))
                history.add_match(test)
                if match_features is not None:
                    X_train.append(features_to_array(match_features))
                    y_train.append(outcome)
                    xgb_ou_X.append(features_to_array(match_features))
                    xgb_ou_y.append(1 if total_goals > 2 else 0)
                    cal_probs.append([probs_base[0], probs_base[1], probs_base[2]])
                    cal_outcomes.append(outcome)
                continue

            pin_ah_home = odds_ah_data.get("pin_home", 0)
            pin_ah_away = odds_ah_data.get("pin_away", 0)
            if pin_ah_home <= 1.0 or pin_ah_away <= 1.0:
                elo.update(EloMatch(
                    home_team=test["home_team"], away_team=test["away_team"],
                    home_goals=hs, away_goals=aws,
                ))
                history.add_match(test)
                if match_features is not None:
                    X_train.append(features_to_array(match_features))
                    y_train.append(outcome)
                    xgb_ou_X.append(features_to_array(match_features))
                    xgb_ou_y.append(1 if total_goals > 2 else 0)
                    cal_probs.append([probs_base[0], probs_base[1], probs_base[2]])
                    cal_outcomes.append(outcome)
                continue

            fair_ah_home_p, fair_ah_away_p = remove_margin_2way(pin_ah_home, pin_ah_away)
            best_ah_home = odds_ah_data.get("best_home", pin_ah_home)
            best_ah_away = odds_ah_data.get("best_away", pin_ah_away)

            is_home_ah = target_market == "ah_home"
            model_p = ah_home_p if is_home_ah else ah_away_p
            fair_p = fair_ah_home_p if is_home_ah else fair_ah_away_p
            best_o = best_ah_home if is_home_ah else best_ah_away

            # AH actual result
            ah_line_val = odds_ah_data.get("line", 0)
            adj_home = hs + ah_line_val
            if is_home_ah:
                won = adj_home > aws
            else:
                won = aws > adj_home

            # AH: only DC Poisson (no XGB variant), all strategies use same prob
            raw_data.append({
                "date": date_str,
                "home": test["home_team"],
                "away": test["away_team"],
                "prob_baseline": float(model_p),
                "prob_xgb": float(model_p),
                "prob_xgb_draw": float(model_p),
                "prob_xgb_cal": float(model_p),
                "fair_prob": float(fair_p),
                "best_odds": float(best_o),
                "won": won,
            })

        # --- Post-match: update models ---
        elo.update(EloMatch(
            home_team=test["home_team"], away_team=test["away_team"],
            home_goals=hs, away_goals=aws,
        ))
        history.add_match(test)

        if match_features is not None:
            X_train.append(features_to_array(match_features))
            y_train.append(outcome)
            xgb_ou_X.append(features_to_array(match_features))
            xgb_ou_y.append(1 if total_goals > 2 else 0)
            cal_probs.append([probs_base[0], probs_base[1], probs_base[2]])
            cal_outcomes.append(outcome)

    return raw_data


# ---------------------------------------------------------------------------
# Grid search (post-processing, instantaneous)
# ---------------------------------------------------------------------------

def grid_search(
    raw_data: list[dict],
    kelly_fraction: float = 0.15,
    min_kelly: float = 1.0,
) -> list[dict]:
    """Sweep all (strategy, edge_threshold, min_prob) combinations."""

    strategies = ["baseline", "xgb", "xgb_draw", "xgb_cal"]
    edge_range = np.arange(3.0, 21.0, 1.0)      # 3% to 20%
    prob_range = np.arange(0.25, 0.75, 0.05)     # 0.25 to 0.70

    results = []

    for strategy in strategies:
        prob_key = f"prob_{strategy}"

        # Pre-extract arrays for speed
        model_probs = np.array([d[prob_key] for d in raw_data])
        fair_probs = np.array([d["fair_prob"] for d in raw_data])
        best_odds = np.array([d["best_odds"] for d in raw_data])
        won = np.array([d["won"] for d in raw_data])

        # Edge = (model - fair) / fair * 100
        edges = np.where(fair_probs > 0, (model_probs - fair_probs) / fair_probs * 100, 0)

        # Kelly stakes
        b = best_odds - 1.0
        q = 1.0 - model_probs
        kelly_raw = np.where(b > 0, (b * model_probs - q) / b, 0)
        kelly_pct = np.maximum(0, kelly_raw * kelly_fraction * 100)

        # PnL per bet (if placed)
        pnl_per_bet = np.where(won, best_odds - 1.0, -1.0)

        for edge_threshold in edge_range:
            for min_prob in prob_range:
                # Filter: edge >= threshold AND prob >= min_prob AND kelly >= min_kelly
                mask = (edges >= edge_threshold) & (model_probs >= min_prob) & (kelly_pct >= min_kelly)
                n_bets = mask.sum()

                if n_bets < 5:
                    continue

                total_pnl = pnl_per_bet[mask].sum()
                wins = won[mask].sum()
                win_rate = wins / n_bets
                roi = total_pnl / n_bets
                avg_edge = edges[mask].mean()
                avg_odds = best_odds[mask].mean()

                results.append({
                    "strategy": strategy,
                    "edge_threshold": round(float(edge_threshold), 1),
                    "min_prob": round(float(min_prob), 2),
                    "n_bets": int(n_bets),
                    "wins": int(wins),
                    "win_rate": round(float(win_rate), 4),
                    "total_pnl": round(float(total_pnl), 2),
                    "roi": round(float(roi), 4),
                    "avg_edge": round(float(avg_edge), 1),
                    "avg_odds": round(float(avg_odds), 2),
                })

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Optimize a single league × market")
    parser.add_argument("--league", type=str, required=True,
                        help="League slug (e.g. bundesliga, premier_league)")
    parser.add_argument("--market", type=str, required=True,
                        help="Market to optimize (home, draw, away, over25, under25, ah_home, ah_away)")
    parser.add_argument("--seasons", nargs="+", type=int, default=[2021, 2022, 2023, 2024, 2025])
    parser.add_argument("--top", type=int, default=30, help="Show top N results")
    parser.add_argument("--min-bets", type=int, default=20, help="Minimum bets to consider")
    args = parser.parse_args()

    print(f"\n{'='*80}")
    print(f"  OPTIMIZER: {args.league.upper()} × {args.market.upper()}")
    print(f"{'='*80}")

    # 1. Load data
    print(f"\n[1/3] Loading {args.league} data...")
    cache_dir = PROJECT_ROOT / "data" / "historical"
    matches = load_historical_data(args.league, args.seasons, cache_dir)
    odds_data = build_multi_market_odds(matches)
    print(f"  {len(matches)} matches, {len(odds_data)} with odds")

    # 2. Collect raw probabilities (walk-forward, runs once)
    print(f"\n[2/3] Running walk-forward to collect {args.market} probabilities...")
    t0 = time.time()
    raw_data = collect_raw_data(matches, odds_data, target_market=args.market)
    t1 = time.time()
    print(f"  {len(raw_data)} matches with valid {args.market} data ({t1-t0:.1f}s)")

    if len(raw_data) < 20:
        print(f"\n[ERROR] Not enough data ({len(raw_data)} matches). Aborting.")
        return

    # 3. Grid search
    print(f"\n[3/3] Grid search: 4 strategies × 18 edges × 10 min_probs = 720 combos...")
    t0 = time.time()
    results = grid_search(raw_data)
    t1 = time.time()
    print(f"  {len(results)} valid combinations ({t1-t0:.2f}s)")

    # Filter by min bets
    results = [r for r in results if r["n_bets"] >= args.min_bets]

    # Sort by PnL (primary), ROI (secondary)
    results.sort(key=lambda r: (r["total_pnl"], r["roi"]), reverse=True)

    # Display
    print(f"\n{'='*80}")
    print(f"  TOP {args.top} COMBINATIONS — {args.league.upper()} × {args.market.upper()}")
    print(f"  (min {args.min_bets} bets)")
    print(f"{'='*80}")
    print(f"  {'#':>3} {'Strategy':<12} {'Edge%':>6} {'MinP':>6} {'Bets':>5} {'WR':>6} {'PnL':>8} {'ROI':>7} {'AvgEdge':>8} {'AvgOdds':>8}")
    print(f"  {'-'*78}")

    for rank, r in enumerate(results[:args.top], 1):
        pnl_str = f"{r['total_pnl']:+.1f}u"
        roi_str = f"{r['roi']:+.1%}"
        print(f"  {rank:>3} {r['strategy']:<12} {r['edge_threshold']:>5.0f}% {r['min_prob']:>5.2f} "
              f"{r['n_bets']:>5} {r['win_rate']:>5.1%} {pnl_str:>8} {roi_str:>7} "
              f"{r['avg_edge']:>7.1f}% {r['avg_odds']:>7.2f}")

    # Current config comparison
    print(f"\n{'='*80}")
    print(f"  CURRENT CONFIG COMPARISON")
    print(f"{'='*80}")

    current_configs = {
        "home": ("xgb", 15.0, 0.50),      # bundesliga current
        "draw": ("xgb_cal", 5.0, 0.28),
        "away": ("xgb", 15.0, 0.40),
        "over25": ("baseline", 7.0, 0.58),
        "under25": ("baseline", 10.0, 0.50),
        "ah_home": ("baseline", 8.0, 0.38),
        "ah_away": ("baseline", 15.0, 0.62),
    }

    if args.market in current_configs:
        cur_strat, cur_edge, cur_prob = current_configs[args.market]
        # Find current in results
        cur_result = None
        for r in results:
            if (r["strategy"] == cur_strat and
                abs(r["edge_threshold"] - cur_edge) < 0.5 and
                abs(r["min_prob"] - cur_prob) < 0.025):
                cur_result = r
                break

        if cur_result:
            print(f"  Current: {cur_strat} edge={cur_edge}% min_p={cur_prob} -> "
                  f"{cur_result['n_bets']} bets, {cur_result['total_pnl']:+.1f}u, {cur_result['roi']:+.1%}")
        else:
            print(f"  Current config ({cur_strat} edge={cur_edge}% min_p={cur_prob}) not in grid "
                  f"or < {args.min_bets} bets")

        if results:
            best = results[0]
            print(f"  Best:    {best['strategy']} edge={best['edge_threshold']}% min_p={best['min_prob']} -> "
                  f"{best['n_bets']} bets, {best['total_pnl']:+.1f}u, {best['roi']:+.1%}")

            if cur_result:
                delta = best["total_pnl"] - cur_result["total_pnl"]
                print(f"  Delta:   {delta:+.1f}u")

    # Show worst combos too (what to avoid)
    print(f"\n{'='*80}")
    print(f"  WORST 10 COMBINATIONS (what to avoid)")
    print(f"{'='*80}")
    worst = sorted(results, key=lambda r: r["total_pnl"])[:10]
    print(f"  {'#':>3} {'Strategy':<12} {'Edge%':>6} {'MinP':>6} {'Bets':>5} {'WR':>6} {'PnL':>8} {'ROI':>7}")
    print(f"  {'-'*60}")
    for rank, r in enumerate(worst, 1):
        pnl_str = f"{r['total_pnl']:+.1f}u"
        roi_str = f"{r['roi']:+.1%}"
        print(f"  {rank:>3} {r['strategy']:<12} {r['edge_threshold']:>5.0f}% {r['min_prob']:>5.2f} "
              f"{r['n_bets']:>5} {r['win_rate']:>5.1%} {pnl_str:>8} {roi_str:>7}")

    print()


if __name__ == "__main__":
    main()

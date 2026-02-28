#!/usr/bin/env python3
"""Full pipeline backtest: DC + ELO + XGBoost + Calibration + Bandit.

Compares 4 configurations side-by-side:
  1. BASELINE: Dixon-Coles + ELO (weighted average 65/35)
  2. +XGB:     Baseline + XGBoost stacking (62 features)
  3. +CAL:     +XGB + Isotonic Regression calibration
  4. +BANDIT:  +CAL + Contextual Bandit market selection

Walk-forward backtest with real Pinnacle + Max odds.

Usage:
    python scripts/backtest_full_pipeline.py
    python scripts/backtest_full_pipeline.py --leagues premier_league ligue_1
    python scripts/backtest_full_pipeline.py --leagues premier_league la_liga bundesliga serie_a ligue_1
    python scripts/backtest_full_pipeline.py --min-edge 3
    python scripts/backtest_full_pipeline.py --seasons 2022 2023 2024 2025
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.football_data_uk import load_historical_data, build_odds_lookup
from src.data.odds_api import remove_margin
from src.models.dixon_coles import DixonColesModel, MatchResult
from src.models.elo import EloRating, EloMatch
from src.models.ensemble import EnsemblePredictor
from src.models.features import MatchHistory, compute_features, features_to_array
from src.models.xgb_model import XGBStackingModel
from src.models.calibrator import ProbabilityCalibrator
from src.models.bandit import ContextualBandit
from src.evaluation.calibration import evaluate


def run_full_backtest(
    matches: list[dict],
    odds_data: dict,
    min_training: int = 120,
    min_edge: float = 5.0,
    away_edge: float = 15.0,
    disable_away: bool = False,
    min_kelly: float = 1.0,
    dc_weight: float = 0.65,
    elo_weight: float = 0.35,
    refit_interval: int = 30,
    xgb_retrain_interval: int = 60,
    calibrator_retrain_interval: int = 100,
    use_temp_scaling: bool = False,
    temp_scaling_t: float = 1.2,
) -> dict:
    """Run walk-forward backtest testing all pipeline configurations.

    Returns dict with results for each configuration.
    """
    matches = sorted(matches, key=lambda m: m["kickoff"])
    n = len(matches)
    logger.info(f"Starting FULL pipeline backtest on {n} matches, "
                f"{len(odds_data)} with odds")

    # Per-config accumulators
    configs = ["baseline", "xgb", "xgb_cal", "xgb_cal_bandit"]
    all_probs = {c: [] for c in configs}
    all_outcomes = {c: [] for c in configs}
    bets = {c: [] for c in configs}
    edges_found = {c: 0 for c in configs}

    odds_matched = 0

    # Models
    elo = EloRating()
    history = MatchHistory()
    dc = None
    xgb_model = XGBStackingModel()
    calibrator = ProbabilityCalibrator(method="isotonic")
    bandit = ContextualBandit()

    # XGBoost training data
    xgb_X: list[np.ndarray] = []
    xgb_y: list[int] = []

    # Calibrator training data (XGBoost predictions on validation)
    cal_probs_buffer: list[np.ndarray] = []
    cal_outcomes_buffer: list[int] = []

    # Bandit training data (matches with outcomes + odds)
    bandit_training: list[dict] = []

    # Initialize with first min_training matches
    for m in matches[:min_training]:
        elo.update(EloMatch(
            home_team=m["home_team"], away_team=m["away_team"],
            home_goals=m["home_score"], away_goals=m["away_score"],
        ))
        history.add_match(m)
        bandit_training.append(m)

    start_time = time.time()

    for i in range(min_training, n):
        test = matches[i]

        # === Phase 1: Update with PREVIOUS match ===
        if i > min_training:
            prev = matches[i - 1]

            # Compute features BEFORE adding to history (walk-forward safe)
            if dc is not None:
                try:
                    prev_features = compute_features(
                        prev["home_team"], prev["away_team"],
                        prev["kickoff"], history,
                        dc_model=dc, elo_model=elo,
                    )
                    prev_hs, prev_as = prev["home_score"], prev["away_score"]
                    prev_outcome = 0 if prev_hs > prev_as else (1 if prev_hs == prev_as else 2)
                    xgb_X.append(features_to_array(prev_features))
                    xgb_y.append(prev_outcome)

                    # If XGBoost is fitted, store its prediction for calibrator training
                    if xgb_model.is_fitted:
                        xgb_pred = xgb_model.model.predict_proba(
                            features_to_array(prev_features).reshape(1, -1)
                        )[0]
                        cal_probs_buffer.append(xgb_pred)
                        cal_outcomes_buffer.append(prev_outcome)
                except Exception:
                    pass

            # Now add to history and update ELO
            history.add_match(prev)
            elo.update(EloMatch(
                home_team=prev["home_team"], away_team=prev["away_team"],
                home_goals=prev["home_score"], away_goals=prev["away_score"],
            ))
            bandit_training.append(prev)

        # === Phase 2: Refit models ===

        # Dixon-Coles refit
        if dc is None or (i - min_training) % refit_interval == 0:
            dc_train = [
                MatchResult(
                    home_team=m["home_team"], away_team=m["away_team"],
                    home_goals=m["home_score"], away_goals=m["away_score"],
                    date=m["kickoff"],
                )
                for m in matches[:i]
            ]
            dc = DixonColesModel()
            try:
                dc.fit(dc_train)
            except ValueError:
                continue

        # XGBoost retrain
        if (len(xgb_X) >= XGBStackingModel.MIN_TRAINING_SAMPLES
                and (i - min_training) % xgb_retrain_interval == 0):
            X_arr = np.array(xgb_X)
            y_arr = np.array(xgb_y)
            split = int(len(X_arr) * 0.8)
            xgb_model.fit(
                X_arr[:split], y_arr[:split],
                X_val=X_arr[split:], y_val=y_arr[split:],
            )

        # Calibrator retrain
        if (len(cal_probs_buffer) >= 100
                and (i - min_training) % calibrator_retrain_interval == 0):
            cal_p = np.array(cal_probs_buffer)
            cal_o = np.array(cal_outcomes_buffer)
            calibrator = ProbabilityCalibrator(method="isotonic")
            calibrator.fit(cal_p, cal_o)

        # Bandit retrain (same interval as calibrator)
        if (len(bandit_training) >= 200
                and (i - min_training) % calibrator_retrain_interval == 0):
            bandit = ContextualBandit()
            bandit.fit(bandit_training, dc_model=dc, elo_model=elo)

        # Progress
        if (i - min_training) % 200 == 0:
            elapsed = time.time() - start_time
            logger.info(
                f"Progress: {i}/{n} ({elapsed:.0f}s) | "
                f"XGB samples={len(xgb_X)}, CAL samples={len(cal_probs_buffer)}, "
                f"Bandit={'ON' if bandit.is_fitted else 'OFF'}"
            )

        # === Phase 3: Predict with each configuration ===

        # Compute features for current match
        match_features = None
        if dc is not None:
            try:
                match_features = compute_features(
                    test["home_team"], test["away_team"],
                    test["kickoff"], history,
                    dc_model=dc, elo_model=elo,
                )
            except Exception:
                pass

        # Config 1: BASELINE (DC + ELO weighted average)
        ens_base = EnsemblePredictor(dc, elo, dc_weight, elo_weight)
        pred_base = ens_base.predict(test["home_team"], test["away_team"])
        probs_base = np.array([pred_base.home_prob, pred_base.draw_prob, pred_base.away_prob])

        # Config 2: +XGB
        if xgb_model.is_fitted and match_features is not None:
            ens_xgb = EnsemblePredictor(
                dc, elo, dc_weight, elo_weight,
                xgb_model=xgb_model,
            )
            pred_xgb = ens_xgb.predict(
                test["home_team"], test["away_team"],
                match_features=match_features,
            )
            probs_xgb = np.array([pred_xgb.home_prob, pred_xgb.draw_prob, pred_xgb.away_prob])
        else:
            probs_xgb = probs_base.copy()

        # Config 3: +XGB+CAL (temperature scaling or isotonic)
        if xgb_model.is_fitted and match_features is not None:
            if use_temp_scaling:
                ens_cal = EnsemblePredictor(
                    dc, elo, dc_weight, elo_weight,
                    xgb_model=xgb_model,
                    temperature=temp_scaling_t,
                )
            elif calibrator.is_fitted:
                ens_cal = EnsemblePredictor(
                    dc, elo, dc_weight, elo_weight,
                    xgb_model=xgb_model,
                    calibrator=calibrator,
                )
            else:
                ens_cal = None

            if ens_cal is not None:
                pred_cal = ens_cal.predict(
                    test["home_team"], test["away_team"],
                    match_features=match_features,
                )
                probs_cal = np.array([pred_cal.home_prob, pred_cal.draw_prob, pred_cal.away_prob])
            else:
                probs_cal = probs_xgb.copy()
        else:
            probs_cal = probs_xgb.copy()

        # Config 4: +XGB+CAL+BANDIT (same probs as config 3, but different bet selection)
        probs_bandit = probs_cal.copy()

        # Actual outcome
        hs, aws = test["home_score"], test["away_score"]
        outcome = 0 if hs > aws else (1 if hs == aws else 2)
        total_goals = hs + aws

        # Record predictions for calibration metrics
        for cfg, probs in [
            ("baseline", probs_base),
            ("xgb", probs_xgb),
            ("xgb_cal", probs_cal),
            ("xgb_cal_bandit", probs_bandit),
        ]:
            all_probs[cfg].append(probs)
            all_outcomes[cfg].append(outcome)

        # === Phase 4: Edge calculation + betting simulation ===
        date_str = str(test["kickoff"])[:10]
        match_key = f"{test['home_team']}_vs_{test['away_team']}_{date_str}"

        if match_key not in odds_data:
            continue

        odds_matched += 1
        odds = odds_data[match_key]

        fair = remove_margin(
            odds["home_odds"], odds["draw_odds"], odds["away_odds"]
        )
        if fair["home"] <= 0:
            continue

        # Best available odds for each market
        best_odds_map = {
            "home": odds.get("best_home", odds["home_odds"]),
            "draw": odds.get("best_draw", odds["draw_odds"]),
            "away": odds.get("best_away", odds["away_odds"]),
        }

        # Market-specific edge thresholds
        market_thresholds = {
            "home": min_edge,
            "draw": min_edge,
            "away": 9999.0 if disable_away else away_edge,
        }

        # For configs 1-3: standard edge-based betting
        for cfg, probs in [
            ("baseline", probs_base),
            ("xgb", probs_xgb),
            ("xgb_cal", probs_cal),
        ]:
            for market_idx, market_name in enumerate(["home", "draw", "away"]):
                model_p = float(probs[market_idx])
                fair_p = fair[market_name]
                best_o = best_odds_map[market_name]

                if fair_p <= 0 or best_o <= 1.0:
                    continue

                edge = ((model_p - fair_p) / fair_p) * 100

                if edge >= market_thresholds[market_name]:
                    # Kelly filter: only bet if Kelly stake >= min_kelly
                    b = best_o - 1.0
                    q = 1.0 - model_p
                    kelly_raw = (b * model_p - q) / b if b > 0 else 0
                    kelly_pct = max(0, kelly_raw * 0.25 * 100)

                    if kelly_pct < min_kelly:
                        continue

                    edges_found[cfg] += 1
                    won = outcome == market_idx
                    pnl = (best_o - 1.0) if won else -1.0

                    bets[cfg].append({
                        "date": date_str,
                        "home": test["home_team"],
                        "away": test["away_team"],
                        "market": market_name,
                        "model_prob": round(model_p, 4),
                        "fair_prob": round(fair_p, 4),
                        "edge_pct": round(edge, 1),
                        "kelly_pct": round(kelly_pct, 1),
                        "best_odds": best_o,
                        "outcome": ["home", "draw", "away"][outcome],
                        "won": won,
                        "pnl": round(pnl, 2),
                    })

        # Config 4: BANDIT-guided betting
        if bandit.is_fitted:
            bandit_ctx = {
                "home_prob": float(probs_cal[0]),
                "draw_prob": float(probs_cal[1]),
                "away_prob": float(probs_cal[2]),
                "over25_prob": pred_base.over_25_prob if hasattr(pred_base, 'over_25_prob') else 0.5,
                "btts_prob": pred_base.btts_prob if hasattr(pred_base, 'btts_prob') else 0.5,
                "edge_1x2_home": ((float(probs_cal[0]) - fair["home"]) / fair["home"]) * 100 if fair["home"] > 0 else 0,
                "edge_1x2_draw": ((float(probs_cal[1]) - fair["draw"]) / fair["draw"]) * 100 if fair["draw"] > 0 else 0,
                "edge_1x2_away": ((float(probs_cal[2]) - fair["away"]) / fair["away"]) * 100 if fair["away"] > 0 else 0,
                "edge_over25": 0.0,
                "edge_under25": 0.0,
                "edge_skip": 0.0,
                "max_edge": 0.0,
            }
            # Compute max edge
            bandit_ctx["max_edge"] = max(
                bandit_ctx["edge_1x2_home"],
                bandit_ctx["edge_1x2_draw"],
                bandit_ctx["edge_1x2_away"],
                0.0,
            )

            rec = bandit.recommend(bandit_ctx)
            arm = rec["recommended_market"]

            # Map bandit arm to market
            arm_to_market = {
                "1x2_home": ("home", 0),
                "1x2_draw": ("draw", 1),
                "1x2_away": ("away", 2),
            }

            if arm in arm_to_market:
                market_name, market_idx = arm_to_market[arm]
                model_p = float(probs_cal[market_idx])
                fair_p = fair[market_name]
                best_o = best_odds_map[market_name]
                edge = ((model_p - fair_p) / fair_p) * 100 if fair_p > 0 else 0

                if edge >= market_thresholds[market_name] and best_o > 1.0:
                    # Kelly filter
                    b = best_o - 1.0
                    q = 1.0 - model_p
                    kelly_raw = (b * model_p - q) / b if b > 0 else 0
                    kelly_pct = max(0, kelly_raw * 0.25 * 100)

                    if kelly_pct < min_kelly:
                        pass  # Skip this bet
                    else:
                        edges_found["xgb_cal_bandit"] += 1
                        won = outcome == market_idx
                        pnl = (best_o - 1.0) if won else -1.0

                        bets["xgb_cal_bandit"].append({
                            "date": date_str,
                            "home": test["home_team"],
                            "away": test["away_team"],
                            "market": market_name,
                            "bandit_arm": arm,
                            "bandit_confidence": rec["confidence"],
                            "bandit_segment": rec["segment"],
                            "model_prob": round(model_p, 4),
                            "fair_prob": round(fair_p, 4),
                            "edge_pct": round(edge, 1),
                            "kelly_pct": round(kelly_pct, 1),
                            "best_odds": best_o,
                            "outcome": ["home", "draw", "away"][outcome],
                            "won": won,
                            "pnl": round(pnl, 2),
                        })
            # If bandit says "skip" or O/U market: no bet recorded
        else:
            # Bandit not fitted yet: fallback to same as xgb_cal
            for market_idx, market_name in enumerate(["home", "draw", "away"]):
                model_p = float(probs_cal[market_idx])
                fair_p = fair[market_name]
                best_o = best_odds_map[market_name]

                if fair_p <= 0 or best_o <= 1.0:
                    continue
                edge = ((model_p - fair_p) / fair_p) * 100
                if edge >= market_thresholds[market_name]:
                    # Kelly filter
                    b = best_o - 1.0
                    q = 1.0 - model_p
                    kelly_raw = (b * model_p - q) / b if b > 0 else 0
                    kelly_pct = max(0, kelly_raw * 0.25 * 100)

                    if kelly_pct < min_kelly:
                        continue

                    edges_found["xgb_cal_bandit"] += 1
                    won = outcome == market_idx
                    pnl = (best_o - 1.0) if won else -1.0
                    bets["xgb_cal_bandit"].append({
                        "date": date_str,
                        "home": test["home_team"],
                        "away": test["away_team"],
                        "market": market_name,
                        "model_prob": round(model_p, 4),
                        "fair_prob": round(fair_p, 4),
                        "edge_pct": round(edge, 1),
                        "kelly_pct": round(kelly_pct, 1),
                        "best_odds": best_o,
                        "outcome": ["home", "draw", "away"][outcome],
                        "won": won,
                        "pnl": round(pnl, 2),
                    })

    elapsed = time.time() - start_time

    # === Aggregate results per config ===
    results = {
        "elapsed_seconds": round(elapsed, 1),
        "total_matches": n,
        "matches_tested": n - min_training,
        "matches_with_odds": odds_matched,
        "configs": {},
    }

    for cfg in configs:
        probs_arr = np.array(all_probs[cfg]) if all_probs[cfg] else np.empty((0, 3))
        outcomes_arr = np.array(all_outcomes[cfg]) if all_outcomes[cfg] else np.empty(0, dtype=int)

        # Calibration metrics
        if len(probs_arr) >= 10:
            cal_report = evaluate(probs_arr, outcomes_arr)
            cal_dict = {
                "brier_score": round(cal_report.brier_score, 4),
                "log_loss": round(cal_report.log_loss, 4),
                "ece": round(cal_report.ece, 4),
                "accuracy": round(cal_report.accuracy, 4),
                "is_acceptable": cal_report.is_acceptable,
                "n_predictions": cal_report.n_predictions,
            }
        else:
            cal_dict = {"error": "insufficient predictions"}

        # Betting stats
        cfg_bets = bets[cfg]
        n_bets = len(cfg_bets)
        wins = sum(1 for b in cfg_bets if b["won"])
        total_pnl = sum(b["pnl"] for b in cfg_bets)
        roi = total_pnl / n_bets if n_bets > 0 else 0

        # By market
        by_market = {}
        for market in ["home", "draw", "away"]:
            mb = [b for b in cfg_bets if b["market"] == market]
            if mb:
                m_pnl = sum(b["pnl"] for b in mb)
                m_wins = sum(1 for b in mb if b["won"])
                m_edges = [b["edge_pct"] for b in mb]
                by_market[market] = {
                    "bets": len(mb),
                    "wins": m_wins,
                    "win_rate": round(m_wins / len(mb), 4),
                    "pnl": round(m_pnl, 2),
                    "roi": round(m_pnl / len(mb), 4),
                    "avg_edge": round(np.mean(m_edges), 1),
                }

        # Cumulative PnL curve (for plotting)
        cum_pnl = []
        running = 0.0
        for b in cfg_bets:
            running += b["pnl"]
            cum_pnl.append(round(running, 2))

        results["configs"][cfg] = {
            "calibration": cal_dict,
            "betting": {
                "total_bets": n_bets,
                "wins": wins,
                "win_rate": round(wins / n_bets, 4) if n_bets > 0 else 0,
                "total_pnl": round(total_pnl, 2),
                "roi": round(roi, 4),
                "avg_edge": round(np.mean([b["edge_pct"] for b in cfg_bets]), 1) if cfg_bets else 0,
                "by_market": by_market,
            },
            "cumulative_pnl": cum_pnl,
            "bets": cfg_bets,
        }

    # XGBoost feature importance
    if xgb_model.is_fitted:
        results["xgb_info"] = {
            "train_samples": xgb_model._n_train_samples,
            "feature_importance": {
                k: round(v, 4) for k, v in
                list(xgb_model.feature_importance().items())[:15]
            },
        }

    # Bandit segment summary
    if bandit.is_fitted:
        results["bandit_info"] = {
            "segments": len(bandit.get_segment_summary()),
            "summary": {
                seg: {
                    "best_arm": info["best_arm"],
                    "best_roi": info["best_roi"],
                    "n_arms": len(info.get("arms", {})),
                }
                for seg, info in bandit.get_segment_summary().items()
            },
        }

    return results


def print_report(results: dict) -> None:
    """Print formatted comparison report."""
    print("\n" + "=" * 75)
    print("  FULL PIPELINE BACKTEST - CONFIGURATION COMPARISON")
    print("=" * 75)
    print(f"  Matches: {results['matches_tested']} tested, "
          f"{results['matches_with_odds']} with odds | "
          f"Time: {results['elapsed_seconds']:.0f}s")

    config_names = {
        "baseline": "DC + ELO (baseline)",
        "xgb": "+ XGBoost (62 features)",
        "+ Calibration (Isotonic)": "xgb_cal",
        "xgb_cal": "+ Calibration (Isotonic)",
        "xgb_cal_bandit": "+ Bandit (Thompson)",
    }

    # Header
    print(f"\n  {'Config':<30} {'Brier':>8} {'ECE':>8} {'Acc':>8} "
          f"{'Bets':>6} {'Win%':>7} {'PnL':>8} {'ROI':>8}")
    print("  " + "-" * 93)

    for cfg in ["baseline", "xgb", "xgb_cal", "xgb_cal_bandit"]:
        data = results["configs"].get(cfg, {})
        cal = data.get("calibration", {})
        bet = data.get("betting", {})

        name = config_names.get(cfg, cfg)
        brier = cal.get("brier_score", 0)
        ece = cal.get("ece", 0)
        acc = cal.get("accuracy", 0)
        n_bets = bet.get("total_bets", 0)
        wr = bet.get("win_rate", 0)
        pnl = bet.get("total_pnl", 0)
        roi = bet.get("roi", 0)

        pnl_str = f"{pnl:+.1f}u"
        roi_str = f"{roi:+.1%}"

        print(f"  {name:<30} {brier:>8.4f} {ece:>8.4f} {acc:>7.1%} "
              f"{n_bets:>6} {wr:>6.1%} {pnl_str:>8} {roi_str:>8}")

    # Delta analysis
    print(f"\n  {'='*75}")
    print("  DELTA ANALYSIS (vs baseline)")
    print(f"  {'-'*75}")

    base_cal = results["configs"]["baseline"]["calibration"]
    base_bet = results["configs"]["baseline"]["betting"]

    for cfg in ["xgb", "xgb_cal", "xgb_cal_bandit"]:
        data = results["configs"][cfg]
        cal = data["calibration"]
        bet = data["betting"]

        name = config_names.get(cfg, cfg)
        d_brier = cal.get("brier_score", 0) - base_cal.get("brier_score", 0)
        d_ece = cal.get("ece", 0) - base_cal.get("ece", 0)
        d_roi = bet.get("roi", 0) - base_bet.get("roi", 0)
        d_pnl = bet.get("total_pnl", 0) - base_bet.get("total_pnl", 0)

        brier_arrow = "v" if d_brier < 0 else "^"  # lower is better
        ece_arrow = "v" if d_ece < 0 else "^"
        roi_arrow = "^" if d_roi > 0 else "v"

        print(f"  {name:<30} Brier {d_brier:+.4f}{brier_arrow} | "
              f"ECE {d_ece:+.4f}{ece_arrow} | "
              f"ROI {d_roi:+.1%}{roi_arrow} | "
              f"PnL {d_pnl:+.1f}u")

    # By-market breakdown for best config
    print(f"\n  {'='*75}")
    print("  PER-MARKET BREAKDOWN (each config)")
    print(f"  {'-'*75}")

    for cfg in ["baseline", "xgb", "xgb_cal", "xgb_cal_bandit"]:
        name = config_names.get(cfg, cfg)
        by_market = results["configs"][cfg]["betting"].get("by_market", {})
        if not by_market:
            print(f"  {name}: no bets")
            continue
        print(f"\n  {name}:")
        for market, stats in by_market.items():
            arrow = "+" if stats["pnl"] >= 0 else ""
            print(f"    {market:>5}: {stats['bets']:3d} bets | "
                  f"win {stats['win_rate']:.0%} | "
                  f"PnL {arrow}{stats['pnl']:.1f}u | "
                  f"ROI {stats['roi']:+.1%} | "
                  f"avg edge {stats['avg_edge']:.1f}%")

    # Feature importance
    if "xgb_info" in results:
        print(f"\n  {'='*75}")
        print(f"  TOP FEATURES (XGB trained on {results['xgb_info']['train_samples']} samples)")
        print(f"  {'-'*75}")
        for feat, imp in list(results["xgb_info"]["feature_importance"].items())[:10]:
            bar = "#" * int(imp * 120)
            print(f"    {feat:>30}: {imp:.4f} {bar}")

    # Bandit info
    if "bandit_info" in results:
        print(f"\n  {'='*75}")
        print(f"  BANDIT SEGMENTS ({results['bandit_info']['segments']} segments)")
        print(f"  {'-'*75}")
        for seg, info in list(results["bandit_info"]["summary"].items())[:6]:
            print(f"    {seg:<35} -> {info['best_arm']} (ROI: {info['best_roi']:.1f}%)")

    # Verdict
    print(f"\n  {'='*75}")

    # Find best config by ROI
    best_cfg = max(
        ["baseline", "xgb", "xgb_cal", "xgb_cal_bandit"],
        key=lambda c: results["configs"][c]["betting"].get("roi", -999),
    )
    best_roi = results["configs"][best_cfg]["betting"]["roi"]
    best_pnl = results["configs"][best_cfg]["betting"]["total_pnl"]
    best_cal = results["configs"][best_cfg]["calibration"]

    cal_ok = best_cal.get("is_acceptable", False)
    sample_ok = results["configs"][best_cfg]["betting"]["total_bets"] >= 50
    roi_ok = best_roi > -0.05

    if cal_ok and sample_ok and roi_ok:
        if best_roi > 0:
            verdict = f"GO - {config_names.get(best_cfg, best_cfg)} shows +ROI ({best_roi:+.1%}, {best_pnl:+.1f}u)"
        else:
            verdict = f"CAUTIOUS - Best is {config_names.get(best_cfg, best_cfg)} ({best_roi:+.1%})"
    else:
        reasons = []
        if not cal_ok:
            reasons.append("calibration failed")
        if not sample_ok:
            reasons.append("insufficient bets")
        if not roi_ok:
            reasons.append(f"ROI too negative ({best_roi:+.1%})")
        verdict = f"NO-GO - {', '.join(reasons)}"

    print(f"  VERDICT: {verdict}")
    print("=" * 75)


def run_single_league_backtest(league: str, args) -> dict | None:
    """Run backtest for a single league and return results."""
    cache_dir = PROJECT_ROOT / "data" / "historical"

    logger.info(f"\n{'='*60}")
    logger.info(f"  BACKTEST: {league}")
    logger.info(f"{'='*60}")

    # Load data
    logger.info(f"Loading {league} seasons {args.seasons}")
    matches = load_historical_data(league, args.seasons, cache_dir)

    if len(matches) < args.min_training + 50:
        print(f"  [SKIP] {league}: Only {len(matches)} matches (need {args.min_training + 50})")
        return None

    # Build odds lookup
    odds_data = build_odds_lookup(matches, odds_source="pinnacle")

    # Data quality
    has_pinnacle = sum(1 for m in matches if m.get("pinnacle_home", 0) > 1.0)
    has_max = sum(1 for m in matches if m.get("max_home", 0) > 1.0)
    logger.info(f"Data: {len(matches)} matches | Pinnacle: {has_pinnacle} | Max: {has_max}")

    # Run backtest
    results = run_full_backtest(
        matches, odds_data,
        min_training=args.min_training,
        min_edge=args.min_edge,
        away_edge=args.away_edge,
        disable_away=args.disable_away,
        min_kelly=args.min_kelly,
        refit_interval=args.refit_interval,
        xgb_retrain_interval=args.xgb_retrain,
        use_temp_scaling=args.temp_scaling,
        temp_scaling_t=args.temp_t,
    )

    results["league"] = league
    return results


def main():
    parser = argparse.ArgumentParser(description="Full pipeline backtest")
    parser.add_argument(
        "--seasons", nargs="+", type=int, default=[2021, 2022, 2023, 2024, 2025],
        help="Seasons to include (default: 2021-2025)"
    )
    parser.add_argument(
        "--leagues", nargs="+", default=["premier_league"],
        help="Leagues to backtest (default: premier_league). "
             "Use 'all' for all 5 top leagues."
    )
    # Keep --league for backwards compatibility
    parser.add_argument("--league", default=None,
                        help="Single league (deprecated, use --leagues)")
    parser.add_argument("--min-edge", type=float, default=5.0,
                        help="Min edge %% for home/draw betting (default: 5)")
    parser.add_argument("--away-edge", type=float, default=15.0,
                        help="Min edge %% for away betting (default: 15)")
    parser.add_argument("--disable-away", action="store_true",
                        help="Completely disable away market betting")
    parser.add_argument("--min-kelly", type=float, default=1.0,
                        help="Min Kelly stake %% to qualify (default: 1.0)")
    parser.add_argument("--min-training", type=int, default=120,
                        help="Min training matches before testing")
    parser.add_argument("--refit-interval", type=int, default=30,
                        help="DC refit interval")
    parser.add_argument("--xgb-retrain", type=int, default=60,
                        help="XGB retrain interval")
    parser.add_argument("--temp-scaling", action="store_true",
                        help="Use temperature scaling instead of isotonic calibration")
    parser.add_argument("--temp-t", type=float, default=1.2,
                        help="Temperature for temp scaling (default: 1.2)")
    args = parser.parse_args()

    # Resolve leagues
    ALL_TOP_5 = ["premier_league", "ligue_1", "la_liga", "bundesliga", "serie_a"]

    if args.league:
        # Backwards compat: --league overrides --leagues
        leagues = [args.league]
    elif "all" in args.leagues:
        leagues = ALL_TOP_5
    else:
        leagues = args.leagues

    results_dir = PROJECT_ROOT / "data" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    all_results = {}

    for league in leagues:
        results = run_single_league_backtest(league, args)
        if results is None:
            continue

        all_results[league] = results

        # Print report
        print_report(results)

        # Save per-league summary
        summary = {
            "league": league,
            "elapsed_seconds": results["elapsed_seconds"],
            "total_matches": results["total_matches"],
            "matches_tested": results["matches_tested"],
            "matches_with_odds": results["matches_with_odds"],
            "configs": {},
        }
        for cfg, data in results["configs"].items():
            summary["configs"][cfg] = {
                "calibration": data["calibration"],
                "betting": {k: v for k, v in data["betting"].items()},
            }
        if "xgb_info" in results:
            summary["xgb_info"] = results["xgb_info"]
        if "bandit_info" in results:
            summary["bandit_info"] = results["bandit_info"]

        summary_path = results_dir / f"backtest_{league}_summary.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"\n  Summary saved to {summary_path}")

        # Save bets per config
        for cfg in results["configs"]:
            cfg_bets = results["configs"][cfg].get("bets", [])
            if cfg_bets:
                bets_path = results_dir / f"backtest_{league}_{cfg}_bets.json"
                with open(bets_path, "w") as f:
                    json.dump(cfg_bets, f, indent=2, default=str)

    # If multiple leagues, print cross-league summary
    if len(all_results) > 1:
        print(f"\n\n{'='*80}")
        print("  CROSS-LEAGUE SUMMARY")
        print(f"{'='*80}")
        print(f"\n  {'League':<20} {'Matches':>8} {'Best Config':<28} {'ROI':>8} {'PnL':>8} {'Bets':>6}")
        print(f"  {'-'*80}")

        total_pnl = 0.0
        total_bets = 0

        for league, results in all_results.items():
            best_cfg = max(
                results["configs"],
                key=lambda c: results["configs"][c]["betting"].get("roi", -999),
            )
            bet = results["configs"][best_cfg]["betting"]
            roi = bet.get("roi", 0)
            pnl = bet.get("total_pnl", 0)
            n_bets = bet.get("total_bets", 0)
            total_pnl += pnl
            total_bets += n_bets

            config_names = {
                "baseline": "DC + ELO",
                "xgb": "+ XGBoost",
                "xgb_cal": "+ Calibration",
                "xgb_cal_bandit": "+ Bandit",
            }
            print(f"  {league:<20} {results['matches_tested']:>8} "
                  f"{config_names.get(best_cfg, best_cfg):<28} "
                  f"{roi:>+7.1%} {pnl:>+7.1f}u {n_bets:>6}")

        overall_roi = total_pnl / total_bets if total_bets > 0 else 0
        print(f"  {'-'*80}")
        print(f"  {'TOTAL':<20} {'':>8} {'':>28} "
              f"{overall_roi:>+7.1%} {total_pnl:>+7.1f}u {total_bets:>6}")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    main()

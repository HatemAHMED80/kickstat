#!/usr/bin/env python3
"""Full backtest with real historical odds from football-data.co.uk.

This is the definitive test: can our model beat the bookmakers?

Uses:
- Pinnacle closing odds for fair value (sharpest line in the market)
- Market max odds for PnL calculation (best odds actually available)
- XGBoost stacking model with form + shot + dominance features

Usage:
    python scripts/backtest_with_odds.py
    python scripts/backtest_with_odds.py --seasons 2022 2023 2024
    python scripts/backtest_with_odds.py --min-edge 3
    python scripts/backtest_with_odds.py --no-xgb   # baseline without XGBoost
"""

import argparse
import json
import sys
import time
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
from src.evaluation.calibration import evaluate


def run_backtest(
    matches: list[dict],
    odds_data: dict,
    min_training: int = 100,
    min_edge: float = 5.0,
    dc_weight: float = 0.65,
    elo_weight: float = 0.35,
    refit_interval: int = 30,
    use_xgb: bool = True,
    xgb_retrain_interval: int = 60,
) -> dict:
    """Run walk-forward backtest with real odds.

    Returns dict with all results for analysis.
    """
    matches = sorted(matches, key=lambda m: m["kickoff"])
    n = len(matches)
    logger.info(f"Starting backtest on {n} matches, {len(odds_data)} with odds"
                f" | XGBoost={'ON' if use_xgb else 'OFF'}")

    all_probs = []
    all_outcomes = []
    betting_results = []
    edges_found = 0
    odds_matched = 0

    # Build ELO + history up to min_training
    elo = EloRating()
    history = MatchHistory()
    for m in matches[:min_training]:
        elo.update(EloMatch(
            home_team=m["home_team"], away_team=m["away_team"],
            home_goals=m["home_score"], away_goals=m["away_score"],
        ))
        history.add_match(m)

    dc = None
    xgb_model = XGBStackingModel() if use_xgb else None
    xgb_training_X: list[np.ndarray] = []
    xgb_training_y: list[int] = []
    start_time = time.time()

    for i in range(min_training, n):
        test = matches[i]

        # === Phase 1: Process PREVIOUS match (update training data) ===
        if i > min_training:
            prev = matches[i - 1]

            # Compute features for prev BEFORE adding it to history (walk-forward)
            if use_xgb and dc is not None:
                prev_features = compute_features(
                    prev["home_team"], prev["away_team"],
                    prev["kickoff"], history,
                    dc_model=dc, elo_model=elo,
                )
                prev_hs, prev_as = prev["home_score"], prev["away_score"]
                prev_outcome = 0 if prev_hs > prev_as else (1 if prev_hs == prev_as else 2)
                xgb_training_X.append(features_to_array(prev_features))
                xgb_training_y.append(prev_outcome)

            # NOW add prev to history and update ELO
            history.add_match(prev)
            elo.update(EloMatch(
                home_team=prev["home_team"], away_team=prev["away_team"],
                home_goals=prev["home_score"], away_goals=prev["away_score"],
            ))

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

            if (i - min_training) % 100 == 0:
                elapsed = time.time() - start_time
                xgb_status = (f", XGB samples={len(xgb_training_X)}"
                              if use_xgb else "")
                logger.info(f"Progress: {i}/{n} ({elapsed:.0f}s){xgb_status}")

        # XGBoost retrain
        if (use_xgb and xgb_model is not None
                and len(xgb_training_X) >= XGBStackingModel.MIN_TRAINING_SAMPLES
                and (i - min_training) % xgb_retrain_interval == 0):
            X_arr = np.array(xgb_training_X)
            y_arr = np.array(xgb_training_y)
            split = int(len(X_arr) * 0.8)
            xgb_model.fit(
                X_arr[:split], y_arr[:split],
                X_val=X_arr[split:], y_val=y_arr[split:],
            )

        # === Phase 3: Predict ===
        match_features = None
        if use_xgb and dc is not None:
            match_features = compute_features(
                test["home_team"], test["away_team"],
                test["kickoff"], history,
                dc_model=dc, elo_model=elo,
            )

        ensemble = EnsemblePredictor(
            dc, elo, dc_weight, elo_weight,
            xgb_model=xgb_model if use_xgb else None,
        )
        pred = ensemble.predict(
            test["home_team"], test["away_team"],
            match_features=match_features,
        )

        probs = np.array([pred.home_prob, pred.draw_prob, pred.away_prob])
        all_probs.append(probs)

        # Actual outcome
        hs, aws = test["home_score"], test["away_score"]
        if hs > aws:
            outcome = 0
        elif hs == aws:
            outcome = 1
        else:
            outcome = 2
        all_outcomes.append(outcome)

        # === Phase 4: Edge calculation with real odds ===
        date_str = str(test["kickoff"])[:10]
        match_key = f"{test['home_team']}_vs_{test['away_team']}_{date_str}"
        if match_key in odds_data:
            odds_matched += 1
            odds = odds_data[match_key]

            fair = remove_margin(
                odds["home_odds"], odds["draw_odds"], odds["away_odds"]
            )

            markets = [
                ("home", pred.home_prob, fair["home"],
                 odds.get("best_home", odds["home_odds"])),
                ("draw", pred.draw_prob, fair["draw"],
                 odds.get("best_draw", odds["draw_odds"])),
                ("away", pred.away_prob, fair["away"],
                 odds.get("best_away", odds["away_odds"])),
            ]

            for market_name, model_p, fair_p, best_odds in markets:
                if fair_p <= 0 or best_odds <= 1.0:
                    continue
                edge = ((model_p - fair_p) / fair_p) * 100

                if edge >= min_edge:
                    edges_found += 1
                    won = (
                        (market_name == "home" and outcome == 0)
                        or (market_name == "draw" and outcome == 1)
                        or (market_name == "away" and outcome == 2)
                    )
                    pnl = (best_odds - 1.0) if won else -1.0

                    betting_results.append({
                        "date": str(test["kickoff"]),
                        "home": test["home_team"],
                        "away": test["away_team"],
                        "market": market_name,
                        "model_prob": round(model_p, 4),
                        "fair_prob": round(fair_p, 4),
                        "edge_pct": round(edge, 1),
                        "best_odds": best_odds,
                        "outcome": ["home", "draw", "away"][outcome],
                        "won": won,
                        "pnl": round(pnl, 2),
                    })

    elapsed = time.time() - start_time

    # Calibration
    probs_array = np.array(all_probs)
    outcomes_array = np.array(all_outcomes)
    cal = evaluate(probs_array, outcomes_array)

    # Betting stats
    total_pnl = sum(b["pnl"] for b in betting_results)
    n_bets = len(betting_results)
    wins = sum(1 for b in betting_results if b["won"])
    roi = total_pnl / n_bets if n_bets > 0 else 0

    # Edge distribution
    edges = [b["edge_pct"] for b in betting_results]

    # By market breakdown
    by_market = {}
    for market in ["home", "draw", "away"]:
        mb = [b for b in betting_results if b["market"] == market]
        if mb:
            m_pnl = sum(b["pnl"] for b in mb)
            m_wins = sum(1 for b in mb if b["won"])
            by_market[market] = {
                "bets": len(mb),
                "wins": m_wins,
                "win_rate": round(m_wins / len(mb), 3),
                "pnl": round(m_pnl, 2),
                "roi": round(m_pnl / len(mb), 4),
            }

    result = {
        "elapsed_seconds": round(elapsed, 1),
        "total_matches": len(all_probs),
        "matches_with_odds": odds_matched,
        "xgb_enabled": use_xgb,
        "calibration": {
            "brier_score": round(cal.brier_score, 4),
            "log_loss": round(cal.log_loss, 4),
            "ece": round(cal.ece, 4),
            "accuracy": round(cal.accuracy, 4),
            "is_acceptable": cal.is_acceptable,
        },
        "betting": {
            "total_bets": n_bets,
            "wins": wins,
            "win_rate": round(wins / n_bets, 4) if n_bets > 0 else 0,
            "total_pnl": round(total_pnl, 2),
            "roi": round(roi, 4),
            "avg_edge": round(np.mean(edges), 1) if edges else 0,
            "median_edge": round(np.median(edges), 1) if edges else 0,
            "by_market": by_market,
        },
        "bets": betting_results,
    }

    # Feature importance
    if use_xgb and xgb_model and xgb_model.is_fitted:
        result["xgb_train_samples"] = xgb_model._n_train_samples
        result["feature_importance"] = {
            k: round(v, 4) for k, v in
            list(xgb_model.feature_importance().items())[:15]
        }

    return result


def print_report(results: dict) -> None:
    """Print formatted backtest report."""
    mode = "XGBoost STACKING" if results.get("xgb_enabled") else "BASELINE (DC+ELO)"
    print("\n" + "=" * 65)
    print(f"  BACKTEST: {mode}")
    print("=" * 65)

    cal = results["calibration"]
    status = "PASS" if cal["is_acceptable"] else "FAIL"
    print(f"\n  Calibration [{status}]")
    print(f"    Brier Score:  {cal['brier_score']:.4f}  (threshold < 0.62)")
    print(f"    ECE:          {cal['ece']:.4f}  (threshold < 0.08)")
    print(f"    Log Loss:     {cal['log_loss']:.4f}")
    print(f"    Accuracy:     {cal['accuracy']:.1%}")
    print(f"    Predictions:  {results['total_matches']}")

    bet = results["betting"]
    print(f"\n  Betting Simulation")
    print(f"    Matches with odds: {results['matches_with_odds']}")
    print(f"    Edges found (bets): {bet['total_bets']}")
    print(f"    Win rate:       {bet['win_rate']:.1%}")
    print(f"    Avg edge:       {bet['avg_edge']:.1f}%")
    print(f"    Median edge:    {bet['median_edge']:.1f}%")
    print(f"    Total PnL:      {bet['total_pnl']:+.2f} units")
    print(f"    ROI:            {bet['roi']:.1%}")

    print(f"\n  By Market:")
    for market, stats in bet.get("by_market", {}).items():
        arrow = "+" if stats["pnl"] >= 0 else ""
        print(f"    {market:>5}: {stats['bets']:3d} bets, "
              f"win {stats['win_rate']:.0%}, "
              f"PnL {arrow}{stats['pnl']:.1f}u, "
              f"ROI {stats['roi']:.1%}")

    # Feature importance
    if "feature_importance" in results:
        print(f"\n  Top Features (XGB trained on {results.get('xgb_train_samples', '?')} samples):")
        for feat, imp in list(results["feature_importance"].items())[:10]:
            bar = "#" * int(imp * 100)
            print(f"    {feat:>25}: {imp:.3f} {bar}")

    # GO/NO-GO
    print("\n" + "-" * 65)
    go_calibration = cal["is_acceptable"]
    go_sample = bet["total_bets"] >= 50
    go_roi = bet["roi"] > -0.05

    if go_calibration and go_sample and go_roi:
        if bet["roi"] > 0:
            verdict = "GO - Model shows positive ROI"
        else:
            verdict = "CAUTIOUS GO - Calibrated but negative ROI"
    else:
        reasons = []
        if not go_calibration:
            reasons.append("calibration failed")
        if not go_sample:
            reasons.append(f"insufficient bets ({bet['total_bets']})")
        if not go_roi:
            reasons.append(f"ROI too negative ({bet['roi']:.1%})")
        verdict = f"NO-GO - {', '.join(reasons)}"

    print(f"  VERDICT: {verdict}")
    print("=" * 65)
    print(f"\n  Computed in {results['elapsed_seconds']:.0f}s")


def main():
    parser = argparse.ArgumentParser(description="Backtest with real historical odds")
    parser.add_argument(
        "--seasons", nargs="+", type=int, default=[2020, 2021, 2022, 2023, 2024],
        help="Seasons to include (default: 2020-2024)"
    )
    parser.add_argument("--league", default="ligue_1", help="League (default: ligue_1)")
    parser.add_argument("--min-edge", type=float, default=5.0, help="Min edge %% (default: 5)")
    parser.add_argument("--min-training", type=int, default=120, help="Min training matches")
    parser.add_argument("--refit-interval", type=int, default=30, help="Refit DC every N matches")
    parser.add_argument("--dc-weight", type=float, default=0.65, help="Dixon-Coles weight")
    parser.add_argument("--elo-weight", type=float, default=0.35, help="ELO weight")
    parser.add_argument("--no-xgb", action="store_true", help="Disable XGBoost stacking (baseline)")
    parser.add_argument("--xgb-retrain", type=int, default=60, help="XGB retrain interval")
    args = parser.parse_args()

    cache_dir = PROJECT_ROOT / "data" / "historical"

    # Download & parse
    logger.info(f"Loading {args.league} seasons {args.seasons}")
    matches = load_historical_data(args.league, args.seasons, cache_dir)

    if len(matches) < args.min_training + 50:
        print(f"ERROR: Only {len(matches)} matches. Need at least {args.min_training + 50}.")
        sys.exit(1)

    # Build odds lookup (Pinnacle for fair value, Max for PnL)
    odds_data = build_odds_lookup(matches, odds_source="pinnacle")

    # Count matches with valid Pinnacle odds
    has_pinnacle = sum(1 for m in matches if m.get("pinnacle_home", 0) > 1.0)
    has_max = sum(1 for m in matches if m.get("max_home", 0) > 1.0)
    logger.info(f"Matches with Pinnacle odds: {has_pinnacle}/{len(matches)}")
    logger.info(f"Matches with Max odds: {has_max}/{len(matches)}")

    # Check stats availability
    has_stats = sum(1 for m in matches if m.get("hs", 0) > 0)
    logger.info(f"Matches with shot stats: {has_stats}/{len(matches)}")

    # Run backtest
    results = run_backtest(
        matches, odds_data,
        min_training=args.min_training,
        min_edge=args.min_edge,
        dc_weight=args.dc_weight,
        elo_weight=args.elo_weight,
        refit_interval=args.refit_interval,
        use_xgb=not args.no_xgb,
        xgb_retrain_interval=args.xgb_retrain,
    )

    # Print report
    print_report(results)

    # Save detailed results
    results_dir = PROJECT_ROOT / "data" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    suffix = "xgb" if not args.no_xgb else "baseline"

    # Save summary (without individual bets)
    summary = {k: v for k, v in results.items() if k != "bets"}
    summary_path = results_dir / f"backtest_{suffix}_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n  Summary saved to {summary_path}")

    # Save all bets for analysis
    if results["bets"]:
        bets_path = results_dir / f"backtest_{suffix}_bets.json"
        with open(bets_path, "w") as f:
            json.dump(results["bets"], f, indent=2, default=str)
        print(f"  Bets detail saved to {bets_path}")


if __name__ == "__main__":
    main()

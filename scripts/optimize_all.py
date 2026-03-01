#!/usr/bin/env python3
"""Batch optimizer: runs grid search on ALL leagues × ALL markets.

Collects best (strategy, edge_threshold, min_prob) for each combination
and outputs ready-to-paste config dicts.

Usage:
    python scripts/optimize_all.py
    python scripts/optimize_all.py --min-bets 15
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.optimize_market import collect_raw_data, grid_search
from src.data.football_data_uk import load_historical_data, build_multi_market_odds


LEAGUES = ["premier_league", "la_liga", "bundesliga", "serie_a", "ligue_1"]
MARKETS = ["home", "draw", "away", "over25", "under25", "ah_home", "ah_away"]
SEASONS = [2021, 2022, 2023, 2024, 2025]


def run_league(league: str, seasons: list[int], markets: list[str] | None = None, min_bets: int = 15) -> dict:
    """Run optimizer for all markets in a single league.

    Returns dict: market -> best result dict (or None if insufficient data).
    """
    print(f"\n{'#'*80}")
    print(f"  LEAGUE: {league.upper()}")
    print(f"{'#'*80}")

    # Load data once per league
    cache_dir = PROJECT_ROOT / "data" / "historical"
    matches = load_historical_data(league, seasons, cache_dir)
    odds_data = build_multi_market_odds(matches)
    print(f"  {len(matches)} matches, {len(odds_data)} with odds")

    if markets is None:
        markets = MARKETS

    results = {}

    for market in markets:
        print(f"\n  --- {market.upper()} ---")
        t0 = time.time()

        try:
            raw_data = collect_raw_data(matches, odds_data, target_market=market)
        except Exception as e:
            print(f"  [ERROR] collect_raw_data failed: {e}")
            results[market] = None
            continue

        elapsed = time.time() - t0
        print(f"  {len(raw_data)} matches with valid data ({elapsed:.1f}s)")

        if len(raw_data) < min_bets:
            print(f"  [SKIP] Not enough data (< {min_bets})")
            results[market] = None
            continue

        # Grid search
        grid_results = grid_search(raw_data)
        grid_results = [r for r in grid_results if r["n_bets"] >= min_bets]

        if not grid_results:
            print(f"  [SKIP] No valid combinations with >= {min_bets} bets")
            results[market] = None
            continue

        # Sort by PnL then ROI
        grid_results.sort(key=lambda r: (r["total_pnl"], r["roi"]), reverse=True)
        best = grid_results[0]

        # Also find the "safest positive" — best ROI among profitable configs with >= 30 bets
        safe_results = [r for r in grid_results if r["total_pnl"] > 0 and r["n_bets"] >= 30]
        safe_best = None
        if safe_results:
            safe_results.sort(key=lambda r: r["roi"], reverse=True)
            safe_best = safe_results[0]

        print(f"  BEST: {best['strategy']:<12} edge={best['edge_threshold']:>4.0f}% "
              f"min_p={best['min_prob']:.2f} -> {best['n_bets']} bets, "
              f"{best['total_pnl']:+.1f}u, {best['roi']:+.1%}")

        if safe_best and safe_best != best:
            print(f"  SAFE: {safe_best['strategy']:<12} edge={safe_best['edge_threshold']:>4.0f}% "
                  f"min_p={safe_best['min_prob']:.2f} -> {safe_best['n_bets']} bets, "
                  f"{safe_best['total_pnl']:+.1f}u, {safe_best['roi']:+.1%}")

        results[market] = {
            "best": best,
            "safe": safe_best,
            "total_combos": len(grid_results),
        }

    return results


def main():
    parser = argparse.ArgumentParser(description="Batch optimize all leagues × markets")
    parser.add_argument("--min-bets", type=int, default=15, help="Minimum bets to consider")
    parser.add_argument("--leagues", nargs="+", default=LEAGUES, help="Leagues to optimize")
    parser.add_argument("--markets", nargs="+", default=MARKETS, help="Markets to optimize")
    args = parser.parse_args()

    print(f"\n{'='*80}")
    print(f"  BATCH OPTIMIZER: {len(args.leagues)} leagues × {len(args.markets)} markets")
    print(f"  = {len(args.leagues) * len(args.markets)} combinations")
    print(f"{'='*80}")

    markets = args.markets

    all_results = {}
    total_t0 = time.time()

    for league in args.leagues:
        league_results = run_league(league, SEASONS, markets=markets, min_bets=args.min_bets)
        all_results[league] = league_results

    total_elapsed = time.time() - total_t0

    # ===================================================================
    # Summary: build config dicts
    # ===================================================================
    print(f"\n\n{'='*80}")
    print(f"  OPTIMIZATION COMPLETE — {total_elapsed:.0f}s total")
    print(f"{'='*80}")

    # Build the 3 config dicts
    strategy_map = {}     # LEAGUE_MARKET_STRATEGY
    edge_overrides = {}   # LEAGUE_EDGE_OVERRIDES
    min_prob_overrides = {}  # LEAGUE_MIN_PROB_OVERRIDES

    # Default edge thresholds from backtest (for comparison)
    default_edges = {
        "home": 8.0, "draw": 5.0, "away": 15.0,
        "over25": 7.0, "under25": 10.0,
        "ah_home": 8.0, "ah_away": 5.0,
    }
    default_min_probs = {
        "home": 0.42, "draw": 0.28, "away": 0.40,
        "over25": 0.58, "under25": 0.50,
        "ah_home": 0.38, "ah_away": 0.55,
    }

    print(f"\n  {'League':<18} {'Market':<10} {'Strategy':<12} {'Edge%':>6} {'MinP':>6} "
          f"{'Bets':>5} {'PnL':>8} {'ROI':>7}")
    print(f"  {'-'*78}")

    total_pnl = 0.0

    for league in args.leagues:
        strategy_map[league] = {}
        edge_ov = {}
        mp_ov = {}

        for market in markets:
            result = all_results.get(league, {}).get(market)
            if result is None:
                # No data → use baseline defaults
                strategy_map[league][market] = "baseline"
                print(f"  {league:<18} {market:<10} {'baseline':<12} {'N/A':>6} {'N/A':>6} "
                      f"{'N/A':>5} {'N/A':>8} {'N/A':>7}")
                continue

            best = result["best"]
            strategy_map[league][market] = best["strategy"]

            # Edge override: if different from default
            if best["edge_threshold"] != default_edges.get(market, 8.0):
                edge_ov[market] = best["edge_threshold"]

            # Min prob override: if different from default
            if best["min_prob"] != default_min_probs.get(market, 0.40):
                mp_ov[market] = best["min_prob"]

            pnl = best["total_pnl"]
            total_pnl += pnl
            print(f"  {league:<18} {market:<10} {best['strategy']:<12} "
                  f"{best['edge_threshold']:>5.0f}% {best['min_prob']:>5.2f} "
                  f"{best['n_bets']:>5} {pnl:>+7.1f}u {best['roi']:>+6.1%}")

        if edge_ov:
            edge_overrides[league] = edge_ov
        if mp_ov:
            min_prob_overrides[league] = mp_ov

        print()

    print(f"  {'TOTAL':>78} {total_pnl:>+7.1f}u")

    # ===================================================================
    # Output ready-to-paste Python dicts
    # ===================================================================
    print(f"\n\n{'='*80}")
    print(f"  READY-TO-PASTE CONFIG DICTS")
    print(f"{'='*80}")

    print("\nLEAGUE_MARKET_STRATEGY = {")
    for league in args.leagues:
        print(f'    "{league}": {{')
        for market in markets:
            strat = strategy_map.get(league, {}).get(market, "baseline")
            result = all_results.get(league, {}).get(market)
            comment = ""
            if result and result["best"]:
                b = result["best"]
                comment = f"  # {b['total_pnl']:+.1f}u, {b['roi']:+.1%}, {b['n_bets']} bets"
            print(f'        "{market}": "{strat}",{comment}')
        print(f'    }},')
    print("}")

    print("\nLEAGUE_EDGE_OVERRIDES = {")
    for league, overrides in edge_overrides.items():
        print(f'    "{league}": {{')
        for market, val in overrides.items():
            print(f'        "{market}": {val},')
        print(f'    }},')
    print("}")

    print("\nLEAGUE_MIN_PROB_OVERRIDES = {")
    for league, overrides in min_prob_overrides.items():
        print(f'    "{league}": {{')
        for market, val in overrides.items():
            print(f'        "{market}": {val},')
        print(f'    }},')
    print("}")

    # Save results to JSON for later analysis
    output_path = PROJECT_ROOT / "data" / "results" / "optimization_results.json"
    serializable = {}
    for league, markets in all_results.items():
        serializable[league] = {}
        for market, data in markets.items():
            serializable[league][market] = data

    with open(output_path, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"\n  Results saved to {output_path}")


if __name__ == "__main__":
    main()

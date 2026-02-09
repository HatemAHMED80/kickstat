#!/usr/bin/env python3
"""Multi-market, multi-league backtest.

Tests the hypothesis: prop markets (corners, O/U goals) in secondary
leagues are less efficiently priced than 1X2 in top leagues.

Markets tested:
  - 1X2 match result (baseline)
  - Over/Under 2.5 goals
  - Corner 1X2 (home wins/draw/away wins corners)
  - Corner Over/Under

Leagues: top 5 + 14 secondary leagues from football-data.co.uk.

Usage:
    python scripts/backtest_multi_market.py
    python scripts/backtest_multi_market.py --leagues ligue_2 super_lig championship
    python scripts/backtest_multi_market.py --markets corner_1x2 corner_ou
    python scripts/backtest_multi_market.py --min-edge 3
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

from src.data.football_data_uk import (
    LEAGUE_CODES,
    load_historical_data,
    build_multi_market_odds,
)
from src.models.dixon_coles import DixonColesModel, MatchResult
from src.models.elo import EloRating, EloMatch
from src.models.ensemble import EnsemblePredictor
from src.models.prop_models import (
    CornerModel,
    OverUnderGoalsModel,
    remove_margin_2way,
    remove_margin_3way,
)


def run_league_backtest(
    league: str,
    matches: list[dict],
    odds_data: dict,
    min_training: int = 80,
    min_edge: float = 5.0,
    markets: list[str] | None = None,
    refit_interval: int = 30,
) -> dict:
    """Run walk-forward backtest on a single league with all markets.

    Returns detailed results per market.
    """
    if markets is None:
        markets = ["1x2", "ou25", "corner_1x2", "corner_ou"]

    matches = sorted(matches, key=lambda m: m["kickoff"])
    n = len(matches)
    if n < min_training + 30:
        logger.warning(f"{league}: only {n} matches, need {min_training + 30}. Skipping.")
        return {"league": league, "skipped": True, "reason": "insufficient data"}

    logger.info(f"=== {league} ({n} matches) ===")

    # Models
    elo = EloRating()
    corner_model = CornerModel(window=10)
    ou_model = OverUnderGoalsModel(window=10)
    dc = None

    # Build initial state
    for m in matches[:min_training]:
        elo.update(EloMatch(
            home_team=m["home_team"], away_team=m["away_team"],
            home_goals=m["home_score"], away_goals=m["away_score"],
        ))
        corner_model.update(m)
        ou_model.update(m)

    all_bets: list[dict] = []
    matches_processed = 0
    start_time = time.time()

    for i in range(min_training, n):
        test = matches[i]

        # Update with previous match
        if i > min_training:
            prev = matches[i - 1]
            elo.update(EloMatch(
                home_team=prev["home_team"], away_team=prev["away_team"],
                home_goals=prev["home_score"], away_goals=prev["away_score"],
            ))
            corner_model.update(prev)
            ou_model.update(prev)

        # Refit DC periodically
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

        # Get predictions
        dc_pred = dc.predict(test["home_team"], test["away_team"])
        elo_probs = elo.predict_1x2(test["home_team"], test["away_team"])
        corner_pred = corner_model.predict(test["home_team"], test["away_team"])
        ou_pred = ou_model.predict(
            test["home_team"], test["away_team"],
            dc_lambda_h=dc_pred.lambda_home,
            dc_lambda_a=dc_pred.lambda_away,
        )

        # Actual outcomes
        hs, aws = test["home_score"], test["away_score"]
        total_goals = hs + aws
        hc, ac = test.get("hc", 0), test.get("ac", 0)
        total_corners = hc + ac

        # Match key for odds lookup
        date_str = str(test["kickoff"])[:10]
        match_key = f"{test['home_team']}_vs_{test['away_team']}_{date_str}"
        odds_entry = odds_data.get(match_key, {})
        matches_processed += 1

        # === 1X2 Market ===
        if "1x2" in markets and "1x2" in odds_entry:
            odds = odds_entry["1x2"]
            fair_h, fair_d, fair_a = remove_margin_3way(
                odds["pin_home"], odds["pin_draw"], odds["pin_away"]
            )

            # Ensemble: DC 0.65 + ELO 0.35
            w_dc, w_elo = 0.65, 0.35
            ens_h = w_dc * dc_pred.home_win + w_elo * elo_probs["home"]
            ens_d = w_dc * dc_pred.draw + w_elo * elo_probs["draw"]
            ens_a = w_dc * dc_pred.away_win + w_elo * elo_probs["away"]
            total = ens_h + ens_d + ens_a
            ens_h /= total; ens_d /= total; ens_a /= total

            outcome_1x2 = 0 if hs > aws else (1 if hs == aws else 2)
            for name, model_p, fair_p, best_o, win_idx in [
                ("home", ens_h, fair_h, odds["best_home"], 0),
                ("draw", ens_d, fair_d, odds["best_draw"], 1),
                ("away", ens_a, fair_a, odds["best_away"], 2),
            ]:
                if fair_p <= 0 or best_o <= 1.0:
                    continue
                edge = ((model_p - fair_p) / fair_p) * 100
                if edge >= min_edge:
                    won = outcome_1x2 == win_idx
                    all_bets.append({
                        "market_type": "1x2",
                        "market": name,
                        "date": date_str,
                        "home": test["home_team"],
                        "away": test["away_team"],
                        "model_prob": round(model_p, 4),
                        "fair_prob": round(fair_p, 4),
                        "edge_pct": round(edge, 1),
                        "best_odds": best_o,
                        "won": won,
                        "pnl": round((best_o - 1.0) if won else -1.0, 2),
                    })

        # === Over/Under 2.5 Goals ===
        if "ou25" in markets and "ou25" in odds_entry:
            odds = odds_entry["ou25"]
            fair_over, fair_under = remove_margin_2way(
                odds["pin_over"], odds["pin_under"]
            )

            model_over = ou_pred["over_25"]
            model_under = ou_pred["under_25"]

            actual_over = total_goals > 2
            for name, model_p, fair_p, best_o, won in [
                ("over_25", model_over, fair_over, odds["best_over"], actual_over),
                ("under_25", model_under, fair_under, odds["best_under"], not actual_over),
            ]:
                if fair_p <= 0 or best_o <= 1.0:
                    continue
                edge = ((model_p - fair_p) / fair_p) * 100
                if edge >= min_edge:
                    all_bets.append({
                        "market_type": "ou25",
                        "market": name,
                        "date": date_str,
                        "home": test["home_team"],
                        "away": test["away_team"],
                        "model_prob": round(model_p, 4),
                        "fair_prob": round(fair_p, 4),
                        "edge_pct": round(edge, 1),
                        "best_odds": best_o,
                        "won": won,
                        "pnl": round((best_o - 1.0) if won else -1.0, 2),
                    })

        # === Corner 1X2 ===
        if "corner_1x2" in markets and "corner_1x2" in odds_entry and hc + ac > 0:
            odds = odds_entry["corner_1x2"]
            fair_h, fair_d, fair_a = remove_margin_3way(
                odds["pin_home"], odds["pin_draw"], odds["pin_away"]
            )

            # Corner outcome: 0=home more, 1=equal, 2=away more
            if hc > ac:
                corner_outcome = 0
            elif hc == ac:
                corner_outcome = 1
            else:
                corner_outcome = 2

            for name, model_p, fair_p, best_o, win_idx in [
                ("corner_home", corner_pred["home_more_prob"], fair_h, odds["best_home"], 0),
                ("corner_draw", corner_pred["draw_prob"], fair_d, odds["best_draw"], 1),
                ("corner_away", corner_pred["away_more_prob"], fair_a, odds["best_away"], 2),
            ]:
                if fair_p <= 0 or best_o <= 1.0:
                    continue
                edge = ((model_p - fair_p) / fair_p) * 100
                if edge >= min_edge:
                    won = corner_outcome == win_idx
                    all_bets.append({
                        "market_type": "corner_1x2",
                        "market": name,
                        "date": date_str,
                        "home": test["home_team"],
                        "away": test["away_team"],
                        "model_prob": round(model_p, 4),
                        "fair_prob": round(fair_p, 4),
                        "edge_pct": round(edge, 1),
                        "best_odds": best_o,
                        "won": won,
                        "pnl": round((best_o - 1.0) if won else -1.0, 2),
                        "actual_hc": hc,
                        "actual_ac": ac,
                    })

        # === Corner Over/Under ===
        if "corner_ou" in markets and "corner_ou" in odds_entry and hc + ac > 0:
            odds = odds_entry["corner_ou"]
            fair_over, fair_under = remove_margin_2way(
                odds["pin_over"], odds["pin_under"]
            )

            # Use 9.5 as typical total corners line
            model_over_95 = corner_pred["over_probs"].get(9.5, 0.5)
            model_under_95 = 1.0 - model_over_95

            actual_over = total_corners > 9  # O/U at ~9.5

            for name, model_p, fair_p, best_o, won in [
                ("corner_over", model_over_95, fair_over, odds["best_over"], actual_over),
                ("corner_under", model_under_95, fair_under, odds["best_under"], not actual_over),
            ]:
                if fair_p <= 0 or best_o <= 1.0:
                    continue
                edge = ((model_p - fair_p) / fair_p) * 100
                if edge >= min_edge:
                    all_bets.append({
                        "market_type": "corner_ou",
                        "market": name,
                        "date": date_str,
                        "home": test["home_team"],
                        "away": test["away_team"],
                        "model_prob": round(model_p, 4),
                        "fair_prob": round(fair_p, 4),
                        "edge_pct": round(edge, 1),
                        "best_odds": best_o,
                        "won": won,
                        "pnl": round((best_o - 1.0) if won else -1.0, 2),
                        "actual_total_corners": total_corners,
                    })

    elapsed = time.time() - start_time

    # Aggregate results
    result = {
        "league": league,
        "matches_total": n,
        "matches_tested": matches_processed,
        "elapsed_seconds": round(elapsed, 1),
        "by_market": {},
        "all_bets": all_bets,
    }

    for mkt in markets:
        mkt_bets = [b for b in all_bets if b["market_type"] == mkt]
        if not mkt_bets:
            result["by_market"][mkt] = {"bets": 0}
            continue

        n_bets = len(mkt_bets)
        wins = sum(1 for b in mkt_bets if b["won"])
        total_pnl = sum(b["pnl"] for b in mkt_bets)
        edges = [b["edge_pct"] for b in mkt_bets]

        result["by_market"][mkt] = {
            "bets": n_bets,
            "wins": wins,
            "win_rate": round(wins / n_bets, 4),
            "total_pnl": round(total_pnl, 2),
            "roi": round(total_pnl / n_bets, 4),
            "avg_edge": round(np.mean(edges), 1),
            "median_edge": round(np.median(edges), 1),
        }

    return result


def print_league_report(result: dict) -> None:
    """Print results for one league."""
    if result.get("skipped"):
        print(f"  {result['league']:>20}: SKIPPED ({result.get('reason', '')})")
        return

    league = result["league"]
    print(f"\n  {'=' * 55}")
    print(f"  {league.upper()} ({result['matches_tested']} matches, {result['elapsed_seconds']:.0f}s)")
    print(f"  {'=' * 55}")

    for mkt, stats in result["by_market"].items():
        if stats["bets"] == 0:
            print(f"    {mkt:>12}: no edges found")
            continue

        roi = stats["roi"]
        pnl = stats["total_pnl"]
        arrow = "+" if pnl >= 0 else ""
        roi_color = "**" if roi > 0 else ""

        print(f"    {mkt:>12}: {stats['bets']:4d} bets | "
              f"win {stats['win_rate']:.1%} | "
              f"PnL {arrow}{pnl:.1f}u | "
              f"ROI {roi_color}{roi:.1%}{roi_color} | "
              f"edge {stats['avg_edge']:.1f}%")


def print_summary(all_results: list[dict], markets: list[str]) -> None:
    """Print cross-league summary per market."""
    print("\n" + "=" * 70)
    print("  CROSS-LEAGUE SUMMARY")
    print("=" * 70)

    for mkt in markets:
        print(f"\n  --- {mkt.upper()} ---")
        mkt_total_bets = 0
        mkt_total_wins = 0
        mkt_total_pnl = 0.0
        league_results = []

        for r in all_results:
            if r.get("skipped"):
                continue
            stats = r["by_market"].get(mkt, {"bets": 0})
            if stats["bets"] > 0:
                league_results.append((r["league"], stats))
                mkt_total_bets += stats["bets"]
                mkt_total_wins += stats["wins"]
                mkt_total_pnl += stats["total_pnl"]

        if not mkt_total_bets:
            print("    No bets across any league.")
            continue

        # Sort leagues by ROI
        league_results.sort(key=lambda x: x[1]["roi"], reverse=True)

        for league, stats in league_results:
            roi = stats["roi"]
            pnl = stats["total_pnl"]
            marker = " <<<" if roi > 0 else ""
            print(f"    {league:>22}: {stats['bets']:4d} bets, "
                  f"ROI {roi:+.1%}, PnL {pnl:+.1f}u{marker}")

        overall_roi = mkt_total_pnl / mkt_total_bets
        print(f"    {'TOTAL':>22}: {mkt_total_bets:4d} bets, "
              f"ROI {overall_roi:+.1%}, PnL {mkt_total_pnl:+.1f}u")

    # Overall across all markets
    print(f"\n  {'=' * 55}")
    grand_bets = 0
    grand_pnl = 0.0
    for r in all_results:
        if r.get("skipped"):
            continue
        for mkt, stats in r["by_market"].items():
            grand_bets += stats.get("bets", 0)
            grand_pnl += stats.get("total_pnl", 0)

    if grand_bets > 0:
        print(f"  GRAND TOTAL: {grand_bets} bets, "
              f"ROI {grand_pnl / grand_bets:+.1%}, PnL {grand_pnl:+.1f}u")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Multi-market multi-league backtest")
    parser.add_argument(
        "--leagues", nargs="+",
        help="Leagues to test (default: all secondary + ligue_1 as baseline)"
    )
    parser.add_argument(
        "--markets", nargs="+",
        default=["1x2", "ou25", "corner_1x2", "corner_ou"],
        help="Markets to test"
    )
    parser.add_argument(
        "--seasons", nargs="+", type=int, default=[2021, 2022, 2023, 2024],
        help="Seasons (default: 2021-2024)"
    )
    parser.add_argument("--min-edge", type=float, default=5.0, help="Min edge %% (default: 5)")
    parser.add_argument("--min-training", type=int, default=80, help="Min training matches")
    parser.add_argument("--refit-interval", type=int, default=30, help="DC refit interval")
    args = parser.parse_args()

    # Default leagues: 1 top league as baseline + all secondary leagues
    if args.leagues is None:
        args.leagues = [
            "ligue_1",       # baseline top-5
            "ligue_2",       # secondary
            "championship",
            "bundesliga_2",
            "serie_b",
            "la_liga_2",
            "super_lig",
            "super_league_greece",
            "eredivisie",
            "jupiler_league",
            "primeira_liga",
            "scottish_prem",
        ]

    cache_dir = PROJECT_ROOT / "data" / "historical"
    all_results = []

    for league in args.leagues:
        logger.info(f"\n{'='*40}")
        logger.info(f"Loading {league}...")
        try:
            matches = load_historical_data(league, args.seasons, cache_dir)
        except Exception as e:
            logger.warning(f"Failed to load {league}: {e}")
            all_results.append({"league": league, "skipped": True, "reason": str(e)})
            continue

        if len(matches) < args.min_training + 30:
            all_results.append({
                "league": league, "skipped": True,
                "reason": f"only {len(matches)} matches",
            })
            continue

        # Build multi-market odds lookup
        odds_data = build_multi_market_odds(matches)

        # Check corner data availability
        has_corners = sum(1 for m in matches if m.get("hc", 0) > 0)
        logger.info(f"Corner data: {has_corners}/{len(matches)} matches")

        result = run_league_backtest(
            league, matches, odds_data,
            min_training=args.min_training,
            min_edge=args.min_edge,
            markets=args.markets,
            refit_interval=args.refit_interval,
        )
        all_results.append(result)
        print_league_report(result)

    # Cross-league summary
    print_summary(all_results, args.markets)

    # Save results
    results_dir = PROJECT_ROOT / "data" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Summary without individual bets
    summary = []
    for r in all_results:
        s = {k: v for k, v in r.items() if k != "all_bets"}
        summary.append(s)

    summary_path = results_dir / "backtest_multi_market_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n  Summary saved to {summary_path}")

    # Save all bets for analysis
    all_bets = []
    for r in all_results:
        if not r.get("skipped"):
            for b in r.get("all_bets", []):
                b["league"] = r["league"]
                all_bets.append(b)

    if all_bets:
        bets_path = results_dir / "backtest_multi_market_bets.json"
        with open(bets_path, "w") as f:
            json.dump(all_bets, f, indent=2, default=str)
        print(f"  All bets saved to {bets_path}")


if __name__ == "__main__":
    main()

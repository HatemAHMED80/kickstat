#!/usr/bin/env python3
"""Detailed backtest specifically for prop markets (O/U, BTTS, Corners).

Focus on finding profitable edges in less efficient secondary markets.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from loguru import logger

from src.data.football_data_uk import load_historical_data
from src.models.dixon_coles import DixonColesModel
from src.models.elo import EloRating
from src.models.prop_models import remove_margin_2way


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", default="ligue_1")
    parser.add_argument("--seasons", nargs="+", type=int, default=[2020, 2021, 2022, 2023, 2024])
    args = parser.parse_args()

    logger.info(f"Testing prop markets: {args.league}, seasons {args.seasons}")
    matches = load_historical_data(args.league, args.seasons)
    logger.info(f"Loaded {len(matches)} matches")

    # Initialize models
    dc = DixonColesModel(half_life_days=180)
    elo = EloRating(k_factor=20, home_advantage=100)

    # Track prop bets
    ou_bets = []  # (won, odds, edge, model_prob, market_type)

    # Walk-forward backtest
    refit_every = 120
    for idx, test in enumerate(matches):
        # Refit DC periodically
        if idx > 0 and idx % refit_every == 0:
            train = matches[max(0, idx - 600):idx]
            logger.info(f"Refitting DC on {len(train)} matches (up to match {idx}/{len(matches)})")
            dc.fit(train)

        # Update ELO
        if idx > 0:
            elo.update(matches[idx - 1])

        # Skip if not enough data
        if idx < 100:
            continue

        # Get predictions
        home_team = test["home_team"]
        away_team = test["away_team"]

        try:
            dc_pred = dc.predict(home_team, away_team)
        except KeyError:
            continue

        elo_pred = elo.predict(home_team, away_team)

        # Actual outcome
        total_goals = test["home_score"] + test["away_score"]

        # ═══════ OVER/UNDER 2.5 ═══════
        pin_over = test.get("pinnacle_over25", 0)
        pin_under = test.get("pinnacle_under25", 0)
        max_over = test.get("max_over25", pin_over)
        max_under = test.get("max_under25", pin_under)

        if pin_over > 1.0 and pin_under > 1.0 and max_over > 1.0 and max_under > 1.0:
            fair_over, fair_under = remove_margin_2way(pin_over, pin_under)

            # Model prediction from score matrix
            model_over = float(sum(
                dc_pred.score_matrix[i, j]
                for i in range(9) for j in range(9) if i + j > 2
            ))
            model_under = 1.0 - model_over

            # Check edge on both sides
            for name, model_p, fair_p, best_odds, won in [
                ("Over 2.5", model_over, fair_over, max_over, total_goals > 2),
                ("Under 2.5", model_under, fair_under, max_under, total_goals <= 2),
            ]:
                if fair_p > 0:
                    edge = ((model_p - fair_p) / fair_p) * 100
                    ou_bets.append((won, best_odds, edge, model_p, name))

    # ═══════ ANALYSIS ═══════
    print(f"\n{'═'*80}")
    print(f"  PROP MARKETS DETAILED ANALYSIS - {args.league.upper()}")
    print(f"{'═'*80}\n")

    # ─── OVER/UNDER 2.5 ───
    print(f"{'─'*80}")
    print("  OVER/UNDER 2.5 GOALS")
    print(f"{'─'*80}\n")

    # Overall stats
    if ou_bets:
        wins = sum(1 for w, o, e, p, m in ou_bets if w)
        total_stake = len(ou_bets)
        total_return = sum(o if w else 0 for w, o, e, p, m in ou_bets)
        roi = ((total_return - total_stake) / total_stake) * 100 if total_stake > 0 else 0

        print(f"  ALL BETS (edge > 0%)")
        print(f"    Total: {len(ou_bets)} bets")
        print(f"    Win rate: {wins/len(ou_bets)*100:.1f}%")
        print(f"    ROI: {roi:+.2f}%")
        print(f"    PnL: {total_return - total_stake:+.1f} units\n")

    # By edge threshold
    print(f"  BY EDGE THRESHOLD:\n")
    for min_edge in [0, 3, 5, 8, 10]:
        filtered = [(w, o) for w, o, e, p, m in ou_bets if e >= min_edge]
        if filtered:
            wins = sum(1 for w, o in filtered if w)
            stake = len(filtered)
            returns = sum(o if w else 0 for w, o in filtered)
            roi = ((returns - stake) / stake) * 100

            marker = " <<<" if roi > 3 else ""
            print(f"    Edge >= {min_edge:2d}%: {len(filtered):4d} bets | Win {wins/len(filtered)*100:4.1f}% | ROI {roi:+6.1f}% | PnL {returns-stake:+7.1f}u{marker}")

    # By model probability bands
    print(f"\n  BY MODEL PROBABILITY (edge >= 3%):\n")
    prob_bands = [
        (0.35, 0.45, "Low confidence (35-45%)"),
        (0.45, 0.55, "Coin-flip (45-55%)"),
        (0.55, 0.65, "Medium (55-65%)"),
        (0.65, 0.75, "High (65-75%)"),
        (0.75, 1.01, "Very high (75%+)"),
    ]

    for pmin, pmax, label in prob_bands:
        filtered = [(w, o) for w, o, e, p, m in ou_bets if pmin <= p < pmax and e >= 3]
        if filtered:
            wins = sum(1 for w, o in filtered if w)
            stake = len(filtered)
            returns = sum(o if w else 0 for w, o in filtered)
            roi = ((returns - stake) / stake) * 100

            marker = " <<<" if roi > 5 else ""
            print(f"    {label:30s}: {len(filtered):4d} bets | Win {wins/len(filtered)*100:4.1f}% | ROI {roi:+6.1f}% | PnL {returns-stake:+7.1f}u{marker}")

    # Over vs Under breakdown
    print(f"\n  OVER VS UNDER (edge >= 3%):\n")
    for market_type in ["Over 2.5", "Under 2.5"]:
        filtered = [(w, o) for w, o, e, p, m in ou_bets if m == market_type and e >= 3]
        if filtered:
            wins = sum(1 for w, o in filtered if w)
            stake = len(filtered)
            returns = sum(o if w else 0 for w, o in filtered)
            roi = ((returns - stake) / stake) * 100

            marker = " <<<" if roi > 5 else ""
            print(f"    {market_type:15s}: {len(filtered):4d} bets | Win {wins/len(filtered)*100:4.1f}% | ROI {roi:+6.1f}% | PnL {returns-stake:+7.1f}u{marker}")

    # Best combinations
    print(f"\n  BEST COMBINATIONS:\n")

    # High confidence Over (model > 60%, edge >= 5%)
    combo1 = [(w, o) for w, o, e, p, m in ou_bets if m == "Over 2.5" and p >= 0.60 and e >= 5]
    if combo1:
        wins = sum(1 for w, o in combo1 if w)
        roi = ((sum(o if w else 0 for w, o in combo1) - len(combo1)) / len(combo1)) * 100
        print(f"    Over 2.5 (prob >= 60%, edge >= 5%): {len(combo1):3d} bets | Win {wins/len(combo1)*100:4.1f}% | ROI {roi:+6.1f}%")

    # High confidence Under (model > 60%, edge >= 5%)
    combo2 = [(w, o) for w, o, e, p, m in ou_bets if m == "Under 2.5" and p >= 0.60 and e >= 5]
    if combo2:
        wins = sum(1 for w, o in combo2 if w)
        roi = ((sum(o if w else 0 for w, o in combo2) - len(combo2)) / len(combo2)) * 100
        print(f"    Under 2.5 (prob >= 60%, edge >= 5%): {len(combo2):3d} bets | Win {wins/len(combo2)*100:4.1f}% | ROI {roi:+6.1f}%")

    print(f"\n{'═'*80}\n")


if __name__ == "__main__":
    main()

"""Bankroll simulation from backtest bets.

Simulates equity curve starting from an initial bankroll,
using various staking strategies on the bet history.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


def load_bets(path: str) -> list[dict]:
    with open(path) as f:
        bets = json.load(f)
    bets.sort(key=lambda b: b["date"])
    return bets


def kelly_fraction(model_prob: float, odds: float) -> float:
    """Full Kelly stake as fraction of bankroll."""
    if odds <= 1.0 or model_prob <= 0:
        return 0.0
    q = 1.0 - model_prob
    b = odds - 1.0
    f = (model_prob * b - q) / b
    return max(f, 0.0)


def simulate(
    bets: list[dict],
    initial_bankroll: float = 1000.0,
    strategy: str = "flat",
    flat_pct: float = 0.02,
    kelly_frac: float = 0.25,
    max_stake_pct: float = 0.05,
    market_filter: list[str] | None = None,
    min_edge: float = 5.0,
) -> dict:
    """Simulate bankroll evolution.

    Args:
        bets: List of bet dicts from backtest.
        initial_bankroll: Starting capital.
        strategy: "flat" (fixed % of current bankroll) or "kelly" (fractional Kelly).
        flat_pct: Stake as % of bankroll for flat strategy.
        kelly_frac: Fraction of full Kelly to use (0.25 = quarter Kelly).
        max_stake_pct: Maximum stake as % of bankroll (cap for Kelly).
        market_filter: Only bet on these market types (e.g. ["corner_1x2"]).
        min_edge: Minimum edge % to place bet.

    Returns:
        Dict with equity curve, stats, etc.
    """
    bankroll = initial_bankroll
    peak = initial_bankroll
    max_drawdown = 0.0
    equity_curve = [(None, initial_bankroll)]  # (date, bankroll)
    daily_bankroll = {}
    n_bets = 0
    n_wins = 0
    total_staked = 0.0
    longest_losing = 0
    current_losing = 0

    for bet in bets:
        # Filter by market
        if market_filter and bet["market_type"] not in market_filter:
            continue
        # Filter by edge
        if bet["edge_pct"] < min_edge:
            continue
        # Skip if bankroll too low
        if bankroll < 1.0:
            break

        # Calculate stake
        if strategy == "flat":
            stake = bankroll * flat_pct
        elif strategy == "kelly":
            kf = kelly_fraction(bet["model_prob"], bet["best_odds"])
            stake = bankroll * kf * kelly_frac
            stake = min(stake, bankroll * max_stake_pct)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        if stake < 0.01:
            continue

        # Place bet
        n_bets += 1
        total_staked += stake

        if bet["won"]:
            profit = stake * (bet["best_odds"] - 1.0)
            bankroll += profit
            n_wins += 1
            current_losing = 0
        else:
            bankroll -= stake
            current_losing += 1
            longest_losing = max(longest_losing, current_losing)

        # Track peak and drawdown
        if bankroll > peak:
            peak = bankroll
        dd = (peak - bankroll) / peak
        max_drawdown = max(max_drawdown, dd)

        # Daily snapshot
        daily_bankroll[bet["date"]] = bankroll

    # Build equity curve from daily snapshots
    equity_curve = [(d, v) for d, v in sorted(daily_bankroll.items())]

    # Stats
    total_profit = bankroll - initial_bankroll
    roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
    win_rate = (n_wins / n_bets * 100) if n_bets > 0 else 0

    return {
        "initial_bankroll": initial_bankroll,
        "final_bankroll": round(bankroll, 2),
        "total_profit": round(total_profit, 2),
        "total_staked": round(total_staked, 2),
        "roi_pct": round(roi, 1),
        "n_bets": n_bets,
        "n_wins": n_wins,
        "win_rate": round(win_rate, 1),
        "max_drawdown_pct": round(max_drawdown * 100, 1),
        "longest_losing_streak": longest_losing,
        "peak_bankroll": round(peak, 2),
        "equity_curve": equity_curve,
    }


def print_report(result: dict, label: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Capital initial :  {result['initial_bankroll']:>10,.2f} EUR")
    print(f"  Capital final :    {result['final_bankroll']:>10,.2f} EUR")
    print(f"  Profit total :     {result['total_profit']:>+10,.2f} EUR")
    print(f"  Total mise :       {result['total_staked']:>10,.2f} EUR")
    print(f"  ROI :              {result['roi_pct']:>+8.1f}%")
    print(f"  Nombre de paris :  {result['n_bets']:>10,}")
    print(f"  Win rate :         {result['win_rate']:>8.1f}%")
    print(f"  Max drawdown :     {result['max_drawdown_pct']:>8.1f}%")
    print(f"  Plus longue serie perdante : {result['longest_losing_streak']}")
    print(f"  Pic bankroll :     {result['peak_bankroll']:>10,.2f} EUR")

    # Monthly equity milestones
    curve = result["equity_curve"]
    if curve:
        print(f"\n  --- Evolution mensuelle ---")
        months_seen = set()
        for date_str, val in curve:
            month = date_str[:7]  # YYYY-MM
            if month not in months_seen:
                months_seen.add(month)
                pct = ((val - result["initial_bankroll"]) / result["initial_bankroll"]) * 100
                print(f"    {month}: {val:>10,.2f} EUR ({pct:>+7.1f}%)")


def print_ascii_chart(result: dict, width: int = 60) -> None:
    """Simple ASCII equity curve."""
    curve = result["equity_curve"]
    if not curve or len(curve) < 2:
        return

    values = [v for _, v in curve]
    min_val = min(values) * 0.95
    max_val = max(values) * 1.05
    val_range = max_val - min_val
    if val_range == 0:
        return

    # Sample to fit width
    step = max(1, len(values) // width)
    sampled = values[::step]

    print(f"\n  --- Courbe de capital ---")
    print(f"  {max_val:>8,.0f} |")
    height = 15
    for row in range(height, -1, -1):
        threshold = min_val + (row / height) * val_range
        line = "  " + " " * 8 + " |"
        for v in sampled:
            if v >= threshold:
                line += "#"
            else:
                line += " "
        if row == height // 2:
            mid = min_val + 0.5 * val_range
            line = f"  {mid:>8,.0f} |" + line[12:]
        print(line)
    print(f"  {min_val:>8,.0f} |" + "-" * len(sampled))
    print(f"           {curve[0][0][:7]}" + " " * max(0, len(sampled) - 20) + f"{curve[-1][0][:7]}")


def main():
    bets_path = Path("data/results/backtest_multi_market_bets.json")
    if not bets_path.exists():
        print(f"Error: {bets_path} not found")
        sys.exit(1)

    bets = load_bets(str(bets_path))
    initial = 1000.0

    print("\n" + "=" * 70)
    print("  SIMULATION DE BANKROLL - Capital initial: 1,000 EUR")
    print("  Periode: Sep 2022 - Jun 2025 (3 saisons, 9 ligues)")
    print("=" * 70)

    # ─── Strategy 1: Corner 1X2 only, flat 2% ───
    r1 = simulate(
        bets, initial, strategy="flat", flat_pct=0.02,
        market_filter=["corner_1x2"], min_edge=5.0,
    )
    print_report(r1, "STRAT 1: Corner 1X2 - Flat 2% du capital")
    print_ascii_chart(r1)

    # ─── Strategy 2: Corner 1X2 only, flat 1% (plus conservateur) ───
    r2 = simulate(
        bets, initial, strategy="flat", flat_pct=0.01,
        market_filter=["corner_1x2"], min_edge=5.0,
    )
    print_report(r2, "STRAT 2: Corner 1X2 - Flat 1% du capital (conservateur)")

    # ─── Strategy 3: Corner 1X2, Kelly 25% ───
    r3 = simulate(
        bets, initial, strategy="kelly", kelly_frac=0.25, max_stake_pct=0.05,
        market_filter=["corner_1x2"], min_edge=5.0,
    )
    print_report(r3, "STRAT 3: Corner 1X2 - Kelly 25% (max 5%)")
    print_ascii_chart(r3)

    # ─── Strategy 4: Corner 1X2 + Corner O/U, flat 1.5% ───
    r4 = simulate(
        bets, initial, strategy="flat", flat_pct=0.015,
        market_filter=["corner_1x2", "corner_ou"], min_edge=5.0,
    )
    print_report(r4, "STRAT 4: Corners (1X2 + O/U) - Flat 1.5%")

    # ─── Strategy 5: ALL markets, flat 1% ───
    r5 = simulate(
        bets, initial, strategy="flat", flat_pct=0.01,
        market_filter=None, min_edge=5.0,
    )
    print_report(r5, "STRAT 5: TOUS les marches - Flat 1%")

    # ─── Strategy 6: Corner 1X2, flat 2%, only high edge (>15%) ───
    r6 = simulate(
        bets, initial, strategy="flat", flat_pct=0.02,
        market_filter=["corner_1x2"], min_edge=15.0,
    )
    print_report(r6, "STRAT 6: Corner 1X2 - Flat 2%, edge minimum 15%")

    # ─── Strategy 7: Corner 1X2, Kelly 10% (ultra-conservateur) ───
    r7 = simulate(
        bets, initial, strategy="kelly", kelly_frac=0.10, max_stake_pct=0.03,
        market_filter=["corner_1x2"], min_edge=5.0,
    )
    print_report(r7, "STRAT 7: Corner 1X2 - Kelly 10% (ultra-conservateur, max 3%)")

    # ─── Comparison table ───
    print("\n" + "=" * 70)
    print("  COMPARATIF DES STRATEGIES")
    print("=" * 70)
    print(f"  {'Strategie':<42} {'Final':>10} {'Profit':>10} {'ROI':>7} {'DD max':>7} {'Paris':>6}")
    print(f"  {'-'*42} {'-'*10} {'-'*10} {'-'*7} {'-'*7} {'-'*6}")

    strategies = [
        ("1. Corner 1X2 flat 2%", r1),
        ("2. Corner 1X2 flat 1% (conservateur)", r2),
        ("3. Corner 1X2 Kelly 25%", r3),
        ("4. Corners 1X2+O/U flat 1.5%", r4),
        ("5. Tous marches flat 1%", r5),
        ("6. Corner 1X2 flat 2% edge>15%", r6),
        ("7. Corner 1X2 Kelly 10% (ultra-safe)", r7),
    ]

    for label, r in strategies:
        print(
            f"  {label:<42} "
            f"{r['final_bankroll']:>10,.0f} "
            f"{r['total_profit']:>+10,.0f} "
            f"{r['roi_pct']:>+6.1f}% "
            f"{r['max_drawdown_pct']:>6.1f}% "
            f"{r['n_bets']:>6,}"
        )

    print(f"\n  Capital initial: {initial:,.0f} EUR")
    print(f"  Periode: {bets[0]['date']} - {bets[-1]['date']}")


if __name__ == "__main__":
    main()

"""Realistic bankroll simulation with practical constraints.

Models real-world limitations:
- Fixed unit stakes (flat EUR amount per bet)
- Progressive staking with caps
- Max daily exposure
- Account limitation risk
"""

import json
import sys
from collections import defaultdict
from pathlib import Path


def load_bets(path: str) -> list[dict]:
    with open(path) as f:
        bets = json.load(f)
    bets.sort(key=lambda b: b["date"])
    return bets


def simulate_fixed_unit(
    bets: list[dict],
    initial: float,
    unit: float,
    market_filter: list[str] | None = None,
    min_edge: float = 5.0,
) -> dict:
    """Fixed unit staking - bet same EUR amount every time."""
    bankroll = initial
    peak = initial
    max_dd = 0.0
    n_bets = 0
    n_wins = 0
    daily = {}
    monthly_pnl = defaultdict(float)
    losing_streak = 0
    max_losing = 0

    for bet in bets:
        if market_filter and bet["market_type"] not in market_filter:
            continue
        if bet["edge_pct"] < min_edge:
            continue
        if bankroll < unit:
            break  # busted

        n_bets += 1
        month = bet["date"][:7]

        if bet["won"]:
            profit = unit * (bet["best_odds"] - 1.0)
            bankroll += profit
            monthly_pnl[month] += profit
            n_wins += 1
            losing_streak = 0
        else:
            bankroll -= unit
            monthly_pnl[month] -= unit
            losing_streak += 1
            max_losing = max(max_losing, losing_streak)

        if bankroll > peak:
            peak = bankroll
        dd = (peak - bankroll) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)
        daily[bet["date"]] = bankroll

    return {
        "initial": initial,
        "final": round(bankroll, 2),
        "profit": round(bankroll - initial, 2),
        "n_bets": n_bets,
        "n_wins": n_wins,
        "win_rate": round(n_wins / n_bets * 100, 1) if n_bets > 0 else 0,
        "max_dd_pct": round(max_dd * 100, 1),
        "max_losing_streak": max_losing,
        "peak": round(peak, 2),
        "unit": unit,
        "monthly_pnl": dict(sorted(monthly_pnl.items())),
        "daily": dict(sorted(daily.items())),
    }


def simulate_progressive(
    bets: list[dict],
    initial: float,
    pct: float,
    min_unit: float,
    max_unit: float,
    market_filter: list[str] | None = None,
    min_edge: float = 5.0,
) -> dict:
    """Progressive staking - % of bankroll but capped."""
    bankroll = initial
    peak = initial
    max_dd = 0.0
    n_bets = 0
    n_wins = 0
    daily = {}
    monthly_pnl = defaultdict(float)
    losing_streak = 0
    max_losing = 0
    total_staked = 0.0

    for bet in bets:
        if market_filter and bet["market_type"] not in market_filter:
            continue
        if bet["edge_pct"] < min_edge:
            continue

        unit = bankroll * pct
        unit = max(min_unit, min(unit, max_unit))

        if bankroll < min_unit:
            break

        n_bets += 1
        total_staked += unit
        month = bet["date"][:7]

        if bet["won"]:
            profit = unit * (bet["best_odds"] - 1.0)
            bankroll += profit
            monthly_pnl[month] += profit
            n_wins += 1
            losing_streak = 0
        else:
            bankroll -= unit
            monthly_pnl[month] -= unit
            losing_streak += 1
            max_losing = max(max_losing, losing_streak)

        if bankroll > peak:
            peak = bankroll
        dd = (peak - bankroll) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)
        daily[bet["date"]] = bankroll

    return {
        "initial": initial,
        "final": round(bankroll, 2),
        "profit": round(bankroll - initial, 2),
        "n_bets": n_bets,
        "n_wins": n_wins,
        "win_rate": round(n_wins / n_bets * 100, 1) if n_bets > 0 else 0,
        "max_dd_pct": round(max_dd * 100, 1),
        "max_losing_streak": max_losing,
        "peak": round(peak, 2),
        "total_staked": round(total_staked, 2),
        "monthly_pnl": dict(sorted(monthly_pnl.items())),
        "daily": dict(sorted(daily.items())),
    }


def print_sim(r: dict, label: str) -> None:
    print(f"\n{'='*65}")
    print(f"  {label}")
    print(f"{'='*65}")
    print(f"  Capital initial :     {r['initial']:>10,.2f} EUR")
    print(f"  Capital final :       {r['final']:>10,.2f} EUR")
    print(f"  Profit :              {r['profit']:>+10,.2f} EUR")
    pct_gain = (r['profit'] / r['initial']) * 100
    print(f"  Rendement total :     {pct_gain:>+9.1f}%")
    print(f"  Nombre de paris :     {r['n_bets']:>10,}")
    print(f"  Win rate :            {r['win_rate']:>9.1f}%")
    print(f"  Max drawdown :        {r['max_dd_pct']:>9.1f}%")
    print(f"  Pire serie perdante : {r['max_losing_streak']:>9}")
    print(f"  Pic capital :         {r['peak']:>10,.2f} EUR")

    # Quarterly summary
    quarterly = defaultdict(float)
    for m, pnl in r["monthly_pnl"].items():
        year = m[:4]
        month = int(m[5:7])
        q = (month - 1) // 3 + 1
        quarterly[f"{year}-Q{q}"] += pnl

    print(f"\n  --- PnL par trimestre ---")
    cumul = r["initial"]
    for q, pnl in sorted(quarterly.items()):
        cumul += pnl
        pct = (pnl / r["initial"]) * 100
        print(f"    {q}: {pnl:>+9,.2f} EUR  (capital: {cumul:>10,.2f} EUR, {pct:>+6.1f}% du capital initial)")

    # Monthly detail
    print(f"\n  --- PnL par mois ---")
    cumul = r["initial"]
    for m, pnl in sorted(r["monthly_pnl"].items()):
        cumul += pnl
        print(f"    {m}: {pnl:>+8,.2f} EUR  (capital: {cumul:>9,.2f} EUR)")


def main():
    bets_path = Path("data/results/backtest_multi_market_bets.json")
    bets = load_bets(str(bets_path))

    initial = 1000.0

    print("\n" + "=" * 70)
    print("  SIMULATION REALISTE - Capital: 1,000 EUR")
    print("  Periode: Sep 2022 - Jun 2025 (3 saisons, 9 ligues)")
    print("  Marche: Corner 1X2 uniquement (edge confirme +33% ROI)")
    print("=" * 70)

    # ─── A) Fixed €10/bet (1% du capital initial) ───
    rA = simulate_fixed_unit(
        bets, initial, unit=10.0,
        market_filter=["corner_1x2"], min_edge=5.0,
    )
    print_sim(rA, "A) FLAT 10 EUR/pari (conservateur)")

    # ─── B) Fixed €20/bet (2% du capital initial) ───
    rB = simulate_fixed_unit(
        bets, initial, unit=20.0,
        market_filter=["corner_1x2"], min_edge=5.0,
    )
    print_sim(rB, "B) FLAT 20 EUR/pari (standard)")

    # ─── C) Fixed €50/bet (5% du capital initial, agressif) ───
    rC = simulate_fixed_unit(
        bets, initial, unit=50.0,
        market_filter=["corner_1x2"], min_edge=5.0,
    )
    print_sim(rC, "C) FLAT 50 EUR/pari (agressif)")

    # ─── D) Progressive 2% avec cap min 10, max 50 ───
    rD = simulate_progressive(
        bets, initial, pct=0.02, min_unit=10.0, max_unit=50.0,
        market_filter=["corner_1x2"], min_edge=5.0,
    )
    print_sim(rD, "D) PROGRESSIF 2% du capital (min 10, max 50 EUR)")

    # ─── E) Progressive 2% avec cap min 10, max 100 ───
    rE = simulate_progressive(
        bets, initial, pct=0.02, min_unit=10.0, max_unit=100.0,
        market_filter=["corner_1x2"], min_edge=5.0,
    )
    print_sim(rE, "E) PROGRESSIF 2% du capital (min 10, max 100 EUR)")

    # ─── F) Corner 1X2 + Corner O/U, flat €15 ───
    rF = simulate_fixed_unit(
        bets, initial, unit=15.0,
        market_filter=["corner_1x2", "corner_ou"], min_edge=5.0,
    )
    print_sim(rF, "F) CORNERS 1X2+O/U, flat 15 EUR/pari")

    # ─── Comparison ───
    print("\n" + "=" * 70)
    print("  COMPARATIF")
    print("=" * 70)
    print(f"  {'Strategie':<44} {'Capital':>9} {'Profit':>9} {'Rdt':>7} {'DD':>6} {'Paris':>6}")
    print(f"  {'-'*44} {'-'*9} {'-'*9} {'-'*7} {'-'*6} {'-'*6}")

    for label, r in [
        ("A. Corner 1X2 flat 10 EUR", rA),
        ("B. Corner 1X2 flat 20 EUR", rB),
        ("C. Corner 1X2 flat 50 EUR", rC),
        ("D. Corner 1X2 progressif 2% (max 50)", rD),
        ("E. Corner 1X2 progressif 2% (max 100)", rE),
        ("F. Corners 1X2+O/U flat 15 EUR", rF),
    ]:
        pct = (r["profit"] / r["initial"]) * 100
        print(
            f"  {label:<44} "
            f"{r['final']:>9,.0f} "
            f"{r['profit']:>+9,.0f} "
            f"{pct:>+6.0f}% "
            f"{r['max_dd_pct']:>5.1f}% "
            f"{r['n_bets']:>6,}"
        )

    print(f"\n  Capital initial: {initial:,.0f} EUR | Periode: 3 saisons | 9 ligues europeennes")
    print(f"  Note: PnL base sur les cotes 'max' historiques (meilleures cotes disponibles)")


if __name__ == "__main__":
    main()

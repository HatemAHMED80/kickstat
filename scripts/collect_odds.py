#!/usr/bin/env python3
"""Collect and archive odds from The Odds API.

Run this script 2-3 times per week (before match days) to build
a historical odds database. Each run costs 1 API request.

Free tier: 500 requests/month ≈ 16/day ≈ enough for daily collection.

Usage:
    python scripts/collect_odds.py
    python scripts/collect_odds.py --league ligue_1
    python scripts/collect_odds.py --dry-run

The script:
1. Fetches current odds for upcoming matches
2. Extracts best odds across bookmakers + removes margin
3. Appends to data/odds/odds_history.csv (no duplicates)
4. Shows remaining API quota
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.odds_api import OddsAPIClient, extract_best_odds, remove_margin


def collect_odds(league: str = "ligue_1", dry_run: bool = False) -> pd.DataFrame:
    """Fetch current odds and return as DataFrame."""
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        print("ERROR: ODDS_API_KEY not found in .env")
        sys.exit(1)

    client = OddsAPIClient(api_key=api_key)

    try:
        odds_data = client.get_odds(league=league, markets="h2h,totals", regions="eu")
    except Exception as e:
        print(f"ERROR fetching odds: {e}")
        client.close()
        sys.exit(1)

    if not odds_data:
        print("No upcoming matches found.")
        client.close()
        return pd.DataFrame()

    print(f"Fetched odds for {len(odds_data)} matches")
    print(f"API requests remaining: {client.remaining_requests}/500")

    rows = []
    for match in odds_data:
        best = extract_best_odds(match)

        # Skip matches without H2H odds
        if best["home"]["odds"] == 0 or best["draw"]["odds"] == 0 or best["away"]["odds"] == 0:
            continue

        fair = remove_margin(best["home"]["odds"], best["draw"]["odds"], best["away"]["odds"])

        rows.append({
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "commence_time": match.get("commence_time", ""),
            "home_team": match.get("home_team", ""),
            "away_team": match.get("away_team", ""),
            "home_odds": best["home"]["odds"],
            "home_bookmaker": best["home"]["bookmaker"],
            "draw_odds": best["draw"]["odds"],
            "draw_bookmaker": best["draw"]["bookmaker"],
            "away_odds": best["away"]["odds"],
            "away_bookmaker": best["away"]["bookmaker"],
            "over25_odds": best["over25"]["odds"],
            "under25_odds": best["under25"]["odds"],
            "fair_home": round(fair["home"], 4),
            "fair_draw": round(fair["draw"], 4),
            "fair_away": round(fair["away"], 4),
            "overround": round(fair["overround"], 4),
            "league": league,
        })

    client.close()
    return pd.DataFrame(rows)


def save_odds(df_new: pd.DataFrame, odds_dir: Path) -> None:
    """Append new odds to history CSV, avoiding duplicates."""
    odds_dir.mkdir(parents=True, exist_ok=True)
    history_path = odds_dir / "odds_history.csv"

    if history_path.exists():
        df_existing = pd.read_csv(history_path)
        # Deduplicate: same match + same day = skip
        df_existing["_date"] = pd.to_datetime(df_existing["collected_at"]).dt.date
        df_new["_date"] = pd.to_datetime(df_new["collected_at"]).dt.date

        merged = pd.concat([df_existing, df_new], ignore_index=True)
        merged = merged.drop_duplicates(
            subset=["home_team", "away_team", "commence_time", "_date"],
            keep="first",
        )
        merged = merged.drop(columns=["_date"])
        new_count = len(merged) - len(df_existing)
    else:
        merged = df_new
        if "_date" in merged.columns:
            merged = merged.drop(columns=["_date"])
        new_count = len(merged)

    merged.to_csv(history_path, index=False)
    print(f"\nSaved to {history_path}")
    print(f"  New entries: {new_count}")
    print(f"  Total entries: {len(merged)}")


def main():
    parser = argparse.ArgumentParser(description="Collect odds from The Odds API")
    parser.add_argument("--league", default="ligue_1", help="League key (default: ligue_1)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but don't save")
    args = parser.parse_args()

    print(f"=== Odds Collection: {args.league} ===")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n")

    df = collect_odds(league=args.league, dry_run=args.dry_run)

    if df.empty:
        return

    # Display
    display_cols = ["home_team", "away_team", "home_odds", "draw_odds", "away_odds",
                    "fair_home", "fair_draw", "fair_away", "overround"]
    print(f"\n{df[display_cols].to_string(index=False)}\n")

    if args.dry_run:
        print("(dry run - not saved)")
    else:
        odds_dir = PROJECT_ROOT / "data" / "odds"
        save_odds(df, odds_dir)

    print("\nDone.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Sync predictions.json → Supabase `bets` table (as unresolved bets).

Reads the current predictions from web/public/predictions.json,
extracts matches with a recommended_bet, and upserts them into
the Supabase `bets` table with resolved=false.

Usage:
    python scripts/sync_predictions.py
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

import requests

PREDICTIONS_FILE = ROOT / "web" / "public" / "predictions.json"


def get_supabase_config():
    """Load Supabase URL and service_role key from .env."""
    if load_dotenv:
        load_dotenv(ROOT / ".env")

    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url:
        print("ERROR: SUPABASE_URL not set in .env")
        sys.exit(1)
    if not key:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set in .env")
        sys.exit(1)

    return url, key


def load_predictions():
    """Load predictions from predictions.json."""
    if not PREDICTIONS_FILE.exists():
        print(f"ERROR: {PREDICTIONS_FILE} not found")
        sys.exit(1)

    with open(PREDICTIONS_FILE, encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, dict):
        return raw.get("predictions", [])
    return raw


def prediction_to_bet(pred: dict) -> dict | None:
    """Convert a prediction to a bets table record."""
    recommended_bet = pred.get("recommended_bet")
    if not recommended_bet:
        return None

    kickoff = pred.get("kickoff", "")
    best_odds = pred.get("best_odds", {})
    model_probs = pred.get("model_probs", {})
    edges = pred.get("edge", {})

    # For secondary markets (over25, under25, etc.), get prob from the right field
    prob = model_probs.get(recommended_bet)
    if prob is None:
        # Try over_under dict
        ou = pred.get("over_under", {})
        prob = ou.get(recommended_bet)

    edge = edges.get(recommended_bet)
    if edge is not None:
        # Convert from decimal to percentage if needed
        edge = round(float(edge) * 100, 1) if abs(float(edge)) < 1 else round(float(edge), 1)

    odds = best_odds.get(recommended_bet)

    return {
        "id": pred.get("match_id", ""),
        "date": kickoff[:10] if kickoff else "",
        "kickoff": kickoff,
        "home_team": pred.get("home_team", ""),
        "away_team": pred.get("away_team", ""),
        "league": pred.get("league", ""),
        "recommended_bet": recommended_bet,
        "odds": float(odds) if odds else None,
        "model_prob": round(float(prob), 4) if prob else None,
        "edge_pct": edge,
        "confidence_badge": pred.get("confidence_badge"),
        "resolved": False,
    }


def delete_stale_pending(url: str, headers: dict, current_ids: set[str], dates: set[str]):
    """Delete unresolved bets for the given dates that are NOT in current_ids.

    This cleans up stale predictions from previous pipeline runs (e.g. removed
    leagues, changed team names, dropped markets).
    """
    if not dates:
        return

    # Fetch all unresolved bets for the relevant dates
    date_list = ",".join(f'"{d}"' for d in sorted(dates))
    fetch_headers = {
        "apikey": headers["apikey"],
        "Authorization": headers["Authorization"],
    }
    r = requests.get(
        f"{url}/rest/v1/bets",
        headers=fetch_headers,
        params={
            "resolved": "eq.false",
            "date": f"in.({','.join(sorted(dates))})",
            "select": "id",
        },
    )
    if r.status_code != 200:
        print(f"  WARNING: Could not fetch stale bets: {r.status_code}")
        return

    existing = r.json()
    stale_ids = [row["id"] for row in existing if row["id"] not in current_ids]

    if not stale_ids:
        return

    # Delete stale bets in batches
    print(f"  Cleaning up {len(stale_ids)} stale unresolved bet(s)...")
    del_headers = {
        "apikey": headers["apikey"],
        "Authorization": headers["Authorization"],
        "Prefer": "return=minimal",
    }
    for i in range(0, len(stale_ids), 50):
        batch_ids = stale_ids[i : i + 50]
        id_filter = ",".join(batch_ids)
        dr = requests.delete(
            f"{url}/rest/v1/bets",
            headers=del_headers,
            params={"id": f"in.({id_filter})"},
        )
        if dr.status_code not in (200, 204):
            print(f"  WARNING: Delete failed: {dr.status_code} {dr.text[:200]}")


def main():
    url, key = get_supabase_config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }

    predictions = load_predictions()
    print(f"Loaded {len(predictions)} predictions from {PREDICTIONS_FILE.name}")

    # Convert to bet records
    bets = []
    for pred in predictions:
        bet = prediction_to_bet(pred)
        if bet and bet["id"]:
            bets.append(bet)

    print(f"  {len(bets)} with recommended bets")

    if not bets:
        print("  Nothing to sync.")
        return

    # Clean up stale unresolved bets for the same dates
    current_ids = {b["id"] for b in bets}
    bet_dates = {b["date"] for b in bets if b["date"]}
    delete_stale_pending(url, headers, current_ids, bet_dates)

    # Upsert in batches of 100
    BATCH = 100
    total = 0
    for i in range(0, len(bets), BATCH):
        batch = bets[i : i + BATCH]
        r = requests.post(
            f"{url}/rest/v1/bets",
            headers=headers,
            json=batch,
        )
        if r.status_code in (200, 201):
            total += len(batch)
            print(f"  Upserted {total}/{len(bets)}")
        else:
            print(f"  FAILED batch {i // BATCH + 1}: {r.status_code} {r.text[:200]}")
            break

    print(f"Done. {total} pending bets synced to Supabase.")


if __name__ == "__main__":
    main()

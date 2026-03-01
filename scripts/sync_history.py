#!/usr/bin/env python3
"""
Sync history.json → Supabase `bets` table.

Usage:
  python scripts/sync_history.py --seed      # First time: load all history.json
  python scripts/sync_history.py --update    # Re-run fetch_results then sync new/changed rows

Requires env vars (in .env at project root):
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from supabase import create_client


def get_supabase():
    """Create Supabase client with service_role key."""
    if load_dotenv:
        load_dotenv(ROOT / ".env")

    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url:
        print("ERROR: SUPABASE_URL not set in .env")
        sys.exit(1)
    if not key:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set in .env")
        print("Get it from: Supabase Dashboard > Settings > API > service_role")
        sys.exit(1)

    return create_client(url, key)


def load_history():
    """Load history.json from web/public/."""
    path = ROOT / "web" / "public" / "history.json"
    if not path.exists():
        print(f"ERROR: {path} not found")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def seed(supabase):
    """Seed all records from history.json into Supabase."""
    records = load_history()
    print(f"Loaded {len(records)} records from history.json")

    # Convert date fields to string for Supabase
    for r in records:
        if r.get("date"):
            r["date"] = str(r["date"])

    # Upsert in batches of 500
    batch_size = 500
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        supabase.table("bets").upsert(batch).execute()
        total += len(batch)
        print(f"  Upserted {total}/{len(records)}")

    print(f"Done. {len(records)} records in Supabase.")


def update(supabase):
    """Fetch latest results and sync to Supabase."""
    # Re-run fetch_results.py first
    fetch_script = ROOT / "scripts" / "fetch_results.py"
    if fetch_script.exists():
        print("Running fetch_results.py...")
        os.system(f"python3 {fetch_script}")
        print()

    # Now sync the updated history.json
    seed(supabase)


def main():
    parser = argparse.ArgumentParser(description="Sync bets to Supabase")
    parser.add_argument("--seed", action="store_true", help="Seed all from history.json")
    parser.add_argument("--update", action="store_true", help="Fetch results then sync")
    args = parser.parse_args()

    if not args.seed and not args.update:
        parser.print_help()
        sys.exit(1)

    sb = get_supabase()

    if args.seed:
        seed(sb)
    elif args.update:
        update(sb)


if __name__ == "__main__":
    main()

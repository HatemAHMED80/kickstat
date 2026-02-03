#!/usr/bin/env python3
"""
Daily Sync Script.

Run this script daily (via cron or systemd timer) to:
1. Sync fixtures from Football-Data.org
2. Generate Dixon-Coles predictions
3. Update odds from The Odds API (if configured)
4. Calculate edges and store in database

Cron example (every day at 6:00 AM):
0 6 * * * cd /path/to/football-predictions/backend && python scripts/daily_sync.py >> logs/daily_sync.log 2>&1

Systemd timer alternative: see backend/config/daily-sync.timer
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import argparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

# Configure logging
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
logger.add(
    log_dir / "daily_sync_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="INFO"
)


def run_fixtures_sync():
    """Sync fixtures and predictions."""
    logger.info(">>> Running fixtures sync with Dixon-Coles...")
    from scripts.sync_with_dixon_coles import sync_with_dixon_coles
    return sync_with_dixon_coles()


def run_odds_sync():
    """Sync real odds if API key is configured."""
    logger.info(">>> Checking for odds API...")
    from app.core import get_settings
    settings = get_settings()

    if settings.odds_api_key:
        logger.info(">>> Running real odds sync...")
        from scripts.sync_real_odds import sync_real_odds
        return sync_real_odds()
    else:
        logger.info(">>> Odds API not configured, skipping")
        return {"skipped": True}


def run_xg_update():
    """Export updated xG data."""
    logger.info(">>> Exporting xG data...")
    from app.services.data.understat import get_xg_provider
    provider = get_xg_provider()
    provider.export_to_csv()
    return {"status": "exported"}


def main():
    parser = argparse.ArgumentParser(description="Daily sync script")
    parser.add_argument("--fixtures-only", action="store_true", help="Only sync fixtures")
    parser.add_argument("--odds-only", action="store_true", help="Only sync odds")
    parser.add_argument("--xg-only", action="store_true", help="Only export xG data")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes")
    args = parser.parse_args()

    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info(f"DAILY SYNC STARTED - {start_time.isoformat()}")
    logger.info("=" * 60)

    results = {}

    try:
        # Run specific or all syncs
        if args.fixtures_only:
            results["fixtures"] = run_fixtures_sync()
        elif args.odds_only:
            results["odds"] = run_odds_sync()
        elif args.xg_only:
            results["xg"] = run_xg_update()
        else:
            # Full sync
            results["fixtures"] = run_fixtures_sync()
            results["odds"] = run_odds_sync()
            results["xg"] = run_xg_update()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info(f"DAILY SYNC COMPLETED - Duration: {duration:.1f}s")
        logger.info("=" * 60)
        logger.info(f"Results: {results}")

        return results

    except Exception as e:
        logger.error(f"DAILY SYNC FAILED: {e}")
        raise


if __name__ == "__main__":
    main()

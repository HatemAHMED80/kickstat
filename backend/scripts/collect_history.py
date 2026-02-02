#!/usr/bin/env python3
"""
Collect historical data for training the ML model.
Fetches 3 seasons of data (2022, 2023, 2024).

WARNING: This uses many API requests. Run sparingly!

Usage:
    python scripts/collect_history.py
    python scripts/collect_history.py --seasons 2023 2024
    python scripts/collect_history.py --dry-run
"""

import sys
import argparse
from pathlib import Path
from datetime import date

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.core import init_db, get_database_manager, get_settings
from app.services.data.collector import DataCollector
from app.services.data.api_football import get_api_football_client

settings = get_settings()


def parse_args():
    parser = argparse.ArgumentParser(description="Collect historical football data")

    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        default=[2022, 2023, 2024],
        help="Seasons to collect (default: 2022 2023 2024)",
    )
    parser.add_argument(
        "--league",
        type=int,
        default=61,
        help="League ID (default: 61 = Ligue 1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check API status without collecting data",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Also collect match statistics (uses more API calls)",
    )

    return parser.parse_args()


def check_api_status():
    """Check API status and remaining requests."""
    api = get_api_football_client()
    status = api.get_status()

    account = status.get("account", {})
    subscription = status.get("subscription", {})
    requests_info = status.get("requests", {})

    logger.info("=== API-Football Status ===")
    logger.info(f"Plan: {subscription.get('plan', 'Unknown')}")
    logger.info(f"Requests today: {requests_info.get('current', 0)}")
    logger.info(f"Limit: {requests_info.get('limit_day', 0)}")
    logger.info(
        f"Remaining: {requests_info.get('limit_day', 0) - requests_info.get('current', 0)}"
    )

    return requests_info.get("limit_day", 0) - requests_info.get("current", 0)


def estimate_requests(seasons: list[int], with_stats: bool = False) -> int:
    """Estimate the number of API requests needed."""
    # Per season:
    # - 1 request for teams
    # - 1 request for standings
    # - ~380 fixtures (38 matchdays * 10 matches) / 20 per page = ~19 requests
    # - If stats: 380 * 1 = 380 additional requests

    fixtures_per_season = 380
    requests_per_season = 1 + 1 + (fixtures_per_season // 20 + 1)

    if with_stats:
        requests_per_season += fixtures_per_season

    total = len(seasons) * requests_per_season

    logger.info(f"Estimated requests needed: {total}")
    return total


def main():
    args = parse_args()

    # Check API status
    remaining = check_api_status()

    # Estimate needed requests
    needed = estimate_requests(args.seasons, args.stats)

    if args.dry_run:
        logger.info(f"Dry run complete. Would need ~{needed} requests, have {remaining} remaining")
        return

    if needed > remaining:
        logger.warning(
            f"Not enough API requests remaining! Need ~{needed}, have {remaining}"
        )
        logger.warning("Consider running over multiple days or upgrading your API plan")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != "y":
            return

    # Initialize database
    init_db()

    with get_database_manager() as db:
        collector = DataCollector(db)

        # Sync competitions first
        logger.info("=== Syncing competitions ===")
        collector.sync_competitions()

        for season in args.seasons:
            logger.info(f"\n{'='*50}")
            logger.info(f"=== Collecting data for season {season} ===")
            logger.info(f"{'='*50}\n")

            # Teams
            logger.info(f"Syncing teams for {season}...")
            teams = collector.sync_teams(league_id=args.league, season=season)
            logger.info(f"Found {len(teams)} teams")

            # Fixtures
            logger.info(f"Syncing fixtures for {season}...")
            matches = collector.sync_fixtures(league_id=args.league, season=season)
            logger.info(f"Found {len(matches)} fixtures")

            # Match statistics (optional, uses many requests)
            if args.stats:
                logger.info(f"Syncing match statistics for {season}...")
                from sqlalchemy import select
                from app.models import Match, Competition

                # Get finished matches for this season
                competition = db.execute(
                    select(Competition).where(Competition.api_id == args.league)
                ).scalar_one_or_none()

                if competition:
                    finished_matches = db.execute(
                        select(Match).where(
                            Match.competition_id == competition.id,
                            Match.status == "finished",
                        )
                    ).scalars().all()

                    for i, match in enumerate(finished_matches):
                        if match.api_id:
                            collector.sync_fixture_statistics(match.api_id)
                            if (i + 1) % 50 == 0:
                                logger.info(f"  Processed {i + 1}/{len(finished_matches)} matches")

            # Standings (only for current/recent seasons)
            if season >= 2023:
                logger.info(f"Syncing standings for {season}...")
                collector.sync_standings(league_id=args.league, season=season)

    logger.info("\n=== Historical data collection complete ===")


if __name__ == "__main__":
    main()

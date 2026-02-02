#!/usr/bin/env python3
"""
Sync data from external sources to database.

Usage:
    python scripts/sync_data.py --all
    python scripts/sync_data.py --teams --season 2024
    python scripts/sync_data.py --fixtures --season 2024
    python scripts/sync_data.py --standings
    python scripts/sync_data.py --injuries
"""

import sys
import argparse
from pathlib import Path
from datetime import date

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.core import init_db, get_database_manager
from app.services.data.collector import DataCollector


def parse_args():
    parser = argparse.ArgumentParser(description="Sync football data from external sources")

    parser.add_argument("--all", action="store_true", help="Sync all data")
    parser.add_argument("--competitions", action="store_true", help="Sync competitions")
    parser.add_argument("--teams", action="store_true", help="Sync teams")
    parser.add_argument("--fixtures", action="store_true", help="Sync fixtures")
    parser.add_argument("--standings", action="store_true", help="Sync standings")
    parser.add_argument("--injuries", action="store_true", help="Sync injuries from Transfermarkt")
    parser.add_argument("--players", action="store_true", help="Sync players for all teams")

    parser.add_argument("--season", type=int, default=2024, help="Season year (default: 2024)")
    parser.add_argument(
        "--league",
        type=int,
        default=61,
        help="League ID (default: 61 = Ligue 1)",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # Initialize database
    init_db()

    with get_database_manager() as db:
        collector = DataCollector(db)

        if args.all or args.competitions:
            logger.info("=== Syncing competitions ===")
            comps = collector.sync_competitions()
            logger.info(f"Synced {len(comps)} competitions")

        if args.all or args.teams:
            logger.info(f"=== Syncing teams for season {args.season} ===")
            teams = collector.sync_teams(league_id=args.league, season=args.season)
            logger.info(f"Synced {len(teams)} teams")

        if args.all or args.players:
            logger.info("=== Syncing players ===")
            # Get all teams from DB and sync players
            from sqlalchemy import select
            from app.models import Team

            teams = db.execute(select(Team)).scalars().all()
            total_players = 0
            for team in teams:
                if team.api_id:
                    players = collector.sync_team_players(team.api_id, args.season)
                    total_players += len(players)
            logger.info(f"Synced {total_players} players total")

        if args.all or args.fixtures:
            logger.info(f"=== Syncing fixtures for season {args.season} ===")
            matches = collector.sync_fixtures(
                league_id=args.league,
                season=args.season,
            )
            logger.info(f"Synced {len(matches)} fixtures")

        if args.all or args.standings:
            logger.info(f"=== Syncing standings for season {args.season} ===")
            standings = collector.sync_standings(league_id=args.league, season=args.season)
            logger.info(f"Synced {len(standings)} standings")

        if args.all or args.injuries:
            logger.info("=== Syncing injuries from Transfermarkt ===")
            count = collector.sync_injuries()
            logger.info(f"Updated {count} injuries")

    logger.info("=== Sync complete ===")


if __name__ == "__main__":
    main()

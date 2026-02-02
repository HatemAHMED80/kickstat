#!/usr/bin/env python3
"""
Sync odds from API-Football for upcoming matches.

Run every 15 minutes:
    */15 * * * * python scripts/cron/sync_odds.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger

from app.core.database import SessionLocal
from app.services.odds import get_odds_fetcher, get_edge_calculator


def main():
    """Main function to sync odds."""
    logger.info("Starting odds sync...")

    db = SessionLocal()

    try:
        # Fetch odds for upcoming matches
        fetcher = get_odds_fetcher()
        processed = fetcher.fetch_upcoming_odds(db, days_ahead=7)

        logger.info(f"Synced odds for {processed} matches")

        # Recalculate edges after odds update
        if processed > 0:
            logger.info("Recalculating edges...")
            from app.models.database import Match, Prediction
            from datetime import datetime

            # Get matches with new odds and predictions
            matches = (
                db.query(Match)
                .filter(
                    Match.status == "scheduled",
                    Match.kickoff > datetime.utcnow(),
                )
                .all()
            )

            calculator = get_edge_calculator()
            edge_count = 0

            for match in matches:
                prediction = (
                    db.query(Prediction)
                    .filter(Prediction.match_id == match.id)
                    .first()
                )

                if prediction:
                    edges = calculator.calculate_and_store_edges(db, match, prediction)
                    edge_count += len(edges)

            logger.info(f"Calculated {edge_count} edges for {len(matches)} matches")

    except Exception as e:
        logger.error(f"Error syncing odds: {e}")
        raise
    finally:
        db.close()

    logger.info("Odds sync complete")


if __name__ == "__main__":
    main()

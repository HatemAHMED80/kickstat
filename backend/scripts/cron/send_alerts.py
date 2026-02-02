#!/usr/bin/env python3
"""
Send Telegram alerts for upcoming matches with good edges.

Run every hour:
    0 * * * * python scripts/cron/send_alerts.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger

from app.core.database import SessionLocal
from app.services.notifications import get_alert_service


def main():
    """Main function to send alerts."""
    logger.info("Starting alert sender...")

    db = SessionLocal()

    try:
        alert_service = get_alert_service()

        # Send alerts for matches in the next 24 hours
        stats = alert_service.send_alerts_for_upcoming_matches(db, hours_ahead=24)

        logger.info(
            f"Alert run complete: "
            f"sent={stats['sent']}, "
            f"failed={stats['failed']}, "
            f"skipped={stats['skipped']}"
        )

    except Exception as e:
        logger.error(f"Error sending alerts: {e}")
        raise
    finally:
        db.close()

    logger.info("Alert sender complete")


if __name__ == "__main__":
    main()

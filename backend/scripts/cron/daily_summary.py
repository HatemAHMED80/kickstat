#!/usr/bin/env python3
"""
Send daily summary of opportunities to subscribers.

Run daily at 8 AM:
    0 8 * * * python scripts/cron/daily_summary.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger

from app.core.database import SessionLocal
from app.services.notifications import get_alert_service


def main():
    """Main function to send daily summary."""
    logger.info("Starting daily summary sender...")

    db = SessionLocal()

    try:
        alert_service = get_alert_service()
        stats = alert_service.send_daily_summary(db)

        logger.info(f"Daily summary sent: sent={stats['sent']}, failed={stats['failed']}")

    except Exception as e:
        logger.error(f"Error sending daily summary: {e}")
        raise
    finally:
        db.close()

    logger.info("Daily summary complete")


if __name__ == "__main__":
    main()

"""
Alert Service

Orchestrates sending alerts to users based on their preferences.
"""

from datetime import datetime, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.database import User, Match, EdgeCalculation, AlertHistory
from .telegram_bot import get_telegram_bot, TelegramBot


class AlertService:
    """
    Orchestrates sending alerts to users.

    Handles:
    - Finding matches that need alerts
    - Finding users who should receive alerts
    - Sending alerts via appropriate channels
    - Avoiding duplicate alerts
    """

    def __init__(self, telegram_bot: Optional[TelegramBot] = None):
        self.telegram = telegram_bot or get_telegram_bot()

    def send_alerts_for_upcoming_matches(
        self,
        db: Session,
        hours_ahead: int = 24,
    ) -> dict:
        """
        Send alerts for matches happening in the next N hours.

        Args:
            db: Database session
            hours_ahead: How many hours ahead to look

        Returns:
            Stats dict with sent/failed counts
        """
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours_ahead)

        # Find matches with edges that haven't been alerted
        matches_with_edges = (
            db.query(Match, EdgeCalculation)
            .join(EdgeCalculation, EdgeCalculation.match_id == Match.id)
            .filter(
                Match.status == "scheduled",
                Match.kickoff > now,
                Match.kickoff <= cutoff,
                EdgeCalculation.edge_percentage >= 5.0,  # Minimum edge
            )
            .all()
        )

        if not matches_with_edges:
            logger.info("No matches with edges found for alerting")
            return {"sent": 0, "failed": 0, "skipped": 0}

        # Group edges by match
        match_edges = {}
        for match, edge in matches_with_edges:
            if match.id not in match_edges:
                match_edges[match.id] = {"match": match, "edges": []}
            match_edges[match.id]["edges"].append(edge)

        # Get users with alerts enabled
        users = (
            db.query(User)
            .filter(
                User.telegram_alerts_enabled == True,
                User.telegram_chat_id.isnot(None),
                User.subscription_status == "active",
            )
            .all()
        )

        if not users:
            logger.info("No users with alerts enabled")
            return {"sent": 0, "failed": 0, "skipped": 0}

        stats = {"sent": 0, "failed": 0, "skipped": 0}

        for user in users:
            for match_id, data in match_edges.items():
                match = data["match"]
                edges = data["edges"]

                # Filter edges by user's threshold
                relevant_edges = [
                    e for e in edges
                    if e.edge_percentage >= user.min_edge_threshold
                ]

                if not relevant_edges:
                    continue

                # Check if already alerted for this match
                already_alerted = (
                    db.query(AlertHistory)
                    .filter(
                        AlertHistory.user_id == user.id,
                        AlertHistory.match_id == match_id,
                        AlertHistory.delivered == True,
                    )
                    .first()
                )

                if already_alerted:
                    stats["skipped"] += 1
                    continue

                # Send alert for best edge
                best_edge = max(relevant_edges, key=lambda e: e.edge_percentage)
                success = self.telegram.send_edge_alert(db, user, best_edge, match)

                if success:
                    stats["sent"] += 1
                else:
                    stats["failed"] += 1

        logger.info(f"Alert run complete: {stats}")
        return stats

    def send_daily_summary(self, db: Session) -> dict:
        """
        Send a daily summary of opportunities to all subscribed users.

        Args:
            db: Database session

        Returns:
            Stats dict
        """
        now = datetime.utcnow()
        end_of_day = now.replace(hour=23, minute=59, second=59)

        # Get today's matches with edges
        edges = (
            db.query(EdgeCalculation)
            .join(Match)
            .filter(
                Match.status == "scheduled",
                Match.kickoff >= now,
                Match.kickoff <= end_of_day,
                EdgeCalculation.edge_percentage >= 5.0,
            )
            .order_by(EdgeCalculation.edge_percentage.desc())
            .limit(10)
            .all()
        )

        if not edges:
            logger.info("No edges found for daily summary")
            return {"sent": 0, "failed": 0}

        # Get matches
        match_ids = [e.match_id for e in edges]
        matches = db.query(Match).filter(Match.id.in_(match_ids)).all()
        match_map = {m.id: m for m in matches}

        edge_match_pairs = [
            (e, match_map.get(e.match_id))
            for e in edges
            if match_map.get(e.match_id)
        ]

        # Get users
        users = (
            db.query(User)
            .filter(
                User.telegram_alerts_enabled == True,
                User.telegram_chat_id.isnot(None),
                User.subscription_status == "active",
            )
            .all()
        )

        stats = {"sent": 0, "failed": 0}

        message = self.telegram.format_daily_summary(edge_match_pairs)

        for user in users:
            success = self.telegram.send_message(user.telegram_chat_id, message)
            if success:
                stats["sent"] += 1
            else:
                stats["failed"] += 1

        logger.info(f"Daily summary sent: {stats}")
        return stats

    def send_test_alert(self, db: Session, user: User) -> bool:
        """
        Send a test alert to verify Telegram connection.

        Args:
            db: Database session
            user: User to send test to

        Returns:
            True if sent successfully
        """
        if not user.telegram_chat_id:
            return False

        message = """
🔔 <b>Test d'alerte Kickstat</b>

✅ Votre connexion Telegram fonctionne correctement !

Vous recevrez les alertes quand notre IA détecte des opportunités avec un edge ≥ {threshold}%.

Modifiez vos préférences sur kickstat.app/settings
""".format(threshold=user.min_edge_threshold).strip()

        success = self.telegram.send_message(user.telegram_chat_id, message)

        if success:
            logger.info(f"Test alert sent to {user.email}")

        return success


# Singleton instance
_alert_service: Optional[AlertService] = None


def get_alert_service() -> AlertService:
    """Get or create the AlertService singleton."""
    global _alert_service
    if _alert_service is None:
        _alert_service = AlertService()
    return _alert_service

"""
Telegram Bot Service

Handles sending alerts and receiving commands from users.
"""

from datetime import datetime
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy.orm import Session

from app.core import get_settings
from app.models.database import User, Match, EdgeCalculation, AlertHistory

settings = get_settings()


class TelegramBot:
    """
    Telegram bot for sending alerts and handling user commands.

    Uses the Telegram Bot API directly via HTTP for simplicity.
    For webhook mode, set up a route to receive updates.
    """

    def __init__(self):
        self.token = settings.telegram_bot_token
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.client = httpx.Client(timeout=30.0)

    def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
        disable_preview: bool = True,
    ) -> bool:
        """
        Send a text message to a Telegram chat.

        Args:
            chat_id: Telegram chat ID
            text: Message text (can include HTML formatting)
            parse_mode: "HTML" or "Markdown"
            disable_preview: Disable link previews

        Returns:
            True if sent successfully
        """
        try:
            response = self.client.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": disable_preview,
                },
            )
            response.raise_for_status()

            result = response.json()
            if not result.get("ok"):
                logger.error(f"Telegram API error: {result}")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
            return False

    def format_edge_alert(
        self,
        edge: EdgeCalculation,
        match: Match,
    ) -> str:
        """
        Format an edge opportunity as a Telegram message.

        Args:
            edge: The edge calculation
            match: The match

        Returns:
            Formatted HTML message
        """
        # Risk emoji
        risk_emoji = {
            "safe": "🟢",
            "medium": "🟠",
            "risky": "🔴",
        }.get(edge.risk_level, "⚪")

        # Market display name
        market_names = {
            "1x2_home": "Victoire domicile",
            "1x2_draw": "Match nul",
            "1x2_away": "Victoire extérieur",
            "over_25": "Plus de 2.5 buts",
            "under_25": "Moins de 2.5 buts",
            "btts_yes": "Les deux équipes marquent",
            "btts_no": "Au moins une équipe ne marque pas",
        }
        market_name = market_names.get(edge.market, edge.market)

        # Format kickoff time
        kickoff_str = match.kickoff.strftime("%d/%m à %H:%M")

        message = f"""
⚽ <b>OPPORTUNITÉ DÉTECTÉE</b>

{risk_emoji} <b>{edge.risk_level.upper()}</b>

🏟 <b>{match.home_team.name} vs {match.away_team.name}</b>
📅 {kickoff_str}

📊 <b>Pari :</b> {market_name}

🎯 <b>Notre modèle :</b> {edge.model_probability:.1f}%
📉 <b>Bookmakers :</b> {edge.bookmaker_probability:.1f}%

💰 <b>AVANTAGE : +{edge.edge_percentage:.1f}%</b>
🎰 <b>Cote :</b> {edge.best_odds:.2f} @ {edge.bookmaker_name}

📈 <b>Stake suggéré :</b> {edge.kelly_stake * 100:.1f}% du capital

<a href="https://kickstat.app/match/{match.id}">🔗 Voir l'analyse complète</a>
""".strip()

        return message

    def format_daily_summary(
        self,
        edges: list[tuple[EdgeCalculation, Match]],
    ) -> str:
        """
        Format a daily summary of opportunities.

        Args:
            edges: List of (EdgeCalculation, Match) tuples

        Returns:
            Formatted HTML message
        """
        if not edges:
            return "📊 Aucune opportunité détectée pour aujourd'hui."

        safe_count = sum(1 for e, _ in edges if e.risk_level == "safe")
        medium_count = sum(1 for e, _ in edges if e.risk_level == "medium")
        risky_count = sum(1 for e, _ in edges if e.risk_level == "risky")

        message = f"""
📊 <b>RÉSUMÉ DU JOUR</b>

<b>{len(edges)} opportunités détectées :</b>
🟢 Sûr : {safe_count}
🟠 Moyen : {medium_count}
🔴 Risqué : {risky_count}

<b>Top 3 opportunités :</b>
"""

        # Add top 3
        for edge, match in edges[:3]:
            risk_emoji = {"safe": "🟢", "medium": "🟠", "risky": "🔴"}.get(edge.risk_level, "⚪")
            message += f"\n{risk_emoji} {match.home_team.short_name or match.home_team.name} vs {match.away_team.short_name or match.away_team.name}"
            message += f"\n   +{edge.edge_percentage:.1f}% | Cote {edge.best_odds:.2f}"

        message += f"\n\n<a href=\"https://kickstat.app/dashboard\">🔗 Voir toutes les opportunités</a>"

        return message.strip()

    def send_edge_alert(
        self,
        db: Session,
        user: User,
        edge: EdgeCalculation,
        match: Match,
    ) -> bool:
        """
        Send an edge alert to a user and record in history.

        Args:
            db: Database session
            user: The user to alert
            edge: The edge opportunity
            match: The match

        Returns:
            True if sent successfully
        """
        if not user.telegram_chat_id:
            logger.warning(f"User {user.email} has no Telegram chat_id")
            return False

        if not user.telegram_alerts_enabled:
            logger.debug(f"Alerts disabled for user {user.email}")
            return False

        # Check user's minimum edge threshold
        if edge.edge_percentage < user.min_edge_threshold:
            logger.debug(f"Edge {edge.edge_percentage}% below user threshold {user.min_edge_threshold}%")
            return False

        message = self.format_edge_alert(edge, match)
        success = self.send_message(user.telegram_chat_id, message)

        # Record in history
        history = AlertHistory(
            user_id=user.id,
            match_id=match.id,
            edge_id=edge.id,
            channel="telegram",
            message=message[:500],  # Truncate for storage
            sent_at=datetime.utcnow(),
            delivered=success,
            error_message=None if success else "Send failed",
        )
        db.add(history)
        db.commit()

        if success:
            logger.info(f"Sent alert to {user.email} for match {match.id}")
        else:
            logger.error(f"Failed to send alert to {user.email}")

        return success

    def handle_command(
        self,
        db: Session,
        chat_id: str,
        command: str,
        args: list[str],
        username: Optional[str] = None,
    ) -> str:
        """
        Handle a bot command from a user.

        Args:
            db: Database session
            chat_id: Telegram chat ID
            command: Command without the /
            args: Command arguments
            username: Telegram username if available

        Returns:
            Response message to send
        """
        if command == "start":
            return self._handle_start()

        elif command == "connect":
            if not args:
                return "❌ Usage: /connect <votre_token>\n\nRécupérez votre token sur kickstat.app/settings"
            return self._handle_connect(db, chat_id, args[0], username)

        elif command == "alerts":
            return self._handle_alerts_toggle(db, chat_id)

        elif command == "today":
            return self._handle_today(db, chat_id)

        elif command == "help":
            return self._handle_help()

        else:
            return "❓ Commande inconnue. Tapez /help pour voir les commandes disponibles."

    def _handle_start(self) -> str:
        """Handle /start command."""
        return """
👋 <b>Bienvenue sur Kickstat Bot !</b>

Je vous envoie des alertes quand notre IA détecte des opportunités de paris avec un avantage significatif.

<b>Pour commencer :</b>
1. Créez un compte sur kickstat.app
2. Allez dans Paramètres → Telegram
3. Copiez votre token de connexion
4. Envoyez-le ici avec /connect <token>

<b>Commandes disponibles :</b>
/connect <token> - Lier votre compte
/alerts - Activer/désactiver les alertes
/today - Opportunités du jour
/help - Aide

💡 Les alertes sont envoyées quelques heures avant les matchs.
""".strip()

    def _handle_connect(
        self,
        db: Session,
        chat_id: str,
        token: str,
        username: Optional[str],
    ) -> str:
        """Handle /connect command."""
        from app.services.auth import get_supabase_auth

        auth = get_supabase_auth()
        user = auth.link_telegram_account(db, token, chat_id, username)

        if user:
            return f"""
✅ <b>Compte connecté !</b>

Votre compte Telegram est maintenant lié à {user.email}.

Les alertes sont <b>activées</b> par défaut.
Vous recevrez les opportunités avec un edge ≥ {user.min_edge_threshold}%.

Utilisez /alerts pour désactiver les notifications.
""".strip()
        else:
            return "❌ Token invalide ou expiré. Générez un nouveau token sur kickstat.app/settings"

    def _handle_alerts_toggle(self, db: Session, chat_id: str) -> str:
        """Handle /alerts command to toggle alerts."""
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()

        if not user:
            return "❌ Compte non connecté. Utilisez /connect <token> pour lier votre compte."

        user.telegram_alerts_enabled = not user.telegram_alerts_enabled
        db.commit()

        if user.telegram_alerts_enabled:
            return f"""
✅ <b>Alertes activées</b>

Vous recevrez les opportunités avec un edge ≥ {user.min_edge_threshold}%.

Modifiez vos préférences sur kickstat.app/settings
""".strip()
        else:
            return """
🔕 <b>Alertes désactivées</b>

Vous ne recevrez plus d'alertes Telegram.

Utilisez /alerts pour les réactiver.
""".strip()

    def _handle_today(self, db: Session, chat_id: str) -> str:
        """Handle /today command."""
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()

        if not user:
            return "❌ Compte non connecté. Utilisez /connect <token>"

        # Check subscription
        if user.subscription_status != "active":
            return """
🔒 <b>Abonnement requis</b>

Souscrivez à Kickstat pour voir les opportunités du jour.

👉 kickstat.app/pricing
""".strip()

        # Get today's opportunities
        from app.services.odds import get_edge_calculator

        calculator = get_edge_calculator()
        edges = calculator.get_top_opportunities(
            db,
            limit=10,
            min_edge=user.min_edge_threshold,
        )

        if not edges:
            return "📊 Aucune opportunité détectée pour aujourd'hui avec vos critères."

        # Get matches
        match_ids = [e.match_id for e in edges]
        matches = db.query(Match).filter(Match.id.in_(match_ids)).all()
        match_map = {m.id: m for m in matches}

        edge_match_pairs = [(e, match_map.get(e.match_id)) for e in edges if match_map.get(e.match_id)]

        return self.format_daily_summary(edge_match_pairs)

    def _handle_help(self) -> str:
        """Handle /help command."""
        return """
📚 <b>Aide Kickstat Bot</b>

<b>Commandes :</b>
/start - Message de bienvenue
/connect <token> - Lier votre compte Kickstat
/alerts - Activer/désactiver les alertes
/today - Opportunités du jour (abonnés)
/help - Cette aide

<b>Fonctionnement :</b>
• Les alertes sont envoyées ~24h avant les matchs
• Seules les opportunités au-dessus de votre seuil sont envoyées
• Modifiez vos préférences sur kickstat.app/settings

<b>Support :</b>
support@kickstat.app
""".strip()

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Singleton instance
_telegram_bot: Optional[TelegramBot] = None


def get_telegram_bot() -> TelegramBot:
    """Get or create the TelegramBot singleton."""
    global _telegram_bot
    if _telegram_bot is None:
        _telegram_bot = TelegramBot()
    return _telegram_bot

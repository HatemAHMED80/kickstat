"""
Stripe Payment Service

Handles subscriptions, one-time payments, and webhook processing.
"""

from datetime import datetime
from typing import Optional

import stripe
from loguru import logger
from sqlalchemy.orm import Session

from api.core import get_settings
from api.models.database import User, MatchPurchase

settings = get_settings()


# Subscription plans configuration
SUBSCRIPTION_PLANS = {
    "premium": {
        "name": "Kickstat Premium",
        "price_eur": 3999,  # 39.99 EUR in cents
        "interval": "month",
        "features": [
            "L1 + L2 complets",
            "Combinés à forte cote",
            "Alertes Telegram en temps réel",
            "Accès API",
            "Historique illimité",
        ],
    },
}

MATCH_PRICE_CENTS = 99  # 0.99 EUR


class StripeService:
    """Stripe payment operations."""

    def __init__(self):
        stripe.api_key = settings.stripe_secret_key
        self.webhook_secret = settings.stripe_webhook_secret
        self.basic_price_id = settings.stripe_basic_price_id
        self.pro_price_id = settings.stripe_pro_price_id
        self.premium_price_id = settings.stripe_premium_price_id

    def get_or_create_customer(self, db: Session, user: User) -> str:
        """
        Get or create a Stripe customer for a user.

        Args:
            db: Database session
            user: The user model

        Returns:
            Stripe customer ID
        """
        if user.stripe_customer_id:
            return user.stripe_customer_id

        # Create new Stripe customer
        customer = stripe.Customer.create(
            email=user.email,
            name=user.full_name,
            metadata={
                "user_id": user.id,
            },
        )

        # Save to database
        user.stripe_customer_id = customer.id
        user.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Created Stripe customer {customer.id} for user {user.email}")
        return customer.id

    def create_checkout_session(
        self,
        db: Session,
        user: User,
        plan: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """
        Create a Stripe Checkout session for a subscription.

        Args:
            db: Database session
            user: The user model
            plan: "basic" or "pro"
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel

        Returns:
            Checkout session URL
        """
        if plan not in ("basic", "pro", "premium"):
            raise ValueError(f"Invalid plan: {plan}")

        customer_id = self.get_or_create_customer(db, user)
        if plan == "premium":
            price_id = self.premium_price_id
        elif plan == "basic":
            price_id = self.basic_price_id
        else:
            price_id = self.pro_price_id

        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": user.id,
                "plan": plan,
            },
        )

        logger.info(f"Created checkout session {session.id} for user {user.email}, plan={plan}")
        return session.url

    def create_match_payment(
        self,
        db: Session,
        user: User,
        match_id: int,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """
        Create a Stripe Checkout session for a single match purchase.

        Args:
            db: Database session
            user: The user model
            match_id: The match to purchase
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel

        Returns:
            Checkout session URL
        """
        # Check if already purchased
        existing = (
            db.query(MatchPurchase)
            .filter(
                MatchPurchase.user_id == user.id,
                MatchPurchase.match_id == match_id,
                MatchPurchase.status == "completed",
            )
            .first()
        )

        if existing:
            raise ValueError("Match already purchased")

        customer_id = self.get_or_create_customer(db, user)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "eur",
                        "unit_amount": MATCH_PRICE_CENTS,
                        "product_data": {
                            "name": f"Match #{match_id} - Prédiction complète",
                            "description": "Accès à l'analyse détaillée et aux opportunités de ce match",
                        },
                    },
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": user.id,
                "match_id": str(match_id),
                "type": "match_purchase",
            },
        )

        # Create pending purchase record
        purchase = MatchPurchase(
            user_id=user.id,
            match_id=match_id,
            stripe_payment_intent_id=session.payment_intent,
            amount_cents=MATCH_PRICE_CENTS,
            status="pending",
        )
        db.add(purchase)
        db.commit()

        logger.info(f"Created match payment session {session.id} for user {user.email}, match={match_id}")
        return session.url

    def get_customer_portal_url(self, db: Session, user: User, return_url: str) -> str:
        """
        Get a Stripe Customer Portal URL for subscription management.

        Args:
            db: Database session
            user: The user model
            return_url: URL to return to after portal session

        Returns:
            Portal session URL
        """
        if not user.stripe_customer_id:
            raise ValueError("User has no Stripe customer ID")

        session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=return_url,
        )

        return session.url

    def handle_webhook(self, db: Session, payload: bytes, sig_header: str) -> dict:
        """
        Process a Stripe webhook event.

        Args:
            db: Database session
            payload: Raw webhook payload
            sig_header: Stripe-Signature header

        Returns:
            Dict with processing result
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid Stripe webhook signature")
            raise ValueError("Invalid signature")

        event_type = event["type"]
        data = event["data"]["object"]

        logger.info(f"Processing Stripe webhook: {event_type}")

        # Handle different event types
        if event_type == "checkout.session.completed":
            return self._handle_checkout_completed(db, data)

        elif event_type == "customer.subscription.created":
            return self._handle_subscription_created(db, data)

        elif event_type == "customer.subscription.updated":
            return self._handle_subscription_updated(db, data)

        elif event_type == "customer.subscription.deleted":
            return self._handle_subscription_deleted(db, data)

        elif event_type == "invoice.payment_succeeded":
            return self._handle_invoice_paid(db, data)

        elif event_type == "invoice.payment_failed":
            return self._handle_invoice_failed(db, data)

        else:
            logger.debug(f"Unhandled Stripe event type: {event_type}")
            return {"status": "ignored", "type": event_type}

    def _handle_checkout_completed(self, db: Session, data: dict) -> dict:
        """Handle checkout.session.completed event."""
        metadata = data.get("metadata", {})
        user_id = metadata.get("user_id")

        if not user_id:
            logger.warning("Checkout completed without user_id in metadata")
            return {"status": "error", "reason": "missing_user_id"}

        # Check if it's a match purchase
        if metadata.get("type") == "match_purchase":
            match_id = metadata.get("match_id")
            payment_intent = data.get("payment_intent")

            purchase = (
                db.query(MatchPurchase)
                .filter(
                    MatchPurchase.user_id == user_id,
                    MatchPurchase.match_id == int(match_id),
                )
                .first()
            )

            if purchase:
                purchase.status = "completed"
                purchase.stripe_payment_intent_id = payment_intent
                db.commit()

                logger.info(f"Match purchase completed: user={user_id}, match={match_id}")
                return {"status": "success", "type": "match_purchase"}

        return {"status": "success", "type": "checkout"}

    def _handle_subscription_created(self, db: Session, data: dict) -> dict:
        """Handle customer.subscription.created event."""
        customer_id = data.get("customer")
        subscription_id = data.get("id")
        status = data.get("status")

        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()

        if not user:
            logger.warning(f"Subscription created for unknown customer: {customer_id}")
            return {"status": "error", "reason": "unknown_customer"}

        # Determine plan from price
        items = data.get("items", {}).get("data", [])
        price_id = items[0]["price"]["id"] if items else None

        if price_id == self.premium_price_id:
            tier = "premium"
        elif price_id == self.basic_price_id:
            tier = "basic"
        elif price_id == self.pro_price_id:
            tier = "pro"
        else:
            tier = "premium"  # Default

        user.stripe_subscription_id = subscription_id
        user.subscription_tier = tier
        user.subscription_status = "active" if status == "active" else "inactive"

        # Set subscription end date
        current_period_end = data.get("current_period_end")
        if current_period_end:
            user.subscription_ends_at = datetime.fromtimestamp(current_period_end)

        user.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Subscription created: user={user.email}, tier={tier}, status={status}")
        return {"status": "success", "tier": tier}

    def _handle_subscription_updated(self, db: Session, data: dict) -> dict:
        """Handle customer.subscription.updated event."""
        customer_id = data.get("customer")
        status = data.get("status")

        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()

        if not user:
            return {"status": "error", "reason": "unknown_customer"}

        # Update status
        user.subscription_status = "active" if status == "active" else "inactive"

        # Update end date
        current_period_end = data.get("current_period_end")
        if current_period_end:
            user.subscription_ends_at = datetime.fromtimestamp(current_period_end)

        user.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Subscription updated: user={user.email}, status={status}")
        return {"status": "success"}

    def _handle_subscription_deleted(self, db: Session, data: dict) -> dict:
        """Handle customer.subscription.deleted event."""
        customer_id = data.get("customer")

        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()

        if not user:
            return {"status": "error", "reason": "unknown_customer"}

        user.subscription_status = "cancelled"
        user.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Subscription cancelled: user={user.email}")
        return {"status": "success"}

    def _handle_invoice_paid(self, db: Session, data: dict) -> dict:
        """Handle invoice.payment_succeeded event."""
        customer_id = data.get("customer")

        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()

        if user and user.subscription_status != "active":
            user.subscription_status = "active"
            user.updated_at = datetime.utcnow()
            db.commit()

        return {"status": "success"}

    def _handle_invoice_failed(self, db: Session, data: dict) -> dict:
        """Handle invoice.payment_failed event."""
        customer_id = data.get("customer")

        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()

        if user:
            user.subscription_status = "inactive"
            user.updated_at = datetime.utcnow()
            db.commit()

            logger.warning(f"Payment failed for user {user.email}")

        return {"status": "success"}


# Singleton instance
_stripe_service: Optional[StripeService] = None


def get_stripe_service() -> StripeService:
    """Get or create the StripeService singleton."""
    global _stripe_service
    if _stripe_service is None:
        _stripe_service = StripeService()
    return _stripe_service

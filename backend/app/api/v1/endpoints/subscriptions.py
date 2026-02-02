"""
Subscription endpoints.

Handles Stripe subscriptions and payments.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import get_settings
from app.core.database import get_db
from app.models.database import User
from app.services.auth import get_current_user
from app.services.payments import get_stripe_service, StripeService, SUBSCRIPTION_PLANS


router = APIRouter()
settings = get_settings()


class PlanInfo(BaseModel):
    """Subscription plan information."""
    id: str
    name: str
    price_eur: int
    interval: str
    features: list[str]


class PlansResponse(BaseModel):
    """List of available plans."""
    plans: list[PlanInfo]
    match_price_cents: int


class CheckoutRequest(BaseModel):
    """Checkout session request."""
    plan: str = "premium"  # "premium" (seul plan disponible)


class CheckoutResponse(BaseModel):
    """Checkout session response."""
    url: str


class MatchPurchaseRequest(BaseModel):
    """Match purchase request."""
    match_id: int


class SubscriptionStatus(BaseModel):
    """Current subscription status."""
    tier: str
    status: str
    ends_at: str | None
    stripe_customer_id: str | None


@router.get("/plans", response_model=PlansResponse)
async def get_subscription_plans():
    """
    Get available subscription plans.

    Returns pricing and features for each plan.
    """
    plans = [
        PlanInfo(
            id=plan_id,
            name=plan["name"],
            price_eur=plan["price_eur"],
            interval=plan["interval"],
            features=plan["features"],
        )
        for plan_id, plan in SUBSCRIPTION_PLANS.items()
    ]

    return PlansResponse(
        plans=plans,
        match_price_cents=99,  # 0.99 EUR
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    request: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    stripe: StripeService = Depends(get_stripe_service),
):
    """
    Create a Stripe Checkout session for subscription.

    Redirects the user to Stripe's hosted checkout page.
    """
    if request.plan not in ("premium",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan. Use 'premium'.",
        )

    success_url = f"{settings.frontend_url}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{settings.frontend_url}/subscription/cancel"

    url = stripe.create_checkout_session(
        db=db,
        user=user,
        plan=request.plan,
        success_url=success_url,
        cancel_url=cancel_url,
    )

    return CheckoutResponse(url=url)


@router.post("/purchase-match", response_model=CheckoutResponse)
async def create_match_purchase(
    request: MatchPurchaseRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    stripe: StripeService = Depends(get_stripe_service),
):
    """
    Create a Stripe Checkout session for a single match purchase (0.99 EUR).

    Used by free users to access full predictions for a single match.
    """
    from app.models.database import Match

    # Verify match exists
    match = db.query(Match).filter(Match.id == request.match_id).first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    success_url = f"{settings.frontend_url}/match/{request.match_id}?purchased=true"
    cancel_url = f"{settings.frontend_url}/match/{request.match_id}"

    try:
        url = stripe.create_match_payment(
            db=db,
            user=user,
            match_id=request.match_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return CheckoutResponse(url=url)


@router.get("/portal")
async def get_customer_portal(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    stripe: StripeService = Depends(get_stripe_service),
):
    """
    Get Stripe Customer Portal URL for subscription management.

    Allows users to update payment methods, view invoices, cancel subscription.
    """
    if not user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No subscription found. Subscribe first.",
        )

    return_url = f"{settings.frontend_url}/settings"

    url = stripe.get_customer_portal_url(db, user, return_url)

    return {"url": url}


@router.get("/status", response_model=SubscriptionStatus)
async def get_subscription_status(
    user: User = Depends(get_current_user),
):
    """
    Get current subscription status.
    """
    return SubscriptionStatus(
        tier=user.subscription_tier,
        status=user.subscription_status,
        ends_at=user.subscription_ends_at.isoformat() if user.subscription_ends_at else None,
        stripe_customer_id=user.stripe_customer_id,
    )

"""
Authentication endpoints.

Handles user authentication via Supabase.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.models.database import User
from api.services.auth import get_current_user, get_supabase_auth, SupabaseAuth


router = APIRouter()


class UserResponse(BaseModel):
    """User data response."""
    id: str
    email: str
    full_name: str | None
    subscription_tier: str
    subscription_status: str
    telegram_connected: bool
    telegram_alerts_enabled: bool

    class Config:
        from_attributes = True


class TelegramConnectResponse(BaseModel):
    """Response with Telegram connect token."""
    token: str
    bot_username: str
    instructions: str


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    user: User = Depends(get_current_user),
):
    """
    Get the current authenticated user's information.

    Requires a valid JWT token in the Authorization header.
    """
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        subscription_tier=user.subscription_tier,
        subscription_status=user.subscription_status,
        telegram_connected=user.telegram_chat_id is not None,
        telegram_alerts_enabled=user.telegram_alerts_enabled,
    )


@router.post("/telegram/connect", response_model=TelegramConnectResponse)
async def generate_telegram_connect_token(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    auth: SupabaseAuth = Depends(get_supabase_auth),
):
    """
    Generate a token to connect Telegram account.

    The user sends this token to the Telegram bot with /connect <token>
    to link their Telegram account.
    """
    token = auth.generate_telegram_connect_token(db, user.id)

    return TelegramConnectResponse(
        token=token,
        bot_username="kickstat_bot",  # Update with actual bot username
        instructions="Envoyez /connect {} au bot @kickstat_bot sur Telegram".format(token),
    )


@router.delete("/telegram")
async def disconnect_telegram(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    auth: SupabaseAuth = Depends(get_supabase_auth),
):
    """
    Disconnect Telegram from the user's account.
    """
    success = auth.unlink_telegram_account(db, user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to disconnect Telegram",
        )

    return {"message": "Telegram disconnected successfully"}

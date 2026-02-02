"""
FastAPI dependencies for authentication.

Use these in your endpoint functions to require authentication.
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database import User
from .supabase import get_supabase_auth, SupabaseAuth


# Security scheme for JWT bearer tokens
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    auth: SupabaseAuth = Depends(get_supabase_auth),
) -> User:
    """
    Get the current authenticated user.

    Raises HTTPException 401 if not authenticated.

    Usage:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"email": user.email}
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify the token
    user_data = auth.get_user_from_token(credentials.credentials)

    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Sync user to local database
    user = auth.sync_user_to_db(db, user_data)

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
    auth: SupabaseAuth = Depends(get_supabase_auth),
) -> Optional[User]:
    """
    Get the current user if authenticated, None otherwise.

    Useful for endpoints that behave differently for authenticated users.

    Usage:
        @app.get("/opportunities")
        async def get_opportunities(user: Optional[User] = Depends(get_current_user_optional)):
            if user and user.subscription_tier == "pro":
                return full_opportunities
            return limited_opportunities
    """
    if not credentials:
        return None

    # Verify the token
    user_data = auth.get_user_from_token(credentials.credentials)

    if not user_data:
        return None

    # Sync user to local database
    user = auth.sync_user_to_db(db, user_data)

    return user


async def require_subscription(
    user: User = Depends(get_current_user),
) -> User:
    """
    Require the user to have an active subscription (basic or pro).

    Raises HTTPException 403 if no active subscription.

    Usage:
        @app.get("/premium-content")
        async def premium_route(user: User = Depends(require_subscription)):
            return {"content": "Premium stuff"}
    """
    if user.subscription_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required",
        )

    if user.subscription_tier not in ("basic", "pro", "premium"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Subscription tier required",
        )

    return user


async def require_pro_subscription(
    user: User = Depends(get_current_user),
) -> User:
    """
    Require the user to have an active Pro subscription.

    Usage:
        @app.get("/api-access")
        async def api_route(user: User = Depends(require_pro_subscription)):
            return {"api_key": "..."}
    """
    if user.subscription_status != "active" or user.subscription_tier != "pro":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pro subscription required",
        )

    return user


def check_match_access(user: User, match_id: int, db: Session) -> bool:
    """
    Check if a user has access to a specific match's full predictions.

    Access is granted if:
    - User has an active subscription (basic or pro)
    - User has purchased this specific match

    Args:
        user: The authenticated user
        match_id: The match ID to check access for
        db: Database session

    Returns:
        True if user has access, False otherwise
    """
    from app.models.database import MatchPurchase

    # Premium/Pro/Basic subscribers have full access
    if user.subscription_status == "active" and user.subscription_tier in ("basic", "pro", "premium"):
        return True

    # Check for individual match purchase
    purchase = (
        db.query(MatchPurchase)
        .filter(
            MatchPurchase.user_id == user.id,
            MatchPurchase.match_id == match_id,
            MatchPurchase.status == "completed",
        )
        .first()
    )

    return purchase is not None

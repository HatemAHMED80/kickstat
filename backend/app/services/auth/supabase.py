"""
Supabase Authentication Service

Handles JWT validation, user sync, and Supabase client operations.
"""

import secrets
from datetime import datetime
from typing import Optional

import httpx
from jose import jwt, JWTError
from loguru import logger
from sqlalchemy.orm import Session

from app.core import get_settings
from app.models.database import User

settings = get_settings()


class SupabaseAuth:
    """Supabase authentication client."""

    def __init__(self):
        self.url = settings.supabase_url
        self.anon_key = settings.supabase_anon_key
        self.service_role_key = settings.supabase_service_role_key
        self.jwt_secret = settings.supabase_jwt_secret

        # HTTP client for Supabase API calls
        self.client = httpx.Client(
            base_url=self.url,
            headers={
                "apikey": self.service_role_key,
                "Authorization": f"Bearer {self.service_role_key}",
            },
            timeout=30.0,
        )

    def verify_token(self, token: str) -> Optional[dict]:
        """
        Verify a Supabase JWT token and return the payload.

        Args:
            token: The JWT token from the Authorization header

        Returns:
            The decoded token payload if valid, None otherwise
        """
        try:
            # Decode and verify the JWT
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
            return payload
        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            return None

    def get_user_from_token(self, token: str) -> Optional[dict]:
        """
        Get user info from a valid token.

        Returns user dict with: id, email, user_metadata
        """
        payload = self.verify_token(token)
        if not payload:
            return None

        return {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "user_metadata": payload.get("user_metadata", {}),
        }

    def sync_user_to_db(self, db: Session, user_data: dict) -> User:
        """
        Sync a Supabase user to the local database.

        Creates the user if they don't exist, updates if they do.

        Args:
            db: SQLAlchemy session
            user_data: Dict with id, email, user_metadata

        Returns:
            The User model instance
        """
        user_id = user_data["id"]
        email = user_data["email"]
        metadata = user_data.get("user_metadata", {})

        # Check if user exists
        user = db.query(User).filter(User.id == user_id).first()

        if user:
            # Update existing user
            user.email = email
            user.full_name = metadata.get("full_name", user.full_name)
            user.last_login_at = datetime.utcnow()
            user.updated_at = datetime.utcnow()
        else:
            # Create new user
            user = User(
                id=user_id,
                email=email,
                full_name=metadata.get("full_name"),
                subscription_tier="free",
                subscription_status="inactive",
                telegram_alerts_enabled=False,
                min_edge_threshold=5.0,
                alert_hours_before=24,
                preferred_leagues=[61],  # Default to Ligue 1
                created_at=datetime.utcnow(),
                last_login_at=datetime.utcnow(),
            )
            db.add(user)

        db.commit()
        db.refresh(user)

        logger.info(f"User synced: {email} (id={user_id})")
        return user

    def generate_telegram_connect_token(self, db: Session, user_id: str) -> str:
        """
        Generate a unique token for connecting Telegram account.

        The user sends this token to the Telegram bot to link their account.

        Args:
            db: SQLAlchemy session
            user_id: The user's Supabase ID

        Returns:
            A unique 32-character token
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User not found: {user_id}")

        # Generate a secure random token
        token = secrets.token_urlsafe(24)

        # Store it temporarily
        user.telegram_connect_token = token
        user.updated_at = datetime.utcnow()
        db.commit()

        return token

    def link_telegram_account(
        self, db: Session, token: str, chat_id: str, username: Optional[str] = None
    ) -> Optional[User]:
        """
        Link a Telegram account to a user using the connect token.

        Called by the Telegram bot when a user sends /connect <token>.

        Args:
            db: SQLAlchemy session
            token: The connect token from the user
            chat_id: The Telegram chat ID
            username: Optional Telegram username

        Returns:
            The User if found and linked, None otherwise
        """
        user = db.query(User).filter(User.telegram_connect_token == token).first()

        if not user:
            logger.warning(f"Invalid Telegram connect token: {token[:8]}...")
            return None

        # Link the account
        user.telegram_chat_id = chat_id
        user.telegram_username = username
        user.telegram_connect_token = None  # Clear the token
        user.telegram_alerts_enabled = True  # Enable by default
        user.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(user)

        logger.info(f"Telegram linked for user {user.email}: chat_id={chat_id}")
        return user

    def unlink_telegram_account(self, db: Session, user_id: str) -> bool:
        """
        Unlink a Telegram account from a user.

        Args:
            db: SQLAlchemy session
            user_id: The user's Supabase ID

        Returns:
            True if successful
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        user.telegram_chat_id = None
        user.telegram_username = None
        user.telegram_alerts_enabled = False
        user.telegram_connect_token = None
        user.updated_at = datetime.utcnow()

        db.commit()

        logger.info(f"Telegram unlinked for user {user.email}")
        return True

    def get_supabase_user(self, user_id: str) -> Optional[dict]:
        """
        Fetch user data directly from Supabase Admin API.

        Args:
            user_id: The Supabase user ID

        Returns:
            User data dict or None
        """
        try:
            response = self.client.get(f"/auth/v1/admin/users/{user_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch Supabase user {user_id}: {e}")
            return None

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Singleton instance
_supabase_auth: Optional[SupabaseAuth] = None


def get_supabase_auth() -> SupabaseAuth:
    """Get or create the SupabaseAuth singleton."""
    global _supabase_auth
    if _supabase_auth is None:
        _supabase_auth = SupabaseAuth()
    return _supabase_auth

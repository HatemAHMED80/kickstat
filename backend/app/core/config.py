"""
Application configuration using pydantic-settings.
"""

from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars not defined here
    )

    # Application
    environment: str = "development"
    debug: bool = True
    secret_key: str = "change-me-in-production"
    api_v1_prefix: str = "/api/v1"

    # Database (use SQLite by default for simplicity)
    database_url: str = "sqlite:///./data/kickstat.db"
    redis_url: str = "redis://localhost:6379/0"

    # CORS (add frontend_url and common origins)
    cors_origins: List[str] = [
        "http://localhost:3000",
        "https://kickstat.vercel.app",
        "https://*.vercel.app",
    ]

    # API Keys
    api_football_key: str = ""
    api_football_host: str = "v3.football.api-sports.io"
    openweathermap_api_key: str = ""

    # ML
    mlflow_tracking_uri: str = "sqlite:///mlflow.db"
    model_version: str = "latest"

    # Scraping
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    transfermarkt_rate_limit: int = 10
    understat_rate_limit: int = 20

    # Competition IDs (API-Football)
    ligue1_id: int = 61
    coupe_de_france_id: int = 66
    trophee_champions_id: int = 65

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_basic_price_id: str = ""
    stripe_pro_price_id: str = ""
    stripe_premium_price_id: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_webhook_url: str = ""

    # Frontend URL (for redirects)
    frontend_url: str = "http://localhost:3000"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

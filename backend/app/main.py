"""
Football Prediction System - FastAPI Application
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core import get_settings, init_db
from app.api.v1 import router as api_v1_router

settings = get_settings()


def run_background_sync():
    """Run sync in background thread."""
    import time
    time.sleep(5)  # Wait for API to be fully ready

    logger.info("Starting background sync for all leagues...")
    try:
        from scripts.sync_football_data import sync_fixtures
        leagues = ["ligue_1", "premier_league", "la_liga", "bundesliga", "serie_a"]
        for league in leagues:
            try:
                logger.info(f"Syncing {league}...")
                sync_fixtures(league)
                time.sleep(2)  # Small delay between leagues to avoid rate limits
            except Exception as e:
                logger.error(f"Failed to sync {league}: {e}")
        logger.info("Background sync completed for all leagues!")
    except Exception as e:
        logger.error(f"Background sync failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting Football Prediction System...")
    logger.info(f"Environment: {settings.environment}")

    # Initialize database tables
    logger.info("Initializing database tables...")
    init_db()

    # Start background sync in a separate thread (non-blocking)
    import threading
    sync_thread = threading.Thread(target=run_background_sync, daemon=True)
    sync_thread.start()
    logger.info("Background sync thread started - API is ready!")

    yield
    logger.info("Shutting down Football Prediction System...")


app = FastAPI(
    title="Football Prediction API",
    description="API de prédiction de matchs de football - Ligue 1 & Coupes Françaises",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS - allow all Vercel preview deployments and localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://kickstat.vercel.app"],
    allow_origin_regex=r"(https://.*\.vercel\.app|http://localhost:\d+)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(api_v1_router, prefix=settings.api_v1_prefix)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.post("/admin/sync")
async def sync_real_data(secret: str, league: str = "ligue_1"):
    """
    Sync real data from Football-Data.org + The Odds API.

    Args:
        secret: Admin secret key
        league: League to sync (ligue_1, premier_league, la_liga, bundesliga, serie_a)
    """
    if secret != settings.secret_key:
        return {"error": "Invalid secret key"}

    try:
        from scripts.sync_football_data import sync_fixtures
        result = sync_fixtures(league)
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return {"status": "error", "message": str(e)}

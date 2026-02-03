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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting Football Prediction System...")
    logger.info(f"Environment: {settings.environment}")

    # Initialize database tables
    logger.info("Initializing database tables...")
    init_db()

    # Auto-seed if database is empty (for Render's ephemeral filesystem)
    from app.core.database import SessionLocal
    from app.models.database import Team
    db = SessionLocal()
    try:
        team_count = db.query(Team).count()
        if team_count == 0:
            logger.info("Database is empty, seeding with demo data...")
            from scripts.seed_data import seed_database
            seed_database()
            logger.info("Database seeded successfully!")
    except Exception as e:
        logger.warning(f"Could not check/seed database: {e}")
    finally:
        db.close()

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
    allow_origins=["http://localhost:3000", "http://localhost:3001", "https://kickstat.vercel.app"],
    allow_origin_regex=r"https://.*\.vercel\.app",
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


@app.post("/admin/seed")
async def seed_database(secret: str):
    """
    Seed the database with demo data.
    Requires secret key for protection.
    """
    if secret != settings.secret_key:
        return {"error": "Invalid secret key"}

    try:
        from scripts.seed_data import seed_database as run_seed
        run_seed()
        return {"status": "success", "message": "Database seeded successfully"}
    except Exception as e:
        logger.error(f"Seed failed: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/admin/sync")
async def sync_real_data(secret: str):
    """
    Sync real data from API-Football.
    Fetches upcoming Ligue 1 fixtures and odds.
    """
    if secret != settings.secret_key:
        return {"error": "Invalid secret key"}

    try:
        from scripts.sync_real_data import sync_fixtures
        result = sync_fixtures()
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return {"status": "error", "message": str(e)}

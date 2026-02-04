"""
Admin endpoints for triggering sync and maintenance tasks.
"""

import asyncio
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from loguru import logger

from app.core import get_settings

settings = get_settings()

router = APIRouter()

# Simple secret key for admin endpoints (use SECRET_KEY from settings)
ADMIN_SECRET = settings.secret_key


def verify_admin_key(x_admin_key: str = Header(...)):
    """Verify admin API key."""
    if x_admin_key != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    return True


def run_sync(league: str):
    """Run sync in background."""
    import subprocess
    import sys

    logger.info(f"Starting sync for league: {league}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "scripts.sync_football_data", "--league", league],
            capture_output=True,
            text=True,
            timeout=300,  # 5 min timeout
            cwd="/opt/render/project/src/backend" if settings.environment == "production" else None
        )
        logger.info(f"Sync completed for {league}")
        logger.info(f"stdout: {result.stdout[-2000:] if result.stdout else 'none'}")
        if result.stderr:
            logger.warning(f"stderr: {result.stderr[-1000:]}")
    except subprocess.TimeoutExpired:
        logger.error(f"Sync timeout for {league}")
    except Exception as e:
        logger.error(f"Sync failed for {league}: {e}")


@router.post("/sync")
async def trigger_sync(
    background_tasks: BackgroundTasks,
    league: str = "all",
    x_admin_key: str = Header(...),
):
    """
    Trigger data sync for specified league.

    Requires X-Admin-Key header with the secret key.

    Args:
        league: ligue_1, premier_league, la_liga, bundesliga, serie_a, or all
    """
    verify_admin_key(x_admin_key)

    valid_leagues = ["ligue_1", "premier_league", "la_liga", "bundesliga", "serie_a", "all"]
    if league not in valid_leagues:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid league. Must be one of: {', '.join(valid_leagues)}"
        )

    # Run sync in background
    background_tasks.add_task(run_sync, league)

    return {
        "status": "started",
        "message": f"Sync started for {league}",
        "note": "Check logs for progress"
    }


@router.get("/health")
async def admin_health():
    """Health check endpoint."""
    return {"status": "ok", "environment": settings.environment}

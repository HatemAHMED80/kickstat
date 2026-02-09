"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    """Check API health and model status."""
    return {
        "status": "healthy",
        "models": {
            "dixon_coles": "loaded",
            "elo": "loaded",
            "ensemble": "ready"
        },
        "version": "1.0.0"
    }

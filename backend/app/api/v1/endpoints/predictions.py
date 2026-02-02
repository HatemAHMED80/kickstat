"""
Predictions API endpoints.
"""

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SimulationRequest(BaseModel):
    """Request body for custom prediction simulation."""

    home_team_id: int
    away_team_id: int
    competition_type: str = "league"  # league or cup
    neutral_venue: bool = False
    home_injuries: Optional[list[int]] = None  # Player IDs
    away_injuries: Optional[list[int]] = None


@router.post("/simulate")
async def simulate_prediction(request: SimulationRequest):
    """Run a custom prediction simulation with specified parameters."""
    # TODO: Implement ML model inference
    return {
        "request": request.model_dump(),
        "prediction": None,
        "message": "Endpoint ready - ML model integration pending",
    }


@router.get("/accuracy")
async def get_model_accuracy():
    """Get model accuracy statistics."""
    # TODO: Implement accuracy tracking
    return {
        "overall_accuracy": None,
        "by_competition": {},
        "message": "Endpoint ready - accuracy tracking pending",
    }

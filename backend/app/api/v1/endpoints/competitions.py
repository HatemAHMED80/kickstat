"""
Competitions API endpoints.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_competitions():
    """List all tracked competitions."""
    # TODO: Implement database query
    return {
        "competitions": [
            {"id": 61, "name": "Ligue 1", "type": "league"},
            {"id": 66, "name": "Coupe de France", "type": "cup"},
            {"id": 65, "name": "Trophée des Champions", "type": "cup"},
        ],
        "message": "Static data - database integration pending",
    }


@router.get("/{competition_id}/standings")
async def get_standings(competition_id: int):
    """Get current standings for a competition."""
    # TODO: Implement database query
    return {
        "competition_id": competition_id,
        "standings": [],
        "message": "Endpoint ready - database integration pending",
    }


@router.get("/{competition_id}/matches")
async def get_competition_matches(competition_id: int, matchday: int = None):
    """Get matches for a competition, optionally filtered by matchday."""
    # TODO: Implement database query
    return {
        "competition_id": competition_id,
        "matchday": matchday,
        "matches": [],
        "message": "Endpoint ready - database integration pending",
    }

"""
Teams API endpoints.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_teams():
    """List all tracked teams."""
    # TODO: Implement database query
    return {"teams": [], "message": "Endpoint ready - database integration pending"}


@router.get("/{team_id}")
async def get_team(team_id: int):
    """Get team details and current stats."""
    # TODO: Implement database query
    return {"team_id": team_id, "message": "Endpoint ready - database integration pending"}


@router.get("/{team_id}/players")
async def get_team_players(team_id: int):
    """Get team roster with availability status."""
    # TODO: Implement database query
    return {"team_id": team_id, "players": [], "message": "Endpoint ready - database integration pending"}


@router.get("/{team_id}/form")
async def get_team_form(team_id: int, last_n: int = 5):
    """Get team's recent form (last N matches)."""
    # TODO: Implement form calculation
    return {"team_id": team_id, "form": None, "message": "Endpoint ready - database integration pending"}

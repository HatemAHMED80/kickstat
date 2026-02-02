"""
Odds and Edge endpoints.

Returns betting opportunities with edge calculations.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database import User, Match, EdgeCalculation, MatchOdds
from app.services.auth import get_current_user_optional, check_match_access
from app.services.odds import get_edge_calculator


router = APIRouter()


class TeamInfo(BaseModel):
    """Basic team information."""
    id: int
    name: str
    short_name: str | None
    logo_url: str | None


class MatchInfo(BaseModel):
    """Match information for opportunities."""
    id: int
    home_team: TeamInfo
    away_team: TeamInfo
    kickoff: datetime
    competition_name: str | None
    matchday: int | None


class OpportunityResponse(BaseModel):
    """Single betting opportunity."""
    id: int
    match: MatchInfo
    market: str
    market_display: str
    model_probability: float
    bookmaker_probability: float
    edge_percentage: float
    best_odds: float
    bookmaker_name: str
    risk_level: str
    confidence: float
    kelly_stake: float | None


class OpportunitiesListResponse(BaseModel):
    """List of opportunities."""
    opportunities: list[OpportunityResponse]
    total: int
    free_preview_count: int


class MatchOddsResponse(BaseModel):
    """Odds for a specific match."""
    match_id: int
    bookmaker: str
    home_win_odds: float | None
    draw_odds: float | None
    away_win_odds: float | None
    over_25_odds: float | None
    under_25_odds: float | None
    btts_yes_odds: float | None
    btts_no_odds: float | None
    home_win_implied: float | None
    draw_implied: float | None
    away_win_implied: float | None
    fetched_at: datetime


# Market display names
MARKET_NAMES = {
    "1x2_home": "Victoire domicile",
    "1x2_draw": "Match nul",
    "1x2_away": "Victoire extérieur",
    "over_25": "Plus de 2.5 buts",
    "under_25": "Moins de 2.5 buts",
    "btts_yes": "Les deux équipes marquent",
    "btts_no": "Clean sheet",
}


@router.get("/opportunities", response_model=OpportunitiesListResponse)
async def get_opportunities(
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
    risk_level: Optional[str] = Query(None, description="Filter by risk: safe, medium, risky"),
    min_edge: float = Query(5.0, description="Minimum edge percentage"),
    limit: int = Query(20, le=50),
):
    """
    Get betting opportunities ranked by edge.

    Free users see limited preview (first 3 opportunities).
    Subscribers see all opportunities.
    """
    calculator = get_edge_calculator()

    opportunities = calculator.get_top_opportunities(
        db=db,
        limit=limit,
        min_edge=min_edge,
        risk_level=risk_level,
    )

    # Determine access level
    is_subscriber = (
        user is not None
        and user.subscription_status == "active"
        and user.subscription_tier in ("basic", "pro")
    )

    free_preview_count = 3

    # Build response
    result = []
    for edge in opportunities:
        # Get match with teams
        match = (
            db.query(Match)
            .filter(Match.id == edge.match_id)
            .first()
        )

        if not match:
            continue

        # Check if this should be visible
        index = len(result)
        is_visible = is_subscriber or index < free_preview_count

        if not is_visible:
            # Still include in count but don't show details
            continue

        result.append(
            OpportunityResponse(
                id=edge.id,
                match=MatchInfo(
                    id=match.id,
                    home_team=TeamInfo(
                        id=match.home_team.id,
                        name=match.home_team.name,
                        short_name=match.home_team.short_name,
                        logo_url=match.home_team.logo_url,
                    ),
                    away_team=TeamInfo(
                        id=match.away_team.id,
                        name=match.away_team.name,
                        short_name=match.away_team.short_name,
                        logo_url=match.away_team.logo_url,
                    ),
                    kickoff=match.kickoff,
                    competition_name=match.competition.name if match.competition else None,
                    matchday=match.matchday,
                ),
                market=edge.market,
                market_display=MARKET_NAMES.get(edge.market, edge.market),
                model_probability=edge.model_probability,
                bookmaker_probability=edge.bookmaker_probability,
                edge_percentage=edge.edge_percentage,
                best_odds=edge.best_odds,
                bookmaker_name=edge.bookmaker_name,
                risk_level=edge.risk_level,
                confidence=edge.confidence,
                kelly_stake=edge.kelly_stake,
            )
        )

    return OpportunitiesListResponse(
        opportunities=result,
        total=len(opportunities),
        free_preview_count=free_preview_count if not is_subscriber else 0,
    )


@router.get("/matches/{match_id}/edges")
async def get_match_edges(
    match_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Get all edge calculations for a specific match.

    Requires subscription or match purchase for full access.
    """
    # Check match exists
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    # Check access
    has_access = False
    if user:
        has_access = check_match_access(user, match_id, db)

    # Get edges
    edges = (
        db.query(EdgeCalculation)
        .filter(EdgeCalculation.match_id == match_id)
        .order_by(EdgeCalculation.edge_percentage.desc())
        .all()
    )

    if not has_access:
        # Return limited info for non-subscribers
        return {
            "match_id": match_id,
            "has_access": False,
            "edges_count": len(edges),
            "best_edge": edges[0].edge_percentage if edges else None,
            "preview": [
                {
                    "market": e.market,
                    "market_display": MARKET_NAMES.get(e.market, e.market),
                    "edge_percentage": e.edge_percentage,
                    "risk_level": e.risk_level,
                }
                for e in edges[:2]  # Show first 2 as teaser
            ],
            "message": "Abonnez-vous ou achetez ce match pour voir l'analyse complète",
        }

    # Full access
    return {
        "match_id": match_id,
        "has_access": True,
        "edges": [
            {
                "id": e.id,
                "market": e.market,
                "market_display": MARKET_NAMES.get(e.market, e.market),
                "model_probability": e.model_probability,
                "bookmaker_probability": e.bookmaker_probability,
                "edge_percentage": e.edge_percentage,
                "best_odds": e.best_odds,
                "bookmaker_name": e.bookmaker_name,
                "risk_level": e.risk_level,
                "confidence": e.confidence,
                "kelly_stake": e.kelly_stake,
            }
            for e in edges
        ],
    }


@router.get("/matches/{match_id}/odds", response_model=list[MatchOddsResponse])
async def get_match_odds(
    match_id: int,
    db: Session = Depends(get_db),
):
    """
    Get all bookmaker odds for a specific match.

    This is public data, no subscription required.
    """
    # Check match exists
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    odds = (
        db.query(MatchOdds)
        .filter(MatchOdds.match_id == match_id)
        .all()
    )

    return [
        MatchOddsResponse(
            match_id=o.match_id,
            bookmaker=o.bookmaker,
            home_win_odds=o.home_win_odds,
            draw_odds=o.draw_odds,
            away_win_odds=o.away_win_odds,
            over_25_odds=o.over_25_odds,
            under_25_odds=o.under_25_odds,
            btts_yes_odds=o.btts_yes_odds,
            btts_no_odds=o.btts_no_odds,
            home_win_implied=o.home_win_implied,
            draw_implied=o.draw_implied,
            away_win_implied=o.away_win_implied,
            fetched_at=o.fetched_at,
        )
        for o in odds
    ]

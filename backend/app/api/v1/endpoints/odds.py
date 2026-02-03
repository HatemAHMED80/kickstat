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
from app.core import get_settings
from app.models.database import User, Match, EdgeCalculation, MatchOdds, Prediction
from app.services.auth import get_current_user_optional, check_match_access
from app.services.odds import get_edge_calculator
from app.services.ml.dixon_coles import get_dixon_coles_model

settings = get_settings()


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


@router.get("/matches/{match_id}/analysis")
async def get_match_analysis(
    match_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Get complete Dixon-Coles analysis for a match.

    Includes:
    - Score matrix with probabilities
    - All markets (1X2, O/U, BTTS, exact scores)
    - Expected goals
    - Edge calculations
    - Recommended bets
    """
    # Check match exists
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    # Get prediction
    prediction = db.query(Prediction).filter(Prediction.match_id == match_id).first()

    # Get edges
    edges = (
        db.query(EdgeCalculation)
        .filter(EdgeCalculation.match_id == match_id)
        .order_by(EdgeCalculation.edge_percentage.desc())
        .all()
    )

    # Get odds
    odds = db.query(MatchOdds).filter(MatchOdds.match_id == match_id).first()

    # Get Dixon-Coles predictions
    model = get_dixon_coles_model()
    dc_predictions = model.predict_all_markets(
        match.home_team.name,
        match.away_team.name
    )

    # Check access - in development, allow all
    is_dev = settings.environment == "development"
    is_subscriber = (
        user is not None
        and user.subscription_status == "active"
    )
    has_access = is_dev or is_subscriber

    # Build response
    response = {
        "match": {
            "id": match.id,
            "home_team": {
                "id": match.home_team.id,
                "name": match.home_team.name,
                "short_name": match.home_team.short_name,
                "logo_url": match.home_team.logo_url,
            },
            "away_team": {
                "id": match.away_team.id,
                "name": match.away_team.name,
                "short_name": match.away_team.short_name,
                "logo_url": match.away_team.logo_url,
            },
            "kickoff": match.kickoff.isoformat(),
            "competition": match.competition.name if match.competition else "Ligue 1",
            "matchday": match.matchday,
        },
        "has_access": has_access,
    }

    if has_access:
        # Full analysis
        response["analysis"] = {
            "expected_goals": dc_predictions.get("expected_goals", {}),
            "probabilities": {
                "1x2": dc_predictions.get("1x2", {}),
                "over_under": dc_predictions.get("over_under", {}),
                "btts": dc_predictions.get("btts", {}),
            },
            "exact_scores": dc_predictions.get("exact_scores", [])[:10],
            "asian_handicaps": dc_predictions.get("asian_handicap", {}),
            "score_matrix": dc_predictions.get("score_matrix", []),
        }

        response["edges"] = [
            {
                "market": e.market,
                "market_display": MARKET_NAMES.get(e.market, e.market),
                "model_probability": round(e.model_probability * 100, 1),
                "bookmaker_probability": round(e.bookmaker_probability * 100, 1),
                "edge_percentage": round(e.edge_percentage, 1),
                "best_odds": e.best_odds,
                "risk_level": e.risk_level,
                "kelly_stake": round(e.kelly_stake * 100, 1) if e.kelly_stake else 0,
                "confidence": round(e.confidence * 100, 1),
            }
            for e in edges
        ]

        response["odds"] = {
            "bookmaker": odds.bookmaker if odds else "N/A",
            "home_win": odds.home_win_odds if odds else None,
            "draw": odds.draw_odds if odds else None,
            "away_win": odds.away_win_odds if odds else None,
            "over_25": odds.over_25_odds if odds else None,
            "under_25": odds.under_25_odds if odds else None,
            "btts_yes": odds.btts_yes_odds if odds else None,
            "btts_no": odds.btts_no_odds if odds else None,
        }

        # Recommended bets (edges > 5%)
        response["recommendations"] = [
            {
                "market": e.market,
                "market_display": MARKET_NAMES.get(e.market, e.market),
                "edge": round(e.edge_percentage, 1),
                "odds": e.best_odds,
                "stake": f"{round(e.kelly_stake * 100, 1)}%" if e.kelly_stake else "1%",
                "risk": e.risk_level,
            }
            for e in edges if e.edge_percentage >= 5
        ]
    else:
        # Preview only
        response["preview"] = {
            "best_edge": round(edges[0].edge_percentage, 1) if edges else 0,
            "edges_count": len(edges),
            "expected_goals_total": round(
                dc_predictions.get("expected_goals", {}).get("total", 2.5), 2
            ),
        }
        response["message"] = "Abonnez-vous pour voir l'analyse complète"

    return response


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

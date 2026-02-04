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


# Market display names (French, consistent naming)
MARKET_NAMES = {
    # 1X2
    "1x2_home": "Victoire domicile",
    "1x2_draw": "Match nul",
    "1x2_away": "Victoire extérieur",
    # Over/Under
    "over_15": "Plus de 1.5 buts",
    "over_25": "Plus de 2.5 buts",
    "over_35": "Plus de 3.5 buts",
    "under_15": "Moins de 1.5 buts",
    "under_25": "Moins de 2.5 buts",
    "under_35": "Moins de 3.5 buts",
    # BTTS
    "btts_yes": "Les 2 équipes marquent",
    "btts_no": "Les 2 ne marquent pas",
    # Double Chance
    "double_1x": "1X (Dom ou Nul)",
    "double_x2": "X2 (Nul ou Ext)",
    "double_12": "12 (Pas de nul)",
    # Draw No Bet
    "dnb_home": "DNB Domicile",
    "dnb_away": "DNB Extérieur",
}


@router.get("/opportunities", response_model=OpportunitiesListResponse)
async def get_opportunities(
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
    risk_level: Optional[str] = Query(None, description="Filter by risk: safe, medium, risky"),
    competition: Optional[str] = Query(None, description="Filter by competition name"),
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
        limit=limit * 3 if competition else limit,  # Get more to filter
        min_edge=min_edge,
        risk_level=risk_level,
    )

    # Filter by competition if specified
    if competition:
        filtered_opportunities = []
        for edge in opportunities:
            match = db.query(Match).filter(Match.id == edge.match_id).first()
            if match and match.competition and match.competition.name == competition:
                filtered_opportunities.append(edge)
        opportunities = filtered_opportunities[:limit]

    # For MVP phase, give full access to everyone
    # TODO: Re-enable subscription check when payment is ready
    is_subscriber = True
    free_preview_count = 0

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


@router.get("/competitions")
async def get_competitions(db: Session = Depends(get_db)):
    """
    Get all available competitions with match counts.
    """
    from app.models.database import Competition
    from sqlalchemy import func

    # Get competitions with upcoming match counts
    competitions = db.query(Competition).all()

    result = []
    for comp in competitions:
        match_count = db.query(Match).filter(
            Match.competition_id == comp.id,
            Match.status == "scheduled"
        ).count()

        if match_count > 0:  # Only return competitions with upcoming matches
            result.append({
                "id": comp.id,
                "name": comp.name,
                "short_name": comp.short_name,
                "country": comp.country,
                "logo_url": comp.logo_url,
                "match_count": match_count,
            })

    # Sort by match count descending
    result.sort(key=lambda x: x["match_count"], reverse=True)

    return {"competitions": result}


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

    # For MVP phase, give full access to everyone
    # TODO: Re-enable subscription check when payment is ready
    has_access = True

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

    # For now, allow full analysis access to everyone (MVP phase)
    # TODO: Re-enable subscription check when payment is ready
    has_access = True

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
        # Calculate extended markets from score matrix
        import numpy as np
        matrix = np.array(dc_predictions.get("score_matrix", []))
        p1x2 = dc_predictions.get("1x2", {})

        # Double Chance
        double_chance = {
            "1x": round((p1x2.get("home_win", 0) + p1x2.get("draw", 0)) * 100, 1),
            "x2": round((p1x2.get("draw", 0) + p1x2.get("away_win", 0)) * 100, 1),
            "12": round((p1x2.get("home_win", 0) + p1x2.get("away_win", 0)) * 100, 1),
        }

        # Draw No Bet
        total_decisive = p1x2.get("home_win", 0) + p1x2.get("away_win", 0)
        draw_no_bet = {
            "home": round((p1x2.get("home_win", 0) / total_decisive * 100) if total_decisive > 0 else 50, 1),
            "away": round((p1x2.get("away_win", 0) / total_decisive * 100) if total_decisive > 0 else 50, 1),
        }

        # Clean Sheet & Win to Nil
        home_cs = float(np.sum(matrix[:, 0])) if len(matrix) > 0 else 0
        away_cs = float(np.sum(matrix[0, :])) if len(matrix) > 0 else 0
        home_wtn = float(np.sum(matrix[1:, 0])) if len(matrix) > 1 else 0
        away_wtn = float(np.sum(matrix[0, 1:])) if len(matrix) > 0 else 0

        clean_sheet = {
            "home": round(home_cs * 100, 1),
            "away": round(away_cs * 100, 1),
        }
        win_to_nil = {
            "home": round(home_wtn * 100, 1),
            "away": round(away_wtn * 100, 1),
        }

        # Team to Score
        team_scores = {
            "home": round((1 - home_cs) * 100, 1) if home_cs < 1 else 0,
            "away": round((1 - away_cs) * 100, 1) if away_cs < 1 else 0,
        }

        # Exact Total Goals
        exact_totals = {}
        for total in range(7):
            prob = sum(matrix[i, total-i] for i in range(max(0, total-10), min(total+1, 11))
                      if 0 <= total-i < 11 and i < len(matrix))
            exact_totals[str(total)] = round(float(prob) * 100, 1)

        # Odd/Even
        odd = sum(matrix[i, j] for i in range(min(11, len(matrix)))
                  for j in range(min(11, len(matrix[0]) if len(matrix) > 0 else 0)) if (i+j) % 2 == 1)
        even = sum(matrix[i, j] for i in range(min(11, len(matrix)))
                   for j in range(min(11, len(matrix[0]) if len(matrix) > 0 else 0)) if (i+j) % 2 == 0)
        odd_even = {
            "odd": round(float(odd) * 100, 1),
            "even": round(float(even) * 100, 1),
        }

        # Margin of Victory (Home)
        margin_home = {
            "by_1": round(float(sum(matrix[i, i-1] for i in range(1, min(11, len(matrix))))) * 100, 1),
            "by_2": round(float(sum(matrix[i, i-2] for i in range(2, min(11, len(matrix))))) * 100, 1),
            "by_3_plus": round(float(sum(matrix[i, j] for i in range(min(11, len(matrix)))
                              for j in range(min(11, len(matrix[0]) if len(matrix) > 0 else 0)) if i - j >= 3)) * 100, 1),
        }

        # Team Exact Goals
        home_exact = {str(g): round(float(np.sum(matrix[g, :])) * 100, 1) for g in range(min(5, len(matrix)))}
        away_exact = {str(g): round(float(np.sum(matrix[:, g])) * 100, 1) for g in range(min(5, len(matrix[0]) if len(matrix) > 0 else 0))}

        # Team Over Goals
        home_o05 = 1 - float(np.sum(matrix[0, :])) if len(matrix) > 0 else 0.5
        home_o15 = 1 - float(np.sum(matrix[0, :])) - float(np.sum(matrix[1, :])) if len(matrix) > 1 else 0.3
        away_o05 = 1 - float(np.sum(matrix[:, 0])) if len(matrix) > 0 else 0.5
        away_o15 = 1 - float(np.sum(matrix[:, 0])) - float(np.sum(matrix[:, 1])) if len(matrix) > 0 and len(matrix[0]) > 1 else 0.3

        team_overs = {
            "home_o05": round(home_o05 * 100, 1),
            "home_o15": round(home_o15 * 100, 1),
            "away_o05": round(away_o05 * 100, 1),
            "away_o15": round(away_o15 * 100, 1),
        }

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
            # Extended markets
            "double_chance": double_chance,
            "draw_no_bet": draw_no_bet,
            "clean_sheet": clean_sheet,
            "win_to_nil": win_to_nil,
            "team_scores": team_scores,
            "exact_totals": exact_totals,
            "odd_even": odd_even,
            "margin_home": margin_home,
            "home_exact_goals": home_exact,
            "away_exact_goals": away_exact,
            "team_overs": team_overs,
        }

        # Calculate edges from LIVE Dixon-Coles predictions (not stored DB values)
        # This ensures consistency between the table probabilities and recommended bets
        live_edges = []

        # Map of markets to odds and probabilities
        market_configs = [
            ("1x2_home", odds.home_win_odds if odds else None, p1x2.get("home_win", 0)),
            ("1x2_draw", odds.draw_odds if odds else None, p1x2.get("draw", 0)),
            ("1x2_away", odds.away_win_odds if odds else None, p1x2.get("away_win", 0)),
            ("over_25", odds.over_25_odds if odds else None, dc_predictions.get("over_under", {}).get("over_2.5", 0)),
            ("under_25", odds.under_25_odds if odds else None, dc_predictions.get("over_under", {}).get("under_2.5", 0)),
            ("btts_yes", odds.btts_yes_odds if odds else None, dc_predictions.get("btts", {}).get("btts_yes", 0)),
            ("btts_no", odds.btts_no_odds if odds else None, dc_predictions.get("btts", {}).get("btts_no", 0)),
        ]

        for market, market_odds, model_prob in market_configs:
            if market_odds and market_odds > 1 and model_prob > 0:
                book_prob = 1 / market_odds
                edge = ((model_prob - book_prob) / book_prob) * 100
                kelly = ((model_prob * market_odds - 1) / (market_odds - 1)) * 0.5 if edge > 0 else 0

                # Determine risk level based on probability
                if model_prob >= 0.6:
                    risk = "safe"
                elif model_prob >= 0.4:
                    risk = "medium"
                else:
                    risk = "risky"

                live_edges.append({
                    "market": market,
                    "market_display": MARKET_NAMES.get(market, market),
                    "model_probability": round(model_prob * 100, 1),
                    "bookmaker_probability": round(book_prob * 100, 1),
                    "edge_percentage": round(edge, 1),
                    "best_odds": market_odds,
                    "risk_level": risk,
                    "kelly_stake": round(kelly * 100, 1) if kelly > 0 else 0,
                    "confidence": round(model_prob * 100, 1),
                })

        # Sort by edge descending
        live_edges.sort(key=lambda x: x["edge_percentage"], reverse=True)
        response["edges"] = live_edges

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

        # Recommended bets (edges > 5%) - uses live calculations for consistency
        response["recommendations"] = [
            {
                "market": e["market"],
                "market_display": e["market_display"],
                "edge": e["edge_percentage"],
                "odds": e["best_odds"],
                "stake": f"{e['kelly_stake']}%" if e["kelly_stake"] > 0 else "1%",
                "risk": e["risk_level"],
            }
            for e in live_edges if e["edge_percentage"] >= 5
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

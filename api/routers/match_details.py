"""Detailed match information endpoint for complete match cards."""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.football_data_uk import load_historical_data
from src.models.features import MatchHistory, compute_form_features, compute_shots_features, compute_dominance_features

router = APIRouter()

# Global match history (will be loaded on startup)
match_history = None
history_loaded = False


class RecentMatchDetail(BaseModel):
    """Details of a recent match."""
    date: str
    opponent: str
    score: str  # e.g., "2-1"
    result: str  # "win", "draw", "loss"
    home_away: str  # "home" or "away"
    goals_scored: int
    goals_conceded: int
    clean_sheet: bool


class TeamFormStats(BaseModel):
    """Form statistics for a team."""
    ppg: float  # Points per game
    goals_scored_avg: float
    goals_conceded_avg: float
    shots_per_game: float
    shots_on_target_per_game: float
    shot_accuracy: float  # %
    corners_per_game: float
    fouls_per_game: float
    dominance_score: float  # 0-1
    recent_matches: List[RecentMatchDetail]


class HeadToHeadStats(BaseModel):
    """Head-to-head statistics."""
    total_matches: int
    home_wins: int
    draws: int
    away_wins: int
    avg_goals: float
    over_25_rate: float  # % of matches with >2.5 goals
    recent_results: List[dict]  # Last 5 H2H


class ModelInsights(BaseModel):
    """Model predictions and insights."""
    probabilities: dict  # {home, draw, away}
    market_probabilities: Optional[dict] = None
    edges: Optional[dict] = None  # Edge over market
    best_odds: Optional[dict] = None
    bookmakers: Optional[dict] = None
    model_strength: dict  # DC attack/defense parameters
    elo_ratings: dict  # {home, away, diff}


class OpportunityDetected(BaseModel):
    """Betting opportunity with positive edge."""
    market: str  # e.g., "Nice to win"
    edge_percent: float
    odds: float
    model_prob: float
    market_prob: float
    kelly_stake: float
    confidence: str  # "HIGH", "MEDIUM", "LOW"


class MatchDetailedCard(BaseModel):
    """Complete match information card."""
    # Basic info
    match_id: str
    league: str
    home_team: str
    away_team: str
    kickoff: str
    home_position: Optional[int] = None  # League position
    away_position: Optional[int] = None

    # Form & stats
    home_form: TeamFormStats
    away_form: TeamFormStats

    # H2H
    head_to_head: HeadToHeadStats

    # Model insights
    model_insights: ModelInsights

    # Opportunities
    opportunities: List[OpportunityDetected]

    # Additional markets
    over_under: Optional[dict] = None
    btts: Optional[dict] = None
    correct_score: Optional[dict] = None


def ensure_history_loaded():
    """Load historical match data for stats computation."""
    global match_history, history_loaded

    if not history_loaded or match_history is None:
        logger.info("Loading historical match data for stats...")
        # Load last 2 seasons for form calculation
        ligue1 = load_historical_data("ligue_1", [2023, 2024])
        pl = load_historical_data("premier_league", [2023, 2024])

        match_history = MatchHistory()
        for m in sorted(ligue1 + pl, key=lambda x: x["kickoff"]):
            match_history.add_match(m)

        history_loaded = True
        logger.info(f"Loaded {len(match_history.matches)} historical matches")


def get_team_form_stats(team: str, match_date: datetime, history: MatchHistory) -> TeamFormStats:
    """Compute detailed form statistics for a team."""
    recent_matches = history.get_team_matches(team, match_date, last_n=5)

    if not recent_matches:
        # Return defaults if no history
        return TeamFormStats(
            ppg=0,
            goals_scored_avg=0,
            goals_conceded_avg=0,
            shots_per_game=0,
            shots_on_target_per_game=0,
            shot_accuracy=0,
            corners_per_game=0,
            fouls_per_game=0,
            dominance_score=0.5,
            recent_matches=[],
        )

    # Compute form
    form_features = compute_form_features(team, [m[0] for m in recent_matches])
    shots_features = compute_shots_features(team, [m[0] for m in recent_matches])
    dom_features = compute_dominance_features(team, [m[0] for m in recent_matches])

    # Build recent match details
    recent_details = []
    for match, is_home in recent_matches:
        home_score = match["home_score"]
        away_score = match["away_score"]

        if is_home:
            goals_scored = home_score
            goals_conceded = away_score
            opponent = match["away_team"]
        else:
            goals_scored = away_score
            goals_conceded = home_score
            opponent = match["home_team"]

        if goals_scored > goals_conceded:
            result = "win"
        elif goals_scored == goals_conceded:
            result = "draw"
        else:
            result = "loss"

        recent_details.append(RecentMatchDetail(
            date=str(match["kickoff"])[:10],
            opponent=opponent,
            score=f"{goals_scored}-{goals_conceded}",
            result=result,
            home_away="home" if is_home else "away",
            goals_scored=goals_scored,
            goals_conceded=goals_conceded,
            clean_sheet=(goals_conceded == 0),
        ))

    return TeamFormStats(
        ppg=form_features["ppg"],
        goals_scored_avg=form_features["goals_for"],
        goals_conceded_avg=form_features["goals_against"],
        shots_per_game=shots_features["shots_per_game"],
        shots_on_target_per_game=shots_features["shots_on_target_per_game"],
        shot_accuracy=shots_features["shot_accuracy"] * 100,
        corners_per_game=dom_features["corners_per_game"],
        fouls_per_game=dom_features["fouls_per_game"],
        dominance_score=dom_features["dominance_score"],
        recent_matches=recent_details,
    )


def get_h2h_stats(home_team: str, away_team: str, match_date: datetime, history: MatchHistory) -> HeadToHeadStats:
    """Compute head-to-head statistics."""
    h2h_matches = history.get_h2h_matches(home_team, away_team, match_date, last_n=10)

    if not h2h_matches:
        return HeadToHeadStats(
            total_matches=0,
            home_wins=0,
            draws=0,
            away_wins=0,
            avg_goals=0,
            over_25_rate=0,
            recent_results=[],
        )

    home_wins = 0
    draws = 0
    away_wins = 0
    total_goals = 0
    over_25_count = 0

    recent_results = []
    for m in h2h_matches[:5]:  # Last 5 only for display
        is_home_at_home = m["home_team"] == home_team

        if is_home_at_home:
            home_score = m["home_score"]
            away_score = m["away_score"]
        else:
            home_score = m["away_score"]
            away_score = m["home_score"]

        if home_score > away_score:
            home_wins += 1
            result = "home_win"
        elif home_score == away_score:
            draws += 1
            result = "draw"
        else:
            away_wins += 1
            result = "away_win"

        match_total = m["home_score"] + m["away_score"]
        total_goals += match_total
        if match_total > 2:
            over_25_count += 1

        recent_results.append({
            "date": str(m["kickoff"])[:10],
            "score": f"{home_score}-{away_score}",
            "result": result,
        })

    return HeadToHeadStats(
        total_matches=len(h2h_matches),
        home_wins=home_wins,
        draws=draws,
        away_wins=away_wins,
        avg_goals=total_goals / len(h2h_matches),
        over_25_rate=(over_25_count / len(h2h_matches)) * 100,
        recent_results=recent_results,
    )


@router.get("/match/{match_id}/detailed", response_model=MatchDetailedCard)
async def get_match_detailed_card(match_id: str):
    """Get complete detailed match card with all stats and insights.

    Args:
        match_id: Format "home_team_vs_away_team_league_date"
    """
    ensure_history_loaded()

    # Parse match_id (simplified for now - in production, fetch from prediction endpoint)
    # This is a placeholder - the real implementation would fetch match details
    # from the predictions endpoint and enrich with historical stats

    raise HTTPException(
        status_code=501,
        detail="This endpoint is under construction. Use /predictions endpoint for now."
    )


@router.get("/health")
async def health_check():
    """Health check for match details service."""
    return {
        "status": "ok",
        "history_loaded": history_loaded,
        "total_matches": len(match_history.matches) if match_history else 0,
    }

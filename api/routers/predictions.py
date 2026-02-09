"""Predictions endpoints."""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from loguru import logger

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.football_data_uk import load_historical_data
from src.data.fixtures_api import fetch_today_fixtures, fetch_tomorrow_fixtures
from src.data.odds_api import OddsAPIClient, extract_best_odds, remove_margin
from src.models.dixon_coles import DixonColesModel, MatchResult
from src.models.elo import EloRating
from src.models.features import MatchHistory

router = APIRouter()

# Global model instances (will be loaded on startup)
dc_model = None
elo_model = None
match_history = None
models_trained = False

class TeamRecentMatch(BaseModel):
    """Recent match details for a team."""
    date: str
    opponent: str
    score: str
    result: str  # "win", "draw", "loss"
    home_away: str
    clean_sheet: bool


class TeamStats(BaseModel):
    """Detailed team statistics."""
    ppg: float
    goals_scored_avg: float
    goals_conceded_avg: float
    shots_per_game: float
    shots_on_target_per_game: float
    shot_accuracy: float
    corners_per_game: float
    dominance_score: float
    recent_form: str  # e.g., "🟢🟢🔴🟡🟢"
    recent_matches: List[TeamRecentMatch]


class H2HStats(BaseModel):
    """Head-to-head statistics."""
    total_matches: int
    home_wins: int
    draws: int
    away_wins: int
    avg_goals: float
    over_25_rate: float
    recent_results: List[dict]


class MatchPrediction(BaseModel):
    """Match prediction response with complete stats."""
    match_id: str
    league: str
    home_team: str
    away_team: str
    kickoff: str
    model_probs: dict  # {home: float, draw: float, away: float}
    best_odds: Optional[dict] = None  # {home: float, draw: float, away: float}
    bookmaker: Optional[dict] = None  # {home: str, draw: str, away: str}
    edge: Optional[dict] = None  # {home: float, draw: float, away: float}
    recommended_bet: Optional[str] = None
    kelly_stake: Optional[float] = None
    segment: str  # e.g., "Underdogs (30-45%)"

    # Quality metrics (new)
    quality_score: Optional[float] = None  # Composite score: edge × sqrt(probability)
    confidence_badge: Optional[str] = None  # "SAFE", "VALUE", "RISKY"

    # Additional markets
    over_under_15: Optional[dict] = None
    over_under_15_odds: Optional[dict] = None
    over_under_15_edge: Optional[dict] = None
    over_under: Optional[dict] = None
    over_under_odds: Optional[dict] = None
    over_under_edge: Optional[dict] = None
    over_under_35: Optional[dict] = None
    over_under_35_odds: Optional[dict] = None
    over_under_35_edge: Optional[dict] = None
    btts: Optional[dict] = None
    btts_odds: Optional[dict] = None
    btts_edge: Optional[dict] = None
    correct_score: Optional[dict] = None

    # Detailed stats (new)
    home_stats: Optional[TeamStats] = None
    away_stats: Optional[TeamStats] = None
    h2h_stats: Optional[H2HStats] = None
    model_strength: Optional[dict] = None  # DC attack/defense parameters
    elo_ratings: Optional[dict] = None  # {home, away, diff}

def get_probability_segment(prob: float) -> str:
    """Get segment label for a probability."""
    if prob < 0.30:
        return "Longshots (0-30%)"
    elif prob < 0.45:
        return "Underdogs (30-45%)"
    elif prob < 0.55:
        return "Coin-flip (45-55%)"
    elif prob < 0.65:
        return "Slight fav (55-65%)"
    elif prob < 0.75:
        return "Favorites (65-75%)"
    else:
        return "Strong fav (75%+)"

def calculate_edge(model_prob: float, fair_prob: float) -> float:
    """Calculate edge percentage."""
    if fair_prob <= 0:
        return 0.0
    return ((model_prob - fair_prob) / fair_prob) * 100

def kelly_criterion(prob: float, odds: float) -> float:
    """Calculate Kelly stake as % of bankroll."""
    if odds <= 1.0:
        return 0.0
    q = 1 - prob
    kelly = (prob * (odds - 1) - q) / (odds - 1)
    # Fractional Kelly (25% of full Kelly for safety)
    return max(0, kelly * 0.25 * 100)


def calculate_quality_score(edge: float, probability: float) -> float:
    """Calculate quality score: edge × sqrt(probability).

    This favors bets with both good edge AND reasonable win probability.
    Examples:
    - Edge 15%, Prob 25% → 15 × 0.5 = 7.5
    - Edge 5%, Prob 60% → 5 × 0.77 = 3.9
    """
    import math
    return edge * math.sqrt(probability)


def get_confidence_badge(edge: float, probability: float) -> str:
    """Determine confidence badge based on edge and probability.

    - SAFE: High probability (>55%), moderate edge (>3%)
    - VALUE: Medium probability (>40%), strong edge (>8%)
    - RISKY: Low probability (<40%), any edge OR high edge (>15%)
    """
    if probability > 0.55 and edge > 3:
        return "SAFE"
    elif probability > 0.40 and edge > 8:
        return "VALUE"
    elif edge > 15:
        return "RISKY"  # High edge but potentially low prob
    elif probability < 0.40:
        return "RISKY"
    else:
        return "VALUE"  # Default for moderate cases


def apply_home_bias_correction(
    model_probs: dict[str, float],
    correction_factor: float = 0.92
) -> dict[str, float]:
    """Apply home bias correction to reduce overconfidence on home wins.

    The market systematically undervalues away teams and overvalues home teams.
    This correction reduces home probability and redistributes to draw and away.

    Args:
        model_probs: Original probabilities {home, draw, away}
        correction_factor: Factor to apply to home prob (0.92 = -8%)

    Returns:
        Corrected probabilities (normalized to sum to 1)
    """
    corrected = model_probs.copy()

    # Reduce home probability
    original_home = corrected["home"]
    corrected["home"] = original_home * correction_factor

    # Redistribute the difference to draw and away (60/40 split)
    difference = original_home - corrected["home"]
    corrected["draw"] += difference * 0.6
    corrected["away"] += difference * 0.4

    # Normalize to ensure sum = 1.0
    total = sum(corrected.values())
    corrected = {k: v / total for k, v in corrected.items()}

    return corrected


def ensure_models_trained():
    """Ensure models are trained before making predictions."""
    global dc_model, elo_model, match_history, models_trained

    if not models_trained or dc_model is None or elo_model is None:
        # Load last 2 seasons for training + history
        ligue1_matches_raw = load_historical_data("ligue_1", [2023, 2024])
        pl_matches_raw = load_historical_data("premier_league", [2023, 2024])
        all_matches_raw = ligue1_matches_raw + pl_matches_raw

        # Sort chronologically
        all_matches_raw.sort(key=lambda m: m["kickoff"])

        # Initialize MatchHistory for stats computation
        match_history = MatchHistory()
        for m in all_matches_raw:
            match_history.add_match(m)

        # Convert dicts to MatchResult objects for Dixon-Coles
        all_matches = [
            MatchResult(
                home_team=m["home_team"],
                away_team=m["away_team"],
                home_goals=m["home_score"],
                away_goals=m["away_score"],
                date=m["kickoff"],
            )
            for m in all_matches_raw
        ]

        # Train Dixon-Coles
        dc_model = DixonColesModel(half_life_days=180)
        dc_model.fit(all_matches)

        # Train ELO
        elo_model = EloRating(k_factor=20, home_advantage=100)
        for match in all_matches:
            elo_model.update(match)

        models_trained = True
        logger.info(f"Models trained on {len(all_matches)} matches, history has {len(match_history.matches)} matches")

def compute_team_stats(team: str, match_date: datetime) -> Optional[TeamStats]:
    """Compute detailed statistics for a team."""
    if match_history is None:
        return None

    recent = match_history.get_team_matches(team, match_date, last_n=5)
    if not recent:
        return None

    # Calculate stats manually
    points = 0
    goals_scored = 0
    goals_conceded = 0
    shots_total = 0
    shots_on_target_total = 0
    corners_total = 0

    # Build recent match details
    recent_matches = []
    for match, is_home in recent:
        home_score = match["home_score"]
        away_score = match["away_score"]

        if is_home:
            gs = home_score
            gc = away_score
            opponent = match["away_team"]
            shots = match.get("hs", 0)
            sot = match.get("hst", 0)
            c = match.get("hc", 0)
        else:
            gs = away_score
            gc = home_score
            opponent = match["home_team"]
            shots = match.get("as", 0)
            sot = match.get("ast", 0)
            c = match.get("ac", 0)

        goals_scored += gs
        goals_conceded += gc
        shots_total += shots
        shots_on_target_total += sot
        corners_total += c

        if gs > gc:
            result = "win"
            points += 3
        elif gs == gc:
            result = "draw"
            points += 1
        else:
            result = "loss"

        recent_matches.append(TeamRecentMatch(
            date=str(match["kickoff"])[:10],
            opponent=opponent,
            score=f"{gs}-{gc}",
            result=result,
            home_away="home" if is_home else "away",
            clean_sheet=(gc == 0),
        ))

    n = len(recent)
    ppg = points / n
    shot_accuracy = (shots_on_target_total / shots_total * 100) if shots_total > 0 else 0
    dominance = (shots_on_target_total + corners_total) / max(1, shots_on_target_total + corners_total + 100)

    # Generate form string (emoji)
    form_emoji = ''.join(['🟢' if m.result == 'win' else '🟡' if m.result == 'draw' else '🔴' for m in recent_matches])

    return TeamStats(
        ppg=ppg,
        goals_scored_avg=goals_scored / n,
        goals_conceded_avg=goals_conceded / n,
        shots_per_game=shots_total / n,
        shots_on_target_per_game=shots_on_target_total / n,
        shot_accuracy=shot_accuracy,
        corners_per_game=corners_total / n,
        dominance_score=dominance,
        recent_form=form_emoji,
        recent_matches=recent_matches,
    )


def compute_h2h(home_team: str, away_team: str, match_date: datetime) -> Optional[H2HStats]:
    """Compute head-to-head statistics."""
    if match_history is None:
        return None

    h2h = match_history.get_h2h_matches(home_team, away_team, match_date, last_n=10)
    if not h2h:
        return None

    home_wins = 0
    draws = 0
    away_wins = 0
    total_goals = 0
    over_25_count = 0

    recent_results = []
    for m in h2h[:5]:  # Last 5 for display
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

    return H2HStats(
        total_matches=len(h2h),
        home_wins=home_wins,
        draws=draws,
        away_wins=away_wins,
        avg_goals=total_goals / len(h2h),
        over_25_rate=(over_25_count / len(h2h)) * 100,
        recent_results=recent_results,
    )


def generate_prediction(
    home_team: str,
    away_team: str,
    league: str,
    kickoff: str,
    real_odds: Optional[dict] = None
) -> MatchPrediction:
    """Generate a prediction for a single match using trained models.

    Args:
        home_team: Home team name.
        away_team: Away team name.
        league: League name.
        kickoff: Match kickoff time (ISO format).
        real_odds: Optional dict with real odds from The Odds API.
                  Format: {"home": {...}, "draw": {...}, "away": {...}}
                  Each contains {"odds": float, "bookmaker": str}
    """
    ensure_models_trained()

    # Get predictions from both models
    try:
        dc_pred = dc_model.predict(home_team, away_team)
        elo_pred = elo_model.predict_1x2(home_team, away_team)
    except KeyError:
        # Team not in training data, use default probabilities
        dc_pred_probs = {"home": 0.33, "draw": 0.33, "away": 0.33}
        elo_pred_probs = {"home": 0.33, "draw": 0.33, "away": 0.33}
    else:
        dc_pred_probs = {
            "home": dc_pred.home_win,
            "draw": dc_pred.draw,
            "away": dc_pred.away_win
        }
        elo_pred_probs = {
            "home": elo_pred["home"],
            "draw": elo_pred["draw"],
            "away": elo_pred["away"]
        }

    # Ensemble: 65% DC, 35% ELO
    model_probs_raw = {
        "home": 0.65 * dc_pred_probs["home"] + 0.35 * elo_pred_probs["home"],
        "draw": 0.65 * dc_pred_probs["draw"] + 0.35 * elo_pred_probs["draw"],
        "away": 0.65 * dc_pred_probs["away"] + 0.35 * elo_pred_probs["away"],
    }

    # Apply home bias correction (-8% on home probability)
    model_probs = apply_home_bias_correction(model_probs_raw, correction_factor=0.92)

    # Extract Over/Under and BTTS from Dixon-Coles (only DC provides these)
    over_under_15_probs = None
    over_under_probs = None
    over_under_35_probs = None
    btts_probs = None
    correct_score_data = None

    if 'dc_pred' in locals() and hasattr(dc_pred, 'over_25'):
        over_under_15_probs = {
            "over_15": dc_pred.over_15,
            "under_15": 1 - dc_pred.over_15,
        }
        over_under_probs = {
            "over_25": dc_pred.over_25,
            "under_25": 1 - dc_pred.over_25,
        }
        over_under_35_probs = {
            "over_35": dc_pred.over_35,
            "under_35": 1 - dc_pred.over_35,
        }
        btts_probs = {
            "yes": dc_pred.btts_yes,
            "no": dc_pred.btts_no,
        }

        # Extract top 5 most likely correct scores
        if hasattr(dc_pred, 'score_matrix'):
            score_probs = []
            for h_goals in range(6):  # 0-5 goals
                for a_goals in range(6):
                    prob = dc_pred.score_matrix[h_goals, a_goals]
                    score_probs.append((f"{h_goals}-{a_goals}", prob))

            # Sort by probability and get top 5
            score_probs.sort(key=lambda x: x[1], reverse=True)
            correct_score_data = {score: prob for score, prob in score_probs[:5]}

    # Use real odds if available, otherwise fall back to mock odds
    if real_odds and all(real_odds.get(k, {}).get("odds", 0) > 0 for k in ["home", "away"]):
        # Real odds from The Odds API
        best_odds = {
            "home": real_odds["home"]["odds"],
            "draw": real_odds.get("draw", {}).get("odds", 0) or 3.5,  # Fallback for draw
            "away": real_odds["away"]["odds"],
        }
        bookmaker = {
            "home": real_odds["home"]["bookmaker"],
            "draw": real_odds.get("draw", {}).get("bookmaker", "N/A"),
            "away": real_odds["away"]["bookmaker"],
        }
    else:
        # Mock odds (fallback when no real odds available)
        # Using inverse of fair probability with 5% margin
        fair_odds = {
            "home": 1 / model_probs["home"] if model_probs["home"] > 0 else 10.0,
            "draw": 1 / model_probs["draw"] if model_probs["draw"] > 0 else 10.0,
            "away": 1 / model_probs["away"] if model_probs["away"] > 0 else 10.0,
        }

        # Add some variance to simulate bookmaker odds
        import random
        best_odds = {
            "home": fair_odds["home"] * random.uniform(0.98, 1.08),
            "draw": fair_odds["draw"] * random.uniform(0.95, 1.05),
            "away": fair_odds["away"] * random.uniform(0.98, 1.08),
        }

        # Mock bookmakers
        bookmakers = ["Betclic", "Unibet", "Bwin", "Pinnacle", "Bet365"]
        bookmaker = {
            "home": random.choice(bookmakers),
            "draw": random.choice(bookmakers),
            "away": random.choice(bookmakers),
        }

    # Calculate edges
    bookmaker_probs = {
        "home": 1 / best_odds["home"],
        "draw": 1 / best_odds["draw"],
        "away": 1 / best_odds["away"],
    }
    total = sum(bookmaker_probs.values())
    fair_probs = {k: v / total for k, v in bookmaker_probs.items()}

    edges = {
        k: calculate_edge(model_probs[k], fair_probs[k])
        for k in ["home", "draw", "away"]
    }

    # Determine recommended bet using asymmetric intelligent filtering
    # Different thresholds per market to account for market efficiency:
    # - HOME: Stricter (edge > 10%, prob > 45%) - market is very efficient
    # - AWAY: Standard (edge > 5%, prob > 35%) - market undervalues aways
    # - DRAW: Moderate (edge > 8%, prob > 30%) - mixed efficiency
    qualified_bets = []
    for outcome in ["home", "draw", "away"]:
        edge = edges[outcome]
        prob = model_probs[outcome]

        if outcome == "home":
            # Stricter filter for home bets (historically unprofitable)
            if edge > 10.0 and prob > 0.45:
                qualified_bets.append((outcome, edge, prob))
        elif outcome == "away":
            # Standard filter for away bets (historically profitable)
            if edge > 5.0 and prob > 0.35:
                qualified_bets.append((outcome, edge, prob))
        else:  # draw
            # Moderate filter for draws
            if edge > 8.0 and prob > 0.30:
                qualified_bets.append((outcome, edge, prob))

    if qualified_bets:
        # Calculate quality score for each qualified bet
        quality_scores = [
            (outcome, calculate_quality_score(edge, prob), edge, prob)
            for outcome, edge, prob in qualified_bets
        ]
        # Pick bet with highest quality score
        best_bet = max(quality_scores, key=lambda x: x[1])
        recommended_bet = best_bet[0]
        quality_score = best_bet[1]
        confidence_badge = get_confidence_badge(best_bet[2], best_bet[3])
    else:
        # No qualified bets
        recommended_bet = None
        quality_score = None
        confidence_badge = None

    # Calculate Kelly stake for recommended bet
    if recommended_bet:
        kelly_stake = kelly_criterion(
            model_probs[recommended_bet],
            best_odds[recommended_bet]
        )
    else:
        kelly_stake = 0.0

    # Determine segment
    max_prob = max(model_probs.values())
    segment = get_probability_segment(max_prob)

    match_id = f"{league}_{home_team}_{away_team}_{kickoff}".replace(" ", "_").lower()

    # Extract Over/Under odds from real_odds if available
    over_under_15_odds_data = None
    over_under_15_edge_data = None
    over_under_odds_data = None
    over_under_edge_data = None
    over_under_35_odds_data = None
    over_under_35_edge_data = None
    btts_odds_data = None
    btts_edge_data = None

    if real_odds:
        # Over/Under 1.5
        if "over15" in real_odds and over_under_15_probs:
            over_under_15_odds_data = {
                "over_15": real_odds["over15"]["odds"],
                "under_15": real_odds.get("under15", {}).get("odds", 0),
            }

            if over_under_15_odds_data["over_15"] > 0 and over_under_15_odds_data["under_15"] > 0:
                over_market_prob = 1 / over_under_15_odds_data["over_15"]
                under_market_prob = 1 / over_under_15_odds_data["under_15"]
                total_market = over_market_prob + under_market_prob

                if total_market > 0:
                    over_market_prob /= total_market
                    under_market_prob /= total_market
                    over_under_15_edge_data = {
                        "over_15": calculate_edge(over_under_15_probs["over_15"], over_market_prob),
                        "under_15": calculate_edge(over_under_15_probs["under_15"], under_market_prob),
                    }

        # Over/Under 2.5
        if "over25" in real_odds and over_under_probs:
            over_under_odds_data = {
                "over_25": real_odds["over25"]["odds"],
                "under_25": real_odds.get("under25", {}).get("odds", 0),
            }

            if over_under_odds_data["over_25"] > 0 and over_under_odds_data["under_25"] > 0:
                over_market_prob = 1 / over_under_odds_data["over_25"]
                under_market_prob = 1 / over_under_odds_data["under_25"]
                total_market = over_market_prob + under_market_prob

                if total_market > 0:
                    over_market_prob /= total_market
                    under_market_prob /= total_market
                    over_under_edge_data = {
                        "over_25": calculate_edge(over_under_probs["over_25"], over_market_prob),
                        "under_25": calculate_edge(over_under_probs["under_25"], under_market_prob),
                    }

        # Over/Under 3.5
        if "over35" in real_odds and over_under_35_probs:
            over_under_35_odds_data = {
                "over_35": real_odds["over35"]["odds"],
                "under_35": real_odds.get("under35", {}).get("odds", 0),
            }

            if over_under_35_odds_data["over_35"] > 0 and over_under_35_odds_data["under_35"] > 0:
                over_market_prob = 1 / over_under_35_odds_data["over_35"]
                under_market_prob = 1 / over_under_35_odds_data["under_35"]
                total_market = over_market_prob + under_market_prob

                if total_market > 0:
                    over_market_prob /= total_market
                    under_market_prob /= total_market
                    over_under_35_edge_data = {
                        "over_35": calculate_edge(over_under_35_probs["over_35"], over_market_prob),
                        "under_35": calculate_edge(over_under_35_probs["under_35"], under_market_prob),
                    }

    # Compute detailed stats for teams
    match_datetime = datetime.fromisoformat(kickoff.replace('Z', '+00:00'))
    home_stats = compute_team_stats(home_team, match_datetime)
    away_stats = compute_team_stats(away_team, match_datetime)
    h2h_stats = compute_h2h(home_team, away_team, match_datetime)

    # Extract model strength parameters
    model_strength = None
    elo_ratings = None
    if dc_model and dc_model.is_fitted:
        home_team_params = dc_model.teams.get(home_team)
        away_team_params = dc_model.teams.get(away_team)
        if home_team_params and away_team_params:
            model_strength = {
                "home_attack": home_team_params.attack,
                "home_defense": home_team_params.defense,
                "away_attack": away_team_params.attack,
                "away_defense": away_team_params.defense,
            }

    if elo_model:
        elo_ratings = {
            "home": elo_model.get_rating(home_team),
            "away": elo_model.get_rating(away_team),
            "diff": elo_model.get_rating(home_team) - elo_model.get_rating(away_team),
        }

    return MatchPrediction(
        match_id=match_id,
        league=league,
        home_team=home_team,
        away_team=away_team,
        kickoff=kickoff,
        model_probs=model_probs,
        best_odds=best_odds,
        bookmaker=bookmaker,
        edge=edges,
        recommended_bet=recommended_bet,
        kelly_stake=kelly_stake,
        segment=segment,
        quality_score=quality_score,
        confidence_badge=confidence_badge,
        over_under_15=over_under_15_probs,
        over_under_15_odds=over_under_15_odds_data,
        over_under_15_edge=over_under_15_edge_data,
        over_under=over_under_probs,
        over_under_odds=over_under_odds_data,
        over_under_edge=over_under_edge_data,
        over_under_35=over_under_35_probs,
        over_under_35_odds=over_under_35_odds_data,
        over_under_35_edge=over_under_35_edge_data,
        btts=btts_probs,
        btts_odds=btts_odds_data,
        btts_edge=btts_edge_data,
        correct_score=correct_score_data,
        home_stats=home_stats,
        away_stats=away_stats,
        h2h_stats=h2h_stats,
        model_strength=model_strength,
        elo_ratings=elo_ratings,
    )

@router.get("/predictions", response_model=List[MatchPrediction])
async def get_predictions(
    league: Optional[str] = Query(None, description="Filter by league: ligue_1, premier_league"),
    min_edge: float = Query(0, description="Minimum edge threshold (%)"),
    use_mock: bool = Query(False, description="Use mock fixtures for testing (bypasses API)"),
    use_real_odds: bool = Query(True, description="Fetch real odds from The Odds API"),
):
    """Get today's match predictions using real Dixon-Coles + ELO models.

    Fetches real upcoming fixtures from football-data.org and generates predictions.
    Optionally fetches real bookmaker odds from The Odds API.
    Falls back to mock data if APIs are unavailable or no matches today.
    """

    # Fetch real fixtures from football-data.org
    try:
        if use_mock:
            # Use test fixtures
            import json
            test_fixtures_path = PROJECT_ROOT / "api" / "test_fixtures.json"
            with open(test_fixtures_path) as f:
                upcoming_fixtures = json.load(f)
            logger.info(f"Using {len(upcoming_fixtures)} mock fixtures for testing")
        else:
            # Fetch today's fixtures
            leagues_to_fetch = None
            if league:
                # Map query param to internal format
                leagues_to_fetch = [league]

            upcoming_fixtures = fetch_today_fixtures(leagues=leagues_to_fetch)

            if not upcoming_fixtures:
                # No matches today - try tomorrow
                upcoming_fixtures = fetch_tomorrow_fixtures(leagues=leagues_to_fetch)

                if not upcoming_fixtures:
                    raise ValueError("No fixtures found for today or tomorrow")

    except Exception as e:
        # No fallback - raise clear error
        logger.error(f"Failed to fetch fixtures from football-data.org: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Fixtures API unavailable",
                "message": f"Failed to fetch fixtures from football-data.org: {str(e)}",
                "suggestion": "Check FOOTBALL_DATA_ORG_KEY in .env or try again later",
            }
        )

    # Fetch real odds from The Odds API if requested
    odds_by_match = {}
    if use_real_odds:
        try:
            api_key = os.getenv("ODDS_API_KEY")
            if api_key and api_key != "your_key_here":
                odds_client = OddsAPIClient(api_key)

                # Determine which leagues to fetch odds for
                leagues_for_odds = leagues_to_fetch if leagues_to_fetch else ["ligue_1", "premier_league"]

                # Helper function to normalize team names for matching
                def normalize_team_for_matching(name: str) -> str:
                    """Normalize team name for matching between APIs."""
                    # Common transformations
                    name = name.replace("AS ", "").replace("AFC ", "").replace("FC ", "")
                    name = name.replace(" and Hove Albion", "")
                    name = name.replace("Manchester City", "Man City")
                    name = name.replace("Manchester United", "Man United")
                    name = name.replace("Nottingham Forest", "Nott'm Forest")
                    name = name.replace("Wolverhampton Wanderers", "Wolves")
                    name = name.replace("Tottenham Hotspur", "Tottenham")
                    name = name.replace("Brighton and Hove Albion", "Brighton")
                    name = name.replace("West Ham United", "West Ham")
                    name = name.replace("Newcastle United", "Newcastle")
                    name = name.replace("Leicester City", "Leicester")
                    name = name.replace("Ipswich Town", "Ipswich")
                    name = name.replace("Leeds United", "Leeds")
                    name = name.replace("Paris Saint Germain", "Paris SG")
                    name = name.replace("Paris Saint-Germain", "Paris SG")
                    name = name.replace("Olympique Marseille", "Marseille")
                    name = name.replace("Saint-Etienne", "St Etienne")
                    return name.strip()

                # Fetch odds for each league
                for league_slug in leagues_for_odds:
                    try:
                        odds_data = odds_client.get_odds(league=league_slug, markets="h2h,totals", regions="eu")

                        # Process each match's odds
                        for match_odds in odds_data:
                            home_team_raw = match_odds.get("home_team", "")
                            away_team_raw = match_odds.get("away_team", "")

                            # Normalize team names for matching
                            home_team = normalize_team_for_matching(home_team_raw)
                            away_team = normalize_team_for_matching(away_team_raw)

                            # Extract best odds
                            best_odds = extract_best_odds(match_odds)

                            # Create match key with normalized names
                            match_key = (home_team, away_team)
                            odds_by_match[match_key] = best_odds

                            logger.debug(f"Odds mapped: {home_team} vs {away_team}")

                        logger.info(f"Fetched odds for {len(odds_data)} matches in {league_slug}")
                    except Exception as e:
                        logger.warning(f"Failed to fetch odds for {league_slug}: {e}")
                        continue

                odds_client.close()
            else:
                logger.warning("ODDS_API_KEY not configured, using mock odds")
        except Exception as e:
            logger.warning(f"Failed to fetch odds from The Odds API: {e}. Using mock odds.")

    # Generate predictions for each fixture
    predictions = []
    for fixture in upcoming_fixtures:
        # Look for matching odds
        match_key = (fixture["home"], fixture["away"])
        real_odds = odds_by_match.get(match_key)

        pred = generate_prediction(
            home_team=fixture["home"],
            away_team=fixture["away"],
            league=fixture["league"],
            kickoff=fixture["kickoff"],
            real_odds=real_odds
        )
        predictions.append(pred)

    # Filter by league
    if league:
        league_display = "Ligue 1" if league == "ligue_1" else "Premier League"
        predictions = [p for p in predictions if p.league == league_display]

    # Filter by min edge
    if min_edge > 0:
        predictions = [
            p for p in predictions
            if p.edge and max(p.edge.values()) >= min_edge
        ]

    return predictions


@router.post("/train")
async def train_models():
    """Train models on historical data.

    This endpoint trains Dixon-Coles and ELO models on recent historical data.
    Should be called periodically (e.g., weekly) to keep models up-to-date.
    """
    global dc_model, elo_model, models_trained

    # Load last 2 seasons for training
    ligue1_matches = load_historical_data("ligue_1", [2023, 2024])
    pl_matches = load_historical_data("premier_league", [2023, 2024])

    all_matches = ligue1_matches + pl_matches

    # Train Dixon-Coles
    dc_model = DixonColesModel(half_life_days=180)
    dc_model.fit(all_matches)

    # Train ELO
    elo_model = EloRating(k_factor=20, home_advantage=100)
    for match in all_matches:
        elo_model.update(match)

    models_trained = True

    return {
        "status": "success",
        "models_trained": True,
        "training_matches": len(all_matches),
        "dc_teams": len(dc_model.teams) if dc_model else 0,
    }

@router.get("/predictions/{match_id}")
async def get_prediction_detail(match_id: str):
    """Get detailed prediction for a specific match."""
    # Mock response for demo
    return {
        "match_id": match_id,
        "detail": "Detailed prediction endpoint - to be implemented",
        "note": "Would return full score matrix, probability distributions, etc."
    }

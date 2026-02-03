"""
Sync real data from Football-Data.org.

Uses the free tier which includes Ligue 1 with current season data.
"""

from datetime import datetime
from loguru import logger

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal
from app.core import get_settings
from app.models.database import (
    Competition, Team, Match, Prediction, MatchOdds, EdgeCalculation
)
from app.services.data.football_data_org import get_football_data_client, FootballDataOrgClient


settings = get_settings()


def calculate_match_probabilities(home_elo: float, away_elo: float) -> dict:
    """Calculate 1X2 probabilities based on ELO ratings."""
    elo_diff = home_elo - away_elo
    elo_diff += 65  # Home advantage

    home_exp = 1 / (1 + 10 ** (-elo_diff / 400))
    away_exp = 1 - home_exp

    draw_base = 0.26
    draw_adj = 0.04 * (1 - abs(home_exp - 0.5) * 2)
    draw_prob = draw_base + draw_adj

    home_prob = home_exp * (1 - draw_prob)
    away_prob = away_exp * (1 - draw_prob)

    total = home_prob + draw_prob + away_prob

    return {
        "home_win": round(home_prob / total, 3),
        "draw": round(draw_prob / total, 3),
        "away_win": round(away_prob / total, 3),
    }


def calculate_goals_probs(home_elo: float, away_elo: float) -> dict:
    """Calculate over/under and BTTS probabilities."""
    avg_goals = 2.6
    elo_factor = (home_elo + away_elo - 3000) / 1000

    expected_total = avg_goals + elo_factor * 0.3

    over_25_prob = 0.48 + (expected_total - 2.6) * 0.15
    over_25_prob = max(0.30, min(0.70, over_25_prob))

    btts_prob = 0.50 + (expected_total - 2.6) * 0.1
    btts_prob = max(0.35, min(0.65, btts_prob))

    return {
        "over_25": round(over_25_prob, 3),
        "under_25": round(1 - over_25_prob, 3),
        "btts_yes": round(btts_prob, 3),
        "btts_no": round(1 - btts_prob, 3),
    }


def prob_to_odds(prob: float) -> float:
    """Convert probability to decimal odds."""
    if prob <= 0:
        return 10.0
    return round(1 / prob, 2)


def odds_to_prob(odds: float) -> float:
    """Convert decimal odds to implied probability."""
    if odds <= 1:
        return 0
    return round(1 / odds, 3)


def calculate_edge(model_prob: float, book_prob: float) -> float:
    """Calculate edge percentage."""
    if book_prob <= 0:
        return 0
    return round((model_prob - book_prob) / book_prob * 100, 2)


def classify_risk(edge: float, confidence: float) -> str:
    """Classify bet risk level."""
    if edge >= 10 and confidence >= 0.7:
        return "safe"
    elif edge >= 5 and confidence >= 0.5:
        return "medium"
    else:
        return "risky"


def kelly_criterion(prob: float, odds: float, fraction: float = 0.25) -> float:
    """Calculate Kelly criterion stake."""
    b = odds - 1
    q = 1 - prob
    kelly = (b * prob - q) / b
    return round(max(0, kelly * fraction), 3)


def generate_bookmaker_odds(model_probs: dict, margin: float = 0.05) -> dict:
    """
    Generate simulated bookmaker odds from model probabilities.
    Adds a margin to simulate real bookmaker pricing.
    """
    # Add margin to create "worse" odds than fair value
    adjusted_probs = {}
    for key, prob in model_probs.items():
        # Bookmakers typically offer worse odds, adding ~5% margin
        adjusted_probs[key] = min(0.95, prob * (1 + margin))

    return {
        "home_win_odds": prob_to_odds(adjusted_probs.get("home_win", 0.33)),
        "draw_odds": prob_to_odds(adjusted_probs.get("draw", 0.33)),
        "away_win_odds": prob_to_odds(adjusted_probs.get("away_win", 0.33)),
        "over_25_odds": prob_to_odds(adjusted_probs.get("over_25", 0.5)),
        "under_25_odds": prob_to_odds(adjusted_probs.get("under_25", 0.5)),
    }


def sync_fixtures():
    """Sync real fixtures from Football-Data.org."""
    logger.info("Starting real data sync from Football-Data.org...")

    api = get_football_data_client()
    db = SessionLocal()

    try:
        # Get competition info
        comp_data = api.get_competition(FootballDataOrgClient.LIGUE_1)
        logger.info(f"Competition: {comp_data.get('name')} - Season {comp_data.get('currentSeason', {}).get('startDate', 'N/A')}")

        current_season = comp_data.get("currentSeason", {})
        season_year = current_season.get("startDate", "2025")[:4]

        # Get or create Ligue 1 competition
        competition = db.query(Competition).filter(Competition.api_id == 61).first()
        if not competition:
            competition = Competition(
                api_id=61,
                name="Ligue 1",
                short_name="L1",
                country="France",
                type="league",
                season=int(season_year),
                logo_url="https://media.api-sports.io/football/leagues/61.png"
            )
            db.add(competition)
            db.commit()
            db.refresh(competition)
        else:
            competition.season = int(season_year)
            db.commit()

        # Fetch teams
        logger.info("Fetching Ligue 1 teams...")
        api_teams = api.get_teams(FootballDataOrgClient.LIGUE_1)
        logger.info(f"Found {len(api_teams)} teams")

        team_map = {}  # API team ID -> local team
        for team_data in api_teams:
            team_id = team_data.get("id")
            team_name = team_data.get("name")

            existing = db.query(Team).filter(Team.api_id == team_id).first()
            if not existing:
                # Assign ELO based on historical strength
                elo = get_team_elo(team_name)
                team = Team(
                    api_id=team_id,
                    name=team_name,
                    short_name=team_data.get("tla"),
                    code=team_data.get("tla"),
                    logo_url=team_data.get("crest"),
                    elo_rating=elo,
                )
                db.add(team)
                db.commit()
                db.refresh(team)
                team_map[team_id] = team
            else:
                team_map[team_id] = existing

        logger.info(f"Synced {len(team_map)} teams")

        # Fetch scheduled matches
        logger.info("Fetching scheduled Ligue 1 matches...")
        matches = api.get_scheduled_matches(FootballDataOrgClient.LIGUE_1)
        logger.info(f"Found {len(matches)} scheduled matches")

        matches_created = 0
        odds_created = 0
        edges_created = 0

        for match_data in matches[:20]:  # Limit to 20 matches
            match_id = match_data.get("id")

            # Skip if already exists
            existing_match = db.query(Match).filter(Match.api_id == match_id).first()
            if existing_match:
                continue

            home_team_data = match_data.get("homeTeam", {})
            away_team_data = match_data.get("awayTeam", {})

            home_team = team_map.get(home_team_data.get("id"))
            away_team = team_map.get(away_team_data.get("id"))

            if not home_team or not away_team:
                logger.warning(f"Teams not found for match {match_id}")
                continue

            # Parse kickoff time
            kickoff_str = match_data.get("utcDate")
            kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))

            # Get matchday
            matchday = match_data.get("matchday")

            # Create match
            match = Match(
                api_id=match_id,
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                competition_id=competition.id,
                kickoff=kickoff,
                matchday=str(matchday) if matchday else None,
                status="scheduled",
            )
            db.add(match)
            db.commit()
            db.refresh(match)
            matches_created += 1

            # Calculate predictions
            home_elo = home_team.elo_rating or 1500
            away_elo = away_team.elo_rating or 1500

            probs_1x2 = calculate_match_probabilities(home_elo, away_elo)
            probs_goals = calculate_goals_probs(home_elo, away_elo)

            elo_diff = abs(home_elo - away_elo)
            confidence = min(0.9, 0.5 + elo_diff / 500)

            prediction = Prediction(
                match_id=match.id,
                home_win_prob=probs_1x2["home_win"] * 100,
                draw_prob=probs_1x2["draw"] * 100,
                away_win_prob=probs_1x2["away_win"] * 100,
                confidence=confidence,
                model_version="v1.0-elo",
            )
            db.add(prediction)
            db.commit()
            db.refresh(prediction)

            # Generate simulated odds (football-data.org doesn't provide odds on free tier)
            all_probs = {**probs_1x2, **probs_goals}
            simulated_odds = generate_bookmaker_odds(all_probs)

            # Create odds record
            match_odds = MatchOdds(
                match_id=match.id,
                bookmaker="Simulated",
                home_win_odds=simulated_odds["home_win_odds"],
                draw_odds=simulated_odds["draw_odds"],
                away_win_odds=simulated_odds["away_win_odds"],
                over_25_odds=simulated_odds["over_25_odds"],
                under_25_odds=simulated_odds["under_25_odds"],
                home_win_implied=odds_to_prob(simulated_odds["home_win_odds"]),
                draw_implied=odds_to_prob(simulated_odds["draw_odds"]),
                away_win_implied=odds_to_prob(simulated_odds["away_win_odds"]),
            )
            db.add(match_odds)
            odds_created += 1
            db.commit()

            # Calculate edges (compare model vs simulated bookmaker)
            markets = [
                ("1x2_home", "home_win_odds", probs_1x2["home_win"]),
                ("1x2_draw", "draw_odds", probs_1x2["draw"]),
                ("1x2_away", "away_win_odds", probs_1x2["away_win"]),
                ("over_25", "over_25_odds", probs_goals["over_25"]),
                ("under_25", "under_25_odds", probs_goals["under_25"]),
            ]

            for market, odds_key, model_prob in markets:
                best_odds = simulated_odds[odds_key]
                book_prob = odds_to_prob(best_odds)
                edge = calculate_edge(model_prob, book_prob)

                if edge > 3:
                    risk = classify_risk(edge, confidence)
                    kelly = kelly_criterion(model_prob, best_odds)

                    edge_calc = EdgeCalculation(
                        match_id=match.id,
                        prediction_id=prediction.id,
                        market=market,
                        model_probability=model_prob,
                        bookmaker_probability=book_prob,
                        edge_percentage=edge,
                        best_odds=best_odds,
                        bookmaker_name="Simulated",
                        risk_level=risk,
                        kelly_stake=kelly,
                        confidence=confidence,
                    )
                    db.add(edge_calc)
                    edges_created += 1

            db.commit()

        logger.info("=" * 50)
        logger.info("SYNC COMPLETED")
        logger.info("=" * 50)
        logger.info(f"Matches created: {matches_created}")
        logger.info(f"Odds records: {odds_created}")
        logger.info(f"Edge calculations: {edges_created}")
        logger.info("=" * 50)

        return {
            "matches_created": matches_created,
            "odds_created": odds_created,
            "edges_created": edges_created,
        }

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()
        api.close()


def get_team_elo(team_name: str) -> int:
    """Get historical ELO rating for a team."""
    # Approximate ELO ratings based on historical performance
    elo_ratings = {
        "Paris Saint-Germain": 1850,
        "Paris Saint-Germain FC": 1850,
        "AS Monaco": 1720,
        "AS Monaco FC": 1720,
        "Olympique de Marseille": 1700,
        "Olympique Marseille": 1700,
        "Olympique Lyonnais": 1680,
        "Olympique Lyon": 1680,
        "LOSC Lille": 1660,
        "Lille OSC": 1660,
        "Stade Rennais FC 1901": 1640,
        "Stade Rennais": 1640,
        "OGC Nice": 1620,
        "RC Lens": 1610,
        "RC Strasbourg Alsace": 1580,
        "Montpellier HSC": 1570,
        "Toulouse FC": 1560,
        "FC Nantes": 1550,
        "Stade Brestois 29": 1540,
        "Stade de Reims": 1530,
        "AJ Auxerre": 1520,
        "Angers SCO": 1510,
        "Le Havre AC": 1500,
        "AS Saint-Étienne": 1490,
    }

    for name, elo in elo_ratings.items():
        if name.lower() in team_name.lower() or team_name.lower() in name.lower():
            return elo

    return 1500  # Default


if __name__ == "__main__":
    sync_fixtures()

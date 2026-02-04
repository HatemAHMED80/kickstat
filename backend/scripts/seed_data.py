"""
Seed script to populate the database with demo data.
Run with: python -m scripts.seed_data
"""

import random
from datetime import datetime, timedelta
from loguru import logger

# Setup path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import engine, SessionLocal
from app.models.database import (
    Base, Competition, Team, Stadium, Match, Prediction,
    MatchOdds, EdgeCalculation
)


# =============================================================================
# LIGUE 1 DATA
# =============================================================================

LIGUE1_TEAMS = [
    {"name": "Paris Saint-Germain", "short_name": "PSG", "code": "PSG", "elo": 1850, "logo_url": "https://media.api-sports.io/football/teams/85.png"},
    {"name": "Olympique de Marseille", "short_name": "Marseille", "code": "OM", "elo": 1720, "logo_url": "https://media.api-sports.io/football/teams/81.png"},
    {"name": "AS Monaco", "short_name": "Monaco", "code": "ASM", "elo": 1750, "logo_url": "https://media.api-sports.io/football/teams/91.png"},
    {"name": "Olympique Lyonnais", "short_name": "Lyon", "code": "OL", "elo": 1700, "logo_url": "https://media.api-sports.io/football/teams/80.png"},
    {"name": "LOSC Lille", "short_name": "Lille", "code": "LOSC", "elo": 1680, "logo_url": "https://media.api-sports.io/football/teams/79.png"},
    {"name": "RC Lens", "short_name": "Lens", "code": "RCL", "elo": 1660, "logo_url": "https://media.api-sports.io/football/teams/116.png"},
    {"name": "OGC Nice", "short_name": "Nice", "code": "OGCN", "elo": 1640, "logo_url": "https://media.api-sports.io/football/teams/84.png"},
    {"name": "Stade Rennais", "short_name": "Rennes", "code": "SRFC", "elo": 1630, "logo_url": "https://media.api-sports.io/football/teams/94.png"},
    {"name": "RC Strasbourg", "short_name": "Strasbourg", "code": "RCSA", "elo": 1580, "logo_url": "https://media.api-sports.io/football/teams/95.png"},
    {"name": "Montpellier HSC", "short_name": "Montpellier", "code": "MHSC", "elo": 1560, "logo_url": "https://media.api-sports.io/football/teams/82.png"},
    {"name": "Toulouse FC", "short_name": "Toulouse", "code": "TFC", "elo": 1550, "logo_url": "https://media.api-sports.io/football/teams/96.png"},
    {"name": "Stade de Reims", "short_name": "Reims", "code": "SDR", "elo": 1540, "logo_url": "https://media.api-sports.io/football/teams/93.png"},
    {"name": "Stade Brestois", "short_name": "Brest", "code": "SB29", "elo": 1620, "logo_url": "https://media.api-sports.io/football/teams/106.png"},
    {"name": "FC Nantes", "short_name": "Nantes", "code": "FCN", "elo": 1520, "logo_url": "https://media.api-sports.io/football/teams/83.png"},
    {"name": "AJ Auxerre", "short_name": "Auxerre", "code": "AJA", "elo": 1480, "logo_url": "https://media.api-sports.io/football/teams/98.png"},
    {"name": "Le Havre AC", "short_name": "Le Havre", "code": "HAC", "elo": 1470, "logo_url": "https://media.api-sports.io/football/teams/99.png"},
    {"name": "AS Saint-Étienne", "short_name": "Saint-Étienne", "code": "ASSE", "elo": 1500, "logo_url": "https://media.api-sports.io/football/teams/1063.png"},
    {"name": "Angers SCO", "short_name": "Angers", "code": "SCO", "elo": 1460, "logo_url": "https://media.api-sports.io/football/teams/77.png"},
]

BOOKMAKERS = ["Betclic", "Winamax", "Unibet", "ParionsSport", "Bet365"]

MARKETS = [
    "1x2_home", "1x2_draw", "1x2_away",
    "over_25", "under_25",
    "btts_yes", "btts_no"
]

MARKET_NAMES = {
    "1x2_home": "Victoire domicile",
    "1x2_draw": "Match nul",
    "1x2_away": "Victoire extérieur",
    "over_25": "Plus de 2.5 buts",
    "under_25": "Moins de 2.5 buts",
    "btts_yes": "Les 2 équipes marquent",
    "btts_no": "Les 2 ne marquent pas",
}


def calculate_match_probabilities(home_elo: float, away_elo: float) -> dict:
    """Calculate 1X2 probabilities based on ELO ratings."""
    elo_diff = home_elo - away_elo
    # Home advantage bonus
    elo_diff += 65

    # Win expectancy
    home_exp = 1 / (1 + 10 ** (-elo_diff / 400))
    away_exp = 1 - home_exp

    # Add draw probability (roughly 25-30% for Ligue 1)
    draw_base = 0.26
    draw_adj = 0.04 * (1 - abs(home_exp - 0.5) * 2)  # More likely draw when teams are close
    draw_prob = draw_base + draw_adj

    # Adjust home/away for draw
    home_prob = home_exp * (1 - draw_prob)
    away_prob = away_exp * (1 - draw_prob)

    # Normalize
    total = home_prob + draw_prob + away_prob

    return {
        "home_win": round(home_prob / total, 3),
        "draw": round(draw_prob / total, 3),
        "away_win": round(away_prob / total, 3),
    }


def calculate_goals_probs(home_elo: float, away_elo: float) -> dict:
    """Calculate over/under and BTTS probabilities."""
    # Expected goals based on ELO
    avg_goals = 2.6  # Ligue 1 average
    elo_factor = (home_elo + away_elo - 3000) / 1000

    expected_total = avg_goals + elo_factor * 0.3

    # Over 2.5 probability (using Poisson approximation)
    over_25_prob = 0.48 + (expected_total - 2.6) * 0.15
    over_25_prob = max(0.30, min(0.70, over_25_prob))

    # BTTS
    btts_prob = 0.50 + (expected_total - 2.6) * 0.1
    btts_prob = max(0.35, min(0.65, btts_prob))

    return {
        "over_25": round(over_25_prob, 3),
        "under_25": round(1 - over_25_prob, 3),
        "btts_yes": round(btts_prob, 3),
        "btts_no": round(1 - btts_prob, 3),
    }


def prob_to_odds(prob: float, margin: float = 0.05, variance: float = 0.0) -> float:
    """
    Convert probability to decimal odds with bookmaker margin and variance.

    Args:
        prob: True probability (0-1)
        margin: Bookmaker margin (positive = house edge)
        variance: Random variance to simulate bookmaker mispricing (-/+ means under/overestimate)
    """
    if prob <= 0:
        return 50.0
    # Apply variance first (simulates bookmaker's probability estimation error)
    adjusted_prob = prob + variance
    adjusted_prob = max(0.01, min(0.99, adjusted_prob))  # Keep in valid range
    # Then apply margin
    implied = adjusted_prob * (1 + margin)
    return round(1 / implied, 2)


def odds_to_prob(odds: float) -> float:
    """Convert decimal odds to implied probability."""
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


def kelly_criterion(prob: float, odds: float, fraction: float = 0.5) -> float:
    """Calculate Kelly criterion stake."""
    b = odds - 1
    q = 1 - prob
    kelly = (b * prob - q) / b
    return round(max(0, kelly * fraction), 3)


def seed_database():
    """Populate database with demo data."""
    logger.info("Starting database seed...")

    # Create tables
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # Check if already seeded
        existing = db.query(Team).first()
        if existing:
            logger.info("Database already seeded. Clearing existing data...")
            # Clear edge calculations, predictions, odds, matches
            db.query(EdgeCalculation).delete()
            db.query(MatchOdds).delete()
            db.query(Prediction).delete()
            db.query(Match).delete()
            db.commit()

        # 1. Create Competition
        logger.info("Creating Ligue 1 competition...")
        competition = db.query(Competition).filter(Competition.api_id == 61).first()
        if not competition:
            competition = Competition(
                api_id=61,
                name="Ligue 1",
                short_name="L1",
                country="France",
                type="league",
                season=2024,
                logo_url="https://media.api-sports.io/football/leagues/61.png"
            )
            db.add(competition)
            db.commit()
            db.refresh(competition)

        # 2. Create Teams
        logger.info("Creating teams...")
        teams = []
        for i, team_data in enumerate(LIGUE1_TEAMS):
            team = db.query(Team).filter(Team.name == team_data["name"]).first()
            if not team:
                team = Team(
                    api_id=100 + i,
                    name=team_data["name"],
                    short_name=team_data["short_name"],
                    code=team_data["code"],
                    elo_rating=team_data["elo"],
                    logo_url=team_data["logo_url"],
                )
                db.add(team)
            else:
                team.elo_rating = team_data["elo"]
                team.logo_url = team_data["logo_url"]
            teams.append(team)
        db.commit()

        # Refresh teams
        teams = db.query(Team).all()
        logger.info(f"Created {len(teams)} teams")

        # 3. Create upcoming matches (next 2 matchdays)
        logger.info("Creating matches...")

        # Shuffle teams for matchday pairings
        random.shuffle(teams)

        matches = []
        match_id_counter = 1

        # Create matches for 2 matchdays
        for matchday in [21, 22]:
            # Determine kickoff times (use UTC to match the edge calculator filter)
            if matchday == 21:
                base_date = datetime.utcnow() + timedelta(days=2)
            else:
                base_date = datetime.utcnow() + timedelta(days=9)

            # Create 9 matches per matchday
            for i in range(0, 18, 2):
                home_team = teams[i]
                away_team = teams[i + 1]

                # Varied kickoff times
                kickoff_hour = random.choice([15, 17, 19, 21])
                kickoff = base_date.replace(hour=kickoff_hour, minute=0, second=0, microsecond=0)

                match = Match(
                    api_id=1000 + match_id_counter,
                    home_team_id=home_team.id,
                    away_team_id=away_team.id,
                    competition_id=competition.id,
                    kickoff=kickoff,
                    matchday=matchday,
                    status="scheduled",
                )
                db.add(match)
                matches.append((match, home_team, away_team))
                match_id_counter += 1

            # Rotate teams for next matchday
            teams = teams[1:] + [teams[0]]

        db.commit()
        logger.info(f"Created {len(matches)} matches")

        # 4. Create predictions, odds, and edges
        logger.info("Creating predictions, odds, and edge calculations...")

        for match, home_team, away_team in matches:
            db.refresh(match)

            # Calculate probabilities
            probs_1x2 = calculate_match_probabilities(home_team.elo_rating, away_team.elo_rating)
            probs_goals = calculate_goals_probs(home_team.elo_rating, away_team.elo_rating)

            all_probs = {
                "1x2_home": probs_1x2["home_win"],
                "1x2_draw": probs_1x2["draw"],
                "1x2_away": probs_1x2["away_win"],
                **probs_goals
            }

            # Confidence based on ELO difference
            elo_diff = abs(home_team.elo_rating - away_team.elo_rating)
            confidence = min(0.9, 0.5 + elo_diff / 500)

            # Create Prediction (probabilities stored as 0-100)
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

            # Create odds for multiple bookmakers
            for bookmaker in BOOKMAKERS[:random.randint(2, 4)]:
                # Add bookmaker margin and variance to simulate mispricing
                margin = random.uniform(0.03, 0.06)

                # Variance simulates bookmaker's probability estimation error
                # Negative variance = bookmaker UNDERESTIMATES probability = positive edge for us
                # We want ~40% of bets to have positive edge for demo purposes
                def get_variance():
                    return random.uniform(-0.08, 0.04)  # More likely to underestimate

                odds = MatchOdds(
                    match_id=match.id,
                    bookmaker=bookmaker,
                    home_win_odds=prob_to_odds(probs_1x2["home_win"], margin, get_variance()),
                    draw_odds=prob_to_odds(probs_1x2["draw"], margin, get_variance()),
                    away_win_odds=prob_to_odds(probs_1x2["away_win"], margin, get_variance()),
                    over_25_odds=prob_to_odds(probs_goals["over_25"], margin, get_variance()),
                    under_25_odds=prob_to_odds(probs_goals["under_25"], margin, get_variance()),
                    btts_yes_odds=prob_to_odds(probs_goals["btts_yes"], margin, get_variance()),
                    btts_no_odds=prob_to_odds(probs_goals["btts_no"], margin, get_variance()),
                    home_win_implied=odds_to_prob(prob_to_odds(probs_1x2["home_win"], margin, 0)),
                    draw_implied=odds_to_prob(prob_to_odds(probs_1x2["draw"], margin, 0)),
                    away_win_implied=odds_to_prob(prob_to_odds(probs_1x2["away_win"], margin, 0)),
                )
                db.add(odds)

            db.commit()

            # Find best odds for each market and create edge calculations
            match_odds = db.query(MatchOdds).filter(MatchOdds.match_id == match.id).all()

            for market in MARKETS:
                model_prob = all_probs[market]

                # Find best odds for this market
                best_odds = 1.0
                best_bookmaker = ""

                for odds in match_odds:
                    if market == "1x2_home" and odds.home_win_odds and odds.home_win_odds > best_odds:
                        best_odds = odds.home_win_odds
                        best_bookmaker = odds.bookmaker
                    elif market == "1x2_draw" and odds.draw_odds and odds.draw_odds > best_odds:
                        best_odds = odds.draw_odds
                        best_bookmaker = odds.bookmaker
                    elif market == "1x2_away" and odds.away_win_odds and odds.away_win_odds > best_odds:
                        best_odds = odds.away_win_odds
                        best_bookmaker = odds.bookmaker
                    elif market == "over_25" and odds.over_25_odds and odds.over_25_odds > best_odds:
                        best_odds = odds.over_25_odds
                        best_bookmaker = odds.bookmaker
                    elif market == "under_25" and odds.under_25_odds and odds.under_25_odds > best_odds:
                        best_odds = odds.under_25_odds
                        best_bookmaker = odds.bookmaker
                    elif market == "btts_yes" and odds.btts_yes_odds and odds.btts_yes_odds > best_odds:
                        best_odds = odds.btts_yes_odds
                        best_bookmaker = odds.bookmaker
                    elif market == "btts_no" and odds.btts_no_odds and odds.btts_no_odds > best_odds:
                        best_odds = odds.btts_no_odds
                        best_bookmaker = odds.bookmaker

                if best_odds <= 1.0:
                    continue

                book_prob = odds_to_prob(best_odds)
                edge = calculate_edge(model_prob, book_prob)

                # Only create edge if positive
                if edge > 3:  # At least 3% edge
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
                        bookmaker_name=best_bookmaker,
                        risk_level=risk,
                        kelly_stake=kelly,
                        confidence=confidence,
                    )
                    db.add(edge_calc)

            db.commit()

        # Summary
        total_matches = db.query(Match).count()
        total_edges = db.query(EdgeCalculation).count()

        logger.info("=" * 50)
        logger.info("SEED COMPLETED SUCCESSFULLY")
        logger.info("=" * 50)
        logger.info(f"Teams: {len(teams)}")
        logger.info(f"Matches: {total_matches}")
        logger.info(f"Edge calculations: {total_edges}")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Error during seed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()

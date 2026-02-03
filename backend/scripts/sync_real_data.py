"""
Sync real data from API-Football.

Fetches upcoming Ligue 1 fixtures, odds, and calculates predictions.
"""

from datetime import datetime, timedelta
from loguru import logger

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal, engine
from app.core import get_settings
from app.models.database import (
    Base, Competition, Team, Match, Prediction, MatchOdds, EdgeCalculation
)
from app.services.data.api_football import get_api_football_client, APIFootballClient


settings = get_settings()

# ELO calculation helpers
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


def sync_fixtures():
    """Sync real fixtures from API-Football."""
    logger.info("Starting real data sync from API-Football...")

    api = get_api_football_client()
    db = SessionLocal()

    try:
        # Check API status
        status = api.get_status()
        logger.info(f"API Status: {status}")

        # Get or create Ligue 1 competition
        # API-Football free plan only supports seasons 2022-2024
        # Using 2024 season for testing with real data
        from datetime import date
        current_date = date.today()
        current_season = 2024  # Free plan limitation
        logger.info(f"Using season: {current_season} (free plan)")

        competition = db.query(Competition).filter(Competition.api_id == 61).first()
        if not competition:
            competition = Competition(
                api_id=61,
                name="Ligue 1",
                short_name="L1",
                country="France",
                type="league",
                season=current_season,
                logo_url="https://media.api-sports.io/football/leagues/61.png"
            )
            db.add(competition)
            db.commit()
            db.refresh(competition)
        else:
            # Update season if changed
            if competition.season != current_season:
                competition.season = current_season
                db.commit()

        # Fetch teams if needed
        existing_teams = db.query(Team).filter(Team.api_id.isnot(None)).count()
        if existing_teams < 18:
            logger.info("Fetching Ligue 1 teams...")
            api_teams = api.get_teams(league_id=61, season=current_season)

            for team_data in api_teams:
                team_info = team_data.get("team", {})
                team_id = team_info.get("id")

                existing = db.query(Team).filter(Team.api_id == team_id).first()
                if not existing:
                    team = Team(
                        api_id=team_id,
                        name=team_info.get("name"),
                        short_name=team_info.get("code"),
                        code=team_info.get("code"),
                        logo_url=team_info.get("logo"),
                        elo_rating=1500,  # Default ELO
                    )
                    db.add(team)

            db.commit()
            logger.info(f"Synced {len(api_teams)} teams")

        # Fetch fixtures from season 2024 (free plan compatible)
        # Using end of season dates (May 2025) for real match data
        logger.info("Fetching Ligue 1 fixtures from season 2024...")

        # Get last matchdays of 2024 season
        fixture_date_from = date(2025, 5, 1)
        fixture_date_to = date(2025, 5, 25)

        fixtures = api.get_fixtures(
            league_id=61,
            season=current_season,
            date_from=fixture_date_from,
            date_to=fixture_date_to,
        )

        matches_created = 0
        odds_created = 0
        edges_created = 0

        for fixture in fixtures:
            fixture_info = fixture.get("fixture", {})
            fixture_id = fixture_info.get("id")

            # Skip if already exists
            existing_match = db.query(Match).filter(Match.api_id == fixture_id).first()
            if existing_match:
                continue

            teams_info = fixture.get("teams", {})
            home_team_id = teams_info.get("home", {}).get("id")
            away_team_id = teams_info.get("away", {}).get("id")

            # Get local team IDs
            home_team = db.query(Team).filter(Team.api_id == home_team_id).first()
            away_team = db.query(Team).filter(Team.api_id == away_team_id).first()

            if not home_team or not away_team:
                logger.warning(f"Teams not found for fixture {fixture_id}")
                continue

            # Parse kickoff time and adjust to future dates for demo
            kickoff_str = fixture_info.get("date")
            original_kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))

            # Shift dates to future for demo (keep time, change to next weeks)
            days_offset = (matches_created % 14) + 1  # Spread over 2 weeks
            demo_kickoff = datetime.now() + timedelta(days=days_offset)
            demo_kickoff = demo_kickoff.replace(
                hour=original_kickoff.hour,
                minute=original_kickoff.minute,
                second=0,
                microsecond=0
            )

            # Create match
            match = Match(
                api_id=fixture_id,
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                competition_id=competition.id,
                kickoff=demo_kickoff,
                matchday=fixture.get("league", {}).get("round", "").split(" - ")[-1] if fixture.get("league", {}).get("round") else None,
                status="scheduled",
            )
            db.add(match)
            db.commit()
            db.refresh(match)
            matches_created += 1

            # Calculate predictions
            probs_1x2 = calculate_match_probabilities(
                home_team.elo_rating or 1500,
                away_team.elo_rating or 1500
            )
            probs_goals = calculate_goals_probs(
                home_team.elo_rating or 1500,
                away_team.elo_rating or 1500
            )

            elo_diff = abs((home_team.elo_rating or 1500) - (away_team.elo_rating or 1500))
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

            # Fetch odds from API
            try:
                api_odds = api.get_odds(fixture_id)

                for odds_data in api_odds:
                    bookmakers = odds_data.get("bookmakers", [])

                    for bookmaker in bookmakers[:3]:  # Limit to 3 bookmakers
                        bk_name = bookmaker.get("name")
                        bets = bookmaker.get("bets", [])

                        home_odds = draw_odds = away_odds = None
                        over_25_odds = under_25_odds = None

                        for bet in bets:
                            bet_name = bet.get("name")
                            values = bet.get("values", [])

                            if bet_name == "Match Winner":
                                for v in values:
                                    if v.get("value") == "Home":
                                        home_odds = float(v.get("odd", 0))
                                    elif v.get("value") == "Draw":
                                        draw_odds = float(v.get("odd", 0))
                                    elif v.get("value") == "Away":
                                        away_odds = float(v.get("odd", 0))

                            elif bet_name == "Goals Over/Under":
                                for v in values:
                                    if "Over 2.5" in str(v.get("value", "")):
                                        over_25_odds = float(v.get("odd", 0))
                                    elif "Under 2.5" in str(v.get("value", "")):
                                        under_25_odds = float(v.get("odd", 0))

                        if home_odds and draw_odds and away_odds:
                            match_odds = MatchOdds(
                                match_id=match.id,
                                bookmaker=bk_name,
                                home_win_odds=home_odds,
                                draw_odds=draw_odds,
                                away_win_odds=away_odds,
                                over_25_odds=over_25_odds,
                                under_25_odds=under_25_odds,
                                home_win_implied=odds_to_prob(home_odds),
                                draw_implied=odds_to_prob(draw_odds),
                                away_win_implied=odds_to_prob(away_odds),
                            )
                            db.add(match_odds)
                            odds_created += 1

                db.commit()
            except Exception as e:
                logger.warning(f"Could not fetch odds for fixture {fixture_id}: {e}")

            # Calculate edges
            all_probs = {
                "1x2_home": probs_1x2["home_win"],
                "1x2_draw": probs_1x2["draw"],
                "1x2_away": probs_1x2["away_win"],
                **probs_goals
            }

            match_odds_list = db.query(MatchOdds).filter(MatchOdds.match_id == match.id).all()

            markets = [
                ("1x2_home", "home_win_odds"),
                ("1x2_draw", "draw_odds"),
                ("1x2_away", "away_win_odds"),
                ("over_25", "over_25_odds"),
                ("under_25", "under_25_odds"),
            ]

            for market, odds_attr in markets:
                model_prob = all_probs.get(market, 0)

                best_odds = 1.0
                best_bookmaker = ""

                for odds in match_odds_list:
                    odds_value = getattr(odds, odds_attr, None)
                    if odds_value and odds_value > best_odds:
                        best_odds = odds_value
                        best_bookmaker = odds.bookmaker

                if best_odds <= 1.0:
                    continue

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
                        bookmaker_name=best_bookmaker,
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


if __name__ == "__main__":
    sync_fixtures()

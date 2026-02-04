"""
Sync real data from Football-Data.org + The Odds API.

Uses:
- Football-Data.org: Real fixtures, teams, standings
- The Odds API: Real betting odds from multiple bookmakers
- Dixon-Coles Model: Advanced Poisson model for predictions
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
from app.services.data.odds_api import get_odds_api_client, TheOddsAPIClient
from app.services.ml.dixon_coles import get_dixon_coles_model, get_team_rating


settings = get_settings()


def odds_to_prob(odds: float) -> float:
    """Convert decimal odds to implied probability."""
    if odds <= 1:
        return 0
    return round(1 / odds, 4)


def calculate_edge(model_prob: float, book_prob: float) -> float:
    """Calculate edge percentage."""
    if book_prob <= 0:
        return 0
    return round((model_prob - book_prob) / book_prob * 100, 2)


def classify_risk(model_prob: float, edge: float) -> str:
    """Classify bet risk level based on probability and edge."""
    if model_prob >= 0.6:
        return "safe"
    elif model_prob >= 0.4:
        return "medium"
    else:
        return "risky"


def kelly_criterion(prob: float, odds: float, fraction: float = 0.5) -> float:
    """Calculate Kelly criterion stake (half-Kelly by default)."""
    if odds <= 1 or prob <= 0:
        return 0
    b = odds - 1
    kelly = ((prob * odds) - 1) / b
    return round(max(0, kelly * fraction), 4)


def match_teams_fuzzy(name1: str, name2: str) -> bool:
    """Fuzzy match two team names."""
    n1 = name1.lower().replace("fc ", "").replace(" fc", "").strip()
    n2 = name2.lower().replace("fc ", "").replace(" fc", "").strip()
    return n1 in n2 or n2 in n1


def fetch_real_odds(odds_client: TheOddsAPIClient, sport_key: str = "soccer_france_ligue_one"):
    """Fetch real odds from The Odds API."""
    settings = get_settings()

    if not settings.odds_api_key:
        logger.warning("No ODDS_API_KEY configured - skipping real odds fetch")
        return []

    try:
        odds_data = odds_client.get_odds(sport_key)
        logger.info(f"Fetched real odds for {len(odds_data)} matches from The Odds API")
        return odds_data
    except Exception as e:
        logger.error(f"Failed to fetch odds: {e}")
        return []


def sync_fixtures(league: str = "ligue_1"):
    """
    Sync real fixtures from Football-Data.org with real odds from The Odds API.
    Uses Dixon-Coles model for predictions.

    Args:
        league: League to sync (ligue_1, premier_league, la_liga, bundesliga, serie_a)
    """
    logger.info("=" * 60)
    logger.info("SYNCING REAL DATA WITH DIXON-COLES MODEL")
    logger.info("=" * 60)

    # League configurations
    LEAGUES = {
        "ligue_1": {
            "fd_code": FootballDataOrgClient.LIGUE_1,
            "odds_key": TheOddsAPIClient.SPORTS["ligue_1"],
            "api_id": 61,
            "name": "Ligue 1",
            "country": "France",
        },
        "premier_league": {
            "fd_code": FootballDataOrgClient.PREMIER_LEAGUE,
            "odds_key": TheOddsAPIClient.SPORTS["premier_league"],
            "api_id": 39,
            "name": "Premier League",
            "country": "England",
        },
        "la_liga": {
            "fd_code": FootballDataOrgClient.LA_LIGA,
            "odds_key": TheOddsAPIClient.SPORTS["la_liga"],
            "api_id": 140,
            "name": "La Liga",
            "country": "Spain",
        },
        "bundesliga": {
            "fd_code": FootballDataOrgClient.BUNDESLIGA,
            "odds_key": TheOddsAPIClient.SPORTS["bundesliga"],
            "api_id": 78,
            "name": "Bundesliga",
            "country": "Germany",
        },
        "serie_a": {
            "fd_code": FootballDataOrgClient.SERIE_A,
            "odds_key": TheOddsAPIClient.SPORTS["serie_a"],
            "api_id": 135,
            "name": "Serie A",
            "country": "Italy",
        },
    }

    league_config = LEAGUES.get(league, LEAGUES["ligue_1"])
    logger.info(f"Syncing {league_config['name']} ({league_config['country']})...")

    # Initialize Dixon-Coles model for this league
    dc_model = get_dixon_coles_model(league)
    logger.info(f"Loaded Dixon-Coles model with {len(dc_model.teams)} team ratings")

    api = get_football_data_client()
    odds_client = get_odds_api_client()
    db = SessionLocal()

    try:
        # Get competition info
        comp_data = api.get_competition(league_config["fd_code"])
        logger.info(f"Competition: {comp_data.get('name')} - Season {comp_data.get('currentSeason', {}).get('startDate', 'N/A')}")

        current_season = comp_data.get("currentSeason", {})
        season_year = current_season.get("startDate", "2025")[:4]

        # Get or create competition
        competition = db.query(Competition).filter(Competition.api_id == league_config["api_id"]).first()
        if not competition:
            competition = Competition(
                api_id=league_config["api_id"],
                name=league_config["name"],
                short_name=league_config["name"][:3].upper(),
                country=league_config["country"],
                type="league",
                season=int(season_year),
                logo_url=f"https://media.api-sports.io/football/leagues/{league_config['api_id']}.png"
            )
            db.add(competition)
            db.commit()
            db.refresh(competition)
        else:
            competition.season = int(season_year)
            db.commit()

        # Fetch REAL odds from The Odds API
        logger.info("Fetching real odds from The Odds API...")
        real_odds_data = fetch_real_odds(odds_client, league_config["odds_key"])
        logger.info(f"Got real odds for {len(real_odds_data)} matches")

        # Fetch teams
        logger.info(f"Fetching {league_config['name']} teams...")
        api_teams = api.get_teams(league_config["fd_code"])
        logger.info(f"Found {len(api_teams)} teams")

        team_map = {}  # API team ID -> local team
        for team_data in api_teams:
            team_id = team_data.get("id")
            team_name = team_data.get("name")

            existing = db.query(Team).filter(Team.api_id == team_id).first()
            if not existing:
                # Get Dixon-Coles rating
                dc_rating = get_team_rating(team_name)
                team = Team(
                    api_id=team_id,
                    name=team_name,
                    short_name=team_data.get("tla"),
                    code=team_data.get("tla"),
                    logo_url=team_data.get("crest"),
                    # Store attack/defense as ELO for backwards compatibility
                    # ELO = (attack * 500) + (2 - defense) * 500 normalized to ~1500 range
                    elo_rating=int(dc_rating['attack'] * 500 + (2 - dc_rating['defense']) * 500),
                )
                db.add(team)
                db.commit()
                db.refresh(team)
                team_map[team_id] = team
            else:
                team_map[team_id] = existing

        logger.info(f"Synced {len(team_map)} teams")

        # Fetch scheduled matches
        logger.info(f"Fetching scheduled {league_config['name']} matches...")
        matches = api.get_scheduled_matches(league_config["fd_code"])
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

            # Calculate predictions using Dixon-Coles model
            dc_predictions = dc_model.predict_all_markets(home_team.name, away_team.name)
            probs_1x2 = dc_predictions['1x2']
            probs_over_under = dc_predictions['over_under']
            probs_btts = dc_predictions['btts']
            expected_goals = dc_predictions['expected_goals']

            # Confidence based on expected goals difference (higher diff = more confident)
            xg_diff = abs(expected_goals['home'] - expected_goals['away'])
            confidence = min(0.9, 0.5 + xg_diff * 0.15)

            prediction = Prediction(
                match_id=match.id,
                home_win_prob=probs_1x2["home_win"] * 100,
                draw_prob=probs_1x2["draw"] * 100,
                away_win_prob=probs_1x2["away_win"] * 100,
                confidence=confidence,
                model_version="v2.0-dixon-coles",
            )
            db.add(prediction)
            db.commit()
            db.refresh(prediction)

            logger.debug(f"  DC predictions: H={probs_1x2['home_win']:.1%} D={probs_1x2['draw']:.1%} A={probs_1x2['away_win']:.1%}")

            # Find REAL odds for this match from The Odds API
            matched_odds = None
            for odds_match in real_odds_data:
                if (match_teams_fuzzy(home_team.name, odds_match.home_team) and
                    match_teams_fuzzy(away_team.name, odds_match.away_team)):
                    matched_odds = odds_match
                    break

            if matched_odds and matched_odds.bookmakers:
                # Create odds records for each REAL bookmaker
                for bm in matched_odds.bookmakers:
                    match_odds = MatchOdds(
                        match_id=match.id,
                        bookmaker=bm.bookmaker,
                        home_win_odds=bm.home_win,
                        draw_odds=bm.draw,
                        away_win_odds=bm.away_win,
                        over_25_odds=bm.over_25 if bm.over_25 else None,
                        under_25_odds=bm.under_25 if bm.under_25 else None,
                        btts_yes_odds=bm.btts_yes if bm.btts_yes else None,
                        btts_no_odds=bm.btts_no if bm.btts_no else None,
                        home_win_implied=odds_to_prob(bm.home_win),
                        draw_implied=odds_to_prob(bm.draw),
                        away_win_implied=odds_to_prob(bm.away_win),
                    )
                    db.add(match_odds)
                    odds_created += 1

                db.commit()
                logger.info(f"  ✓ {home_team.name} vs {away_team.name} - {len(matched_odds.bookmakers)} real bookmakers")

                # Calculate edges (compare Dixon-Coles model vs REAL bookmaker odds)
                # Get best odds across all bookmakers
                best_1x2 = matched_odds.get_best_odds("1x2")

                # All markets to check for edges
                markets = [
                    ("1x2_home", best_1x2.get("home_win", {}).get("odds", 0), best_1x2.get("home_win", {}).get("bookmaker", ""), probs_1x2["home_win"]),
                    ("1x2_draw", best_1x2.get("draw", {}).get("odds", 0), best_1x2.get("draw", {}).get("bookmaker", ""), probs_1x2["draw"]),
                    ("1x2_away", best_1x2.get("away_win", {}).get("odds", 0), best_1x2.get("away_win", {}).get("bookmaker", ""), probs_1x2["away_win"]),
                    ("over_25", 0, "", probs_over_under.get("over_2.5", 0)),  # Odds API doesn't have O/U in free tier
                    ("btts_yes", 0, "", probs_btts.get("btts_yes", 0)),  # Same for BTTS
                ]

                for market, best_odds, bookmaker, model_prob in markets:
                    if best_odds <= 1.0 or model_prob <= 0:
                        continue

                    book_prob = odds_to_prob(best_odds)
                    edge = calculate_edge(model_prob, book_prob)

                    # Only create edge calculation if edge > 3%
                    if edge > 3:
                        risk = classify_risk(model_prob, edge)
                        kelly = kelly_criterion(model_prob, best_odds)

                        edge_calc = EdgeCalculation(
                            match_id=match.id,
                            prediction_id=prediction.id,
                            market=market,
                            model_probability=model_prob,
                            bookmaker_probability=book_prob,
                            edge_percentage=edge,
                            best_odds=best_odds,
                            bookmaker_name=bookmaker,
                            risk_level=risk,
                            kelly_stake=kelly,
                            confidence=confidence,
                        )
                        db.add(edge_calc)
                        edges_created += 1

                db.commit()
            else:
                logger.warning(f"  ⚠ {home_team.name} vs {away_team.name} - No real odds found")

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
        odds_client.close()


def sync_all_leagues():
    """Sync all supported leagues with real data."""
    leagues = ["ligue_1", "premier_league", "la_liga", "bundesliga", "serie_a"]
    results = {}

    for league in leagues:
        try:
            result = sync_fixtures(league)
            results[league] = result
        except Exception as e:
            logger.error(f"Failed to sync {league}: {e}")
            results[league] = {"error": str(e)}

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sync real football data")
    parser.add_argument(
        "--league",
        choices=["ligue_1", "premier_league", "la_liga", "bundesliga", "serie_a", "all"],
        default="ligue_1",
        help="League to sync (default: ligue_1)"
    )
    args = parser.parse_args()

    if args.league == "all":
        sync_all_leagues()
    else:
        sync_fixtures(args.league)

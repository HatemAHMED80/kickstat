"""
Sync real odds from The Odds API.

Updates match odds in database with real bookmaker data.
Falls back to simulated odds if API not configured.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.core.database import SessionLocal
from app.core import get_settings
from app.models.database import Match, MatchOdds, Team
from app.services.data.odds_api import get_odds_api_client, TheOddsAPIClient


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    # Remove common suffixes/prefixes
    replacements = {
        " FC": "",
        "FC ": "",
        " AC": "",
        "AC ": "",
        " SC": "",
        "SC ": "",
        "Paris Saint-Germain": "Paris Saint Germain",
        "PSG": "Paris Saint Germain",
        "Olympique de Marseille": "Marseille",
        "Olympique Lyonnais": "Lyon",
        "LOSC": "Lille",
    }

    result = name
    for old, new in replacements.items():
        result = result.replace(old, new)

    return result.strip()


def find_matching_team(db_teams: list, api_team_name: str) -> str:
    """Find matching team in database by name."""
    normalized_api = normalize_team_name(api_team_name).lower()

    for team in db_teams:
        normalized_db = normalize_team_name(team.name).lower()
        if normalized_api in normalized_db or normalized_db in normalized_api:
            return team

    return None


def sync_real_odds():
    """Sync real odds from The Odds API."""
    settings = get_settings()
    db = SessionLocal()

    if not settings.odds_api_key:
        logger.warning("ODDS_API_KEY not configured - skipping real odds sync")
        logger.info("Get a free API key at: https://the-odds-api.com/")
        return {"error": "API key not configured"}

    client = get_odds_api_client()

    try:
        logger.info("=== Syncing Real Odds from The Odds API ===")

        # Get all teams for matching
        all_teams = db.query(Team).all()

        # Get upcoming matches from database
        upcoming_matches = (
            db.query(Match)
            .filter(Match.status == "scheduled")
            .filter(Match.kickoff >= datetime.utcnow())
            .all()
        )

        logger.info(f"Found {len(upcoming_matches)} upcoming matches in database")

        # Get live odds from API
        odds_data = client.get_ligue1_odds()
        logger.info(f"Got odds for {len(odds_data)} matches from API")

        updated = 0
        matched = 0

        for api_match in odds_data:
            # Try to match with database
            api_home = api_match.home_team
            api_away = api_match.away_team

            home_team = find_matching_team(all_teams, api_home)
            away_team = find_matching_team(all_teams, api_away)

            if not home_team or not away_team:
                logger.debug(f"Could not match: {api_home} vs {api_away}")
                continue

            # Find match in database
            db_match = (
                db.query(Match)
                .filter(Match.home_team_id == home_team.id)
                .filter(Match.away_team_id == away_team.id)
                .filter(Match.status == "scheduled")
                .first()
            )

            if not db_match:
                logger.debug(f"No scheduled match found for {home_team.name} vs {away_team.name}")
                continue

            matched += 1

            # Get best odds
            best_odds = api_match.get_best_odds("1x2")

            if not best_odds:
                continue

            # Update or create odds record
            existing_odds = (
                db.query(MatchOdds)
                .filter(MatchOdds.match_id == db_match.id)
                .filter(MatchOdds.bookmaker == "Best Available")
                .first()
            )

            if existing_odds:
                existing_odds.home_win_odds = best_odds["home_win"]["odds"]
                existing_odds.draw_odds = best_odds["draw"]["odds"]
                existing_odds.away_win_odds = best_odds["away_win"]["odds"]
                existing_odds.home_win_implied = 1 / best_odds["home_win"]["odds"]
                existing_odds.draw_implied = 1 / best_odds["draw"]["odds"]
                existing_odds.away_win_implied = 1 / best_odds["away_win"]["odds"]
                existing_odds.fetched_at = datetime.utcnow()
            else:
                new_odds = MatchOdds(
                    match_id=db_match.id,
                    bookmaker="Best Available",
                    home_win_odds=best_odds["home_win"]["odds"],
                    draw_odds=best_odds["draw"]["odds"],
                    away_win_odds=best_odds["away_win"]["odds"],
                    home_win_implied=1 / best_odds["home_win"]["odds"],
                    draw_implied=1 / best_odds["draw"]["odds"],
                    away_win_implied=1 / best_odds["away_win"]["odds"],
                )
                db.add(new_odds)

            # Also add individual bookmaker odds
            for bm in api_match.bookmakers[:5]:  # Top 5 bookmakers
                bm_odds = (
                    db.query(MatchOdds)
                    .filter(MatchOdds.match_id == db_match.id)
                    .filter(MatchOdds.bookmaker == bm.bookmaker)
                    .first()
                )

                if bm_odds:
                    bm_odds.home_win_odds = bm.home_win
                    bm_odds.draw_odds = bm.draw
                    bm_odds.away_win_odds = bm.away_win
                    bm_odds.home_win_implied = 1 / bm.home_win
                    bm_odds.draw_implied = 1 / bm.draw
                    bm_odds.away_win_implied = 1 / bm.away_win
                    bm_odds.fetched_at = datetime.utcnow()
                else:
                    new_bm_odds = MatchOdds(
                        match_id=db_match.id,
                        bookmaker=bm.bookmaker,
                        home_win_odds=bm.home_win,
                        draw_odds=bm.draw,
                        away_win_odds=bm.away_win,
                        home_win_implied=1 / bm.home_win,
                        draw_implied=1 / bm.draw,
                        away_win_implied=1 / bm.away_win,
                    )
                    db.add(new_bm_odds)

            updated += 1

            logger.info(
                f"Updated odds: {home_team.name} vs {away_team.name} | "
                f"H:{best_odds['home_win']['odds']:.2f} D:{best_odds['draw']['odds']:.2f} "
                f"A:{best_odds['away_win']['odds']:.2f}"
            )

        db.commit()

        usage = client.get_usage()

        logger.info("=" * 60)
        logger.info("SYNC COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Matches in API: {len(odds_data)}")
        logger.info(f"Matches matched: {matched}")
        logger.info(f"Odds updated: {updated}")
        logger.info(f"API requests remaining: {usage.get('remaining_requests', 'N/A')}")
        logger.info("=" * 60)

        return {
            "api_matches": len(odds_data),
            "matched": matched,
            "updated": updated,
            "api_usage": usage,
        }

    except Exception as e:
        logger.error(f"Error syncing odds: {e}")
        db.rollback()
        raise
    finally:
        db.close()
        client.close()


if __name__ == "__main__":
    sync_real_odds()

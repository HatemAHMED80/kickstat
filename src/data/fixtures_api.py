"""Fixtures API integration using football-data.org.

API Docs: https://www.football-data.org/documentation/api
Free tier: 10 requests/minute (14,400/day), current season access
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests
from loguru import logger


# Competition IDs for football-data.org
COMPETITION_IDS = {
    "ligue_1": 2015,        # Ligue 1 (France)
    "premier_league": 2021,  # Premier League (England)
    "serie_a": 2019,         # Serie A (Italy)
    "bundesliga": 2002,      # Bundesliga (Germany)
    "la_liga": 2014,         # La Liga (Spain)
}

# Team name mapping: football-data.org → Our historical data format
TEAM_NAME_MAPPING = {
    # Ligue 1
    "Paris Saint-Germain FC": "Paris SG",
    "Olympique de Marseille": "Marseille",
    "AS Monaco FC": "Monaco",
    "Lille OSC": "Lille",
    "Olympique Lyonnais": "Lyon",
    "RC Lens": "Lens",
    "OGC Nice": "Nice",
    "Stade Rennais FC 1901": "Rennes",
    "Montpellier HSC": "Montpellier",
    "RC Strasbourg Alsace": "Strasbourg",
    "FC Nantes": "Nantes",
    "Stade Brestois 29": "Brest",
    "Stade de Reims": "Reims",
    "Toulouse FC": "Toulouse",
    "Le Havre AC": "Le Havre",
    "AJ Auxerre": "Auxerre",
    "Angers SCO": "Angers",
    "AS Saint-Étienne": "St Etienne",
    "Paris FC": "Paris FC",

    # Premier League
    "Manchester City FC": "Man City",
    "Manchester United FC": "Man United",
    "Liverpool FC": "Liverpool",
    "Arsenal FC": "Arsenal",
    "Chelsea FC": "Chelsea",
    "Tottenham Hotspur FC": "Tottenham",
    "Newcastle United FC": "Newcastle",
    "Brighton & Hove Albion FC": "Brighton",
    "Aston Villa FC": "Aston Villa",
    "West Ham United FC": "West Ham",
    "Crystal Palace FC": "Crystal Palace",
    "Fulham FC": "Fulham",
    "Brentford FC": "Brentford",
    "AFC Bournemouth": "Bournemouth",
    "Everton FC": "Everton",
    "Nottingham Forest FC": "Nott'm Forest",
    "Wolverhampton Wanderers FC": "Wolves",
    "Leicester City FC": "Leicester",
    "Ipswich Town FC": "Ipswich",
    "Southampton FC": "Southampton",
    "Leeds United FC": "Leeds",
}


def normalize_team_name(api_name: str) -> str:
    """Normalize team name from football-data.org to our format.

    Args:
        api_name: Team name from football-data.org.

    Returns:
        Normalized team name matching our historical data.
    """
    # Try exact mapping first
    if api_name in TEAM_NAME_MAPPING:
        return TEAM_NAME_MAPPING[api_name]

    # Fallback: strip "FC", "AFC", etc. and try again
    clean_name = api_name.replace(" FC", "").replace(" AFC", "").replace(" United", "")
    if clean_name in TEAM_NAME_MAPPING.values():
        return clean_name

    # Last resort: return as-is with warning
    logger.warning(f"Unknown team name from API: {api_name}")
    return api_name


def fetch_fixtures(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    leagues: Optional[List[str]] = None,
    status: str = "SCHEDULED"
) -> List[Dict]:
    """Fetch fixtures from football-data.org.

    Args:
        date_from: Start date in YYYY-MM-DD format. Defaults to today.
        date_to: End date in YYYY-MM-DD format. Defaults to date_from + 7 days.
        leagues: List of league slugs (e.g., ["ligue_1", "premier_league"]).
                Defaults to Ligue 1 and Premier League.
        status: Match status filter. Options: SCHEDULED, LIVE, FINISHED, etc.

    Returns:
        List of fixture dicts with keys: home, away, league, kickoff, fixture_id.

    Raises:
        ValueError: If API key is not set.
        requests.RequestException: If API request fails.
    """
    api_key = os.getenv("FOOTBALL_DATA_ORG_KEY")
    if not api_key or api_key == "your_key_here":
        raise ValueError(
            "FOOTBALL_DATA_ORG_KEY not set. Get your free key at "
            "https://www.football-data.org/client/register and add to .env file."
        )

    # Default to today
    if date_from is None:
        date_from = datetime.now().strftime("%Y-%m-%d")

    # Default to 7 days from date_from
    if date_to is None:
        date_to_obj = datetime.strptime(date_from, "%Y-%m-%d") + timedelta(days=7)
        date_to = date_to_obj.strftime("%Y-%m-%d")

    # Default to Ligue 1 + Premier League
    if leagues is None:
        leagues = ["ligue_1", "premier_league"]

    logger.info(f"Fetching fixtures from {date_from} to {date_to} for leagues: {leagues}")

    # API request headers
    base_url = "https://api.football-data.org/v4"
    headers = {"X-Auth-Token": api_key}

    # Fetch fixtures for each league
    all_fixtures = []
    for league_slug in leagues:
        if league_slug not in COMPETITION_IDS:
            logger.warning(f"Unknown league slug: {league_slug}")
            continue

        competition_id = COMPETITION_IDS[league_slug]
        league_name = league_slug.replace("_", " ").title()

        try:
            # Request fixtures for this competition
            response = requests.get(
                f"{base_url}/competitions/{competition_id}/matches",
                headers=headers,
                params={
                    "dateFrom": date_from,
                    "dateTo": date_to,
                    "status": status,
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            # Parse matches
            matches = data.get("matches", [])
            logger.info(f"Found {len(matches)} {status} matches for {league_name}")

            for match in matches:
                try:
                    # Normalize team names
                    home_team = normalize_team_name(match["homeTeam"]["name"])
                    away_team = normalize_team_name(match["awayTeam"]["name"])

                    fixture = {
                        "home": home_team,
                        "away": away_team,
                        "league": league_name,
                        "kickoff": match["utcDate"],  # ISO format
                        "fixture_id": match["id"],
                        "venue": match.get("venue", "Unknown"),
                        "status": match["status"],
                    }
                    all_fixtures.append(fixture)

                except (KeyError, TypeError) as e:
                    logger.warning(f"Failed to parse match: {e}")
                    continue

        except requests.RequestException as e:
            logger.error(f"API request failed for {league_name}: {e}")
            # Don't fail completely - continue with other leagues
            continue

    logger.info(f"Total: {len(all_fixtures)} fixtures across {len(leagues)} leagues")
    return all_fixtures


def fetch_today_fixtures(leagues: Optional[List[str]] = None) -> List[Dict]:
    """Fetch today's upcoming fixtures.

    Args:
        leagues: List of league slugs. Defaults to Ligue 1 + Premier League.

    Returns:
        List of fixture dicts.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    return fetch_fixtures(date_from=today, date_to=today, leagues=leagues)


def fetch_tomorrow_fixtures(leagues: Optional[List[str]] = None) -> List[Dict]:
    """Fetch tomorrow's upcoming fixtures.

    Args:
        leagues: List of league slugs. Defaults to Ligue 1 + Premier League.

    Returns:
        List of fixture dicts.
    """
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    return fetch_fixtures(date_from=tomorrow, date_to=tomorrow, leagues=leagues)


def fetch_week_fixtures(leagues: Optional[List[str]] = None) -> List[Dict]:
    """Fetch fixtures for the next 7 days.

    Args:
        leagues: List of league slugs. Defaults to Ligue 1 + Premier League.

    Returns:
        List of fixture dicts.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    week_later = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    return fetch_fixtures(date_from=today, date_to=week_later, leagues=leagues)


# Example usage and testing
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("Testing football-data.org fixtures API...\n")

    try:
        # Test today's fixtures
        fixtures = fetch_today_fixtures()

        if not fixtures:
            print("⚠️  No fixtures today. Trying this week...")
            fixtures = fetch_week_fixtures()

        if fixtures:
            print(f"✅ Found {len(fixtures)} fixtures:\n")
            for f in fixtures[:10]:  # Show first 10
                print(f"  {f['league']}: {f['home']} vs {f['away']}")
                print(f"    Kickoff: {f['kickoff']}")
                print(f"    Venue: {f['venue']}\n")
        else:
            print("⚠️  No upcoming fixtures found.")

    except ValueError as e:
        print(f"❌ Configuration error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

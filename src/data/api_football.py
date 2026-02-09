"""API-Football integration for live fixtures and odds.

API Docs: https://www.api-football.com/documentation-v3
Free tier: 100 requests/day
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests
from loguru import logger


# League IDs for API-Football
LEAGUE_IDS = {
    "ligue_1": 61,
    "premier_league": 39,
    "serie_a": 135,
    "bundesliga": 78,
    "la_liga": 140,
}

# Team name mapping: API-Football → Our historical data
# API-Football uses full official names, we use football-data.co.uk names
TEAM_NAME_MAPPING = {
    # Ligue 1
    "Paris Saint Germain": "Paris SG",
    "Olympique Marseille": "Marseille",
    "AS Monaco": "Monaco",
    "Lille": "Lille",
    "Lyon": "Lyon",
    "Lens": "Lens",
    "Nice": "Nice",
    "Rennes": "Rennes",
    "Montpellier": "Montpellier",
    "Strasbourg": "Strasbourg",
    "Nantes": "Nantes",
    "Brest": "Brest",
    "Reims": "Reims",
    "Toulouse": "Toulouse",
    "Le Havre": "Le Havre",
    "Auxerre": "Auxerre",
    "Angers": "Angers",
    "Saint-Etienne": "St Etienne",

    # Premier League
    "Manchester City": "Man City",
    "Manchester United": "Man United",
    "Liverpool": "Liverpool",
    "Arsenal": "Arsenal",
    "Chelsea": "Chelsea",
    "Tottenham": "Tottenham",
    "Newcastle United": "Newcastle",
    "Brighton": "Brighton",
    "Aston Villa": "Aston Villa",
    "West Ham": "West Ham",
    "Crystal Palace": "Crystal Palace",
    "Fulham": "Fulham",
    "Brentford": "Brentford",
    "Bournemouth": "Bournemouth",
    "Everton": "Everton",
    "Nottingham Forest": "Nott'm Forest",
    "Wolves": "Wolves",
    "Leicester": "Leicester",
    "Ipswich": "Ipswich",
    "Southampton": "Southampton",
}


def normalize_team_name(api_name: str) -> str:
    """Normalize team name from API-Football to our format.

    Args:
        api_name: Team name from API-Football.

    Returns:
        Normalized team name matching our historical data.
    """
    # Try exact mapping first
    if api_name in TEAM_NAME_MAPPING:
        return TEAM_NAME_MAPPING[api_name]

    # Fallback: return as-is (might cause KeyError in predictions)
    logger.warning(f"Unknown team name from API: {api_name}")
    return api_name


def fetch_fixtures(
    date: Optional[str] = None,
    leagues: Optional[List[str]] = None,
    timezone: str = "Europe/Paris"
) -> List[Dict]:
    """Fetch fixtures from API-Football.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
        leagues: List of league slugs (e.g., ["ligue_1", "premier_league"]).
                Defaults to Ligue 1 and Premier League.
        timezone: Timezone for match times. Default: Europe/Paris.

    Returns:
        List of fixture dicts with keys: home_team, away_team, league, kickoff.

    Raises:
        ValueError: If API key is not set.
        requests.RequestException: If API request fails.
    """
    api_key = os.getenv("API_FOOTBALL_KEY")
    if not api_key:
        raise ValueError(
            "API_FOOTBALL_KEY not set. Get your free key at "
            "https://www.api-football.com and add to .env file."
        )

    # Default to today
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # Default to Ligue 1 + Premier League
    if leagues is None:
        leagues = ["ligue_1", "premier_league"]

    # Get season from the requested date
    # Football seasons run Aug-May, so if we're before August, use previous year
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    year = date_obj.year
    if date_obj.month < 8:
        season = year - 1
    else:
        season = year

    logger.info(f"Fetching fixtures for {date} (season {season}) from API-Football (leagues: {leagues})")

    # API request headers
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {
        "x-apisports-key": api_key,
    }

    # Fetch fixtures for each league separately (API limitation)
    all_fixtures = []
    for league_slug in leagues:
        league_id = LEAGUE_IDS[league_slug]

        params = {
            "date": date,
            "league": league_id,
            "season": season,
            "timezone": timezone,
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check API response structure
            if "errors" in data and data["errors"]:
                logger.warning(f"API-Football errors for {league_slug}: {data['errors']}")
                continue

            if "response" not in data:
                logger.warning(f"Unexpected API response structure for {league_slug}: {data}")
                continue

            # Parse fixtures
            for match in data["response"]:
                try:
                    # Extract league name
                    league_name = league_slug.replace("_", " ").title()

                    # Normalize team names
                    home_team = normalize_team_name(match["teams"]["home"]["name"])
                    away_team = normalize_team_name(match["teams"]["away"]["name"])

                    fixture = {
                        "home": home_team,
                        "away": away_team,
                        "league": league_name,
                        "kickoff": match["fixture"]["date"],  # ISO format
                        "fixture_id": match["fixture"]["id"],  # For reference
                        "venue": match["fixture"]["venue"]["name"] if match["fixture"]["venue"]["name"] else "Unknown",
                    }
                    all_fixtures.append(fixture)

                except (KeyError, TypeError) as e:
                    logger.warning(f"Failed to parse fixture: {e}")
                    continue

        except requests.RequestException as e:
            logger.warning(f"API-Football request failed for {league_slug}: {e}")
            continue

    logger.info(f"Found {len(all_fixtures)} upcoming fixtures for {date}")
    return all_fixtures


def fetch_today_fixtures(leagues: Optional[List[str]] = None) -> List[Dict]:
    """Fetch today's fixtures.

    Args:
        leagues: List of league slugs. Defaults to Ligue 1 + Premier League.

    Returns:
        List of fixture dicts.
    """
    return fetch_fixtures(date=None, leagues=leagues)


def fetch_tomorrow_fixtures(leagues: Optional[List[str]] = None) -> List[Dict]:
    """Fetch tomorrow's fixtures.

    Args:
        leagues: List of league slugs. Defaults to Ligue 1 + Premier League.

    Returns:
        List of fixture dicts.
    """
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    return fetch_fixtures(date=tomorrow, leagues=leagues)


def fetch_week_fixtures(leagues: Optional[List[str]] = None) -> List[Dict]:
    """Fetch fixtures for the next 7 days.

    Args:
        leagues: List of league slugs. Defaults to Ligue 1 + Premier League.

    Returns:
        List of fixture dicts (may be from multiple days).
    """
    all_fixtures = []
    for i in range(7):
        date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
        try:
            fixtures = fetch_fixtures(date=date, leagues=leagues)
            all_fixtures.extend(fixtures)
        except Exception as e:
            logger.warning(f"Failed to fetch fixtures for {date}: {e}")
            continue

    return all_fixtures


# Example usage and testing
if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Load .env
    from dotenv import load_dotenv
    load_dotenv()

    # Test fetch
    print("Testing API-Football integration...\n")

    try:
        fixtures = fetch_today_fixtures()

        if not fixtures:
            print("⚠️  No fixtures found for today. Trying tomorrow...")
            fixtures = fetch_tomorrow_fixtures()

        if fixtures:
            print(f"✅ Found {len(fixtures)} fixtures:\n")
            for f in fixtures:
                print(f"  {f['league']}: {f['home']} vs {f['away']}")
                print(f"    Kickoff: {f['kickoff']}")
                print(f"    Venue: {f['venue']}\n")
        else:
            print("⚠️  No fixtures found for today or tomorrow.")
            print("    This is normal if there are no matches scheduled.")

    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

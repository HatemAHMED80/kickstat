"""
Understat Scraper
Scrapes xG (expected goals) data for Ligue 1 matches.

Free source for advanced statistics.
"""

import json
import re
import time
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from app.core import get_settings

settings = get_settings()


@dataclass
class MatchXG:
    """Expected goals data for a match."""

    understat_id: str
    home_team: str
    away_team: str
    date: datetime
    home_xg: float
    away_xg: float
    home_goals: int
    away_goals: int

    # Detailed shot data
    home_shots: int = 0
    away_shots: int = 0
    home_shots_on_target: int = 0
    away_shots_on_target: int = 0


@dataclass
class TeamXG:
    """Season xG statistics for a team."""

    team_name: str
    matches_played: int
    xg: float  # Total expected goals
    xga: float  # Total expected goals against
    goals: int
    goals_against: int
    xg_diff: float  # xG - xGA
    npxg: float  # Non-penalty xG
    npxga: float


class UnderstatScraper:
    """Scraper for Understat xG data."""

    BASE_URL = "https://understat.com"

    # Team name mapping (Understat -> standard)
    TEAM_MAPPING = {
        "Paris Saint Germain": "Paris Saint-Germain",
        "Olympique Marseille": "Olympique de Marseille",
        "Olympique Lyonnais": "Olympique Lyon",
        "AS Monaco": "AS Monaco",
        "Lille": "LOSC Lille",
        "Rennes": "Stade Rennais FC",
        "Lens": "RC Lens",
        "Nice": "OGC Nice",
        "Reims": "Stade de Reims",
        "Montpellier": "Montpellier HSC",
        "Nantes": "FC Nantes",
        "Strasbourg": "RC Strasbourg Alsace",
        "Toulouse": "Toulouse FC",
        "Brest": "Stade Brestois 29",
        "Le Havre": "Le Havre AC",
        "Metz": "FC Metz",
        "Clermont Foot": "Clermont Foot 63",
        "Lorient": "FC Lorient",
    }

    def __init__(self):
        self.client = httpx.Client(
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        self.rate_limit_delay = 60.0 / settings.understat_rate_limit

    def _get_page(self, url: str) -> str:
        """Fetch page with rate limiting."""
        time.sleep(self.rate_limit_delay)
        logger.debug(f"Fetching: {url}")

        response = self.client.get(url)
        response.raise_for_status()
        return response.text

    def _extract_json_data(self, html: str, var_name: str) -> Optional[dict]:
        """Extract JSON data from JavaScript variable in page."""
        pattern = rf"var\s+{var_name}\s*=\s*JSON\.parse\('(.+?)'\)"
        match = re.search(pattern, html)

        if not match:
            return None

        # Unescape the JSON string
        json_str = match.group(1)
        json_str = json_str.encode().decode("unicode_escape")

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return None

    # =========================================================================
    # LEAGUE DATA
    # =========================================================================

    def get_league_matches(self, season: int = 2024) -> list[MatchXG]:
        """Get all matches with xG data for a season."""
        # Understat uses season format like "2024" for 2024-2025
        url = f"{self.BASE_URL}/league/Ligue_1/{season}"
        matches = []

        try:
            html = self._get_page(url)
            data = self._extract_json_data(html, "datesData")

            if not data:
                logger.warning("No match data found")
                return matches

            for match_data in data:
                match = self._parse_match_data(match_data)
                if match:
                    matches.append(match)

        except Exception as e:
            logger.error(f"Failed to scrape league matches: {e}")

        logger.info(f"Found {len(matches)} matches with xG data")
        return matches

    def get_team_season_stats(self, season: int = 2024) -> list[TeamXG]:
        """Get season xG statistics for all teams."""
        url = f"{self.BASE_URL}/league/Ligue_1/{season}"
        teams = []

        try:
            html = self._get_page(url)
            data = self._extract_json_data(html, "teamsData")

            if not data:
                logger.warning("No team data found")
                return teams

            for team_id, team_data in data.items():
                team = self._parse_team_data(team_data)
                if team:
                    teams.append(team)

        except Exception as e:
            logger.error(f"Failed to scrape team stats: {e}")

        return teams

    # =========================================================================
    # MATCH DATA
    # =========================================================================

    def get_match_details(self, match_id: str) -> Optional[dict]:
        """Get detailed shot data for a specific match."""
        url = f"{self.BASE_URL}/match/{match_id}"

        try:
            html = self._get_page(url)

            # Extract shots data
            shots_data = self._extract_json_data(html, "shotsData")
            match_info = self._extract_json_data(html, "match_info")

            return {
                "shots": shots_data,
                "info": match_info,
            }

        except Exception as e:
            logger.error(f"Failed to get match details for {match_id}: {e}")
            return None

    # =========================================================================
    # PARSING
    # =========================================================================

    def _parse_match_data(self, data: dict) -> Optional[MatchXG]:
        """Parse match data from Understat JSON."""
        try:
            # Check if match is finished
            if not data.get("isResult"):
                return None

            return MatchXG(
                understat_id=str(data.get("id", "")),
                home_team=data.get("h", {}).get("title", ""),
                away_team=data.get("a", {}).get("title", ""),
                date=datetime.strptime(data.get("datetime", ""), "%Y-%m-%d %H:%M:%S"),
                home_xg=float(data.get("xG", {}).get("h", 0)),
                away_xg=float(data.get("xG", {}).get("a", 0)),
                home_goals=int(data.get("goals", {}).get("h", 0)),
                away_goals=int(data.get("goals", {}).get("a", 0)),
            )

        except Exception as e:
            logger.debug(f"Failed to parse match: {e}")
            return None

    def _parse_team_data(self, data: dict) -> Optional[TeamXG]:
        """Parse team season data from Understat JSON."""
        try:
            team_name = data.get("title", "")
            history = data.get("history", [])

            if not history:
                return None

            # Aggregate season stats
            total_xg = sum(float(m.get("xG", 0)) for m in history)
            total_xga = sum(float(m.get("xGA", 0)) for m in history)
            total_goals = sum(int(m.get("scored", 0)) for m in history)
            total_against = sum(int(m.get("missed", 0)) for m in history)
            total_npxg = sum(float(m.get("npxG", 0)) for m in history)
            total_npxga = sum(float(m.get("npxGA", 0)) for m in history)

            return TeamXG(
                team_name=team_name,
                matches_played=len(history),
                xg=round(total_xg, 2),
                xga=round(total_xga, 2),
                goals=total_goals,
                goals_against=total_against,
                xg_diff=round(total_xg - total_xga, 2),
                npxg=round(total_npxg, 2),
                npxga=round(total_npxga, 2),
            )

        except Exception as e:
            logger.debug(f"Failed to parse team: {e}")
            return None

    def normalize_team_name(self, understat_name: str) -> str:
        """Normalize Understat team name to standard format."""
        return self.TEAM_MAPPING.get(understat_name, understat_name)

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Singleton
_scraper: Optional[UnderstatScraper] = None


def get_understat_scraper() -> UnderstatScraper:
    """Get or create Understat scraper singleton."""
    global _scraper
    if _scraper is None:
        _scraper = UnderstatScraper()
    return _scraper

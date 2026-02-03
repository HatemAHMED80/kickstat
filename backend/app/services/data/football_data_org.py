"""
Football-Data.org API client.

Free tier includes Ligue 1, Premier League, La Liga, Serie A, Bundesliga, etc.
Supports current season data.
"""

import httpx
from typing import Optional
from loguru import logger

from app.core import get_settings


class FootballDataOrgClient:
    """Client for football-data.org API v4."""

    BASE_URL = "https://api.football-data.org/v4"

    # Competition codes
    LIGUE_1 = "FL1"
    PREMIER_LEAGUE = "PL"
    LA_LIGA = "PD"
    SERIE_A = "SA"
    BUNDESLIGA = "BL1"
    CHAMPIONS_LEAGUE = "CL"

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.football_data_org_key
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "X-Auth-Token": self.api_key,
            },
            timeout=30.0,
        )

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make a GET request to the API."""
        try:
            response = self.client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise

    def get_competition(self, competition_code: str) -> dict:
        """Get competition info."""
        return self._get(f"/competitions/{competition_code}")

    def get_matches(
        self,
        competition_code: str,
        status: Optional[str] = None,
        matchday: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list:
        """
        Get matches for a competition.

        Args:
            competition_code: Competition code (e.g., FL1 for Ligue 1)
            status: Filter by status (SCHEDULED, LIVE, IN_PLAY, PAUSED, FINISHED, etc.)
            matchday: Filter by matchday number
            date_from: Filter from date (YYYY-MM-DD)
            date_to: Filter to date (YYYY-MM-DD)

        Returns:
            List of matches
        """
        params = {}
        if status:
            params["status"] = status
        if matchday:
            params["matchday"] = matchday
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to

        data = self._get(f"/competitions/{competition_code}/matches", params)
        return data.get("matches", [])

    def get_scheduled_matches(self, competition_code: str) -> list:
        """Get upcoming scheduled matches."""
        return self.get_matches(competition_code, status="SCHEDULED")

    def get_teams(self, competition_code: str) -> list:
        """Get all teams in a competition."""
        data = self._get(f"/competitions/{competition_code}/teams")
        return data.get("teams", [])

    def get_standings(self, competition_code: str) -> list:
        """Get current standings."""
        data = self._get(f"/competitions/{competition_code}/standings")
        return data.get("standings", [])

    def close(self):
        """Close the HTTP client."""
        self.client.close()


def get_football_data_client() -> FootballDataOrgClient:
    """Get a configured FootballDataOrg client."""
    return FootballDataOrgClient()

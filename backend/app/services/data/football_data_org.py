"""
Football-Data.org API Client

Free tier includes: Ligue 1, Premier League, La Liga, Serie A, Bundesliga,
Champions League, World Cup, and more.

Supports current season (2025-26) unlike API-Football free tier.
"""

import time
from datetime import date
from typing import Optional
from dataclasses import dataclass

import httpx
from loguru import logger


@dataclass
class RateLimiter:
    """Rate limiter: 10 requests/minute for free tier."""

    max_requests: int = 10
    period: int = 60  # seconds
    requests: list = None

    def __post_init__(self):
        self.requests = []

    def acquire(self) -> bool:
        now = time.time()
        self.requests = [r for r in self.requests if now - r < self.period]

        if len(self.requests) >= self.max_requests:
            wait_time = self.period - (now - self.requests[0])
            logger.warning(f"Rate limit reached. Waiting {wait_time:.1f}s")
            time.sleep(wait_time)
            self.requests = []

        self.requests.append(now)
        return True


class FootballDataOrgClient:
    """
    Client for Football-Data.org API v4.

    Free competitions:
    - FL1: Ligue 1 (France)
    - PL: Premier League
    - BL1: Bundesliga
    - SA: Serie A
    - PD: La Liga
    - CL: Champions League
    - EC: European Championship
    - WC: World Cup
    """

    BASE_URL = "https://api.football-data.org/v4"

    # Competition codes
    LIGUE_1 = "FL1"
    PREMIER_LEAGUE = "PL"
    BUNDESLIGA = "BL1"
    SERIE_A = "SA"
    LA_LIGA = "PD"
    CHAMPIONS_LEAGUE = "CL"

    def __init__(self, api_key: str = None):
        # Free tier works without key (100 req/day)
        # With key: 10 req/min
        self.api_key = api_key
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-Auth-Token"] = api_key

        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers=headers,
            timeout=30.0,
        )
        self.rate_limiter = RateLimiter()

    def _request(self, endpoint: str, params: dict = None) -> dict:
        """Make a rate-limited request."""
        self.rate_limiter.acquire()

        response = self.client.get(endpoint, params=params)

        # Check rate limit headers
        remaining = response.headers.get("X-Requests-Available", "?")
        logger.debug(f"Football-Data.org {endpoint} - Remaining: {remaining}")

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning(f"Rate limited. Waiting {retry_after}s")
            time.sleep(retry_after)
            return self._request(endpoint, params)

        response.raise_for_status()
        return response.json()

    # =========================================================================
    # COMPETITIONS
    # =========================================================================

    def get_competitions(self) -> list[dict]:
        """Get all available competitions."""
        data = self._request("/competitions")
        return data.get("competitions", [])

    def get_competition(self, code: str) -> dict:
        """Get competition details."""
        return self._request(f"/competitions/{code}")

    # =========================================================================
    # STANDINGS
    # =========================================================================

    def get_standings(self, competition: str = "FL1", season: int = None) -> list[dict]:
        """
        Get league standings.

        Args:
            competition: Competition code (FL1 for Ligue 1)
            season: Season year (e.g., 2025 for 2025-26)
        """
        params = {}
        if season:
            params["season"] = season

        data = self._request(f"/competitions/{competition}/standings", params)
        standings = data.get("standings", [])

        # Return the total standings (not home/away)
        for s in standings:
            if s.get("type") == "TOTAL":
                return s.get("table", [])

        return standings[0].get("table", []) if standings else []

    # =========================================================================
    # MATCHES
    # =========================================================================

    def get_matches(
        self,
        competition: str = None,
        team_id: int = None,
        date_from: date = None,
        date_to: date = None,
        status: str = None,
        matchday: int = None,
        season: int = None,
    ) -> list[dict]:
        """
        Get matches with filters.

        Args:
            competition: Competition code
            team_id: Filter by team
            date_from: Start date
            date_to: End date
            status: SCHEDULED, LIVE, IN_PLAY, PAUSED, FINISHED, etc.
            matchday: Specific matchday
            season: Season year
        """
        params = {}
        if date_from:
            params["dateFrom"] = date_from.isoformat()
        if date_to:
            params["dateTo"] = date_to.isoformat()
        if status:
            params["status"] = status
        if matchday:
            params["matchday"] = matchday
        if season:
            params["season"] = season

        if competition:
            endpoint = f"/competitions/{competition}/matches"
        elif team_id:
            endpoint = f"/teams/{team_id}/matches"
        else:
            endpoint = "/matches"

        data = self._request(endpoint, params)
        return data.get("matches", [])

    def get_match(self, match_id: int) -> dict:
        """Get single match details."""
        return self._request(f"/matches/{match_id}")

    def get_todays_matches(self, competition: str = None) -> list[dict]:
        """Get today's matches."""
        today = date.today()
        return self.get_matches(
            competition=competition,
            date_from=today,
            date_to=today,
        )

    # =========================================================================
    # TEAMS
    # =========================================================================

    def get_teams(self, competition: str = "FL1", season: int = None) -> list[dict]:
        """Get teams in a competition."""
        params = {}
        if season:
            params["season"] = season

        data = self._request(f"/competitions/{competition}/teams", params)
        return data.get("teams", [])

    def get_team(self, team_id: int) -> dict:
        """Get team details."""
        return self._request(f"/teams/{team_id}")

    # =========================================================================
    # SCORERS
    # =========================================================================

    def get_scorers(self, competition: str = "FL1", season: int = None, limit: int = 10) -> list[dict]:
        """Get top scorers in a competition."""
        params = {"limit": limit}
        if season:
            params["season"] = season

        data = self._request(f"/competitions/{competition}/scorers", params)
        return data.get("scorers", [])

    # =========================================================================
    # HEAD TO HEAD
    # =========================================================================

    def get_head_to_head(self, match_id: int) -> dict:
        """Get head-to-head for a specific match."""
        data = self._request(f"/matches/{match_id}/head2head")
        return data

    def close(self):
        """Close HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# Singleton instance
_client: Optional[FootballDataOrgClient] = None


def get_football_data_client(api_key: str = None) -> FootballDataOrgClient:
    """Get or create the Football-Data.org client singleton."""
    global _client
    if _client is None:
        _client = FootballDataOrgClient(api_key)
    return _client

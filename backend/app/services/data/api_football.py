"""
API-Football Client
Documentation: https://www.api-football.com/documentation-v3

Free tier: 100 requests/day
"""

import time
from datetime import datetime, date
from typing import Optional, Any
from dataclasses import dataclass

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core import get_settings

settings = get_settings()


@dataclass
class RateLimiter:
    """Simple rate limiter for API calls."""

    max_requests: int
    period: int  # seconds
    requests: list[float] = None

    def __post_init__(self):
        self.requests = []

    def acquire(self) -> bool:
        """Check if we can make a request, and record it."""
        now = time.time()
        # Remove old requests outside the period
        self.requests = [r for r in self.requests if now - r < self.period]

        if len(self.requests) >= self.max_requests:
            wait_time = self.period - (now - self.requests[0])
            logger.warning(f"Rate limit reached. Waiting {wait_time:.1f}s")
            time.sleep(wait_time)
            self.requests = []

        self.requests.append(now)
        return True


class APIFootballClient:
    """Client for API-Football v3."""

    BASE_URL = "https://v3.football.api-sports.io"

    # French competition IDs
    LIGUE_1 = 61
    COUPE_DE_FRANCE = 66
    TROPHEE_CHAMPIONS = 65

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.api_football_key
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "x-apisports-key": self.api_key,
                "x-rapidapi-host": settings.api_football_host,
            },
            timeout=30.0,
        )
        # Free tier: 100 requests/day = ~4 requests/hour to be safe
        self.rate_limiter = RateLimiter(max_requests=100, period=86400)

    def _request(self, endpoint: str, params: dict = None) -> dict:
        """Make a rate-limited request to the API."""
        self.rate_limiter.acquire()

        response = self.client.get(endpoint, params=params)
        response.raise_for_status()

        data = response.json()

        if data.get("errors"):
            logger.error(f"API Error: {data['errors']}")
            raise APIFootballError(data["errors"])

        # Log remaining requests
        remaining = response.headers.get("x-ratelimit-requests-remaining", "?")
        logger.debug(f"API request to {endpoint} - Remaining: {remaining}")

        return data

    # =========================================================================
    # TEAMS
    # =========================================================================

    def get_teams(self, league_id: int, season: int) -> list[dict]:
        """Get all teams in a league for a given season."""
        data = self._request("/teams", {"league": league_id, "season": season})
        return data.get("response", [])

    def get_team(self, team_id: int) -> Optional[dict]:
        """Get team details by ID."""
        data = self._request("/teams", {"id": team_id})
        response = data.get("response", [])
        return response[0] if response else None

    def get_team_statistics(
        self, team_id: int, league_id: int, season: int
    ) -> Optional[dict]:
        """Get team statistics for a season."""
        data = self._request(
            "/teams/statistics",
            {"team": team_id, "league": league_id, "season": season},
        )
        return data.get("response")

    # =========================================================================
    # MATCHES / FIXTURES
    # =========================================================================

    def get_fixtures(
        self,
        league_id: int = None,
        season: int = None,
        team_id: int = None,
        date_from: date = None,
        date_to: date = None,
        last: int = None,
        next_n: int = None,
        status: str = None,
    ) -> list[dict]:
        """
        Get fixtures with various filters.

        Args:
            league_id: Filter by league
            season: Season year (e.g., 2024)
            team_id: Filter by team
            date_from: Start date
            date_to: End date
            last: Last N fixtures
            next_n: Next N fixtures
            status: Match status (NS, LIVE, FT, etc.)
        """
        params = {}

        if league_id:
            params["league"] = league_id
        if season:
            params["season"] = season
        if team_id:
            params["team"] = team_id
        if date_from:
            params["from"] = date_from.isoformat()
        if date_to:
            params["to"] = date_to.isoformat()
        if last:
            params["last"] = last
        if next_n:
            params["next"] = next_n
        if status:
            params["status"] = status

        data = self._request("/fixtures", params)
        return data.get("response", [])

    def get_fixture(self, fixture_id: int) -> Optional[dict]:
        """Get single fixture by ID."""
        data = self._request("/fixtures", {"id": fixture_id})
        response = data.get("response", [])
        return response[0] if response else None

    def get_fixture_statistics(self, fixture_id: int) -> list[dict]:
        """Get statistics for a fixture."""
        data = self._request("/fixtures/statistics", {"fixture": fixture_id})
        return data.get("response", [])

    def get_fixture_events(self, fixture_id: int) -> list[dict]:
        """Get events (goals, cards, subs) for a fixture."""
        data = self._request("/fixtures/events", {"fixture": fixture_id})
        return data.get("response", [])

    def get_fixture_lineups(self, fixture_id: int) -> list[dict]:
        """Get lineups for a fixture."""
        data = self._request("/fixtures/lineups", {"fixture": fixture_id})
        return data.get("response", [])

    def get_fixture_players(self, fixture_id: int) -> list[dict]:
        """
        Get detailed player statistics for a fixture.

        Returns stats including:
        - duels (total, won)
        - tackles (total, blocks, interceptions)
        - dribbles (attempts, success)
        - passes (total, key, accuracy)
        - fouls (drawn, committed)
        """
        data = self._request("/fixtures/players", {"fixture": fixture_id})
        return data.get("response", [])

    def get_head_to_head(self, team1_id: int, team2_id: int, last: int = 10) -> list[dict]:
        """Get head-to-head fixtures between two teams."""
        h2h = f"{team1_id}-{team2_id}"
        data = self._request("/fixtures/headtohead", {"h2h": h2h, "last": last})
        return data.get("response", [])

    # =========================================================================
    # STANDINGS
    # =========================================================================

    def get_standings(self, league_id: int, season: int) -> list[dict]:
        """Get league standings."""
        data = self._request("/standings", {"league": league_id, "season": season})
        response = data.get("response", [])

        if response and response[0].get("league", {}).get("standings"):
            return response[0]["league"]["standings"][0]
        return []

    # =========================================================================
    # PLAYERS
    # =========================================================================

    def get_players(
        self, team_id: int = None, league_id: int = None, season: int = None, page: int = 1
    ) -> tuple[list[dict], dict]:
        """
        Get players with pagination.

        Returns:
            Tuple of (players list, paging info)
        """
        params = {"page": page}
        if team_id:
            params["team"] = team_id
        if league_id:
            params["league"] = league_id
        if season:
            params["season"] = season

        data = self._request("/players", params)
        return data.get("response", []), data.get("paging", {})

    def get_player_squads(self, team_id: int) -> list[dict]:
        """Get current squad for a team."""
        data = self._request("/players/squads", {"team": team_id})
        response = data.get("response", [])
        return response[0].get("players", []) if response else []

    def get_player_season_stats(
        self, player_id: int, season: int
    ) -> Optional[dict]:
        """
        Get full season statistics for a specific player.

        Returns detailed stats including games, goals, assists,
        passes, tackles, duels, dribbles, fouls, cards.
        """
        data = self._request("/players", {"id": player_id, "season": season})
        response = data.get("response", [])
        return response[0] if response else None

    def get_top_players(
        self, league_id: int, season: int, stat_type: str = "topscorers"
    ) -> list[dict]:
        """
        Get top players by stat type.

        Args:
            stat_type: topscorers, topassists, topyellowcards, topredcards
        """
        endpoint = f"/players/{stat_type}"
        data = self._request(endpoint, {"league": league_id, "season": season})
        return data.get("response", [])

    # =========================================================================
    # INJURIES & SUSPENSIONS
    # =========================================================================

    def get_injuries(
        self,
        league_id: int = None,
        season: int = None,
        team_id: int = None,
        fixture_id: int = None,
    ) -> list[dict]:
        """Get injuries for teams/fixtures."""
        params = {}
        if league_id:
            params["league"] = league_id
        if season:
            params["season"] = season
        if team_id:
            params["team"] = team_id
        if fixture_id:
            params["fixture"] = fixture_id

        data = self._request("/injuries", params)
        return data.get("response", [])

    # =========================================================================
    # VENUES
    # =========================================================================

    def get_venues(self, country: str = "France") -> list[dict]:
        """Get venues/stadiums."""
        data = self._request("/venues", {"country": country})
        return data.get("response", [])

    # =========================================================================
    # ODDS (if available in plan)
    # =========================================================================

    def get_odds(self, fixture_id: int) -> list[dict]:
        """Get betting odds for a fixture."""
        data = self._request("/odds", {"fixture": fixture_id})
        return data.get("response", [])

    # =========================================================================
    # UTILITY
    # =========================================================================

    def get_status(self) -> dict:
        """Get API account status."""
        data = self._request("/status")
        return data.get("response", {})

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class APIFootballError(Exception):
    """Custom exception for API-Football errors."""
    pass


# Singleton instance
_client: Optional[APIFootballClient] = None


def get_api_football_client() -> APIFootballClient:
    """Get or create the API-Football client singleton."""
    global _client
    if _client is None:
        _client = APIFootballClient()
    return _client

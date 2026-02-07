"""Football-Data.org API client.

Free tier: 100 requests/day.
Docs: https://www.football-data.org/documentation/api
"""

import time
from datetime import datetime, timedelta
from typing import Optional

import httpx
from loguru import logger


LEAGUE_CODES = {
    "ligue_1": "FL1",
    "premier_league": "PL",
    "la_liga": "PD",
    "bundesliga": "BL1",
    "serie_a": "SA",
}


class FootballDataClient:
    BASE_URL = "https://api.football-data.org/v4"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Football-Data.org API key is required")
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={"X-Auth-Token": api_key},
            timeout=30.0,
        )
        self._request_count = 0
        self._last_request_time = 0.0

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Rate-limited GET request."""
        # Respect rate limit: max 10 req/min on free tier
        elapsed = time.time() - self._last_request_time
        if elapsed < 6.5:
            time.sleep(6.5 - elapsed)

        response = self.client.get(endpoint, params=params)
        self._last_request_time = time.time()
        self._request_count += 1

        response.raise_for_status()
        return response.json()

    def get_matches(
        self,
        league: str = "ligue_1",
        season: int = 2024,
        status: Optional[str] = None,
    ) -> list[dict]:
        """Fetch matches for a league/season.

        Args:
            league: League key from LEAGUE_CODES.
            season: Season start year (2024 = 2024-25).
            status: Filter by status (SCHEDULED, FINISHED, etc.).
        """
        code = LEAGUE_CODES.get(league, league)
        params = {"season": season}
        if status:
            params["status"] = status

        data = self._get(f"/competitions/{code}/matches", params=params)
        matches = data.get("matches", [])
        logger.info(f"Fetched {len(matches)} matches for {league} {season}")
        return matches

    def get_standings(self, league: str = "ligue_1", season: int = 2024) -> list[dict]:
        """Fetch current standings."""
        code = LEAGUE_CODES.get(league, league)
        data = self._get(f"/competitions/{code}/standings", params={"season": season})
        standings = data.get("standings", [])
        if standings:
            return standings[0].get("table", [])
        return []

    def get_finished_matches_with_scores(
        self, league: str = "ligue_1", season: int = 2024
    ) -> list[dict]:
        """Fetch all finished matches with scores for training data."""
        matches = self.get_matches(league, season, status="FINISHED")
        results = []
        for m in matches:
            score = m.get("score", {})
            ft = score.get("fullTime", {})
            if ft.get("home") is not None and ft.get("away") is not None:
                results.append({
                    "home_team": m["homeTeam"]["name"],
                    "away_team": m["awayTeam"]["name"],
                    "home_score": ft["home"],
                    "away_score": ft["away"],
                    "kickoff": m["utcDate"],
                    "matchday": m.get("matchday"),
                })
        logger.info(f"Got {len(results)} finished matches with scores")
        return results

    @property
    def requests_used(self) -> int:
        return self._request_count

    def close(self):
        self.client.close()

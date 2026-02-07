"""The Odds API client.

Free tier: 500 requests/month.
Docs: https://the-odds-api.com/liveapi/guides/v4/
"""

import time
from typing import Optional

import httpx
from loguru import logger


SPORT_KEYS = {
    "ligue_1": "soccer_france_ligue_one",
    "premier_league": "soccer_epl",
    "la_liga": "soccer_spain_la_liga",
    "bundesliga": "soccer_germany_bundesliga",
    "serie_a": "soccer_italy_serie_a",
}


class OddsAPIClient:
    BASE_URL = "https://api.the-odds-api.com/v4"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Odds API key is required")
        self.api_key = api_key
        self.client = httpx.Client(timeout=30.0)
        self.remaining_requests: Optional[int] = None

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict | list:
        """Rate-aware GET request."""
        if self.remaining_requests is not None and self.remaining_requests < 10:
            logger.warning(f"Odds API: only {self.remaining_requests} requests remaining!")

        params = params or {}
        params["apiKey"] = self.api_key

        response = self.client.get(f"{self.BASE_URL}{endpoint}", params=params)
        self.remaining_requests = int(
            response.headers.get("x-requests-remaining", -1)
        )
        response.raise_for_status()
        return response.json()

    def get_odds(
        self,
        league: str = "ligue_1",
        markets: str = "h2h,totals",
        regions: str = "eu",
    ) -> list[dict]:
        """Fetch current odds for upcoming matches.

        Budget: ~1 request per league per call.
        """
        sport = SPORT_KEYS.get(league, league)
        data = self._get(
            f"/sports/{sport}/odds",
            params={"regions": regions, "markets": markets, "oddsFormat": "decimal"},
        )
        logger.info(
            f"Fetched odds for {len(data)} matches ({league}). "
            f"Remaining: {self.remaining_requests}"
        )
        return data

    def close(self):
        self.client.close()


def extract_best_odds(match_odds: dict) -> dict:
    """Extract best available odds across all bookmakers for a match.

    Returns dict with keys: home, draw, away, over25, under25
    and their associated best bookmaker.
    """
    best = {
        "home": {"odds": 0, "bookmaker": None},
        "draw": {"odds": 0, "bookmaker": None},
        "away": {"odds": 0, "bookmaker": None},
        "over25": {"odds": 0, "bookmaker": None},
        "under25": {"odds": 0, "bookmaker": None},
    }

    for bookmaker in match_odds.get("bookmakers", []):
        name = bookmaker["title"]
        for market in bookmaker.get("markets", []):
            if market["key"] == "h2h":
                for outcome in market["outcomes"]:
                    if outcome["name"] == match_odds.get("home_team"):
                        if outcome["price"] > best["home"]["odds"]:
                            best["home"] = {"odds": outcome["price"], "bookmaker": name}
                    elif outcome["name"] == match_odds.get("away_team"):
                        if outcome["price"] > best["away"]["odds"]:
                            best["away"] = {"odds": outcome["price"], "bookmaker": name}
                    elif outcome["name"] == "Draw":
                        if outcome["price"] > best["draw"]["odds"]:
                            best["draw"] = {"odds": outcome["price"], "bookmaker": name}
            elif market["key"] == "totals":
                for outcome in market["outcomes"]:
                    point = outcome.get("point", 2.5)
                    if point == 2.5:
                        key = "over25" if outcome["name"] == "Over" else "under25"
                        if outcome["price"] > best[key]["odds"]:
                            best[key] = {"odds": outcome["price"], "bookmaker": name}

    return best


def remove_margin(home_odds: float, draw_odds: float, away_odds: float) -> dict:
    """Remove bookmaker margin to get fair probabilities.

    This is CRITICAL for correct edge calculation.
    """
    if not all(o > 1.0 for o in [home_odds, draw_odds, away_odds]):
        return {"home": 0, "draw": 0, "away": 0, "overround": 0}

    raw_home = 1 / home_odds
    raw_draw = 1 / draw_odds
    raw_away = 1 / away_odds
    overround = raw_home + raw_draw + raw_away

    return {
        "home": raw_home / overround,
        "draw": raw_draw / overround,
        "away": raw_away / overround,
        "overround": overround,
    }

"""
The Odds API Client.

Fetches real betting odds from multiple bookmakers.
https://the-odds-api.com/

Free tier: 500 requests/month
Supports: Betfair, Pinnacle, Bet365, William Hill, etc.
"""

import httpx
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from loguru import logger

from app.core import get_settings


@dataclass
class BookmakerOdds:
    """Odds from a single bookmaker."""
    bookmaker: str
    bookmaker_key: str
    home_win: float
    draw: float
    away_win: float
    over_25: Optional[float] = None
    under_25: Optional[float] = None
    btts_yes: Optional[float] = None
    btts_no: Optional[float] = None
    last_update: datetime = None


@dataclass
class MatchOddsData:
    """Aggregated odds data for a match."""
    match_id: str
    sport: str
    home_team: str
    away_team: str
    commence_time: datetime
    bookmakers: List[BookmakerOdds]

    def get_best_odds(self, market: str = "1x2") -> Dict:
        """Get the best odds across all bookmakers."""
        if market == "1x2":
            best_home = max(b.home_win for b in self.bookmakers if b.home_win)
            best_draw = max(b.draw for b in self.bookmakers if b.draw)
            best_away = max(b.away_win for b in self.bookmakers if b.away_win)

            home_book = next(b.bookmaker for b in self.bookmakers if b.home_win == best_home)
            draw_book = next(b.bookmaker for b in self.bookmakers if b.draw == best_draw)
            away_book = next(b.bookmaker for b in self.bookmakers if b.away_win == best_away)

            return {
                "home_win": {"odds": best_home, "bookmaker": home_book},
                "draw": {"odds": best_draw, "bookmaker": draw_book},
                "away_win": {"odds": best_away, "bookmaker": away_book},
            }
        elif market == "over_under":
            books_with_ou = [b for b in self.bookmakers if b.over_25 is not None]
            if not books_with_ou:
                return {}
            best_over = max(b.over_25 for b in books_with_ou)
            best_under = max(b.under_25 for b in books_with_ou)
            return {
                "over_25": {"odds": best_over},
                "under_25": {"odds": best_under},
            }
        return {}


class TheOddsAPIClient:
    """
    Client for The Odds API.

    Documentation: https://the-odds-api.com/liveapi/guides/v4/
    """

    BASE_URL = "https://api.the-odds-api.com/v4"

    # Sport keys
    SPORTS = {
        "ligue_1": "soccer_france_ligue_one",
        "ligue_2": "soccer_france_ligue_two",
        "premier_league": "soccer_epl",
        "la_liga": "soccer_spain_la_liga",
        "bundesliga": "soccer_germany_bundesliga",
        "serie_a": "soccer_italy_serie_a",
        "champions_league": "soccer_uefa_champs_league",
    }

    # Preferred bookmakers (in order of preference)
    PREFERRED_BOOKMAKERS = [
        "pinnacle",
        "betfair_ex_eu",
        "betfair",
        "bet365",
        "williamhill",
        "unibet_eu",
        "marathon_bet",
    ]

    def __init__(self, api_key: str = None):
        settings = get_settings()
        self.api_key = api_key or settings.odds_api_key or ""
        self.client = httpx.Client(timeout=30.0)
        self._remaining_requests = None
        self._used_requests = None

    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """Make GET request to API."""
        if not self.api_key:
            logger.warning("No API key configured for The Odds API")
            return {}

        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        params["apiKey"] = self.api_key

        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()

            # Track usage
            self._remaining_requests = response.headers.get("x-requests-remaining")
            self._used_requests = response.headers.get("x-requests-used")

            logger.debug(
                f"Odds API: {self._used_requests} used, {self._remaining_requests} remaining"
            )

            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Odds API error: {e}")
            return {}

    def get_sports(self) -> List[Dict]:
        """Get list of available sports."""
        return self._get("sports") or []

    def get_odds(
        self,
        sport_key: str = "soccer_france_ligue_one",
        regions: str = "eu",
        markets: str = "h2h",
        odds_format: str = "decimal",
    ) -> List[MatchOddsData]:
        """
        Get odds for upcoming matches in a sport.

        Args:
            sport_key: Sport identifier
            regions: Region for bookmakers (eu, uk, us, au)
            markets: Market types (h2h, spreads, totals)
            odds_format: decimal or american

        Returns:
            List of MatchOddsData objects
        """
        data = self._get(
            f"sports/{sport_key}/odds",
            params={
                "regions": regions,
                "markets": markets,
                "oddsFormat": odds_format,
            },
        )

        if not data:
            return []

        matches = []
        for event in data:
            bookmakers = []
            for bm in event.get("bookmakers", []):
                # Get h2h (1X2) odds
                h2h_market = next(
                    (m for m in bm.get("markets", []) if m.get("key") == "h2h"),
                    None,
                )

                if not h2h_market:
                    continue

                outcomes = h2h_market.get("outcomes", [])

                home_team = event.get("home_team", "")
                away_team = event.get("away_team", "")

                home_odds = next(
                    (o["price"] for o in outcomes if o["name"] == home_team),
                    None,
                )
                draw_odds = next(
                    (o["price"] for o in outcomes if o["name"] == "Draw"),
                    None,
                )
                away_odds = next(
                    (o["price"] for o in outcomes if o["name"] == away_team),
                    None,
                )

                if home_odds and draw_odds and away_odds:
                    bookmakers.append(
                        BookmakerOdds(
                            bookmaker=bm.get("title", ""),
                            bookmaker_key=bm.get("key", ""),
                            home_win=home_odds,
                            draw=draw_odds,
                            away_win=away_odds,
                            last_update=datetime.fromisoformat(
                                bm.get("last_update", "").replace("Z", "+00:00")
                            ) if bm.get("last_update") else None,
                        )
                    )

            if bookmakers:
                matches.append(
                    MatchOddsData(
                        match_id=event.get("id", ""),
                        sport=event.get("sport_key", ""),
                        home_team=event.get("home_team", ""),
                        away_team=event.get("away_team", ""),
                        commence_time=datetime.fromisoformat(
                            event.get("commence_time", "").replace("Z", "+00:00")
                        ),
                        bookmakers=bookmakers,
                    )
                )

        logger.info(f"Fetched odds for {len(matches)} matches from {sport_key}")
        return matches

    def get_ligue1_odds(self) -> List[MatchOddsData]:
        """Get Ligue 1 odds."""
        return self.get_odds(self.SPORTS["ligue_1"])

    def get_best_odds_for_match(
        self,
        home_team: str,
        away_team: str,
        sport_key: str = "soccer_france_ligue_one",
    ) -> Optional[Dict]:
        """
        Get best odds for a specific match.

        Searches by team names (fuzzy matching).
        """
        matches = self.get_odds(sport_key)

        for match in matches:
            # Fuzzy match team names
            if (
                home_team.lower() in match.home_team.lower()
                or match.home_team.lower() in home_team.lower()
            ) and (
                away_team.lower() in match.away_team.lower()
                or match.away_team.lower() in away_team.lower()
            ):
                best = match.get_best_odds("1x2")
                return {
                    "match": f"{match.home_team} vs {match.away_team}",
                    "kickoff": match.commence_time.isoformat(),
                    "best_odds": best,
                    "all_bookmakers": [
                        {
                            "name": b.bookmaker,
                            "home": b.home_win,
                            "draw": b.draw,
                            "away": b.away_win,
                        }
                        for b in match.bookmakers
                    ],
                }

        return None

    def get_usage(self) -> Dict:
        """Get API usage statistics."""
        return {
            "remaining_requests": self._remaining_requests,
            "used_requests": self._used_requests,
        }

    def close(self):
        """Close the HTTP client."""
        self.client.close()


# Singleton
_client: Optional[TheOddsAPIClient] = None


def get_odds_api_client() -> TheOddsAPIClient:
    """Get The Odds API client singleton."""
    global _client
    if _client is None:
        _client = TheOddsAPIClient()
    return _client


# CLI Test
if __name__ == "__main__":
    import os

    # Set API key for testing
    api_key = os.getenv("ODDS_API_KEY", "")

    if not api_key:
        print("Set ODDS_API_KEY environment variable to test")
        print("Get a free key at: https://the-odds-api.com/")
        exit(1)

    client = TheOddsAPIClient(api_key)

    try:
        print("=" * 60)
        print("LIGUE 1 LIVE ODDS")
        print("=" * 60)

        matches = client.get_ligue1_odds()

        for match in matches[:5]:
            print(f"\n{match.home_team} vs {match.away_team}")
            print(f"Kickoff: {match.commence_time}")

            best = match.get_best_odds("1x2")
            print(f"Best odds:")
            print(f"  Home: {best['home_win']['odds']:.2f} ({best['home_win']['bookmaker']})")
            print(f"  Draw: {best['draw']['odds']:.2f} ({best['draw']['bookmaker']})")
            print(f"  Away: {best['away_win']['odds']:.2f} ({best['away_win']['bookmaker']})")

            print(f"\nAll bookmakers ({len(match.bookmakers)}):")
            for bm in match.bookmakers[:3]:
                print(f"  {bm.bookmaker}: {bm.home_win:.2f} / {bm.draw:.2f} / {bm.away_win:.2f}")

        print(f"\nAPI Usage: {client.get_usage()}")

    finally:
        client.close()

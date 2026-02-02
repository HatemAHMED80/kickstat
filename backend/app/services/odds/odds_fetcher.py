"""
Odds Fetcher Service

Fetches and normalizes betting odds from API-Football.
"""

from datetime import datetime, date, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.database import Match, MatchOdds
from app.services.data.api_football import get_api_football_client, APIFootballClient


# Bookmakers to track (API-Football IDs)
TRACKED_BOOKMAKERS = {
    1: "bet365",
    2: "bwin",
    3: "unibet",
    5: "betfair",
    6: "betway",
    8: "winamax",
    11: "betclic",
}


class OddsFetcher:
    """
    Fetches betting odds from API-Football and stores them.

    Uses the existing APIFootballClient to get odds data,
    then normalizes and stores in our database format.
    """

    def __init__(self, api_client: Optional[APIFootballClient] = None):
        self.api = api_client or get_api_football_client()

    def fetch_match_odds(self, match: Match, db: Session) -> list[MatchOdds]:
        """
        Fetch and store odds for a single match.

        Args:
            match: The match to fetch odds for
            db: Database session

        Returns:
            List of MatchOdds stored
        """
        if not match.api_id:
            logger.warning(f"Match {match.id} has no API ID, skipping odds fetch")
            return []

        try:
            raw_odds = self.api.get_odds(match.api_id)
        except Exception as e:
            logger.error(f"Failed to fetch odds for match {match.id}: {e}")
            return []

        if not raw_odds:
            logger.debug(f"No odds returned for match {match.id}")
            return []

        stored_odds = []

        for bookmaker_data in raw_odds:
            bookmaker_id = bookmaker_data.get("bookmaker", {}).get("id")
            bookmaker_name = TRACKED_BOOKMAKERS.get(bookmaker_id)

            if not bookmaker_name:
                continue  # Skip untracked bookmakers

            odds = self._parse_bookmaker_odds(match.id, bookmaker_name, bookmaker_data)
            if odds:
                # Upsert - update if exists, insert if not
                existing = (
                    db.query(MatchOdds)
                    .filter(
                        MatchOdds.match_id == match.id,
                        MatchOdds.bookmaker == bookmaker_name,
                    )
                    .first()
                )

                if existing:
                    # Update existing
                    for key, value in odds.__dict__.items():
                        if not key.startswith("_") and key != "id":
                            setattr(existing, key, value)
                    existing.fetched_at = datetime.utcnow()
                else:
                    db.add(odds)
                    stored_odds.append(odds)

        db.commit()

        logger.debug(f"Stored {len(stored_odds)} odds entries for match {match.id}")
        return stored_odds

    def _parse_bookmaker_odds(
        self, match_id: int, bookmaker_name: str, data: dict
    ) -> Optional[MatchOdds]:
        """
        Parse raw API-Football odds data into MatchOdds object.

        Args:
            match_id: Our internal match ID
            bookmaker_name: Normalized bookmaker name
            data: Raw bookmaker data from API

        Returns:
            MatchOdds object or None if parsing fails
        """
        bets = data.get("bets", [])

        odds = MatchOdds(
            match_id=match_id,
            bookmaker=bookmaker_name,
            fetched_at=datetime.utcnow(),
        )

        for bet in bets:
            bet_id = bet.get("id")
            bet_name = bet.get("name", "").lower()
            values = bet.get("values", [])

            # Match Winner (1X2)
            if bet_id == 1 or "match winner" in bet_name:
                for v in values:
                    value = v.get("value", "").lower()
                    odd = self._safe_float(v.get("odd"))

                    if value == "home" or value == "1":
                        odds.home_win_odds = odd
                        odds.home_win_implied = self._calculate_implied(odd)
                    elif value == "draw" or value == "x":
                        odds.draw_odds = odd
                        odds.draw_implied = self._calculate_implied(odd)
                    elif value == "away" or value == "2":
                        odds.away_win_odds = odd
                        odds.away_win_implied = self._calculate_implied(odd)

            # Over/Under 2.5
            elif bet_id == 5 or "goals over/under" in bet_name:
                for v in values:
                    value = v.get("value", "").lower()
                    odd = self._safe_float(v.get("odd"))

                    if "over 2.5" in value:
                        odds.over_25_odds = odd
                    elif "under 2.5" in value:
                        odds.under_25_odds = odd

            # Both Teams to Score
            elif bet_id == 8 or "both teams score" in bet_name:
                for v in values:
                    value = v.get("value", "").lower()
                    odd = self._safe_float(v.get("odd"))

                    if value == "yes":
                        odds.btts_yes_odds = odd
                    elif value == "no":
                        odds.btts_no_odds = odd

        # Only return if we have at least 1X2 odds
        if odds.home_win_odds and odds.draw_odds and odds.away_win_odds:
            return odds

        return None

    def _safe_float(self, value) -> Optional[float]:
        """Safely convert to float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _calculate_implied(self, decimal_odds: Optional[float]) -> Optional[float]:
        """Calculate implied probability from decimal odds."""
        if not decimal_odds or decimal_odds <= 1:
            return None
        return round((1 / decimal_odds) * 100, 2)

    def fetch_upcoming_odds(
        self,
        db: Session,
        days_ahead: int = 7,
        league_id: int = 61,  # Ligue 1
    ) -> int:
        """
        Fetch odds for all upcoming matches in the next N days.

        Args:
            db: Database session
            days_ahead: Number of days to look ahead
            league_id: League to fetch (default Ligue 1)

        Returns:
            Number of matches processed
        """
        now = datetime.utcnow()
        end_date = now + timedelta(days=days_ahead)

        # Get upcoming matches
        matches = (
            db.query(Match)
            .filter(
                Match.status == "scheduled",
                Match.kickoff >= now,
                Match.kickoff <= end_date,
            )
            .all()
        )

        logger.info(f"Fetching odds for {len(matches)} upcoming matches")

        processed = 0
        for match in matches:
            self.fetch_match_odds(match, db)
            processed += 1

        logger.info(f"Processed odds for {processed} matches")
        return processed

    def sync_odds_for_league(
        self,
        db: Session,
        league_id: int,
        season: int,
    ) -> int:
        """
        Sync odds for all scheduled matches in a league/season.

        Args:
            db: Database session
            league_id: API-Football league ID
            season: Season year

        Returns:
            Number of matches processed
        """
        from app.models.database import Competition

        # Find competition
        competition = (
            db.query(Competition)
            .filter(Competition.api_id == league_id)
            .first()
        )

        if not competition:
            logger.warning(f"Competition not found for league_id={league_id}")
            return 0

        # Get scheduled matches
        matches = (
            db.query(Match)
            .filter(
                Match.competition_id == competition.id,
                Match.status == "scheduled",
                Match.kickoff > datetime.utcnow(),
            )
            .all()
        )

        logger.info(f"Syncing odds for {len(matches)} matches in {competition.name}")

        count = 0
        for match in matches:
            self.fetch_match_odds(match, db)
            count += 1

        return count


# Singleton instance
_odds_fetcher: Optional[OddsFetcher] = None


def get_odds_fetcher() -> OddsFetcher:
    """Get or create the OddsFetcher singleton."""
    global _odds_fetcher
    if _odds_fetcher is None:
        _odds_fetcher = OddsFetcher()
    return _odds_fetcher

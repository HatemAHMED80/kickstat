"""
Transfermarkt Scraper
Scrapes injury data, player values, and referee statistics.

IMPORTANT: Respect rate limits and robots.txt.
"""

import re
import time
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from app.core import get_settings

settings = get_settings()


@dataclass
class InjuryInfo:
    """Player injury information."""

    player_name: str
    player_id: str
    team_name: str
    team_id: str
    injury_type: str
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    days_out: Optional[int] = None
    status: str = "injured"  # injured, doubtful, suspended


@dataclass
class PlayerValue:
    """Player market value."""

    player_name: str
    player_id: str
    team_name: str
    position: str
    market_value: float  # in millions €
    age: Optional[int] = None


@dataclass
class RefereeStats:
    """Referee statistics."""

    name: str
    referee_id: str
    matches: int
    yellow_per_match: float
    red_per_match: float
    penalties_per_match: float


class TransfermarktScraper:
    """Scraper for Transfermarkt data."""

    BASE_URL = "https://www.transfermarkt.com"

    # Ligue 1 teams mapping (Transfermarkt URL slugs)
    LIGUE_1_TEAMS = {
        "paris-saint-germain": "583",
        "as-monaco": "162",
        "olympique-marseille": "244",
        "olympique-lyon": "1041",
        "losc-lille": "1082",
        "stade-rennais-fc": "273",
        "rc-lens": "826",
        "ogc-nice": "417",
        "stade-reims": "1421",
        "montpellier-hsc": "969",
        "fc-nantes": "995",
        "rc-strasbourg-alsace": "667",
        "toulouse-fc": "415",
        "stade-brestois-29": "3911",
        "le-havre-ac": "738",
        "fc-metz": "347",
        "clermont-foot-63": "3524",
        "fc-lorient": "1158",
        "as-saint-etienne": "618",
        "aj-auxerre": "290",
    }

    def __init__(self):
        self.client = httpx.Client(
            headers={
                "User-Agent": settings.user_agent,
                "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        self.rate_limit_delay = 60.0 / settings.transfermarkt_rate_limit

    def _get_page(self, url: str) -> BeautifulSoup:
        """Fetch and parse a page with rate limiting."""
        time.sleep(self.rate_limit_delay)

        logger.debug(f"Fetching: {url}")
        response = self.client.get(url)
        response.raise_for_status()

        return BeautifulSoup(response.text, "lxml")

    # =========================================================================
    # INJURIES
    # =========================================================================

    def get_ligue1_injuries(self) -> list[InjuryInfo]:
        """Get all current injuries for Ligue 1 teams."""
        url = f"{self.BASE_URL}/ligue-1/startseite/wettbewerb/FR1"
        injuries = []

        try:
            soup = self._get_page(url)

            # Find injury section or navigate to injury page
            injury_url = f"{self.BASE_URL}/ligue-1/verletztespieler/wettbewerb/FR1"
            soup = self._get_page(injury_url)

            # Parse injury table
            table = soup.find("table", class_="items")
            if not table:
                logger.warning("No injury table found")
                return injuries

            rows = table.find_all("tr", class_=["odd", "even"])

            for row in rows:
                try:
                    injury = self._parse_injury_row(row)
                    if injury:
                        injuries.append(injury)
                except Exception as e:
                    logger.warning(f"Failed to parse injury row: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to scrape injuries: {e}")

        logger.info(f"Found {len(injuries)} injuries")
        return injuries

    def get_team_injuries(self, team_slug: str, team_id: str) -> list[InjuryInfo]:
        """Get injuries for a specific team."""
        url = f"{self.BASE_URL}/{team_slug}/kader/verein/{team_id}"
        injuries = []

        try:
            soup = self._get_page(url)

            # Look for injury indicators in squad page
            players = soup.find_all("tr", class_=["odd", "even"])

            for player in players:
                injury_icon = player.find("span", class_="verletzt-icon")
                if injury_icon:
                    injury = self._parse_player_injury(player, team_slug, team_id)
                    if injury:
                        injuries.append(injury)

        except Exception as e:
            logger.error(f"Failed to scrape team injuries for {team_slug}: {e}")

        return injuries

    def _parse_injury_row(self, row) -> Optional[InjuryInfo]:
        """Parse a row from the injury table."""
        try:
            # Player info
            player_cell = row.find("td", class_="hauptlink")
            if not player_cell:
                return None

            player_link = player_cell.find("a")
            player_name = player_link.text.strip() if player_link else None
            player_id = self._extract_id(player_link.get("href")) if player_link else None

            # Team info
            team_cell = row.find("td", class_="zentriert")
            team_link = team_cell.find("a") if team_cell else None
            team_name = team_link.get("title") if team_link else None
            team_id = self._extract_id(team_link.get("href")) if team_link else None

            # Injury details
            cells = row.find_all("td")
            injury_type = None
            since = None
            until = None

            for i, cell in enumerate(cells):
                text = cell.text.strip()
                if "injury" in text.lower() or "blessure" in text.lower():
                    injury_type = text
                # Try to parse dates
                if self._is_date(text):
                    if since is None:
                        since = self._parse_date(text)
                    else:
                        until = self._parse_date(text)

            if not player_name:
                return None

            return InjuryInfo(
                player_name=player_name,
                player_id=player_id or "",
                team_name=team_name or "",
                team_id=team_id or "",
                injury_type=injury_type or "Unknown",
                since=since,
                until=until,
            )

        except Exception as e:
            logger.debug(f"Error parsing injury row: {e}")
            return None

    def _parse_player_injury(
        self, player_row, team_slug: str, team_id: str
    ) -> Optional[InjuryInfo]:
        """Parse injury info from a player row in squad page."""
        try:
            player_link = player_row.find("a", class_="spielprofil_tooltip")
            if not player_link:
                return None

            player_name = player_link.text.strip()
            player_id = self._extract_id(player_link.get("href"))

            # Get injury tooltip
            injury_span = player_row.find("span", class_="verletzt-icon")
            injury_type = injury_span.get("title", "Injured") if injury_span else "Injured"

            return InjuryInfo(
                player_name=player_name,
                player_id=player_id or "",
                team_name=team_slug.replace("-", " ").title(),
                team_id=team_id,
                injury_type=injury_type,
            )

        except Exception as e:
            logger.debug(f"Error parsing player injury: {e}")
            return None

    # =========================================================================
    # PLAYER VALUES
    # =========================================================================

    def get_team_values(self, team_slug: str, team_id: str) -> list[PlayerValue]:
        """Get market values for all players in a team."""
        url = f"{self.BASE_URL}/{team_slug}/kader/verein/{team_id}"
        players = []

        try:
            soup = self._get_page(url)
            table = soup.find("table", class_="items")

            if not table:
                return players

            rows = table.find_all("tr", class_=["odd", "even"])

            for row in rows:
                try:
                    player = self._parse_player_value_row(row, team_slug)
                    if player:
                        players.append(player)
                except Exception as e:
                    logger.debug(f"Failed to parse player row: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to scrape team values for {team_slug}: {e}")

        return players

    def _parse_player_value_row(self, row, team_name: str) -> Optional[PlayerValue]:
        """Parse player market value from squad table row."""
        try:
            # Player name
            player_link = row.find("a", class_="spielprofil_tooltip")
            if not player_link:
                return None

            player_name = player_link.text.strip()
            player_id = self._extract_id(player_link.get("href"))

            # Position
            position_cell = row.find("td", class_="posrela")
            position = ""
            if position_cell:
                pos_text = position_cell.find_all("tr")
                if len(pos_text) > 1:
                    position = pos_text[1].text.strip()

            # Market value
            value_cell = row.find("td", class_="rechts hauptlink")
            market_value = 0.0
            if value_cell:
                value_text = value_cell.text.strip()
                market_value = self._parse_market_value(value_text)

            # Age
            age = None
            age_cell = row.find("td", class_="zentriert")
            if age_cell:
                age_text = age_cell.text.strip()
                if age_text.isdigit():
                    age = int(age_text)

            return PlayerValue(
                player_name=player_name,
                player_id=player_id or "",
                team_name=team_name.replace("-", " ").title(),
                position=position,
                market_value=market_value,
                age=age,
            )

        except Exception as e:
            logger.debug(f"Error parsing player value: {e}")
            return None

    # =========================================================================
    # REFEREES
    # =========================================================================

    def get_referee_stats(self, referee_name: str) -> Optional[RefereeStats]:
        """Search and get referee statistics."""
        # Search for referee
        search_url = f"{self.BASE_URL}/schnellsuche/ergebnis/schnellsuche"
        params = {"query": referee_name, "Schiedsrichter": "Schiedsrichter"}

        try:
            response = self.client.get(search_url, params=params)
            soup = BeautifulSoup(response.text, "lxml")

            # Find referee link
            referee_link = soup.find("a", href=re.compile(r"/schiedsrichter/"))
            if not referee_link:
                return None

            referee_url = urljoin(self.BASE_URL, referee_link.get("href"))
            return self._scrape_referee_page(referee_url)

        except Exception as e:
            logger.error(f"Failed to get referee stats for {referee_name}: {e}")
            return None

    def _scrape_referee_page(self, url: str) -> Optional[RefereeStats]:
        """Scrape referee statistics page."""
        try:
            soup = self._get_page(url)

            name = soup.find("h1", class_="data-header__headline-wrapper")
            name = name.text.strip() if name else "Unknown"

            referee_id = self._extract_id(url)

            # Find statistics table
            stats_box = soup.find("div", class_="data-header__box")

            # Default values
            matches = 0
            yellow_per_match = 0.0
            red_per_match = 0.0
            penalties_per_match = 0.0

            if stats_box:
                stats_text = stats_box.text

                # Parse matches
                match_pattern = re.search(r"(\d+)\s*matches", stats_text, re.IGNORECASE)
                if match_pattern:
                    matches = int(match_pattern.group(1))

                # Parse cards per match
                yellow_pattern = re.search(r"(\d+\.?\d*)\s*yellow", stats_text, re.IGNORECASE)
                if yellow_pattern:
                    yellow_per_match = float(yellow_pattern.group(1))

                red_pattern = re.search(r"(\d+\.?\d*)\s*red", stats_text, re.IGNORECASE)
                if red_pattern:
                    red_per_match = float(red_pattern.group(1))

            return RefereeStats(
                name=name,
                referee_id=referee_id or "",
                matches=matches,
                yellow_per_match=yellow_per_match,
                red_per_match=red_per_match,
                penalties_per_match=penalties_per_match,
            )

        except Exception as e:
            logger.error(f"Failed to parse referee page: {e}")
            return None

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def _extract_id(self, url: str) -> Optional[str]:
        """Extract ID from Transfermarkt URL."""
        if not url:
            return None
        # URLs like /player/name/profil/spieler/12345
        match = re.search(r"/(\d+)(?:\?|$|/)", url)
        return match.group(1) if match else None

    def _parse_market_value(self, value_text: str) -> float:
        """Parse market value string to float (in millions)."""
        if not value_text or value_text == "-":
            return 0.0

        value_text = value_text.lower().replace(",", ".").replace(" ", "")

        # Extract number
        match = re.search(r"([\d.]+)", value_text)
        if not match:
            return 0.0

        value = float(match.group(1))

        # Convert to millions
        if "mio" in value_text or "m" in value_text:
            return value
        elif "tsd" in value_text or "k" in value_text:
            return value / 1000
        elif "mrd" in value_text or "bn" in value_text:
            return value * 1000

        return value

    def _is_date(self, text: str) -> bool:
        """Check if text looks like a date."""
        date_patterns = [
            r"\d{1,2}/\d{1,2}/\d{2,4}",
            r"\d{1,2}\.\d{1,2}\.\d{2,4}",
            r"\d{1,2}-\d{1,2}-\d{2,4}",
        ]
        return any(re.match(p, text) for p in date_patterns)

    def _parse_date(self, text: str) -> Optional[datetime]:
        """Parse date from various formats."""
        formats = [
            "%d/%m/%Y",
            "%d.%m.%Y",
            "%d-%m-%Y",
            "%d/%m/%y",
            "%d.%m.%y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(text.strip(), fmt)
            except ValueError:
                continue
        return None

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Singleton instance
_scraper: Optional[TransfermarktScraper] = None


def get_transfermarkt_scraper() -> TransfermarktScraper:
    """Get or create the Transfermarkt scraper singleton."""
    global _scraper
    if _scraper is None:
        _scraper = TransfermarktScraper()
    return _scraper

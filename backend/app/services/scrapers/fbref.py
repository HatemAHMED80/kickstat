"""
FBref Scraper
Scrapes xG (expected goals) data from FBref (StatsBomb data).

FBref provides high-quality advanced statistics from StatsBomb.
Covers: Ligue 1, Premier League, La Liga, Bundesliga, Serie A
"""

import re
import time
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

import cloudscraper
from bs4 import BeautifulSoup
from loguru import logger

from app.core import get_settings

settings = get_settings()


@dataclass
class FBrefMatchXG:
    """Expected goals data for a match from FBref."""

    match_id: str  # FBref match ID
    date: datetime
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    home_xg: float
    away_xg: float
    competition: str
    matchweek: Optional[int] = None
    attendance: Optional[int] = None
    venue: Optional[str] = None


@dataclass
class FBrefTeamSeasonXG:
    """Season xG statistics for a team from FBref."""

    team_name: str
    competition: str
    season: str
    matches_played: int
    goals_for: int
    goals_against: int
    xg: float  # Expected goals for
    xga: float  # Expected goals against
    xg_diff: float  # xG - xGA
    npxg: float  # Non-penalty xG
    npxga: float  # Non-penalty xGA


class FBrefScraper:
    """Scraper for FBref xG data (StatsBomb)."""

    BASE_URL = "https://fbref.com"

    # Competition IDs in FBref
    COMPETITIONS = {
        "ligue1": {"id": 13, "name": "Ligue-1", "full_name": "Ligue 1"},
        "premier_league": {"id": 9, "name": "Premier-League", "full_name": "Premier League"},
        "la_liga": {"id": 12, "name": "La-Liga", "full_name": "La Liga"},
        "bundesliga": {"id": 20, "name": "Bundesliga", "full_name": "Bundesliga"},
        "serie_a": {"id": 11, "name": "Serie-A", "full_name": "Serie A"},
    }

    # Team name mapping (FBref -> standard names used in our DB)
    TEAM_MAPPING = {
        # Ligue 1
        "Paris Saint-Germain": "Paris Saint-Germain",
        "Paris S-G": "Paris Saint-Germain",
        "Marseille": "Olympique de Marseille",
        "Olympique Marseille": "Olympique de Marseille",
        "Lyon": "Olympique Lyon",
        "Olympique Lyonnais": "Olympique Lyon",
        "Monaco": "AS Monaco",
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
        "Auxerre": "AJ Auxerre",
        "Angers": "Angers SCO",
        "Saint-Étienne": "AS Saint-Étienne",
        # Premier League
        "Manchester City": "Manchester City FC",
        "Manchester Utd": "Manchester United FC",
        "Arsenal": "Arsenal FC",
        "Liverpool": "Liverpool FC",
        "Chelsea": "Chelsea FC",
        "Tottenham": "Tottenham Hotspur FC",
        "Newcastle Utd": "Newcastle United FC",
        "Brighton": "Brighton & Hove Albion FC",
        "Aston Villa": "Aston Villa FC",
        "West Ham": "West Ham United FC",
        "Brentford": "Brentford FC",
        "Fulham": "Fulham FC",
        "Crystal Palace": "Crystal Palace FC",
        "Wolves": "Wolverhampton Wanderers FC",
        "Bournemouth": "AFC Bournemouth",
        "Nottingham Forest": "Nottingham Forest FC",
        "Everton": "Everton FC",
        "Leicester City": "Leicester City FC",
        "Ipswich Town": "Ipswich Town FC",
        "Southampton": "Southampton FC",
        # La Liga
        "Barcelona": "FC Barcelona",
        "Real Madrid": "Real Madrid CF",
        "Atlético Madrid": "Club Atlético de Madrid",
        "Athletic Club": "Athletic Club",
        "Real Sociedad": "Real Sociedad de Fútbol",
        "Real Betis": "Real Betis Balompié",
        "Villarreal": "Villarreal CF",
        "Sevilla": "Sevilla FC",
        "Valencia": "Valencia CF",
        "Getafe": "Getafe CF",
        "Celta Vigo": "RC Celta de Vigo",
        "Osasuna": "CA Osasuna",
        "Mallorca": "RCD Mallorca",
        "Las Palmas": "UD Las Palmas",
        "Rayo Vallecano": "Rayo Vallecano de Madrid",
        "Alavés": "Deportivo Alavés",
        "Girona": "Girona FC",
        "Leganés": "CD Leganés",
        "Espanyol": "RCD Espanyol de Barcelona",
        "Valladolid": "Real Valladolid CF",
    }

    def __init__(self):
        # FBref uses Cloudflare - use cloudscraper to bypass
        self.client = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'darwin',
                'desktop': True,
            }
        )
        # FBref has strict rate limiting - be very conservative
        self.rate_limit_delay = getattr(settings, 'fbref_rate_limit', 5.0)

    def _get_page(self, url: str) -> BeautifulSoup:
        """Fetch page with rate limiting and return BeautifulSoup."""
        time.sleep(self.rate_limit_delay)
        logger.debug(f"Fetching FBref: {url}")

        response = self.client.get(url, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")

    # =========================================================================
    # MATCH FIXTURES WITH xG
    # =========================================================================

    def get_season_matches(
        self,
        competition: str = "ligue1",
        season: str = "2024-2025"
    ) -> list[FBrefMatchXG]:
        """
        Get all matches with xG data for a season.

        Args:
            competition: One of 'ligue1', 'premier_league', 'la_liga', 'bundesliga', 'serie_a'
            season: Season in format '2024-2025'

        Returns:
            List of FBrefMatchXG objects
        """
        comp_info = self.COMPETITIONS.get(competition)
        if not comp_info:
            logger.error(f"Unknown competition: {competition}")
            return []

        # URL format: /en/comps/{id}/{season}/schedule/{season}-{name}-Scores-and-Fixtures
        url = (
            f"{self.BASE_URL}/en/comps/{comp_info['id']}/{season}/schedule/"
            f"{season}-{comp_info['name']}-Scores-and-Fixtures"
        )

        matches = []

        try:
            soup = self._get_page(url)

            # Find the main fixtures table
            table = soup.find("table", {"id": "sched_all"})
            if not table:
                # Try alternative table ID for current season
                table = soup.find("table", {"id": re.compile(r"sched_\d+_\d+")})

            if not table:
                logger.warning(f"No fixtures table found for {competition} {season}")
                return matches

            tbody = table.find("tbody")
            if not tbody:
                return matches

            rows = tbody.find_all("tr")
            logger.info(f"Processing {len(rows)} rows from FBref fixtures")

            for row in rows:
                # Skip spacer rows
                if "spacer" in row.get("class", []) or "thead" in row.get("class", []):
                    continue

                match = self._parse_fixture_row(row, comp_info["full_name"])
                if match:
                    matches.append(match)

        except Exception as e:
            logger.error(f"Failed to scrape FBref matches: {e}")

        logger.info(f"Found {len(matches)} matches with xG data from FBref")
        return matches

    def get_current_season_matches(self, competition: str = "ligue1") -> list[FBrefMatchXG]:
        """Get matches for the current season (2024-2025)."""
        return self.get_season_matches(competition, "2024-2025")

    # =========================================================================
    # TEAM SEASON STATS
    # =========================================================================

    def get_team_season_stats(
        self,
        competition: str = "ligue1",
        season: str = "2024-2025"
    ) -> list[FBrefTeamSeasonXG]:
        """
        Get season xG statistics for all teams in a competition.

        Args:
            competition: One of the supported competitions
            season: Season in format '2024-2025'

        Returns:
            List of FBrefTeamSeasonXG objects
        """
        comp_info = self.COMPETITIONS.get(competition)
        if not comp_info:
            logger.error(f"Unknown competition: {competition}")
            return []

        # URL format: /en/comps/{id}/{season}/{season}-{name}-Stats
        url = (
            f"{self.BASE_URL}/en/comps/{comp_info['id']}/{season}/"
            f"{season}-{comp_info['name']}-Stats"
        )

        teams = []

        try:
            soup = self._get_page(url)

            # Find the squad stats table
            table = soup.find("table", {"id": "stats_squads_standard_for"})
            if not table:
                logger.warning(f"No squad stats table found for {competition} {season}")
                return teams

            tbody = table.find("tbody")
            if not tbody:
                return teams

            for row in tbody.find_all("tr"):
                team_stats = self._parse_team_stats_row(row, comp_info["full_name"], season)
                if team_stats:
                    teams.append(team_stats)

        except Exception as e:
            logger.error(f"Failed to scrape FBref team stats: {e}")

        logger.info(f"Found {len(teams)} team stats from FBref")
        return teams

    # =========================================================================
    # PARSING HELPERS
    # =========================================================================

    def _parse_fixture_row(self, row, competition: str) -> Optional[FBrefMatchXG]:
        """Parse a fixture row from the schedule table."""
        try:
            cells = row.find_all(["td", "th"])
            if len(cells) < 10:
                return None

            # Get cell values by data-stat attribute (more reliable)
            def get_stat(stat_name: str) -> Optional[str]:
                cell = row.find(["td", "th"], {"data-stat": stat_name})
                return cell.get_text(strip=True) if cell else None

            # Date
            date_str = get_stat("date")
            if not date_str:
                return None

            # Time
            time_str = get_stat("time") or "00:00"

            # Parse datetime
            try:
                match_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            except ValueError:
                match_dt = datetime.strptime(date_str, "%Y-%m-%d")

            # Teams
            home_team = get_stat("home_team")
            away_team = get_stat("away_team")

            if not home_team or not away_team:
                return None

            # Score (format: "2–1" or empty for future matches)
            score_str = get_stat("score")
            if not score_str or "–" not in score_str:
                return None  # Match not played yet

            score_parts = score_str.split("–")
            if len(score_parts) != 2:
                return None

            home_goals = int(score_parts[0].strip())
            away_goals = int(score_parts[1].strip())

            # xG values
            home_xg_str = get_stat("home_xg")
            away_xg_str = get_stat("away_xg")

            # xG might be empty for some matches
            home_xg = float(home_xg_str) if home_xg_str else 0.0
            away_xg = float(away_xg_str) if away_xg_str else 0.0

            # Skip if no xG data
            if home_xg == 0.0 and away_xg == 0.0:
                return None

            # Matchweek
            matchweek_str = get_stat("gameweek") or get_stat("round")
            matchweek = None
            if matchweek_str:
                try:
                    # Extract number from "Matchweek 1" or just "1"
                    mw_match = re.search(r"(\d+)", matchweek_str)
                    if mw_match:
                        matchweek = int(mw_match.group(1))
                except ValueError:
                    pass

            # Venue
            venue = get_stat("venue")

            # Attendance
            attendance_str = get_stat("attendance")
            attendance = None
            if attendance_str:
                try:
                    attendance = int(attendance_str.replace(",", ""))
                except ValueError:
                    pass

            # Match ID from link
            match_id = ""
            match_link = row.find("a", href=re.compile(r"/matches/"))
            if match_link:
                href = match_link.get("href", "")
                id_match = re.search(r"/matches/([a-f0-9]+)/", href)
                if id_match:
                    match_id = id_match.group(1)

            return FBrefMatchXG(
                match_id=match_id,
                date=match_dt,
                home_team=home_team,
                away_team=away_team,
                home_goals=home_goals,
                away_goals=away_goals,
                home_xg=home_xg,
                away_xg=away_xg,
                competition=competition,
                matchweek=matchweek,
                venue=venue,
                attendance=attendance,
            )

        except Exception as e:
            logger.debug(f"Failed to parse fixture row: {e}")
            return None

    def _parse_team_stats_row(
        self,
        row,
        competition: str,
        season: str
    ) -> Optional[FBrefTeamSeasonXG]:
        """Parse a team stats row from the squad stats table."""
        try:
            def get_stat(stat_name: str) -> Optional[str]:
                cell = row.find(["td", "th"], {"data-stat": stat_name})
                return cell.get_text(strip=True) if cell else None

            team_name = get_stat("team")
            if not team_name:
                return None

            # Basic stats
            matches = int(get_stat("games") or 0)
            goals_for = int(get_stat("goals") or 0)
            goals_against = int(get_stat("goals_against") or 0)

            # xG stats
            xg = float(get_stat("xg") or 0)
            xga = float(get_stat("xg_against") or 0)
            npxg = float(get_stat("npxg") or 0)
            npxga = float(get_stat("npxg_against") or 0)

            return FBrefTeamSeasonXG(
                team_name=team_name,
                competition=competition,
                season=season,
                matches_played=matches,
                goals_for=goals_for,
                goals_against=goals_against,
                xg=round(xg, 2),
                xga=round(xga, 2),
                xg_diff=round(xg - xga, 2),
                npxg=round(npxg, 2),
                npxga=round(npxga, 2),
            )

        except Exception as e:
            logger.debug(f"Failed to parse team stats row: {e}")
            return None

    # =========================================================================
    # UTILITY
    # =========================================================================

    def normalize_team_name(self, fbref_name: str) -> str:
        """Normalize FBref team name to standard format used in our DB."""
        return self.TEAM_MAPPING.get(fbref_name, fbref_name)

    def get_all_competitions_matches(self, season: str = "2024-2025") -> dict[str, list[FBrefMatchXG]]:
        """Get matches for all supported competitions."""
        all_matches = {}

        for comp_key in self.COMPETITIONS.keys():
            logger.info(f"Scraping {comp_key} {season}...")
            matches = self.get_season_matches(comp_key, season)
            all_matches[comp_key] = matches
            # Extra delay between competitions to be nice to FBref
            time.sleep(5)

        return all_matches

    def close(self):
        """Close the HTTP client."""
        # cloudscraper uses requests.Session which has close()
        if hasattr(self.client, 'close'):
            self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Singleton
_scraper: Optional[FBrefScraper] = None


def get_fbref_scraper() -> FBrefScraper:
    """Get or create FBref scraper singleton."""
    global _scraper
    if _scraper is None:
        _scraper = FBrefScraper()
    return _scraper

"""
Unified Football Data Service

Aggregates data from multiple free sources:
- Football-Data.org: Standings, matches, basic stats
- Understat: xG (expected goals) data
- API-Football: Player stats, injuries (limited free tier)
- FBref: Advanced stats (scraping)
"""

import re
import time
import json
import urllib.request
from datetime import datetime, date
from typing import Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class TeamXG:
    """Expected goals data for a team."""
    team_name: str
    matches_played: int = 0
    xg_for: float = 0.0
    xg_against: float = 0.0
    xg_diff: float = 0.0
    npxg: float = 0.0  # Non-penalty xG
    xg_per_match: float = 0.0
    goals_minus_xg: float = 0.0  # Overperformance


@dataclass
class PlayerXG:
    """xG data for a player."""
    player_name: str
    team: str
    position: str
    matches: int = 0
    minutes: int = 0
    goals: int = 0
    xg: float = 0.0
    xg_per_90: float = 0.0
    shots: int = 0
    assists: int = 0
    xa: float = 0.0  # Expected assists


@dataclass
class InjuryInfo:
    """Player injury information."""
    player_name: str
    team: str
    injury_type: str
    status: str  # "out", "doubt", "back_soon"
    expected_return: Optional[date] = None


@dataclass
class MatchPredictionData:
    """All data needed for match prediction."""
    home_team: str
    away_team: str

    # Basic stats
    home_position: int = 0
    away_position: int = 0
    home_points: int = 0
    away_points: int = 0
    home_form: str = ""  # "WWDLW"
    away_form: str = ""

    # Goals
    home_goals_for: int = 0
    home_goals_against: int = 0
    away_goals_for: int = 0
    away_goals_against: int = 0

    # xG (from Understat/FBref)
    home_xg: float = 0.0
    home_xg_against: float = 0.0
    away_xg: float = 0.0
    away_xg_against: float = 0.0

    # Home/Away specific
    home_home_xg: float = 0.0  # xG at home
    away_away_xg: float = 0.0  # xG away

    # H2H
    h2h_matches: int = 0
    h2h_home_wins: int = 0
    h2h_draws: int = 0
    h2h_away_wins: int = 0
    h2h_avg_goals: float = 0.0

    # Injuries
    home_injuries: list = field(default_factory=list)
    away_injuries: list = field(default_factory=list)

    # Key players
    home_key_players_out: list = field(default_factory=list)
    away_key_players_out: list = field(default_factory=list)


class UnderstatScraper:
    """
    Scrape xG data from Understat.

    Supports: Premier League, La Liga, Bundesliga, Serie A, Ligue 1, RFPL
    """

    BASE_URL = "https://understat.com"

    LEAGUE_CODES = {
        "ligue_1": "Ligue_1",
        "premier_league": "EPL",
        "la_liga": "La_liga",
        "bundesliga": "Bundesliga",
        "serie_a": "Serie_A",
    }

    def __init__(self):
        self.session_data = {}

    def _fetch_page(self, url: str) -> str:
        """Fetch HTML page content."""
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode('utf-8')

    def _extract_json_var(self, html: str, var_name: str) -> dict:
        """Extract JSON data from JavaScript variable in HTML."""
        pattern = rf"var {var_name}\s*=\s*JSON\.parse\('(.+?)'\)"
        match = re.search(pattern, html)
        if match:
            json_str = match.group(1)
            # Unescape the string
            json_str = json_str.encode().decode('unicode_escape')
            return json.loads(json_str)
        return {}

    def get_league_teams_xg(self, league: str = "ligue_1", season: int = 2025) -> list[TeamXG]:
        """
        Get xG data for all teams in a league.

        Returns list of TeamXG objects with xG for/against.
        """
        league_code = self.LEAGUE_CODES.get(league, league)
        url = f"{self.BASE_URL}/league/{league_code}/{season}"

        try:
            html = self._fetch_page(url)
            teams_data = self._extract_json_var(html, "teamsData")

            result = []
            for team_id, data in teams_data.items():
                team = TeamXG(
                    team_name=data.get("title", "Unknown"),
                    matches_played=len(data.get("history", [])),
                )

                # Calculate totals from history
                for match in data.get("history", []):
                    team.xg_for += float(match.get("xG", 0))
                    team.xg_against += float(match.get("xGA", 0))
                    team.npxg += float(match.get("npxG", 0))

                if team.matches_played > 0:
                    team.xg_per_match = team.xg_for / team.matches_played
                    team.xg_diff = team.xg_for - team.xg_against

                    # Calculate goals minus xG (overperformance)
                    total_goals = sum(int(m.get("scored", 0)) for m in data.get("history", []))
                    team.goals_minus_xg = total_goals - team.xg_for

                result.append(team)

            logger.info(f"Fetched xG data for {len(result)} teams from Understat")
            return result

        except Exception as e:
            logger.error(f"Error fetching Understat data: {e}")
            return []

    def get_team_xg(self, team_name: str, league: str = "ligue_1", season: int = 2025) -> Optional[TeamXG]:
        """Get xG data for a specific team."""
        teams = self.get_league_teams_xg(league, season)

        # Fuzzy match team name
        team_name_lower = team_name.lower()
        for team in teams:
            if team_name_lower in team.team_name.lower() or team.team_name.lower() in team_name_lower:
                return team

        return None

    def get_top_scorers_xg(self, league: str = "ligue_1", season: int = 2025) -> list[PlayerXG]:
        """Get top scorers with xG data."""
        league_code = self.LEAGUE_CODES.get(league, league)
        url = f"{self.BASE_URL}/league/{league_code}/{season}"

        try:
            html = self._fetch_page(url)
            players_data = self._extract_json_var(html, "playersData")

            result = []
            for player in players_data:
                p = PlayerXG(
                    player_name=player.get("player_name", "Unknown"),
                    team=player.get("team_title", ""),
                    position=player.get("position", ""),
                    matches=int(player.get("games", 0)),
                    minutes=int(player.get("time", 0)),
                    goals=int(player.get("goals", 0)),
                    xg=float(player.get("xG", 0)),
                    shots=int(player.get("shots", 0)),
                    assists=int(player.get("assists", 0)),
                    xa=float(player.get("xA", 0)),
                )

                if p.minutes > 0:
                    p.xg_per_90 = (p.xg / p.minutes) * 90

                result.append(p)

            # Sort by goals
            result.sort(key=lambda x: x.goals, reverse=True)
            logger.info(f"Fetched xG data for {len(result)} players from Understat")
            return result[:50]  # Top 50

        except Exception as e:
            logger.error(f"Error fetching player xG data: {e}")
            return []


class FootballDataOrgAPI:
    """
    Football-Data.org API client for standings, matches, H2H.
    """

    BASE_URL = "https://api.football-data.org/v4"

    def __init__(self, api_key: str = None):
        self.api_key = api_key

    def _request(self, endpoint: str) -> dict:
        """Make API request."""
        url = f"{self.BASE_URL}{endpoint}"
        req = urllib.request.Request(url)
        if self.api_key:
            req.add_header("X-Auth-Token", self.api_key)

        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())

    def get_standings(self, competition: str = "FL1") -> list[dict]:
        """Get league standings."""
        data = self._request(f"/competitions/{competition}/standings")
        for s in data.get("standings", []):
            if s.get("type") == "TOTAL":
                return s.get("table", [])
        return []

    def get_team_form(self, team_id: int, limit: int = 5) -> str:
        """Get recent form string (e.g., 'WWDLW')."""
        data = self._request(f"/teams/{team_id}/matches?status=FINISHED&limit={limit}")
        matches = data.get("matches", [])

        form = ""
        for match in matches[::-1]:  # Oldest first
            home_score = match.get("score", {}).get("fullTime", {}).get("home", 0)
            away_score = match.get("score", {}).get("fullTime", {}).get("away", 0)

            is_home = match.get("homeTeam", {}).get("id") == team_id

            if is_home:
                if home_score > away_score:
                    form += "W"
                elif home_score < away_score:
                    form += "L"
                else:
                    form += "D"
            else:
                if away_score > home_score:
                    form += "W"
                elif away_score < home_score:
                    form += "L"
                else:
                    form += "D"

        return form


class TransfermarktScraper:
    """
    Scrape injury data from Transfermarkt.
    """

    BASE_URL = "https://www.transfermarkt.com"

    # Ligue 1 team slugs
    TEAM_SLUGS = {
        "PSG": "fc-paris-saint-germain",
        "Paris Saint-Germain": "fc-paris-saint-germain",
        "Monaco": "as-monaco",
        "Marseille": "olympique-marseille",
        "Lyon": "olympique-lyon",
        "Lille": "losc-lille",
        "Rennes": "stade-rennais-fc",
        "Lens": "rc-lens",
        "Nice": "ogc-nizza",
        "Nantes": "fc-nantes",
        "Lorient": "fc-lorient",
    }

    def _fetch_page(self, url: str) -> str:
        """Fetch HTML page."""
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode('utf-8')

    def get_team_injuries(self, team_name: str) -> list[InjuryInfo]:
        """Get current injuries for a team."""
        slug = self.TEAM_SLUGS.get(team_name)
        if not slug:
            logger.warning(f"No Transfermarkt slug for team: {team_name}")
            return []

        # This would need proper HTML parsing with BeautifulSoup
        # For now, return empty - would need to implement full scraping
        logger.info(f"Injury scraping for {team_name} - not fully implemented")
        return []


class UnifiedDataService:
    """
    Unified service that aggregates data from all sources.
    """

    def __init__(self, football_data_key: str = None):
        self.understat = UnderstatScraper()
        self.football_data = FootballDataOrgAPI(football_data_key)
        self.transfermarkt = TransfermarktScraper()

        # Cache
        self._xg_cache = {}
        self._standings_cache = {}
        self._cache_time = {}

    def get_match_prediction_data(
        self,
        home_team: str,
        away_team: str,
        league: str = "ligue_1",
        season: int = 2025
    ) -> MatchPredictionData:
        """
        Get all data needed for match prediction.

        Combines:
        - Basic stats from Football-Data.org
        - xG from Understat
        - Injuries from Transfermarkt (if available)
        """
        data = MatchPredictionData(home_team=home_team, away_team=away_team)

        # 1. Get standings
        try:
            standings = self.football_data.get_standings("FL1")
            for team in standings:
                name = team.get("team", {}).get("name", "")
                if home_team.lower() in name.lower() or name.lower() in home_team.lower():
                    data.home_position = team.get("position", 0)
                    data.home_points = team.get("points", 0)
                    data.home_goals_for = team.get("goalsFor", 0)
                    data.home_goals_against = team.get("goalsAgainst", 0)
                elif away_team.lower() in name.lower() or name.lower() in away_team.lower():
                    data.away_position = team.get("position", 0)
                    data.away_points = team.get("points", 0)
                    data.away_goals_for = team.get("goalsFor", 0)
                    data.away_goals_against = team.get("goalsAgainst", 0)
        except Exception as e:
            logger.error(f"Error fetching standings: {e}")

        # 2. Get xG from Understat
        try:
            # Rate limit
            time.sleep(1)

            home_xg = self.understat.get_team_xg(home_team, league, season)
            if home_xg:
                data.home_xg = home_xg.xg_per_match
                data.home_xg_against = home_xg.xg_against / max(home_xg.matches_played, 1)

            away_xg = self.understat.get_team_xg(away_team, league, season)
            if away_xg:
                data.away_xg = away_xg.xg_per_match
                data.away_xg_against = away_xg.xg_against / max(away_xg.matches_played, 1)

        except Exception as e:
            logger.error(f"Error fetching xG data: {e}")

        # 3. Get injuries (if implemented)
        try:
            data.home_injuries = self.transfermarkt.get_team_injuries(home_team)
            data.away_injuries = self.transfermarkt.get_team_injuries(away_team)
        except Exception as e:
            logger.error(f"Error fetching injuries: {e}")

        return data

    def get_league_xg_table(self, league: str = "ligue_1", season: int = 2025) -> list[TeamXG]:
        """Get xG table for entire league."""
        cache_key = f"{league}_{season}"

        # Check cache (1 hour)
        if cache_key in self._xg_cache:
            cached_time = self._cache_time.get(cache_key, 0)
            if time.time() - cached_time < 3600:
                return self._xg_cache[cache_key]

        teams = self.understat.get_league_teams_xg(league, season)

        # Sort by xG difference
        teams.sort(key=lambda x: x.xg_diff, reverse=True)

        # Cache
        self._xg_cache[cache_key] = teams
        self._cache_time[cache_key] = time.time()

        return teams


# Singleton
_service: Optional[UnifiedDataService] = None


def get_unified_data_service(football_data_key: str = None) -> UnifiedDataService:
    """Get or create the unified data service singleton."""
    global _service
    if _service is None:
        _service = UnifiedDataService(football_data_key)
    return _service


# ============================================================================
# CLI Testing
# ============================================================================

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.getenv("FOOTBALL_DATA_ORG_KEY")
    service = UnifiedDataService(api_key)

    print("=" * 60)
    print("TESTING UNIFIED DATA SERVICE")
    print("=" * 60)

    # Test xG table
    print("\n📊 Ligue 1 xG Table:")
    print("-" * 60)

    teams = service.get_league_xg_table("ligue_1", 2025)
    print(f"{'Team':<25} {'xG':<8} {'xGA':<8} {'xG Diff':<10} {'Over/Under':<10}")
    print("-" * 60)

    for team in teams[:10]:
        print(f"{team.team_name:<25} {team.xg_for:>6.1f} {team.xg_against:>7.1f} {team.xg_diff:>+9.1f} {team.goals_minus_xg:>+9.1f}")

    # Test top scorers
    print("\n⚽ Top Scorers with xG:")
    print("-" * 60)

    understat = UnderstatScraper()
    scorers = understat.get_top_scorers_xg("ligue_1", 2025)
    print(f"{'Player':<25} {'Team':<15} {'Goals':<6} {'xG':<8} {'Diff':<8}")
    print("-" * 60)

    for p in scorers[:10]:
        diff = p.goals - p.xg
        print(f"{p.player_name:<25} {p.team:<15} {p.goals:>5} {p.xg:>7.2f} {diff:>+7.2f}")

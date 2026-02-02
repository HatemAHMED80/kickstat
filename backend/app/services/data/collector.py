"""
Data Collection Service
Orchestrates data collection from various sources and stores in database.
"""

from datetime import datetime, date
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from loguru import logger

from app.models import (
    Competition,
    Team,
    Stadium,
    Player,
    Match,
    MatchStats,
    Standing,
    Referee,
)
from app.services.data.api_football import get_api_football_client, APIFootballClient
from app.services.scrapers.transfermarkt import get_transfermarkt_scraper


class DataCollector:
    """
    Orchestrates data collection from multiple sources.

    Usage:
        collector = DataCollector(db_session)
        collector.sync_teams(season=2024)
        collector.sync_fixtures(season=2024)
        collector.sync_injuries()
    """

    def __init__(self, db: Session):
        self.db = db
        self.api = get_api_football_client()

    # =========================================================================
    # COMPETITIONS
    # =========================================================================

    def sync_competitions(self) -> list[Competition]:
        """Sync French competitions to database."""
        competitions_data = [
            {
                "api_id": 61,
                "name": "Ligue 1",
                "short_name": "L1",
                "country": "France",
                "type": "league",
            },
            {
                "api_id": 66,
                "name": "Coupe de France",
                "short_name": "CDF",
                "country": "France",
                "type": "cup",
            },
            {
                "api_id": 65,
                "name": "Trophée des Champions",
                "short_name": "TDC",
                "country": "France",
                "type": "cup",
            },
        ]

        competitions = []
        for data in competitions_data:
            comp = self.db.execute(
                select(Competition).where(Competition.api_id == data["api_id"])
            ).scalar_one_or_none()

            if not comp:
                comp = Competition(**data)
                self.db.add(comp)
                logger.info(f"Created competition: {data['name']}")
            else:
                for key, value in data.items():
                    setattr(comp, key, value)

            competitions.append(comp)

        self.db.commit()
        return competitions

    # =========================================================================
    # TEAMS
    # =========================================================================

    def sync_teams(self, league_id: int = 61, season: int = 2024) -> list[Team]:
        """Sync teams from API-Football to database."""
        logger.info(f"Syncing teams for league {league_id}, season {season}")

        api_teams = self.api.get_teams(league_id=league_id, season=season)
        teams = []

        for team_data in api_teams:
            team_info = team_data.get("team", {})
            venue_info = team_data.get("venue", {})

            # Create/update stadium first
            stadium = None
            if venue_info.get("id"):
                stadium = self._sync_stadium(venue_info)

            # Create/update team
            team = self.db.execute(
                select(Team).where(Team.api_id == team_info["id"])
            ).scalar_one_or_none()

            if not team:
                team = Team(
                    api_id=team_info["id"],
                    name=team_info["name"],
                    short_name=team_info.get("code"),
                    code=team_info.get("code"),
                    logo_url=team_info.get("logo"),
                    stadium_id=stadium.id if stadium else None,
                    founded=team_info.get("founded"),
                )
                self.db.add(team)
                logger.info(f"Created team: {team_info['name']}")
            else:
                team.name = team_info["name"]
                team.logo_url = team_info.get("logo")
                if stadium:
                    team.stadium_id = stadium.id

            teams.append(team)

        self.db.commit()
        logger.info(f"Synced {len(teams)} teams")
        return teams

    def _sync_stadium(self, venue_info: dict) -> Stadium:
        """Create or update stadium from API data."""
        stadium = self.db.execute(
            select(Stadium).where(Stadium.api_id == venue_info["id"])
        ).scalar_one_or_none()

        if not stadium:
            stadium = Stadium(
                api_id=venue_info["id"],
                name=venue_info.get("name"),
                city=venue_info.get("city"),
                capacity=venue_info.get("capacity"),
                surface=venue_info.get("surface"),
            )
            self.db.add(stadium)
            self.db.flush()  # Get ID

        return stadium

    # =========================================================================
    # PLAYERS
    # =========================================================================

    def sync_team_players(self, team_id: int, season: int = 2024) -> list[Player]:
        """Sync players for a specific team."""
        # Get team from DB
        team = self.db.execute(
            select(Team).where(Team.api_id == team_id)
        ).scalar_one_or_none()

        if not team:
            logger.warning(f"Team {team_id} not found in database")
            return []

        # Get squad from API
        api_players = self.api.get_player_squads(team_id)
        players = []

        for player_data in api_players:
            player = self.db.execute(
                select(Player).where(Player.api_id == player_data["id"])
            ).scalar_one_or_none()

            if not player:
                player = Player(
                    api_id=player_data["id"],
                    team_id=team.id,
                    name=player_data.get("name"),
                    position=player_data.get("position"),
                    number=player_data.get("number"),
                )
                self.db.add(player)
            else:
                player.team_id = team.id
                player.position = player_data.get("position")
                player.number = player_data.get("number")

            players.append(player)

        self.db.commit()
        logger.info(f"Synced {len(players)} players for {team.name}")
        return players

    # =========================================================================
    # FIXTURES / MATCHES
    # =========================================================================

    def sync_fixtures(
        self,
        league_id: int = 61,
        season: int = 2024,
        date_from: date = None,
        date_to: date = None,
    ) -> list[Match]:
        """Sync fixtures from API-Football."""
        logger.info(f"Syncing fixtures for league {league_id}, season {season}")

        api_fixtures = self.api.get_fixtures(
            league_id=league_id,
            season=season,
            date_from=date_from,
            date_to=date_to,
        )

        matches = []
        for fixture_data in api_fixtures:
            match = self._sync_fixture(fixture_data)
            if match:
                matches.append(match)

        self.db.commit()
        logger.info(f"Synced {len(matches)} fixtures")
        return matches

    def _sync_fixture(self, fixture_data: dict) -> Optional[Match]:
        """Create or update a single fixture."""
        fixture = fixture_data.get("fixture", {})
        league = fixture_data.get("league", {})
        teams = fixture_data.get("teams", {})
        goals = fixture_data.get("goals", {})
        score = fixture_data.get("score", {})

        fixture_id = fixture.get("id")
        if not fixture_id:
            return None

        # Get team IDs from database
        home_team = self.db.execute(
            select(Team).where(Team.api_id == teams.get("home", {}).get("id"))
        ).scalar_one_or_none()

        away_team = self.db.execute(
            select(Team).where(Team.api_id == teams.get("away", {}).get("id"))
        ).scalar_one_or_none()

        if not home_team or not away_team:
            logger.warning(f"Teams not found for fixture {fixture_id}")
            return None

        # Get competition
        competition = self.db.execute(
            select(Competition).where(Competition.api_id == league.get("id"))
        ).scalar_one_or_none()

        # Parse kickoff time
        kickoff_str = fixture.get("date")
        kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00")) if kickoff_str else None

        # Map status
        status_mapping = {
            "NS": "scheduled",
            "TBD": "scheduled",
            "1H": "live",
            "HT": "live",
            "2H": "live",
            "ET": "live",
            "P": "live",
            "FT": "finished",
            "AET": "finished",
            "PEN": "finished",
            "PST": "postponed",
            "CANC": "postponed",
        }
        status_short = fixture.get("status", {}).get("short", "NS")
        status = status_mapping.get(status_short, "scheduled")

        # Create or update match
        match = self.db.execute(
            select(Match).where(Match.api_id == fixture_id)
        ).scalar_one_or_none()

        if not match:
            match = Match(api_id=fixture_id)
            self.db.add(match)

        match.home_team_id = home_team.id
        match.away_team_id = away_team.id
        match.competition_id = competition.id if competition else None
        match.kickoff = kickoff
        match.matchday = league.get("round")
        match.status = status

        # Scores
        match.home_score = goals.get("home")
        match.away_score = goals.get("away")

        # Half-time scores
        ht = score.get("halftime", {})
        match.home_score_ht = ht.get("home")
        match.away_score_ht = ht.get("away")

        # Extra time
        et = score.get("extratime", {})
        if et.get("home") is not None:
            match.extra_time = True
            match.home_score_et = et.get("home")
            match.away_score_et = et.get("away")

        # Penalties
        pen = score.get("penalty", {})
        if pen.get("home") is not None:
            match.penalties = True
            match.home_penalties = pen.get("home")
            match.away_penalties = pen.get("away")

        return match

    def sync_fixture_statistics(self, fixture_id: int) -> list[MatchStats]:
        """Sync statistics for a specific fixture."""
        match = self.db.execute(
            select(Match).where(Match.api_id == fixture_id)
        ).scalar_one_or_none()

        if not match:
            logger.warning(f"Match {fixture_id} not found")
            return []

        api_stats = self.api.get_fixture_statistics(fixture_id)
        stats_list = []

        for team_stats in api_stats:
            team_api_id = team_stats.get("team", {}).get("id")
            team = self.db.execute(
                select(Team).where(Team.api_id == team_api_id)
            ).scalar_one_or_none()

            if not team:
                continue

            # Parse statistics
            stats_dict = {}
            for stat in team_stats.get("statistics", []):
                stat_type = stat.get("type", "").lower().replace(" ", "_")
                stats_dict[stat_type] = stat.get("value")

            # Create or update match stats
            match_stats = self.db.execute(
                select(MatchStats).where(
                    MatchStats.match_id == match.id,
                    MatchStats.team_id == team.id,
                )
            ).scalar_one_or_none()

            if not match_stats:
                match_stats = MatchStats(match_id=match.id, team_id=team.id)
                self.db.add(match_stats)

            # Map API stats to model
            match_stats.shots = self._parse_stat(stats_dict.get("total_shots"))
            match_stats.shots_on_target = self._parse_stat(stats_dict.get("shots_on_goal"))
            match_stats.possession = self._parse_percentage(stats_dict.get("ball_possession"))
            match_stats.passes = self._parse_stat(stats_dict.get("total_passes"))
            match_stats.pass_accuracy = self._parse_percentage(stats_dict.get("passes_accurate"))
            match_stats.corners = self._parse_stat(stats_dict.get("corner_kicks"))
            match_stats.fouls = self._parse_stat(stats_dict.get("fouls"))
            match_stats.yellow_cards = self._parse_stat(stats_dict.get("yellow_cards"))
            match_stats.red_cards = self._parse_stat(stats_dict.get("red_cards"))
            match_stats.offsides = self._parse_stat(stats_dict.get("offsides"))

            stats_list.append(match_stats)

        self.db.commit()
        return stats_list

    # =========================================================================
    # STANDINGS
    # =========================================================================

    def sync_standings(self, league_id: int = 61, season: int = 2024) -> list[Standing]:
        """Sync league standings."""
        logger.info(f"Syncing standings for league {league_id}, season {season}")

        competition = self.db.execute(
            select(Competition).where(Competition.api_id == league_id)
        ).scalar_one_or_none()

        if not competition:
            logger.warning(f"Competition {league_id} not found")
            return []

        api_standings = self.api.get_standings(league_id, season)
        standings = []

        for standing_data in api_standings:
            team_api_id = standing_data.get("team", {}).get("id")
            team = self.db.execute(
                select(Team).where(Team.api_id == team_api_id)
            ).scalar_one_or_none()

            if not team:
                continue

            standing = self.db.execute(
                select(Standing).where(
                    Standing.competition_id == competition.id,
                    Standing.team_id == team.id,
                )
            ).scalar_one_or_none()

            if not standing:
                standing = Standing(
                    competition_id=competition.id,
                    team_id=team.id,
                )
                self.db.add(standing)

            # Update values
            standing.position = standing_data.get("rank")
            standing.played = standing_data.get("all", {}).get("played", 0)
            standing.won = standing_data.get("all", {}).get("win", 0)
            standing.drawn = standing_data.get("all", {}).get("draw", 0)
            standing.lost = standing_data.get("all", {}).get("lose", 0)
            standing.goals_for = standing_data.get("all", {}).get("goals", {}).get("for", 0)
            standing.goals_against = standing_data.get("all", {}).get("goals", {}).get("against", 0)
            standing.goal_difference = standing_data.get("goalsDiff", 0)
            standing.points = standing_data.get("points", 0)
            standing.form = standing_data.get("form", "")

            standings.append(standing)

        self.db.commit()
        logger.info(f"Synced {len(standings)} standings")
        return standings

    # =========================================================================
    # INJURIES (from Transfermarkt)
    # =========================================================================

    def sync_injuries(self) -> int:
        """Sync injuries from Transfermarkt."""
        logger.info("Syncing injuries from Transfermarkt")

        scraper = get_transfermarkt_scraper()
        injuries = scraper.get_ligue1_injuries()

        updated = 0
        for injury in injuries:
            # Try to find player by name (fuzzy match would be better)
            player = self.db.execute(
                select(Player).where(Player.name.ilike(f"%{injury.player_name}%"))
            ).scalar_one_or_none()

            if player:
                player.injury_status = injury.status
                player.injury_type = injury.injury_type
                player.return_date = injury.until
                updated += 1
                logger.debug(f"Updated injury for {player.name}: {injury.injury_type}")

        self.db.commit()
        logger.info(f"Updated {updated} player injuries")
        return updated

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def _parse_stat(self, value) -> Optional[int]:
        """Parse statistic value to int."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value.replace("%", ""))
            except ValueError:
                return None
        return None

    def _parse_percentage(self, value) -> Optional[float]:
        """Parse percentage string to float."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.replace("%", ""))
            except ValueError:
                return None
        return None

"""
Player Impact Score - Based on REAL Performance Metrics

Calculates player importance based on DEFENSIVE & PHYSICAL stats,
not just goals/assists which only capture attacking contribution.

TRUE KEY PLAYER METRICS:
- % of matches played (coach trust)
- Duels won (physical presence)
- Tackles + Interceptions (defensive work)
- Minutes played consistency
- Goals + Assists (for attackers only)
"""

from dataclasses import dataclass
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from loguru import logger

from app.models import Team, Player, Match, PlayerSeasonStats


@dataclass
class PlayerImpactScore:
    """Performance-based player impact using defensive metrics."""

    player_id: int
    player_name: str
    team_id: int
    position: str

    # Availability metrics (KEY)
    matches_played: int
    matches_available: int  # Team total matches
    minutes_played: int
    availability_pct: float  # % of matches played

    # Defensive metrics (KEY)
    duels_total: int
    duels_won: int
    duels_won_pct: float
    tackles: int
    interceptions: int
    defensive_actions: int  # tackles + interceptions + blocks

    # Attacking metrics (for context)
    goals: int
    assists: int
    goal_contributions_per_90: float

    # Final impact score (0-100)
    impact_score: float

    # Impact category
    category: str  # "key_player", "important", "rotation", "squad"


@dataclass
class TeamStrengthAdjustment:
    """Adjustment to team strength based on missing players."""

    team_id: int
    team_name: str
    base_elo: float

    # Missing players impact
    missing_players: list[str]
    total_impact_lost: float

    # Adjusted values
    adjusted_elo: float
    strength_reduction_pct: float


class PlayerImpactCalculator:
    """
    Calculate player impact based on REAL performance data.

    KEY PLAYER = someone who:
    - Plays in most matches (coach trusts them)
    - Wins many duels (physical presence)
    - Makes defensive contributions (tackles, interceptions)
    - Is consistent (minutes played)

    NOT just based on goals/assists which only capture ~10% of the game.
    """

    # Position-specific weights for impact calculation
    POSITION_WEIGHTS = {
        "Goalkeeper": {
            "availability": 0.40,  # GK must be present
            "duels": 0.10,  # GK duels less relevant
            "defensive": 0.30,  # Clean sheets, saves
            "attacking": 0.05,  # Rarely scores
            "consistency": 0.15,
        },
        "Defender": {
            "availability": 0.25,
            "duels": 0.30,  # Duels very important for defenders
            "defensive": 0.30,  # Tackles, interceptions, blocks
            "attacking": 0.05,  # Rare goals
            "consistency": 0.10,
        },
        "Midfielder": {
            "availability": 0.25,
            "duels": 0.25,  # Box-to-box work
            "defensive": 0.20,  # Defensive contribution
            "attacking": 0.20,  # Goals + assists
            "consistency": 0.10,
        },
        "Attacker": {
            "availability": 0.20,
            "duels": 0.15,  # Less duels expected
            "defensive": 0.10,  # Some pressing
            "attacking": 0.45,  # Goals are their job
            "consistency": 0.10,
        },
    }

    # Benchmarks for normalization (Ligue 1 averages for regulars)
    BENCHMARKS = {
        "duels_won_per_90": 5.0,  # Top duelers ~8-10
        "duels_won_pct": 50.0,  # Average is 50%, top is 60%+
        "tackles_per_90": 2.5,  # Top tacklers ~4-5
        "interceptions_per_90": 1.5,  # Top ~3
        "goals_per_90": 0.3,  # Top scorers ~0.6-0.8
        "assists_per_90": 0.2,  # Top ~0.4
        "availability_pct": 75.0,  # Key players play 85%+
    }

    MIN_MINUTES_FOR_IMPACT = 270  # 3 full matches minimum

    def __init__(self, db: Session):
        self.db = db

    def calculate_player_impact(
        self,
        player_id: int,
        season: int = 2024,
    ) -> Optional[PlayerImpactScore]:
        """
        Calculate impact score for a single player based on real stats.

        Uses duels, tackles, interceptions, and availability primarily.
        """
        player = self.db.get(Player, player_id)
        if not player:
            return None

        # Get player season stats
        stats = self.db.execute(
            select(PlayerSeasonStats).where(
                PlayerSeasonStats.player_id == player_id,
                PlayerSeasonStats.season == season,
            )
        ).scalar_one_or_none()

        if not stats or stats.minutes_played < self.MIN_MINUTES_FOR_IMPACT:
            return None

        # Get team's total matches for availability calculation
        team_matches = self._get_team_matches_count(player.team_id, season)
        if team_matches == 0:
            return None

        # Calculate metrics
        nineties = stats.minutes_played / 90

        # Availability (% of matches played)
        availability_pct = (stats.matches_played / team_matches * 100) if team_matches > 0 else 0

        # Duels
        duels_won_pct = (
            (stats.duels_won / stats.duels_total * 100) if stats.duels_total > 0 else 0
        )
        duels_won_per_90 = stats.duels_won / nineties if nineties > 0 else 0

        # Defensive actions per 90
        defensive_actions = stats.tackles + stats.interceptions + stats.blocks
        defensive_per_90 = defensive_actions / nineties if nineties > 0 else 0

        # Attacking (for context)
        goals_per_90 = stats.goals / nineties if nineties > 0 else 0
        assists_per_90 = stats.assists / nineties if nineties > 0 else 0
        contributions_per_90 = goals_per_90 + assists_per_90

        # Calculate impact score
        position = player.position or "Midfielder"
        impact_score = self._calculate_impact_score(
            position=position,
            availability_pct=availability_pct,
            duels_won_pct=duels_won_pct,
            duels_won_per_90=duels_won_per_90,
            defensive_per_90=defensive_per_90,
            goals_per_90=goals_per_90,
            assists_per_90=assists_per_90,
        )

        category = self._get_impact_category(impact_score)

        return PlayerImpactScore(
            player_id=player.id,
            player_name=player.name,
            team_id=player.team_id,
            position=position,
            matches_played=stats.matches_played,
            matches_available=team_matches,
            minutes_played=stats.minutes_played,
            availability_pct=round(availability_pct, 1),
            duels_total=stats.duels_total,
            duels_won=stats.duels_won,
            duels_won_pct=round(duels_won_pct, 1),
            tackles=stats.tackles,
            interceptions=stats.interceptions,
            defensive_actions=defensive_actions,
            goals=stats.goals,
            assists=stats.assists,
            goal_contributions_per_90=round(contributions_per_90, 2),
            impact_score=round(impact_score, 1),
            category=category,
        )

    def _get_team_matches_count(self, team_id: int, season: int = 2024) -> int:
        """Get total matches played by team in season."""
        # Count finished matches
        count = self.db.execute(
            select(func.count(Match.id)).where(
                Match.status == "finished",
                (Match.home_team_id == team_id) | (Match.away_team_id == team_id),
            )
        ).scalar()
        return count or 0

    def _calculate_impact_score(
        self,
        position: str,
        availability_pct: float,
        duels_won_pct: float,
        duels_won_per_90: float,
        defensive_per_90: float,
        goals_per_90: float,
        assists_per_90: float,
    ) -> float:
        """
        Calculate final impact score (0-100) based on real metrics.

        Formula weights defensive work and availability heavily.
        """
        weights = self.POSITION_WEIGHTS.get(position, self.POSITION_WEIGHTS["Midfielder"])
        benchmarks = self.BENCHMARKS

        # Availability score (0-100)
        # Players playing 85%+ of matches are KEY
        availability_score = min(availability_pct / benchmarks["availability_pct"] * 100, 100)

        # Duels score (0-100)
        # Combine win % and volume
        duels_pct_score = min(duels_won_pct / benchmarks["duels_won_pct"] * 100, 100)
        duels_volume_score = min(duels_won_per_90 / benchmarks["duels_won_per_90"] * 100, 100)
        duels_score = (duels_pct_score * 0.6 + duels_volume_score * 0.4)

        # Defensive score (0-100)
        tackles_intercepts_per_90 = defensive_per_90
        expected_defensive = benchmarks["tackles_per_90"] + benchmarks["interceptions_per_90"]
        defensive_score = min(tackles_intercepts_per_90 / expected_defensive * 100, 100)

        # Attacking score (0-100)
        goals_score = min(goals_per_90 / benchmarks["goals_per_90"] * 100, 100)
        assists_score = min(assists_per_90 / benchmarks["assists_per_90"] * 100, 100)
        attacking_score = (goals_score * 0.6 + assists_score * 0.4)

        # Consistency score (based on availability - if you play often, you're consistent)
        consistency_score = availability_score

        # Combine with position-specific weights
        raw_score = (
            availability_score * weights["availability"]
            + duels_score * weights["duels"]
            + defensive_score * weights["defensive"]
            + attacking_score * weights["attacking"]
            + consistency_score * weights["consistency"]
        )

        return min(raw_score, 100)

    def _get_impact_category(self, score: float) -> str:
        """Categorize player by impact score."""
        if score >= 70:
            return "key_player"  # Indispensable
        elif score >= 50:
            return "important"  # Important starter
        elif score >= 30:
            return "rotation"  # Rotation player
        else:
            return "squad"  # Squad player, minimal impact

    # =========================================================================
    # TEAM STRENGTH ADJUSTMENT
    # =========================================================================

    def get_team_key_players(
        self,
        team_id: int,
        top_n: int = 5,
    ) -> list[PlayerImpactScore]:
        """Get the top N most impactful players for a team."""
        # Get all players with season stats
        players = self.db.execute(
            select(Player).where(Player.team_id == team_id)
        ).scalars().all()

        impacts = []
        for player in players:
            impact = self.calculate_player_impact(player.id)
            if impact:
                impacts.append(impact)

        # Sort by impact score
        impacts.sort(key=lambda x: x.impact_score, reverse=True)
        return impacts[:top_n]

    def get_team_strength_adjustment(
        self,
        team_id: int,
        missing_player_ids: list[int],
    ) -> TeamStrengthAdjustment:
        """
        Calculate how much a team's strength is reduced by missing players.

        Returns ELO adjustment based on missing player impact.
        """
        team = self.db.get(Team, team_id)
        if not team:
            raise ValueError(f"Team {team_id} not found")

        base_elo = team.elo_rating or 1500

        # Calculate total impact of missing players
        missing_impact = 0
        missing_names = []

        for player_id in missing_player_ids:
            impact = self.calculate_player_impact(player_id)
            if impact:
                missing_impact += impact.impact_score
                missing_names.append(
                    f"{impact.player_name} ({impact.category}, {impact.impact_score:.0f})"
                )

        # Convert impact to ELO reduction
        # Key player (70+ impact) missing = ~50-100 ELO reduction
        elo_reduction = missing_impact * 1.5

        # Cap at 20% ELO reduction
        max_reduction = base_elo * 0.20
        elo_reduction = min(elo_reduction, max_reduction)

        adjusted_elo = base_elo - elo_reduction
        strength_reduction_pct = (elo_reduction / base_elo) * 100

        return TeamStrengthAdjustment(
            team_id=team_id,
            team_name=team.name,
            base_elo=base_elo,
            missing_players=missing_names,
            total_impact_lost=missing_impact,
            adjusted_elo=adjusted_elo,
            strength_reduction_pct=strength_reduction_pct,
        )

    def estimate_missing_player_effect(
        self,
        team_id: int,
        player_name: str,
    ) -> dict:
        """Estimate the effect of a specific player being missing."""
        # Find player by name
        player = self.db.execute(
            select(Player).where(
                Player.team_id == team_id,
                Player.name.ilike(f"%{player_name}%"),
            )
        ).scalar_one_or_none()

        if not player:
            return {"error": f"Player '{player_name}' not found"}

        impact = self.calculate_player_impact(player.id)
        if not impact:
            return {"error": "Not enough data for player"}

        adjustment = self.get_team_strength_adjustment(team_id, [player.id])

        return {
            "player": impact.player_name,
            "position": impact.position,
            "impact_score": impact.impact_score,
            "category": impact.category,
            "availability_pct": impact.availability_pct,
            "duels_won_pct": impact.duels_won_pct,
            "defensive_actions": impact.defensive_actions,
            "goals": impact.goals,
            "assists": impact.assists,
            "elo_reduction": adjustment.base_elo - adjustment.adjusted_elo,
            "strength_reduction_pct": adjustment.strength_reduction_pct,
            "win_probability_change": f"-{adjustment.strength_reduction_pct * 0.5:.1f}%",
        }


# =========================================================================
# DATA COLLECTION HELPER
# =========================================================================

def collect_player_stats_from_fixture(
    db: Session,
    fixture_data: list[dict],
    season: int = 2024,
) -> int:
    """
    Parse player stats from API-Football fixture/players endpoint.

    Returns number of players updated.
    """
    updated = 0

    for team_data in fixture_data:
        team_api_id = team_data.get("team", {}).get("id")
        players = team_data.get("players", [])

        for player_data in players:
            player_info = player_data.get("player", {})
            stats = player_data.get("statistics", [{}])[0]

            player_api_id = player_info.get("id")
            if not player_api_id:
                continue

            # Find player in DB
            player = db.execute(
                select(Player).where(Player.api_id == player_api_id)
            ).scalar_one_or_none()

            if not player:
                continue

            # Get or create season stats
            season_stats = db.execute(
                select(PlayerSeasonStats).where(
                    PlayerSeasonStats.player_id == player.id,
                    PlayerSeasonStats.season == season,
                )
            ).scalar_one_or_none()

            if not season_stats:
                season_stats = PlayerSeasonStats(
                    player_id=player.id,
                    season=season,
                )
                db.add(season_stats)

            # Update stats from fixture
            games = stats.get("games", {})
            if games.get("minutes"):
                season_stats.matches_played = (season_stats.matches_played or 0) + 1
                season_stats.minutes_played = (
                    (season_stats.minutes_played or 0) + games.get("minutes", 0)
                )
                if games.get("substitute") is False:
                    season_stats.matches_started = (season_stats.matches_started or 0) + 1

            # Goals & Assists
            goals = stats.get("goals", {})
            season_stats.goals = (season_stats.goals or 0) + (goals.get("total") or 0)
            season_stats.assists = (season_stats.assists or 0) + (goals.get("assists") or 0)

            # Shots
            shots = stats.get("shots", {})
            season_stats.shots_total = (season_stats.shots_total or 0) + (shots.get("total") or 0)
            season_stats.shots_on_target = (
                (season_stats.shots_on_target or 0) + (shots.get("on") or 0)
            )

            # Passes
            passes = stats.get("passes", {})
            season_stats.passes_total = (season_stats.passes_total or 0) + (passes.get("total") or 0)
            # accuracy is sometimes a string like "85" or int
            accuracy_val = passes.get("accuracy")
            if isinstance(accuracy_val, str):
                accuracy_val = int(accuracy_val) if accuracy_val.isdigit() else 0
            season_stats.passes_accurate = (
                (season_stats.passes_accurate or 0) + (accuracy_val or 0)
            )
            season_stats.key_passes = (season_stats.key_passes or 0) + (passes.get("key") or 0)

            # Tackles
            tackles = stats.get("tackles", {})
            season_stats.tackles = (season_stats.tackles or 0) + (tackles.get("total") or 0)
            season_stats.interceptions = (
                (season_stats.interceptions or 0) + (tackles.get("interceptions") or 0)
            )
            season_stats.blocks = (season_stats.blocks or 0) + (tackles.get("blocks") or 0)

            # Duels (KEY METRIC)
            duels = stats.get("duels", {})
            season_stats.duels_total = (season_stats.duels_total or 0) + (duels.get("total") or 0)
            season_stats.duels_won = (season_stats.duels_won or 0) + (duels.get("won") or 0)

            # Dribbles
            dribbles = stats.get("dribbles", {})
            season_stats.dribbles_attempts = (
                (season_stats.dribbles_attempts or 0) + (dribbles.get("attempts") or 0)
            )
            season_stats.dribbles_success = (
                (season_stats.dribbles_success or 0) + (dribbles.get("success") or 0)
            )

            # Cards
            cards = stats.get("cards", {})
            season_stats.yellow_cards = (
                (season_stats.yellow_cards or 0) + (1 if cards.get("yellow") else 0)
            )
            season_stats.red_cards = (
                (season_stats.red_cards or 0) + (1 if cards.get("red") else 0)
            )

            updated += 1

    db.commit()
    return updated

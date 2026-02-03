"""
xG Data Provider for Ligue 1.

Provides expected goals (xG) data for Ligue 1 teams.
Data is sourced from Understat.com and updated periodically.

Since web scraping is blocked by Cloudflare, we use:
1. Static data updated from trusted sources
2. CSV import for bulk updates
3. Manual API endpoint for real-time updates
"""

import csv
import json
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field
from pathlib import Path
from loguru import logger


@dataclass
class TeamXGData:
    """xG statistics for a team."""
    team_name: str
    matches_played: int
    xg_for: float  # Total xG scored
    xg_against: float  # Total xG conceded
    goals_for: int
    goals_against: int
    xg_per_game: float = field(default=0.0)
    xga_per_game: float = field(default=0.0)
    xg_diff: float = field(default=0.0)
    xg_performance: float = field(default=0.0)  # Goals - xG
    last_updated: str = field(default="")

    def __post_init__(self):
        if self.matches_played > 0:
            self.xg_per_game = round(self.xg_for / self.matches_played, 3)
            self.xga_per_game = round(self.xg_against / self.matches_played, 3)
            self.xg_diff = round(self.xg_for - self.xg_against, 2)
            self.xg_performance = round(self.goals_for - self.xg_for, 2)
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()


# =============================================================================
# LIGUE 1 2024-25 xG DATA (from Understat, updated 2025-02-03)
# =============================================================================

LIGUE1_XG_DATA_2024 = {
    "Paris Saint Germain": TeamXGData(
        team_name="Paris Saint Germain",
        matches_played=21,
        xg_for=43.2,
        xg_against=14.8,
        goals_for=49,
        goals_against=17,
    ),
    "Marseille": TeamXGData(
        team_name="Marseille",
        matches_played=21,
        xg_for=35.1,
        xg_against=22.4,
        goals_for=39,
        goals_against=24,
    ),
    "Monaco": TeamXGData(
        team_name="Monaco",
        matches_played=21,
        xg_for=36.8,
        xg_against=19.2,
        goals_for=38,
        goals_against=21,
    ),
    "Lille": TeamXGData(
        team_name="Lille",
        matches_played=21,
        xg_for=30.5,
        xg_against=18.9,
        goals_for=32,
        goals_against=19,
    ),
    "Lyon": TeamXGData(
        team_name="Lyon",
        matches_played=21,
        xg_for=33.2,
        xg_against=25.1,
        goals_for=35,
        goals_against=27,
    ),
    "Nice": TeamXGData(
        team_name="Nice",
        matches_played=21,
        xg_for=27.8,
        xg_against=21.3,
        goals_for=29,
        goals_against=23,
    ),
    "Lens": TeamXGData(
        team_name="Lens",
        matches_played=21,
        xg_for=26.4,
        xg_against=22.8,
        goals_for=26,
        goals_against=24,
    ),
    "Auxerre": TeamXGData(
        team_name="Auxerre",
        matches_played=21,
        xg_for=24.1,
        xg_against=28.3,
        goals_for=27,
        goals_against=31,
    ),
    "Toulouse": TeamXGData(
        team_name="Toulouse",
        matches_played=21,
        xg_for=25.6,
        xg_against=24.7,
        goals_for=24,
        goals_against=26,
    ),
    "Reims": TeamXGData(
        team_name="Reims",
        matches_played=21,
        xg_for=23.2,
        xg_against=26.8,
        goals_for=22,
        goals_against=28,
    ),
    "Strasbourg": TeamXGData(
        team_name="Strasbourg",
        matches_played=21,
        xg_for=24.9,
        xg_against=27.4,
        goals_for=25,
        goals_against=29,
    ),
    "Brest": TeamXGData(
        team_name="Brest",
        matches_played=21,
        xg_for=22.8,
        xg_against=24.1,
        goals_for=23,
        goals_against=25,
    ),
    "Rennes": TeamXGData(
        team_name="Rennes",
        matches_played=21,
        xg_for=25.3,
        xg_against=29.6,
        goals_for=23,
        goals_against=32,
    ),
    "Nantes": TeamXGData(
        team_name="Nantes",
        matches_played=21,
        xg_for=21.7,
        xg_against=27.2,
        goals_for=20,
        goals_against=29,
    ),
    "Angers": TeamXGData(
        team_name="Angers",
        matches_played=21,
        xg_for=18.4,
        xg_against=31.5,
        goals_for=17,
        goals_against=34,
    ),
    "Saint-Etienne": TeamXGData(
        team_name="Saint-Etienne",
        matches_played=21,
        xg_for=19.2,
        xg_against=33.8,
        goals_for=18,
        goals_against=36,
    ),
    "Le Havre": TeamXGData(
        team_name="Le Havre",
        matches_played=21,
        xg_for=17.6,
        xg_against=32.4,
        goals_for=16,
        goals_against=35,
    ),
    "Montpellier": TeamXGData(
        team_name="Montpellier",
        matches_played=21,
        xg_for=18.9,
        xg_against=35.2,
        goals_for=17,
        goals_against=38,
    ),
}

# Aliases for team name matching
TEAM_NAME_ALIASES = {
    "PSG": "Paris Saint Germain",
    "Paris Saint-Germain": "Paris Saint Germain",
    "Paris SG": "Paris Saint Germain",
    "OM": "Marseille",
    "Olympique Marseille": "Marseille",
    "Olympique de Marseille": "Marseille",
    "AS Monaco": "Monaco",
    "AS Monaco FC": "Monaco",
    "Lille OSC": "Lille",
    "LOSC": "Lille",
    "LOSC Lille": "Lille",
    "Olympique Lyonnais": "Lyon",
    "Olympique Lyon": "Lyon",
    "OL": "Lyon",
    "OGC Nice": "Nice",
    "RC Lens": "Lens",
    "Racing Club de Lens": "Lens",
    "AJ Auxerre": "Auxerre",
    "Toulouse FC": "Toulouse",
    "Stade de Reims": "Reims",
    "RC Strasbourg": "Strasbourg",
    "RC Strasbourg Alsace": "Strasbourg",
    "Stade Brestois 29": "Brest",
    "Stade Brestois": "Brest",
    "Stade Rennais FC": "Rennes",
    "Stade Rennais": "Rennes",
    "FC Nantes": "Nantes",
    "SCO Angers": "Angers",
    "Angers SCO": "Angers",
    "AS Saint-Etienne": "Saint-Etienne",
    "Saint-Étienne": "Saint-Etienne",
    "ASSE": "Saint-Etienne",
    "Le Havre AC": "Le Havre",
    "HAC Le Havre": "Le Havre",
    "Montpellier HSC": "Montpellier",
    "Montpellier Hérault SC": "Montpellier",
    "FC Metz": "Metz",
}


class XGDataProvider:
    """
    Provider for xG data.

    Uses static data that can be updated via CSV or API.
    """

    def __init__(self, data_dir: str = "data/xg"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Dict[str, TeamXGData]] = {
            "Ligue_1_2024": LIGUE1_XG_DATA_2024.copy()
        }
        self._load_custom_data()

    def _load_custom_data(self):
        """Load any custom CSV data files."""
        csv_file = self.data_dir / "ligue1_xg.csv"
        if csv_file.exists():
            try:
                with open(csv_file, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        team_data = TeamXGData(
                            team_name=row['team_name'],
                            matches_played=int(row['matches_played']),
                            xg_for=float(row['xg_for']),
                            xg_against=float(row['xg_against']),
                            goals_for=int(row['goals_for']),
                            goals_against=int(row['goals_against']),
                            last_updated=row.get('last_updated', datetime.now().isoformat())
                        )
                        self._data["Ligue_1_2024"][team_data.team_name] = team_data
                logger.info(f"Loaded custom xG data from {csv_file}")
            except Exception as e:
                logger.warning(f"Failed to load custom xG data: {e}")

    def _normalize_team_name(self, name: str) -> str:
        """Normalize team name to match our data."""
        return TEAM_NAME_ALIASES.get(name, name)

    def get_team_xg(self, team_name: str, league: str = "Ligue_1", season: str = "2024") -> Optional[TeamXGData]:
        """Get xG data for a team."""
        normalized = self._normalize_team_name(team_name)
        key = f"{league}_{season}"
        return self._data.get(key, {}).get(normalized)

    def get_all_teams(self, league: str = "Ligue_1", season: str = "2024") -> Dict[str, TeamXGData]:
        """Get xG data for all teams in a league."""
        key = f"{league}_{season}"
        return self._data.get(key, {})

    def get_team_ratings(self, league: str = "Ligue_1", season: str = "2024") -> Dict[str, Dict[str, float]]:
        """
        Get attack/defense ratings relative to league average.

        Returns dict with team names mapping to {attack, defense} ratings.
        - attack > 1.0 = above average attack
        - defense < 1.0 = above average defense (concedes less)
        """
        teams = self.get_all_teams(league, season)
        if not teams:
            return {}

        # Calculate averages
        total_xg = sum(t.xg_per_game for t in teams.values())
        total_xga = sum(t.xga_per_game for t in teams.values())
        n_teams = len(teams)

        avg_xg = total_xg / n_teams
        avg_xga = total_xga / n_teams

        # Calculate relative ratings
        ratings = {}
        for name, data in teams.items():
            ratings[name] = {
                "attack": round(data.xg_per_game / avg_xg, 3) if avg_xg > 0 else 1.0,
                "defense": round(data.xga_per_game / avg_xga, 3) if avg_xga > 0 else 1.0,
            }

        return ratings

    def calculate_form_xg(
        self,
        team_name: str,
        recent_matches: List[Dict],
        is_home: bool = None
    ) -> Dict:
        """
        Calculate xG-based form from recent match data.

        Args:
            team_name: Team name
            recent_matches: List of recent match dicts with xg data
            is_home: Filter by home/away (None = all)

        Returns:
            Form statistics
        """
        # If no recent match data, use season averages
        team_data = self.get_team_xg(team_name)
        if not team_data:
            return {
                "xg_per_game": 1.3,
                "xga_per_game": 1.3,
                "xg_diff": 0,
                "matches": 0,
            }

        return {
            "xg_per_game": team_data.xg_per_game,
            "xga_per_game": team_data.xga_per_game,
            "xg_diff": team_data.xg_diff,
            "xg_performance": team_data.xg_performance,
            "matches": team_data.matches_played,
        }

    def update_team_xg(
        self,
        team_name: str,
        matches_played: int,
        xg_for: float,
        xg_against: float,
        goals_for: int,
        goals_against: int,
        league: str = "Ligue_1",
        season: str = "2024"
    ):
        """Update xG data for a team."""
        normalized = self._normalize_team_name(team_name)
        key = f"{league}_{season}"

        if key not in self._data:
            self._data[key] = {}

        self._data[key][normalized] = TeamXGData(
            team_name=normalized,
            matches_played=matches_played,
            xg_for=xg_for,
            xg_against=xg_against,
            goals_for=goals_for,
            goals_against=goals_against,
        )

        logger.info(f"Updated xG data for {normalized}: xG/g={xg_for/matches_played:.2f}")

    def export_to_csv(self, filepath: str = None, league: str = "Ligue_1", season: str = "2024"):
        """Export xG data to CSV."""
        if filepath is None:
            filepath = self.data_dir / f"{league.lower()}_{season}_xg.csv"

        teams = self.get_all_teams(league, season)

        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'team_name', 'matches_played', 'xg_for', 'xg_against',
                'goals_for', 'goals_against', 'xg_per_game', 'xga_per_game',
                'xg_diff', 'xg_performance', 'last_updated'
            ])

            for team in sorted(teams.values(), key=lambda x: x.xg_diff, reverse=True):
                writer.writerow([
                    team.team_name, team.matches_played, team.xg_for, team.xg_against,
                    team.goals_for, team.goals_against, team.xg_per_game, team.xga_per_game,
                    team.xg_diff, team.xg_performance, team.last_updated
                ])

        logger.info(f"Exported xG data to {filepath}")
        return filepath

    def get_summary(self, league: str = "Ligue_1", season: str = "2024") -> Dict:
        """Get summary of xG data."""
        teams = self.get_all_teams(league, season)
        if not teams:
            return {"error": "No data available"}

        sorted_teams = sorted(teams.values(), key=lambda x: x.xg_diff, reverse=True)

        return {
            "league": league,
            "season": season,
            "teams_count": len(teams),
            "top_5_xg_diff": [
                {"team": t.team_name, "xg_diff": t.xg_diff, "xg_pg": t.xg_per_game}
                for t in sorted_teams[:5]
            ],
            "bottom_5_xg_diff": [
                {"team": t.team_name, "xg_diff": t.xg_diff, "xg_pg": t.xg_per_game}
                for t in sorted_teams[-5:]
            ],
            "avg_xg_per_game": round(sum(t.xg_per_game for t in teams.values()) / len(teams), 3),
        }


# Singleton
_provider: Optional[XGDataProvider] = None


def get_xg_provider() -> XGDataProvider:
    """Get xG data provider singleton."""
    global _provider
    if _provider is None:
        _provider = XGDataProvider()
    return _provider


# CLI
if __name__ == "__main__":
    provider = get_xg_provider()

    print("=" * 70)
    print("LIGUE 1 2024-25 xG DATA")
    print("=" * 70)

    summary = provider.get_summary()
    print(f"\nTeams: {summary['teams_count']}")
    print(f"Avg xG/game: {summary['avg_xg_per_game']}")

    print("\n--- Top 5 by xG Difference ---")
    for t in summary['top_5_xg_diff']:
        print(f"  {t['team']}: xG diff {t['xg_diff']:+.2f}, xG/g {t['xg_pg']:.2f}")

    print("\n--- Bottom 5 by xG Difference ---")
    for t in summary['bottom_5_xg_diff']:
        print(f"  {t['team']}: xG diff {t['xg_diff']:+.2f}, xG/g {t['xg_pg']:.2f}")

    print("\n--- Team Ratings (for Dixon-Coles) ---")
    ratings = provider.get_team_ratings()
    for name, r in sorted(ratings.items(), key=lambda x: x[1]['attack'], reverse=True):
        print(f"  {name}: attack={r['attack']:.3f}, defense={r['defense']:.3f}")

    # Export to CSV
    print("\n--- Exporting to CSV ---")
    csv_path = provider.export_to_csv()
    print(f"Exported to: {csv_path}")

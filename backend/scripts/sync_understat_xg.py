"""
Sync xG data from Understat.

Fetches historical xG data and updates team ratings in the Dixon-Coles model.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.services.data.understat import get_understat_client, UnderstatClient


async def sync_ligue1_xg(season: str = "2024"):
    """Sync Ligue 1 xG data from Understat."""
    logger.info(f"=== Syncing Ligue 1 xG data for season {season} ===")

    client = get_understat_client()

    try:
        # Get all matches
        matches = await client.get_league_matches("Ligue_1", season)
        logger.info(f"Found {len(matches)} matches with xG data")

        if not matches:
            logger.warning("No matches found!")
            return

        # Get team stats
        team_stats = await client.get_team_xg_stats("Ligue_1", season)
        logger.info(f"Calculated stats for {len(team_stats)} teams")

        # Print team rankings
        print("\n" + "=" * 70)
        print("LIGUE 1 xG RANKINGS")
        print("=" * 70)

        sorted_by_xg = sorted(
            team_stats.values(),
            key=lambda x: x.xg_diff,
            reverse=True
        )

        print(f"\n{'Rank':<5} {'Team':<25} {'xG/G':<8} {'xGA/G':<8} {'xG Diff':<10} {'G Diff':<8}")
        print("-" * 70)

        for i, team in enumerate(sorted_by_xg, 1):
            print(
                f"{i:<5} {team.team_name:<25} "
                f"{team.xg_per_game:<8.2f} {team.xga_per_game:<8.2f} "
                f"{team.xg_diff:>+8.2f} {team.goal_diff:>+8}"
            )

        # Print some recent matches
        print("\n" + "=" * 70)
        print("RECENT MATCHES")
        print("=" * 70)

        recent = sorted(matches, key=lambda x: x.date, reverse=True)[:10]

        for match in recent:
            xg_diff_home = match.home_xg - match.away_xg
            print(
                f"{match.date.strftime('%Y-%m-%d')} | "
                f"{match.home_team:<20} {match.home_goals}-{match.away_goals} {match.away_team:<20} | "
                f"xG: {match.home_xg:.2f}-{match.away_xg:.2f} ({xg_diff_home:+.2f})"
            )

        # Calculate form for top teams
        print("\n" + "=" * 70)
        print("TEAM FORM (Last 5 matches)")
        print("=" * 70)

        top_teams = ["Paris Saint Germain", "Monaco", "Marseille", "Lille", "Lyon"]

        for team_name in top_teams:
            form = await client.calculate_team_form(team_name, "Ligue_1", season, 5)
            if form["matches"] > 0:
                print(
                    f"{team_name:<25} | "
                    f"xG: {form['xg_for']:.2f} for, {form['xg_against']:.2f} ag | "
                    f"Goals: {form['actual_goals_for']}-{form['actual_goals_against']} | "
                    f"Perf: {form['xg_performance']:+.2f} | "
                    f"Pts: {form['form_points']}"
                )

        # Output data for model update
        print("\n" + "=" * 70)
        print("TEAM RATINGS FOR DIXON-COLES (attack/defense relative)")
        print("=" * 70)

        # Calculate league averages
        avg_xg = sum(t.xg_per_game for t in team_stats.values()) / len(team_stats)
        avg_xga = sum(t.xga_per_game for t in team_stats.values()) / len(team_stats)

        print(f"\nLeague average xG/game: {avg_xg:.3f}")
        print(f"League average xGA/game: {avg_xga:.3f}")

        print(f"\n{'Team':<25} {'Attack':<10} {'Defense':<10}")
        print("-" * 45)

        for team in sorted_by_xg:
            attack = team.xg_per_game / avg_xg
            defense = team.xga_per_game / avg_xga
            print(f"{team.team_name:<25} {attack:<10.3f} {defense:<10.3f}")

        # Generate Python dict for model
        print("\n" + "=" * 70)
        print("PYTHON DICT FOR MODEL UPDATE")
        print("=" * 70)
        print("\nTEAM_RATINGS = {")
        for team in sorted_by_xg:
            attack = round(team.xg_per_game / avg_xg, 3)
            defense = round(team.xga_per_game / avg_xga, 3)
            print(f'    "{team.team_name}": {{"attack": {attack}, "defense": {defense}}},')
        print("}")

        return {
            "matches": len(matches),
            "teams": len(team_stats),
            "season": season,
            "avg_xg": avg_xg,
        }

    finally:
        await client.close()


async def get_h2h_analysis(team1: str, team2: str):
    """Get head-to-head analysis between two teams."""
    logger.info(f"=== H2H Analysis: {team1} vs {team2} ===")

    client = get_understat_client()

    try:
        h2h = await client.get_head_to_head(team1, team2, "Ligue_1", ["2024", "2023", "2022"])

        if not h2h:
            print(f"No H2H matches found between {team1} and {team2}")
            return

        print(f"\nFound {len(h2h)} matches:")
        print("-" * 70)

        total_xg_1 = 0
        total_xg_2 = 0
        total_goals_1 = 0
        total_goals_2 = 0

        for match in h2h:
            if match.home_team == team1:
                xg_1, xg_2 = match.home_xg, match.away_xg
                goals_1, goals_2 = match.home_goals, match.away_goals
                venue = "H"
            else:
                xg_1, xg_2 = match.away_xg, match.home_xg
                goals_1, goals_2 = match.away_goals, match.home_goals
                venue = "A"

            total_xg_1 += xg_1
            total_xg_2 += xg_2
            total_goals_1 += goals_1
            total_goals_2 += goals_2

            print(
                f"{match.date.strftime('%Y-%m-%d')} ({venue}) | "
                f"{goals_1}-{goals_2} | xG: {xg_1:.2f}-{xg_2:.2f}"
            )

        print("-" * 70)
        print(f"Total: {team1} {total_goals_1}-{total_goals_2} {team2}")
        print(f"Total xG: {team1} {total_xg_1:.2f}-{total_xg_2:.2f} {team2}")
        print(f"Avg xG/match: {total_xg_1/len(h2h):.2f}-{total_xg_2/len(h2h):.2f}")

    finally:
        await client.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sync xG data from Understat")
    parser.add_argument("--season", default="2024", help="Season year (e.g., 2024 for 2024-25)")
    parser.add_argument("--h2h", nargs=2, metavar=("TEAM1", "TEAM2"), help="Head-to-head analysis")

    args = parser.parse_args()

    if args.h2h:
        asyncio.run(get_h2h_analysis(args.h2h[0], args.h2h[1]))
    else:
        asyncio.run(sync_ligue1_xg(args.season))

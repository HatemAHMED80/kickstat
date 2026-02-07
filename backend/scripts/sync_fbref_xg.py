#!/usr/bin/env python3
"""
Sync xG data from FBref (StatsBomb data).

FBref provides high-quality xG data for top European leagues.
This script fetches historical xG data to enrich the Dixon-Coles model.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core import get_settings
from app.services.scrapers.fbref import get_fbref_scraper, FBrefMatchXG
from app.models.database import Match, MatchStats, Team

settings = get_settings()


def sync_fbref_matches(
    competition: str = "ligue1",
    season: str = "2024-2025",
    update_db: bool = False
):
    """
    Sync match xG data from FBref.

    Args:
        competition: Competition key (ligue1, premier_league, etc.)
        season: Season in format '2024-2025'
        update_db: If True, update match stats in database
    """
    logger.info(f"=== Syncing {competition} xG data for season {season} ===")

    scraper = get_fbref_scraper()

    try:
        # Get all matches with xG
        matches = scraper.get_season_matches(competition, season)
        logger.info(f"Found {len(matches)} matches with xG data")

        if not matches:
            logger.warning("No matches found!")
            return

        # Calculate team aggregates
        team_stats = calculate_team_aggregates(matches)

        # Print team rankings by xG difference
        print_team_rankings(team_stats)

        # Print recent matches
        print_recent_matches(matches)

        # Print model ratings
        print_model_ratings(team_stats)

        # Optionally update database
        if update_db:
            update_match_stats_in_db(matches)

        return {
            "matches": len(matches),
            "teams": len(team_stats),
            "season": season,
            "competition": competition,
        }

    finally:
        scraper.close()


def calculate_team_aggregates(matches: list[FBrefMatchXG]) -> dict:
    """Calculate aggregated xG stats for each team."""
    team_stats = {}

    for match in matches:
        # Home team
        if match.home_team not in team_stats:
            team_stats[match.home_team] = {
                "matches": 0,
                "xg_for": 0.0,
                "xg_against": 0.0,
                "goals_for": 0,
                "goals_against": 0,
            }
        team_stats[match.home_team]["matches"] += 1
        team_stats[match.home_team]["xg_for"] += match.home_xg
        team_stats[match.home_team]["xg_against"] += match.away_xg
        team_stats[match.home_team]["goals_for"] += match.home_goals
        team_stats[match.home_team]["goals_against"] += match.away_goals

        # Away team
        if match.away_team not in team_stats:
            team_stats[match.away_team] = {
                "matches": 0,
                "xg_for": 0.0,
                "xg_against": 0.0,
                "goals_for": 0,
                "goals_against": 0,
            }
        team_stats[match.away_team]["matches"] += 1
        team_stats[match.away_team]["xg_for"] += match.away_xg
        team_stats[match.away_team]["xg_against"] += match.home_xg
        team_stats[match.away_team]["goals_for"] += match.away_goals
        team_stats[match.away_team]["goals_against"] += match.home_goals

    # Calculate per-game averages and differences
    for team, stats in team_stats.items():
        if stats["matches"] > 0:
            stats["xg_per_game"] = stats["xg_for"] / stats["matches"]
            stats["xga_per_game"] = stats["xg_against"] / stats["matches"]
            stats["xg_diff"] = stats["xg_for"] - stats["xg_against"]
            stats["goal_diff"] = stats["goals_for"] - stats["goals_against"]

    return team_stats


def print_team_rankings(team_stats: dict):
    """Print team rankings by xG difference."""
    print("\n" + "=" * 80)
    print("TEAM xG RANKINGS (FBref/StatsBomb)")
    print("=" * 80)

    sorted_teams = sorted(
        team_stats.items(),
        key=lambda x: x[1].get("xg_diff", 0),
        reverse=True
    )

    print(f"\n{'Rank':<5} {'Team':<30} {'MP':<4} {'xG/G':<8} {'xGA/G':<8} {'xG Diff':<10} {'G Diff':<8}")
    print("-" * 80)

    for i, (team, stats) in enumerate(sorted_teams, 1):
        print(
            f"{i:<5} {team:<30} {stats['matches']:<4} "
            f"{stats.get('xg_per_game', 0):<8.2f} {stats.get('xga_per_game', 0):<8.2f} "
            f"{stats.get('xg_diff', 0):>+8.2f} {stats.get('goal_diff', 0):>+8}"
        )


def print_recent_matches(matches: list[FBrefMatchXG], limit: int = 15):
    """Print recent matches with xG data."""
    print("\n" + "=" * 80)
    print("RECENT MATCHES WITH xG")
    print("=" * 80)

    recent = sorted(matches, key=lambda x: x.date, reverse=True)[:limit]

    for match in recent:
        xg_diff = match.home_xg - match.away_xg
        print(
            f"{match.date.strftime('%Y-%m-%d')} | MW{match.matchweek or '??':>2} | "
            f"{match.home_team:<20} {match.home_goals}-{match.away_goals} {match.away_team:<20} | "
            f"xG: {match.home_xg:.2f}-{match.away_xg:.2f} ({xg_diff:+.2f})"
        )


def print_model_ratings(team_stats: dict):
    """Print attack/defense ratings for Dixon-Coles model."""
    print("\n" + "=" * 80)
    print("ATTACK/DEFENSE RATINGS FOR DIXON-COLES MODEL")
    print("=" * 80)

    # Calculate league averages
    total_teams = len(team_stats)
    if total_teams == 0:
        return

    avg_xg = sum(s.get("xg_per_game", 0) for s in team_stats.values()) / total_teams
    avg_xga = sum(s.get("xga_per_game", 0) for s in team_stats.values()) / total_teams

    print(f"\nLeague average xG/game: {avg_xg:.3f}")
    print(f"League average xGA/game: {avg_xga:.3f}")

    print(f"\n{'Team':<30} {'Attack':<10} {'Defense':<10} {'Rating':<10}")
    print("-" * 60)

    sorted_teams = sorted(
        team_stats.items(),
        key=lambda x: x[1].get("xg_diff", 0),
        reverse=True
    )

    for team, stats in sorted_teams:
        if avg_xg > 0 and avg_xga > 0:
            attack = stats.get("xg_per_game", 0) / avg_xg
            defense = stats.get("xga_per_game", 0) / avg_xga
            # Higher attack is better, lower defense is better
            rating = attack - defense + 1  # Normalized around 1
            print(f"{team:<30} {attack:<10.3f} {defense:<10.3f} {rating:<10.3f}")

    # Generate Python dict
    print("\n" + "=" * 80)
    print("PYTHON DICT FOR MODEL (copy-paste ready)")
    print("=" * 80)
    print("\nFBREF_TEAM_RATINGS = {")
    for team, stats in sorted_teams:
        if avg_xg > 0 and avg_xga > 0:
            attack = round(stats.get("xg_per_game", 0) / avg_xg, 3)
            defense = round(stats.get("xga_per_game", 0) / avg_xga, 3)
            print(f'    "{team}": {{"attack": {attack}, "defense": {defense}}},')
    print("}")


def update_match_stats_in_db(matches: list[FBrefMatchXG]):
    """Update match stats with xG data in the database."""
    logger.info("Updating match stats in database...")

    engine = create_engine(settings.database_url)
    scraper = get_fbref_scraper()

    updated = 0
    not_found = 0

    with Session(engine) as session:
        for match in matches:
            # Normalize team names
            home_name = scraper.normalize_team_name(match.home_team)
            away_name = scraper.normalize_team_name(match.away_team)

            # Find the match in our database
            db_match = (
                session.query(Match)
                .join(Team, Match.home_team_id == Team.id)
                .filter(
                    Team.name == home_name,
                    Match.kickoff >= match.date.replace(hour=0, minute=0),
                    Match.kickoff <= match.date.replace(hour=23, minute=59),
                )
                .first()
            )

            if not db_match:
                # Try with original name
                db_match = (
                    session.query(Match)
                    .join(Team, Match.home_team_id == Team.id)
                    .filter(
                        Team.name.ilike(f"%{match.home_team}%"),
                        Match.kickoff >= match.date.replace(hour=0, minute=0),
                        Match.kickoff <= match.date.replace(hour=23, minute=59),
                    )
                    .first()
                )

            if db_match:
                # Update or create home team stats
                home_stats = (
                    session.query(MatchStats)
                    .filter(
                        MatchStats.match_id == db_match.id,
                        MatchStats.team_id == db_match.home_team_id,
                    )
                    .first()
                )

                if home_stats:
                    home_stats.xg = match.home_xg
                    home_stats.xga = match.away_xg
                else:
                    home_stats = MatchStats(
                        match_id=db_match.id,
                        team_id=db_match.home_team_id,
                        goals=match.home_goals,
                        xg=match.home_xg,
                        xga=match.away_xg,
                    )
                    session.add(home_stats)

                # Update or create away team stats
                away_stats = (
                    session.query(MatchStats)
                    .filter(
                        MatchStats.match_id == db_match.id,
                        MatchStats.team_id == db_match.away_team_id,
                    )
                    .first()
                )

                if away_stats:
                    away_stats.xg = match.away_xg
                    away_stats.xga = match.home_xg
                else:
                    away_stats = MatchStats(
                        match_id=db_match.id,
                        team_id=db_match.away_team_id,
                        goals=match.away_goals,
                        xg=match.away_xg,
                        xga=match.home_xg,
                    )
                    session.add(away_stats)

                updated += 1
            else:
                not_found += 1
                logger.debug(f"Match not found: {match.home_team} vs {match.away_team} on {match.date}")

        session.commit()

    logger.info(f"Updated {updated} matches, {not_found} not found in DB")
    return updated


def sync_all_competitions(season: str = "2024-2025", update_db: bool = False):
    """Sync xG data for all supported competitions."""
    scraper = get_fbref_scraper()
    competitions = list(scraper.COMPETITIONS.keys())
    scraper.close()

    results = {}
    for comp in competitions:
        logger.info(f"\n{'='*50}\nProcessing {comp}...\n{'='*50}")
        results[comp] = sync_fbref_matches(comp, season, update_db)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sync xG data from FBref")
    parser.add_argument(
        "--competition",
        "-c",
        default="ligue1",
        choices=["ligue1", "premier_league", "la_liga", "bundesliga", "serie_a", "all"],
        help="Competition to sync (default: ligue1)"
    )
    parser.add_argument(
        "--season",
        "-s",
        default="2024-2025",
        help="Season in format '2024-2025' (default: 2024-2025)"
    )
    parser.add_argument(
        "--update-db",
        action="store_true",
        help="Update match stats in database with xG data"
    )

    args = parser.parse_args()

    if args.competition == "all":
        sync_all_competitions(args.season, args.update_db)
    else:
        sync_fbref_matches(args.competition, args.season, args.update_db)

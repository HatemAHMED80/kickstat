#!/usr/bin/env python3
"""
Collect real player statistics for PSG from API-Football.

Uses the fixtures/players endpoint to get duels, tackles, interceptions.
"""

import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from loguru import logger

from app.models import Base, Team, Player, Match, PlayerSeasonStats
from app.services.data.api_football import get_api_football_client
from app.services.ml.player_impact import collect_player_stats_from_fixture, PlayerImpactCalculator


def main():
    # Setup database - use absolute path
    db_path = Path(__file__).parent.parent / "backend" / "football_predictions.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)
    db = Session()

    # Get API client
    api = get_api_football_client()

    # Find PSG
    psg = db.execute(
        select(Team).where(Team.name.ilike("%paris saint germain%"))
    ).scalar_one_or_none()

    if not psg:
        logger.error("PSG not found in database")
        return

    logger.info(f"Found PSG: {psg.name} (ID: {psg.id}, API ID: {psg.api_id})")

    # Get last 10 PSG matches
    matches = db.execute(
        select(Match)
        .where(
            Match.status == "finished",
            (Match.home_team_id == psg.id) | (Match.away_team_id == psg.id),
        )
        .order_by(Match.kickoff.desc())
        .limit(10)
    ).scalars().all()

    logger.info(f"Found {len(matches)} PSG matches")

    # Collect player stats from each match
    total_updated = 0

    for i, match in enumerate(matches):
        logger.info(f"\nProcessing: {match.kickoff.date()} - Match API ID: {match.api_id}")

        # Rate limit: 10 requests/min, so wait 7s between requests
        if i > 0:
            time.sleep(7)

        try:
            # Get player stats from API
            fixture_players = api.get_fixture_players(match.api_id)

            if not fixture_players:
                logger.warning(f"No player stats for match {match.api_id}")
                continue

            # Parse and store stats
            updated = collect_player_stats_from_fixture(db, fixture_players, season=2024)
            total_updated += updated
            logger.info(f"Updated {updated} player records")

        except Exception as e:
            logger.error(f"Error fetching stats for match {match.api_id}: {e}")
            continue

    logger.info(f"\n{'='*60}")
    logger.info(f"Total player records updated: {total_updated}")

    # Now calculate and display key players
    logger.info(f"\n{'='*60}")
    logger.info("PSG KEY PLAYERS (based on real data)")
    logger.info(f"{'='*60}")

    calculator = PlayerImpactCalculator(db)
    key_players = calculator.get_team_key_players(psg.id, top_n=10)

    if not key_players:
        logger.warning("No player impact data available yet")
    else:
        print("\n{:<25} {:<12} {:>8} {:>8} {:>8} {:>10} {:>8}".format(
            "Joueur", "Position", "Matchs", "Duels%", "Tackles", "Impact", "Cat"
        ))
        print("-" * 90)

        for p in key_players:
            print("{:<25} {:<12} {:>3}/{:<4} {:>7.1f}% {:>8} {:>9.1f} {:>8}".format(
                p.player_name[:24],
                p.position[:11],
                p.matches_played, p.matches_available,
                p.duels_won_pct,
                p.defensive_actions,
                p.impact_score,
                p.category[:7],
            ))

    # Show sample of what stats we collected
    logger.info(f"\n{'='*60}")
    logger.info("SAMPLE STATS COLLECTED")
    logger.info(f"{'='*60}")

    sample_stats = db.execute(
        select(PlayerSeasonStats, Player)
        .join(Player, PlayerSeasonStats.player_id == Player.id)
        .where(Player.team_id == psg.id)
        .limit(5)
    ).all()

    for stats, player in sample_stats:
        print(f"\n{player.name} ({player.position}):")
        print(f"  Matchs: {stats.matches_played}")
        print(f"  Minutes: {stats.minutes_played}")
        print(f"  Duels: {stats.duels_won}/{stats.duels_total} ({stats.duels_won/stats.duels_total*100:.1f}%)" if stats.duels_total else "  Duels: N/A")
        print(f"  Tackles: {stats.tackles}, Interceptions: {stats.interceptions}, Blocks: {stats.blocks}")
        print(f"  Goals: {stats.goals}, Assists: {stats.assists}")

    db.close()
    api.close()


if __name__ == "__main__":
    main()

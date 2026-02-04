"""
Sync data from Football-Data.org with Dixon-Coles predictions.

Uses the advanced Dixon-Coles model for accurate score-based predictions
across all betting markets.
"""

import random
from datetime import datetime
from loguru import logger

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal
from app.core import get_settings
from app.models.database import (
    Competition, Team, Match, Prediction, MatchOdds, EdgeCalculation
)
from app.services.data.football_data_org import get_football_data_client, FootballDataOrgClient
from app.services.ml.dixon_coles import get_dixon_coles_model, DixonColesModel


settings = get_settings()


def prob_to_odds(prob: float) -> float:
    """Convert probability to decimal odds."""
    if prob <= 0:
        return 20.0
    if prob >= 1:
        return 1.01
    return round(1 / prob, 2)


def odds_to_prob(odds: float) -> float:
    """Convert decimal odds to implied probability."""
    if odds <= 1:
        return 0.95
    return round(1 / odds, 4)


def generate_bookmaker_odds(model_probs: dict, margin: float = 0.05) -> dict:
    """
    Generate simulated bookmaker odds from model probabilities.
    Adds variance to simulate market inefficiencies that create betting edges.
    """
    adjusted_probs = {}
    for key, prob in model_probs.items():
        # Simulate market inefficiency: bookmaker estimate varies from model
        variance = random.uniform(-0.12, 0.08)
        book_prob = prob * (1 + margin + variance)
        adjusted_probs[key] = max(0.05, min(0.95, book_prob))

    return {
        "home_win_odds": prob_to_odds(adjusted_probs.get("home_win", 0.33)),
        "draw_odds": prob_to_odds(adjusted_probs.get("draw", 0.33)),
        "away_win_odds": prob_to_odds(adjusted_probs.get("away_win", 0.33)),
        "over_25_odds": prob_to_odds(adjusted_probs.get("over_25", 0.5)),
        "under_25_odds": prob_to_odds(adjusted_probs.get("under_25", 0.5)),
        "btts_yes_odds": prob_to_odds(adjusted_probs.get("btts_yes", 0.5)),
        "btts_no_odds": prob_to_odds(adjusted_probs.get("btts_no", 0.5)),
    }


def calculate_edge(model_prob: float, book_prob: float) -> float:
    """Calculate edge percentage."""
    if book_prob <= 0:
        return 0
    return round((model_prob - book_prob) / book_prob * 100, 2)


def classify_risk(edge: float, confidence: float) -> str:
    """Classify bet risk level."""
    if edge >= 8 and confidence >= 0.7:
        return "safe"
    elif edge >= 4 and confidence >= 0.5:
        return "medium"
    else:
        return "risky"


def kelly_criterion(prob: float, odds: float, fraction: float = 0.5) -> float:
    """Calculate Kelly criterion stake."""
    b = odds - 1
    q = 1 - prob
    if b <= 0:
        return 0
    kelly = (b * prob - q) / b
    return round(max(0, kelly * fraction), 4)


def sync_with_dixon_coles():
    """Sync fixtures using Dixon-Coles model for predictions."""
    logger.info("Starting sync with Dixon-Coles predictions...")

    api = get_football_data_client()
    model = get_dixon_coles_model()
    db = SessionLocal()

    try:
        # Get competition info
        comp_data = api.get_competition(FootballDataOrgClient.LIGUE_1)
        logger.info(f"Competition: {comp_data.get('name')}")

        current_season = comp_data.get("currentSeason", {})
        season_year = current_season.get("startDate", "2025")[:4]

        # Get or create competition
        competition = db.query(Competition).filter(Competition.api_id == 61).first()
        if not competition:
            competition = Competition(
                api_id=61,
                name="Ligue 1",
                short_name="L1",
                country="France",
                type="league",
                season=int(season_year),
                logo_url="https://media.api-sports.io/football/leagues/61.png"
            )
            db.add(competition)
            db.commit()
            db.refresh(competition)
        else:
            competition.season = int(season_year)
            db.commit()

        # Fetch teams
        logger.info("Fetching teams...")
        api_teams = api.get_teams(FootballDataOrgClient.LIGUE_1)
        logger.info(f"Found {len(api_teams)} teams")

        team_map = {}
        for team_data in api_teams:
            team_id = team_data.get("id")
            team_name = team_data.get("name")

            existing = db.query(Team).filter(Team.api_id == team_id).first()
            if not existing:
                team = Team(
                    api_id=team_id,
                    name=team_name,
                    short_name=team_data.get("tla"),
                    code=team_data.get("tla"),
                    logo_url=team_data.get("crest"),
                    elo_rating=1500,
                )
                db.add(team)
                db.commit()
                db.refresh(team)
                team_map[team_id] = team
            else:
                team_map[team_id] = existing

        logger.info(f"Synced {len(team_map)} teams")

        # Fetch scheduled matches
        logger.info("Fetching scheduled matches...")
        matches = api.get_scheduled_matches(FootballDataOrgClient.LIGUE_1)
        logger.info(f"Found {len(matches)} scheduled matches")

        matches_created = 0
        predictions_created = 0
        edges_created = 0

        for match_data in matches[:30]:  # Process up to 30 matches
            match_id = match_data.get("id")

            # Skip if exists
            existing_match = db.query(Match).filter(Match.api_id == match_id).first()
            if existing_match:
                continue

            home_team_data = match_data.get("homeTeam", {})
            away_team_data = match_data.get("awayTeam", {})

            home_team = team_map.get(home_team_data.get("id"))
            away_team = team_map.get(away_team_data.get("id"))

            if not home_team or not away_team:
                continue

            # Parse kickoff
            kickoff_str = match_data.get("utcDate")
            kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
            matchday = match_data.get("matchday")

            # Create match
            match = Match(
                api_id=match_id,
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                competition_id=competition.id,
                kickoff=kickoff,
                matchday=str(matchday) if matchday else None,
                status="scheduled",
            )
            db.add(match)
            db.commit()
            db.refresh(match)
            matches_created += 1

            # === DIXON-COLES PREDICTIONS ===
            predictions = model.predict_all_markets(home_team.name, away_team.name)

            probs_1x2 = predictions['1x2']
            over_under = predictions['over_under']
            btts = predictions['btts']
            expected_goals = predictions['expected_goals']
            exact_scores = predictions['exact_scores']

            # Calculate confidence based on expected goals differential
            xg_diff = abs(expected_goals['home'] - expected_goals['away'])
            confidence = min(0.95, 0.5 + xg_diff * 0.15)

            # Create prediction record
            prediction = Prediction(
                match_id=match.id,
                home_win_prob=probs_1x2["home_win"] * 100,
                draw_prob=probs_1x2["draw"] * 100,
                away_win_prob=probs_1x2["away_win"] * 100,
                confidence=confidence,
                model_version="v2.0-dixon-coles",
            )
            db.add(prediction)
            db.commit()
            db.refresh(prediction)
            predictions_created += 1

            # Combine all probabilities for odds generation
            all_probs = {
                "home_win": probs_1x2["home_win"],
                "draw": probs_1x2["draw"],
                "away_win": probs_1x2["away_win"],
                "over_25": over_under.get("over_2.5", 0.55),
                "under_25": over_under.get("under_2.5", 0.45),
                "btts_yes": btts.get("btts_yes", 0.5),
                "btts_no": btts.get("btts_no", 0.5),
            }

            # Generate simulated bookmaker odds
            book_odds = generate_bookmaker_odds(all_probs)

            # Create odds record
            match_odds = MatchOdds(
                match_id=match.id,
                bookmaker="Simulated",
                home_win_odds=book_odds["home_win_odds"],
                draw_odds=book_odds["draw_odds"],
                away_win_odds=book_odds["away_win_odds"],
                over_25_odds=book_odds["over_25_odds"],
                under_25_odds=book_odds["under_25_odds"],
                btts_yes_odds=book_odds.get("btts_yes_odds"),
                btts_no_odds=book_odds.get("btts_no_odds"),
                home_win_implied=odds_to_prob(book_odds["home_win_odds"]),
                draw_implied=odds_to_prob(book_odds["draw_odds"]),
                away_win_implied=odds_to_prob(book_odds["away_win_odds"]),
            )
            db.add(match_odds)
            db.commit()

            # === CALCULATE EDGES FOR ALL MARKETS ===
            markets = [
                ("1x2_home", "home_win_odds", probs_1x2["home_win"], "Victoire domicile"),
                ("1x2_draw", "draw_odds", probs_1x2["draw"], "Match nul"),
                ("1x2_away", "away_win_odds", probs_1x2["away_win"], "Victoire extérieur"),
                ("over_25", "over_25_odds", all_probs["over_25"], "Plus de 2.5 buts"),
                ("under_25", "under_25_odds", all_probs["under_25"], "Moins de 2.5 buts"),
                ("btts_yes", "btts_yes_odds", all_probs["btts_yes"], "Les 2 équipes marquent"),
                ("btts_no", "btts_no_odds", all_probs["btts_no"], "Les 2 ne marquent pas"),
            ]

            for market, odds_key, model_prob, display_name in markets:
                best_odds = book_odds.get(odds_key, 2.0)
                book_prob = odds_to_prob(best_odds)
                edge = calculate_edge(model_prob, book_prob)

                # Only create edge if it's significant (> 3%)
                if edge > 3:
                    risk = classify_risk(edge, confidence)
                    kelly = kelly_criterion(model_prob, best_odds)

                    edge_calc = EdgeCalculation(
                        match_id=match.id,
                        prediction_id=prediction.id,
                        market=market,
                        model_probability=model_prob,
                        bookmaker_probability=book_prob,
                        edge_percentage=edge,
                        best_odds=best_odds,
                        bookmaker_name="Simulated",
                        risk_level=risk,
                        kelly_stake=kelly,
                        confidence=confidence,
                    )
                    db.add(edge_calc)
                    edges_created += 1

            db.commit()

            # Log prediction summary
            logger.info(
                f"  {home_team.name} vs {away_team.name} | "
                f"xG: {expected_goals['home']:.2f}-{expected_goals['away']:.2f} | "
                f"1X2: {probs_1x2['home_win']:.0%}/{probs_1x2['draw']:.0%}/{probs_1x2['away_win']:.0%}"
            )

        logger.info("=" * 60)
        logger.info("SYNC COMPLETED - DIXON-COLES MODEL")
        logger.info("=" * 60)
        logger.info(f"Matches created: {matches_created}")
        logger.info(f"Predictions created: {predictions_created}")
        logger.info(f"Edge calculations: {edges_created}")
        logger.info("=" * 60)

        return {
            "matches_created": matches_created,
            "predictions_created": predictions_created,
            "edges_created": edges_created,
        }

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()
        api.close()


if __name__ == "__main__":
    sync_with_dixon_coles()

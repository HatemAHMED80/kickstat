"""
Prediction Service

High-level service for making match predictions.
"""

from pathlib import Path
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select
from loguru import logger

from app.models import Match, Team, Prediction
from app.services.ml.elo import EloCalculator
from app.services.ml.features import FeatureEngineer, MatchFeatures
from app.services.ml.model import MatchPredictor, PredictionResult, ModelMetrics


# Default model path
MODEL_DIR = Path(__file__).parent.parent.parent.parent / "data" / "models"
DEFAULT_MODEL_PATH = MODEL_DIR / "xgboost_v1.pkl"


class PredictionService:
    """
    Service for training models and making predictions.

    Usage:
        service = PredictionService(db_session)
        metrics = service.train_model()
        prediction = service.predict_match(match_id)
    """

    def __init__(
        self,
        db: Session,
        model_path: Optional[Path] = None,
    ):
        self.db = db
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.feature_engineer = FeatureEngineer(db)
        self.elo_calculator = EloCalculator(db)
        self.predictor = MatchPredictor()

        # Try to load existing model
        if self.model_path.exists():
            try:
                self.predictor.load(self.model_path)
                logger.info("Loaded existing model")
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")

    def train_model(
        self,
        save: bool = True,
        test_size: float = 0.2,
    ) -> ModelMetrics:
        """
        Train prediction model on historical data.

        Args:
            save: Whether to save the trained model
            test_size: Fraction of data for testing

        Returns:
            ModelMetrics with evaluation results
        """
        logger.info("Preparing training data...")

        # Prepare features
        X, y = self.feature_engineer.prepare_training_data(min_matches=3)

        if len(X) < 50:
            raise ValueError(f"Not enough training data: {len(X)} samples")

        # Train model
        metrics = self.predictor.train(X, y, test_size=test_size)

        # Save model
        if save:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            self.predictor.save(self.model_path)

        return metrics

    def predict_match(
        self,
        match_id: int,
        save_to_db: bool = True,
    ) -> Optional[PredictionResult]:
        """
        Predict outcome for a specific match.

        Args:
            match_id: Database ID of the match
            save_to_db: Whether to save prediction to database

        Returns:
            PredictionResult or None if match not found
        """
        match = self.db.get(Match, match_id)
        if not match:
            logger.warning(f"Match {match_id} not found")
            return None

        return self.predict_match_obj(match, save_to_db)

    def predict_match_obj(
        self,
        match: Match,
        save_to_db: bool = True,
    ) -> PredictionResult:
        """
        Predict outcome for a Match object.

        Args:
            match: Match object
            save_to_db: Whether to save prediction to database

        Returns:
            PredictionResult
        """
        # Extract features
        features = self.feature_engineer.extract_features(match)

        # Get prediction
        if self.predictor.is_trained:
            result = self.predictor.predict(features)
        else:
            # Fallback to ELO-only prediction
            logger.warning("Model not trained, using ELO prediction only")
            elo_pred = self.elo_calculator.predict_match(
                features.home_elo,
                features.away_elo,
            )
            result = PredictionResult(
                home_win_prob=elo_pred["home_win"],
                draw_prob=elo_pred["draw"],
                away_win_prob=elo_pred["away_win"],
                predicted_result=max(elo_pred, key=elo_pred.get)[0].upper(),
                confidence=max(elo_pred.values()),
            )

        # Save to database
        if save_to_db:
            self._save_prediction(match, result, features)

        return result

    def predict_upcoming(
        self,
        limit: int = 10,
        save_to_db: bool = True,
    ) -> list[tuple[Match, PredictionResult]]:
        """
        Predict all upcoming matches.

        Returns:
            List of (Match, PredictionResult) tuples
        """
        # Get upcoming matches
        upcoming = self.db.execute(
            select(Match)
            .where(
                Match.status == "scheduled",
                Match.kickoff > datetime.utcnow(),
            )
            .order_by(Match.kickoff)
            .limit(limit)
        ).scalars().all()

        results = []
        for match in upcoming:
            try:
                prediction = self.predict_match_obj(match, save_to_db)
                results.append((match, prediction))
            except Exception as e:
                logger.error(f"Failed to predict match {match.id}: {e}")

        return results

    def _save_prediction(
        self,
        match: Match,
        result: PredictionResult,
        features: MatchFeatures,
    ) -> None:
        """Save prediction to database."""
        # Check if prediction exists
        existing = self.db.execute(
            select(Prediction).where(Prediction.match_id == match.id)
        ).scalar_one_or_none()

        if existing:
            existing.home_win_prob = result.home_win_prob
            existing.draw_prob = result.draw_prob
            existing.away_win_prob = result.away_win_prob
            existing.confidence = result.confidence
            existing.model_version = "xgboost_v1"
        else:
            prediction = Prediction(
                match_id=match.id,
                home_win_prob=result.home_win_prob,
                draw_prob=result.draw_prob,
                away_win_prob=result.away_win_prob,
                confidence=result.confidence,
                model_version="xgboost_v1",
            )
            self.db.add(prediction)

        self.db.commit()

    def evaluate_historical(
        self,
        last_n: int = 50,
    ) -> dict:
        """
        Evaluate model accuracy on recent finished matches.

        Returns:
            Dict with accuracy metrics
        """
        # Get recent finished matches
        matches = self.db.execute(
            select(Match)
            .where(
                Match.status == "finished",
                Match.home_score != None,
            )
            .order_by(Match.kickoff.desc())
            .limit(last_n)
        ).scalars().all()

        correct = 0
        total = 0
        results_breakdown = {"H": {"correct": 0, "total": 0},
                           "D": {"correct": 0, "total": 0},
                           "A": {"correct": 0, "total": 0}}

        for match in matches:
            try:
                # Get actual result
                if match.home_score > match.away_score:
                    actual = "H"
                elif match.home_score < match.away_score:
                    actual = "A"
                else:
                    actual = "D"

                # Get prediction (without saving)
                features = self.feature_engineer.extract_features(match)
                prediction = self.predictor.predict(features)

                results_breakdown[actual]["total"] += 1
                total += 1

                if prediction.predicted_result == actual:
                    correct += 1
                    results_breakdown[actual]["correct"] += 1

            except Exception as e:
                logger.debug(f"Skipping match {match.id}: {e}")

        accuracy = correct / total if total > 0 else 0

        return {
            "accuracy": accuracy,
            "correct": correct,
            "total": total,
            "by_result": results_breakdown,
        }

    def get_match_analysis(
        self,
        match_id: int,
    ) -> dict:
        """
        Get detailed analysis for a match prediction.

        Returns:
            Dict with prediction, features, and explanations
        """
        match = self.db.get(Match, match_id)
        if not match:
            return {"error": "Match not found"}

        home_team = self.db.get(Team, match.home_team_id)
        away_team = self.db.get(Team, match.away_team_id)

        features = self.feature_engineer.extract_features(match)
        prediction = self.predict_match_obj(match, save_to_db=False)

        # Get feature importance
        importance = self.predictor.get_feature_importance(top_n=5)

        return {
            "match": {
                "id": match.id,
                "home_team": home_team.name if home_team else "Unknown",
                "away_team": away_team.name if away_team else "Unknown",
                "kickoff": match.kickoff.isoformat() if match.kickoff else None,
            },
            "prediction": prediction.to_dict(),
            "key_factors": {
                "elo_diff": f"{features.elo_diff:+.0f} ({'+' if features.elo_diff > 0 else ''}{features.elo_home_expected*100:.0f}% home expected)",
                "position_diff": f"{features.position_diff:+d} places",
                "form": f"Home: {features.home_form_points}/15 pts, Away: {features.away_form_points}/15 pts",
                "h2h": f"{features.h2h_home_wins}W-{features.h2h_draws}D-{features.h2h_away_wins}L (last {features.h2h_matches})",
                "rest": f"Home: {features.home_rest_days}d, Away: {features.away_rest_days}d",
            },
            "top_features": importance,
        }

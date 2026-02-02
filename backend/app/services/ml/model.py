"""
Match Prediction Model

Ensemble model for predicting match outcomes (Home/Draw/Away).
Uses RandomForest + LogisticRegression.
"""

import pickle
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import numpy as np
from loguru import logger

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import LabelEncoder, StandardScaler

from app.services.ml.features import MatchFeatures


@dataclass
class PredictionResult:
    """Result of a match prediction."""

    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    predicted_result: str  # "H", "D", "A"
    confidence: float  # Probability of predicted result

    def to_dict(self) -> dict:
        return {
            "home_win": round(self.home_win_prob, 3),
            "draw": round(self.draw_prob, 3),
            "away_win": round(self.away_win_prob, 3),
            "predicted": self.predicted_result,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class ModelMetrics:
    """Model evaluation metrics."""

    accuracy: float
    cv_accuracy: float
    cv_std: float
    classification_report: str
    confusion_matrix: np.ndarray
    feature_importance: dict


class MatchPredictor:
    """
    XGBoost model for match prediction.

    Usage:
        predictor = MatchPredictor()
        predictor.train(X_train, y_train)
        result = predictor.predict(features)
        predictor.save("model.pkl")
    """

    def __init__(self, model_path: Optional[Path] = None):
        self.model: Optional[RandomForestClassifier] = None
        self.label_encoder = LabelEncoder()
        self.scaler = StandardScaler()
        self.feature_names = MatchFeatures.get_feature_names()
        self.is_trained = False

        if model_path and model_path.exists():
            self.load(model_path)

    def train(
        self,
        X: list[list[float]],
        y: list[str],
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> ModelMetrics:
        """
        Train the model on provided data.

        Args:
            X: Feature matrix
            y: Labels ("H", "D", "A")
            test_size: Fraction for test set
            random_state: Random seed

        Returns:
            ModelMetrics with evaluation results
        """
        logger.info(f"Training model on {len(X)} samples...")

        # Convert to numpy
        X_array = np.array(X)
        y_encoded = self.label_encoder.fit_transform(y)

        # Scale features
        X_scaled = self.scaler.fit_transform(X_array)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y_encoded,
            test_size=test_size,
            random_state=random_state,
            stratify=y_encoded,
        )

        # Create and train model (RandomForest - no OpenMP needed)
        self.model = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=random_state,
            n_jobs=1,  # Single thread to avoid OpenMP issues
        )

        self.model.fit(X_train, y_train)

        self.is_trained = True

        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        # Cross-validation
        cv_scores = cross_val_score(self.model, X_array, y_encoded, cv=5)

        # Classification report
        y_test_labels = self.label_encoder.inverse_transform(y_test)
        y_pred_labels = self.label_encoder.inverse_transform(y_pred)
        report = classification_report(y_test_labels, y_pred_labels)

        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)

        # Feature importance
        importance = dict(zip(
            self.feature_names,
            self.model.feature_importances_,
        ))
        importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

        metrics = ModelMetrics(
            accuracy=accuracy,
            cv_accuracy=cv_scores.mean(),
            cv_std=cv_scores.std(),
            classification_report=report,
            confusion_matrix=cm,
            feature_importance=importance,
        )

        logger.info(f"Model trained - Accuracy: {accuracy:.2%}, CV: {cv_scores.mean():.2%} (+/- {cv_scores.std():.2%})")

        return metrics

    def predict(self, features: MatchFeatures) -> PredictionResult:
        """
        Predict outcome for a single match.

        Args:
            features: MatchFeatures object

        Returns:
            PredictionResult with probabilities
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first or load a saved model.")

        X = np.array([features.get_feature_vector()])
        X_scaled = self.scaler.transform(X)
        probs = self.model.predict_proba(X_scaled)[0]

        # Map probabilities to results
        # Label encoder order is alphabetical: A, D, H
        classes = self.label_encoder.classes_
        prob_dict = dict(zip(classes, probs))

        home_prob = prob_dict.get("H", 0.33)
        draw_prob = prob_dict.get("D", 0.33)
        away_prob = prob_dict.get("A", 0.33)

        # Determine predicted result
        predicted_idx = np.argmax(probs)
        predicted = classes[predicted_idx]
        confidence = probs[predicted_idx]

        return PredictionResult(
            home_win_prob=home_prob,
            draw_prob=draw_prob,
            away_win_prob=away_prob,
            predicted_result=predicted,
            confidence=confidence,
        )

    def predict_batch(self, features_list: list[MatchFeatures]) -> list[PredictionResult]:
        """Predict outcomes for multiple matches."""
        return [self.predict(f) for f in features_list]

    def predict_from_vector(self, feature_vector: list[float]) -> PredictionResult:
        """Predict from raw feature vector."""
        if not self.is_trained:
            raise ValueError("Model not trained.")

        X = np.array([feature_vector])
        X_scaled = self.scaler.transform(X)
        probs = self.model.predict_proba(X_scaled)[0]

        classes = self.label_encoder.classes_
        prob_dict = dict(zip(classes, probs))

        predicted_idx = np.argmax(probs)
        predicted = classes[predicted_idx]

        return PredictionResult(
            home_win_prob=prob_dict.get("H", 0.33),
            draw_prob=prob_dict.get("D", 0.33),
            away_win_prob=prob_dict.get("A", 0.33),
            predicted_result=predicted,
            confidence=probs[predicted_idx],
        )

    def get_feature_importance(self, top_n: int = 10) -> dict:
        """Get top N most important features."""
        if not self.is_trained:
            return {}

        importance = dict(zip(
            self.feature_names,
            self.model.feature_importances_,
        ))
        sorted_importance = sorted(importance.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_importance[:top_n])

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    def save(self, path: Path) -> None:
        """Save model to file."""
        if not self.is_trained:
            raise ValueError("Cannot save untrained model.")

        data = {
            "model": self.model,
            "label_encoder": self.label_encoder,
            "scaler": self.scaler,
            "feature_names": self.feature_names,
        }

        with open(path, "wb") as f:
            pickle.dump(data, f)

        logger.info(f"Model saved to {path}")

    def load(self, path: Path) -> None:
        """Load model from file."""
        with open(path, "rb") as f:
            data = pickle.load(f)

        self.model = data["model"]
        self.label_encoder = data["label_encoder"]
        self.scaler = data.get("scaler", StandardScaler())
        self.feature_names = data["feature_names"]
        self.is_trained = True

        logger.info(f"Model loaded from {path}")


class EnsemblePredictor:
    """
    Ensemble of multiple models for more robust predictions.

    Combines XGBoost with ELO-based predictions.
    """

    def __init__(
        self,
        xgb_weight: float = 0.7,
        elo_weight: float = 0.3,
    ):
        self.xgb_predictor = MatchPredictor()
        self.xgb_weight = xgb_weight
        self.elo_weight = elo_weight

    def predict(
        self,
        features: MatchFeatures,
        elo_prediction: dict,
    ) -> PredictionResult:
        """
        Combine XGBoost and ELO predictions.

        Args:
            features: MatchFeatures for XGBoost
            elo_prediction: Dict with home_win, draw, away_win from ELO

        Returns:
            Combined PredictionResult
        """
        # Get XGBoost prediction
        xgb_result = self.xgb_predictor.predict(features)

        # Combine probabilities
        home_prob = (
            self.xgb_weight * xgb_result.home_win_prob +
            self.elo_weight * elo_prediction["home_win"]
        )
        draw_prob = (
            self.xgb_weight * xgb_result.draw_prob +
            self.elo_weight * elo_prediction["draw"]
        )
        away_prob = (
            self.xgb_weight * xgb_result.away_win_prob +
            self.elo_weight * elo_prediction["away_win"]
        )

        # Normalize
        total = home_prob + draw_prob + away_prob
        home_prob /= total
        draw_prob /= total
        away_prob /= total

        # Determine predicted result
        probs = {"H": home_prob, "D": draw_prob, "A": away_prob}
        predicted = max(probs, key=probs.get)
        confidence = probs[predicted]

        return PredictionResult(
            home_win_prob=home_prob,
            draw_prob=draw_prob,
            away_win_prob=away_prob,
            predicted_result=predicted,
            confidence=confidence,
        )

"""
Ensemble Predictor combining multiple models.

Combines:
- Dixon-Coles (Poisson) for score-based predictions
- XGBoost for feature-based classification
- ELO for baseline rating-based predictions

With Platt scaling calibration for well-calibrated probabilities.
"""

import numpy as np
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
import xgboost as xgb
from loguru import logger

from app.services.ml.dixon_coles import DixonColesModel, get_dixon_coles_model
from app.services.ml.advanced_features import AdvancedFeatureEngineer, MatchFeatures
from app.services.ml.elo import EloRatingSystem


@dataclass
class PredictionResult:
    """Complete prediction output."""
    # Match info
    home_team: str
    away_team: str
    kickoff: datetime

    # 1X2 Probabilities (calibrated)
    home_win_prob: float
    draw_prob: float
    away_win_prob: float

    # Goals markets
    over_15_prob: float
    over_25_prob: float
    over_35_prob: float
    under_15_prob: float
    under_25_prob: float
    under_35_prob: float

    # BTTS
    btts_yes_prob: float
    btts_no_prob: float

    # Expected goals
    expected_home_goals: float
    expected_away_goals: float
    expected_total_goals: float

    # Top exact scores
    exact_scores: List[Dict]

    # Asian handicaps
    asian_handicaps: Dict[str, float]

    # Model contributions
    dixon_coles_weight: float
    xgboost_weight: float
    elo_weight: float

    # Confidence metrics
    confidence: float
    model_agreement: float  # How much models agree (0-1)

    def to_dict(self) -> Dict:
        return {
            'home_team': self.home_team,
            'away_team': self.away_team,
            'kickoff': self.kickoff.isoformat() if self.kickoff else None,
            'probabilities': {
                '1x2': {
                    'home_win': round(self.home_win_prob, 4),
                    'draw': round(self.draw_prob, 4),
                    'away_win': round(self.away_win_prob, 4),
                },
                'over_under': {
                    'over_1.5': round(self.over_15_prob, 4),
                    'under_1.5': round(self.under_15_prob, 4),
                    'over_2.5': round(self.over_25_prob, 4),
                    'under_2.5': round(self.under_25_prob, 4),
                    'over_3.5': round(self.over_35_prob, 4),
                    'under_3.5': round(self.under_35_prob, 4),
                },
                'btts': {
                    'yes': round(self.btts_yes_prob, 4),
                    'no': round(self.btts_no_prob, 4),
                }
            },
            'expected_goals': {
                'home': round(self.expected_home_goals, 2),
                'away': round(self.expected_away_goals, 2),
                'total': round(self.expected_total_goals, 2),
            },
            'exact_scores': self.exact_scores,
            'asian_handicaps': self.asian_handicaps,
            'confidence': round(self.confidence, 3),
            'model_agreement': round(self.model_agreement, 3),
        }


class EnsemblePredictor:
    """
    Ensemble model combining Dixon-Coles, XGBoost, and ELO.

    Features:
    - Weighted combination of multiple models
    - Platt scaling calibration
    - Automatic weight optimization
    - Full market coverage (1X2, O/U, BTTS, exact scores, Asian handicaps)
    """

    def __init__(
        self,
        dixon_coles_weight: float = 0.45,
        xgboost_weight: float = 0.35,
        elo_weight: float = 0.20,
        calibrate: bool = True
    ):
        self.weights = {
            'dixon_coles': dixon_coles_weight,
            'xgboost': xgboost_weight,
            'elo': elo_weight
        }

        # Normalize weights
        total = sum(self.weights.values())
        self.weights = {k: v/total for k, v in self.weights.items()}

        self.calibrate = calibrate

        # Models
        self.dixon_coles: DixonColesModel = None
        self.xgboost: xgb.XGBClassifier = None
        self.elo: EloRatingSystem = None
        self.calibrator: CalibratedClassifierCV = None

        # Feature engineer
        self.feature_engineer: AdvancedFeatureEngineer = None

        # Fitted flag
        self._fitted = False

    def initialize_models(self):
        """Initialize all sub-models."""
        self.dixon_coles = get_dixon_coles_model()
        self.elo = EloRatingSystem()
        self.feature_engineer = AdvancedFeatureEngineer()

        # XGBoost with optimized hyperparameters for football
        self.xgboost = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=3,
            gamma=0.1,
            reg_alpha=0.1,
            reg_lambda=1.0,
            objective='multi:softprob',
            num_class=3,
            eval_metric='mlogloss',
            use_label_encoder=False,
            n_jobs=-1,
            random_state=42
        )

    def train_xgboost(
        self,
        X: np.ndarray,
        y: np.ndarray,
        X_val: np.ndarray = None,
        y_val: np.ndarray = None
    ):
        """Train the XGBoost model."""
        logger.info(f"Training XGBoost on {len(X)} samples...")

        eval_set = [(X, y)]
        if X_val is not None and y_val is not None:
            eval_set.append((X_val, y_val))

        self.xgboost.fit(
            X, y,
            eval_set=eval_set,
            verbose=False
        )

        logger.info("XGBoost training complete")

    def calibrate_model(self, X: np.ndarray, y: np.ndarray):
        """
        Apply Platt scaling calibration.

        Ensures that predicted probabilities are well-calibrated:
        - If model predicts 70%, outcomes should occur ~70% of the time
        """
        logger.info("Calibrating probabilities with Platt scaling...")

        # Use logistic regression for Platt scaling
        self.calibrator = CalibratedClassifierCV(
            self.xgboost,
            method='sigmoid',  # Platt scaling
            cv='prefit'
        )

        # Get uncalibrated predictions
        uncalibrated_probs = self.xgboost.predict_proba(X)

        # Fit calibrator
        self.calibrator.fit(X, y)

        logger.info("Calibration complete")

    def _predict_dixon_coles(self, home_team: str, away_team: str) -> Dict:
        """Get Dixon-Coles predictions."""
        if self.dixon_coles is None:
            return None

        try:
            return self.dixon_coles.predict_all_markets(home_team, away_team)
        except Exception as e:
            logger.warning(f"Dixon-Coles prediction failed: {e}")
            return None

    def _predict_xgboost(self, features: MatchFeatures) -> Optional[np.ndarray]:
        """Get XGBoost 1X2 predictions."""
        if self.xgboost is None:
            return None

        try:
            X = features.to_vector().reshape(1, -1)

            if self.calibrator is not None and self.calibrate:
                probs = self.calibrator.predict_proba(X)[0]
            else:
                probs = self.xgboost.predict_proba(X)[0]

            return probs  # [P(home), P(draw), P(away)]
        except Exception as e:
            logger.warning(f"XGBoost prediction failed: {e}")
            return None

    def _predict_elo(self, home_team: str, away_team: str) -> Optional[Dict]:
        """Get ELO-based predictions."""
        if self.elo is None:
            return None

        try:
            return self.elo.predict_match(home_team, away_team)
        except Exception as e:
            logger.warning(f"ELO prediction failed: {e}")
            return None

    def predict(
        self,
        home_team: str,
        away_team: str,
        kickoff: datetime = None,
        features: MatchFeatures = None
    ) -> PredictionResult:
        """
        Generate ensemble prediction for a match.

        Combines all models with weights and returns calibrated probabilities.
        """
        # Get predictions from each model
        dc_pred = self._predict_dixon_coles(home_team, away_team)
        xgb_pred = self._predict_xgboost(features) if features else None
        elo_pred = self._predict_elo(home_team, away_team)

        # Combine 1X2 probabilities
        home_probs = []
        draw_probs = []
        away_probs = []
        weights_used = []

        if dc_pred and dc_pred.get('1x2'):
            home_probs.append(dc_pred['1x2']['home_win'])
            draw_probs.append(dc_pred['1x2']['draw'])
            away_probs.append(dc_pred['1x2']['away_win'])
            weights_used.append(self.weights['dixon_coles'])

        if xgb_pred is not None:
            home_probs.append(xgb_pred[0])
            draw_probs.append(xgb_pred[1])
            away_probs.append(xgb_pred[2])
            weights_used.append(self.weights['xgboost'])

        if elo_pred:
            home_probs.append(elo_pred.get('home_win', 0.33))
            draw_probs.append(elo_pred.get('draw', 0.33))
            away_probs.append(elo_pred.get('away_win', 0.33))
            weights_used.append(self.weights['elo'])

        # Weighted average
        if weights_used:
            total_weight = sum(weights_used)
            home_win_prob = sum(p * w for p, w in zip(home_probs, weights_used)) / total_weight
            draw_prob = sum(p * w for p, w in zip(draw_probs, weights_used)) / total_weight
            away_win_prob = sum(p * w for p, w in zip(away_probs, weights_used)) / total_weight
        else:
            # Fallback
            home_win_prob, draw_prob, away_win_prob = 0.4, 0.25, 0.35

        # Normalize to sum to 1
        total = home_win_prob + draw_prob + away_win_prob
        home_win_prob /= total
        draw_prob /= total
        away_win_prob /= total

        # Calculate model agreement (variance-based)
        if len(home_probs) > 1:
            variance = np.var(home_probs) + np.var(draw_probs) + np.var(away_probs)
            model_agreement = max(0, 1 - variance * 10)  # Scale to 0-1
        else:
            model_agreement = 0.5

        # Get over/under and BTTS from Dixon-Coles (best for these markets)
        if dc_pred:
            ou = dc_pred.get('over_under', {})
            over_15 = ou.get('over_1.5', 0.75)
            over_25 = ou.get('over_2.5', 0.55)
            over_35 = ou.get('over_3.5', 0.35)

            btts = dc_pred.get('btts', {})
            btts_yes = btts.get('btts_yes', 0.5)

            expected = dc_pred.get('expected_goals', {})
            exp_home = expected.get('home', 1.3)
            exp_away = expected.get('away', 1.0)

            exact_scores = dc_pred.get('exact_scores', [])
            asian_handicaps = dc_pred.get('asian_handicap', {})
        else:
            # Fallback estimates
            over_15, over_25, over_35 = 0.75, 0.55, 0.35
            btts_yes = 0.5
            exp_home, exp_away = 1.3, 1.0
            exact_scores = []
            asian_handicaps = {}

        # Confidence based on model agreement and prediction strength
        max_prob = max(home_win_prob, draw_prob, away_win_prob)
        confidence = (max_prob * 0.5 + model_agreement * 0.5)

        return PredictionResult(
            home_team=home_team,
            away_team=away_team,
            kickoff=kickoff,
            home_win_prob=home_win_prob,
            draw_prob=draw_prob,
            away_win_prob=away_win_prob,
            over_15_prob=over_15,
            over_25_prob=over_25,
            over_35_prob=over_35,
            under_15_prob=1 - over_15,
            under_25_prob=1 - over_25,
            under_35_prob=1 - over_35,
            btts_yes_prob=btts_yes,
            btts_no_prob=1 - btts_yes,
            expected_home_goals=exp_home,
            expected_away_goals=exp_away,
            expected_total_goals=exp_home + exp_away,
            exact_scores=exact_scores,
            asian_handicaps=asian_handicaps,
            dixon_coles_weight=self.weights['dixon_coles'],
            xgboost_weight=self.weights['xgboost'],
            elo_weight=self.weights['elo'],
            confidence=confidence,
            model_agreement=model_agreement
        )

    def save(self, path: str):
        """Save ensemble model to disk."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save XGBoost
        if self.xgboost is not None:
            self.xgboost.save_model(str(path / 'xgboost.json'))

        # Save calibrator
        if self.calibrator is not None:
            with open(path / 'calibrator.pkl', 'wb') as f:
                pickle.dump(self.calibrator, f)

        # Save weights and config
        config = {
            'weights': self.weights,
            'calibrate': self.calibrate,
        }
        with open(path / 'config.pkl', 'wb') as f:
            pickle.dump(config, f)

        logger.info(f"Ensemble model saved to {path}")

    def load(self, path: str):
        """Load ensemble model from disk."""
        path = Path(path)

        # Initialize models first
        self.initialize_models()

        # Load XGBoost
        xgb_path = path / 'xgboost.json'
        if xgb_path.exists():
            self.xgboost.load_model(str(xgb_path))

        # Load calibrator
        cal_path = path / 'calibrator.pkl'
        if cal_path.exists():
            with open(cal_path, 'rb') as f:
                self.calibrator = pickle.load(f)

        # Load config
        config_path = path / 'config.pkl'
        if config_path.exists():
            with open(config_path, 'rb') as f:
                config = pickle.load(f)
                self.weights = config.get('weights', self.weights)
                self.calibrate = config.get('calibrate', True)

        self._fitted = True
        logger.info(f"Ensemble model loaded from {path}")


# Singleton instance
_ensemble: Optional[EnsemblePredictor] = None


def get_ensemble_predictor() -> EnsemblePredictor:
    """Get or create ensemble predictor singleton."""
    global _ensemble
    if _ensemble is None:
        _ensemble = EnsemblePredictor()
        _ensemble.initialize_models()
    return _ensemble

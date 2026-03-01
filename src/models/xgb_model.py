"""XGBoost stacking model for football predictions.

Uses DC + ELO probabilities as base features, plus engineered features
from match statistics. Trained via walk-forward to avoid data leakage.
"""

from __future__ import annotations

import numpy as np
import xgboost as xgb
from loguru import logger

from .features import FEATURE_NAMES, features_to_array


class XGBStackingModel:
    """XGBoost 3-class classifier stacking DC + ELO + match stats.

    Learns to correct base model outputs using additional signals.
    Heavy regularization to avoid overconfidence on small samples.
    """

    MIN_TRAINING_SAMPLES = 200

    def __init__(
        self,
        max_depth: int = 3,
        learning_rate: float = 0.06,
        n_estimators: int = 80,
        min_child_weight: int = 20,
        subsample: float = 0.66,
        colsample_bytree: float = 0.62,
        reg_alpha: float = 3.0,
        reg_lambda: float = 8.0,
        scale_pos_weight: float = 1.71,
        early_stopping_rounds: int = 20,
    ):
        """Initialize XGBoost stacking model.

        Default hyperparameters are optimized via Optuna (2h, 4 trials).
        Best ROI: -1.57% (vs -3.0% baseline). Validation: Ligue 1 2022-2024.
        """
        self.params = {
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "n_estimators": n_estimators,
            "min_child_weight": min_child_weight,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "reg_alpha": reg_alpha,
            "reg_lambda": reg_lambda,
            "scale_pos_weight": scale_pos_weight,
        }
        self.early_stopping_rounds = early_stopping_rounds
        self.model: xgb.XGBClassifier | None = None
        self.is_fitted: bool = False
        self._n_train_samples: int = 0

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        X_val: np.ndarray | None = None,
        y_val: np.ndarray | None = None,
    ) -> XGBStackingModel:
        """Train XGBoost on feature matrix.

        Args:
            X: (N, 46) feature matrix
            y: (N,) outcome array (0=home, 1=draw, 2=away)
            X_val: optional validation set for early stopping
            y_val: optional validation labels
        """
        if len(X) < self.MIN_TRAINING_SAMPLES:
            logger.warning(
                f"Only {len(X)} samples, need {self.MIN_TRAINING_SAMPLES}. "
                f"Skipping XGB training."
            )
            return self

        self.model = xgb.XGBClassifier(
            objective="multi:softprob",
            num_class=3,
            eval_metric="mlogloss",
            n_jobs=-1,
            random_state=42,
            verbosity=0,
            **self.params,
        )

        fit_params: dict = {}
        if X_val is not None and y_val is not None and len(X_val) > 0:
            fit_params["eval_set"] = [(X_val, y_val)]
            self.model.set_params(early_stopping_rounds=self.early_stopping_rounds)

        self.model.fit(X, y, **fit_params)
        self.is_fitted = True
        self._n_train_samples = len(X)
        logger.info(f"XGBoost fitted on {len(X)} samples, {len(FEATURE_NAMES)} features")
        return self

    def predict_proba(self, features: dict[str, float]) -> np.ndarray:
        """Predict 1X2 probabilities for a single match.

        Returns array of [home_prob, draw_prob, away_prob].
        """
        if not self.is_fitted:
            raise RuntimeError("XGBStackingModel not fitted")
        X = features_to_array(features).reshape(1, -1)
        return self.model.predict_proba(X)[0]

    def feature_importance(self) -> dict[str, float]:
        """Get feature importance for analysis."""
        if not self.is_fitted:
            return {}
        importances = self.model.feature_importances_
        return dict(sorted(
            zip(FEATURE_NAMES, importances),
            key=lambda x: x[1],
            reverse=True,
        ))

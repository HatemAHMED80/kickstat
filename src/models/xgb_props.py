"""XGBoost binary classifiers for prop markets (O/U 2.5, BTTS, Asian Handicap).

Each prop market gets its own XGBoost binary classifier trained on the same
46 match features used by the 1X2 model. Walk-forward training to avoid leakage.
"""

from __future__ import annotations

import numpy as np
import xgboost as xgb
from loguru import logger

from .features import FEATURE_NAMES, features_to_array


class XGBPropModel:
    """XGBoost binary classifier for a single prop market.

    Predicts P(outcome=1) for binary markets like:
    - Over 2.5 goals (1 = over, 0 = under)
    - BTTS (1 = yes, 0 = no)
    - Asian Handicap home covers (1 = covers, 0 = doesn't)
    """

    MIN_TRAINING_SAMPLES = 200

    def __init__(
        self,
        market_name: str = "prop",
        max_depth: int = 3,
        learning_rate: float = 0.05,
        n_estimators: int = 80,
        min_child_weight: int = 20,
        subsample: float = 0.65,
        colsample_bytree: float = 0.60,
        reg_alpha: float = 3.0,
        reg_lambda: float = 8.0,
        early_stopping_rounds: int = 15,
    ):
        self.market_name = market_name
        self.params = {
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "n_estimators": n_estimators,
            "min_child_weight": min_child_weight,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "reg_alpha": reg_alpha,
            "reg_lambda": reg_lambda,
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
    ) -> XGBPropModel:
        """Train on feature matrix.

        Args:
            X: (N, 46) feature matrix
            y: (N,) binary labels (0 or 1)
        """
        if len(X) < self.MIN_TRAINING_SAMPLES:
            logger.warning(
                f"[{self.market_name}] Only {len(X)} samples, need "
                f"{self.MIN_TRAINING_SAMPLES}. Skipping."
            )
            return self

        self.model = xgb.XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
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
        logger.info(
            f"[{self.market_name}] XGB prop fitted on {len(X)} samples, "
            f"{len(FEATURE_NAMES)} features"
        )
        return self

    def predict_proba(self, features: dict[str, float]) -> float:
        """Predict P(outcome=1) for a single match.

        Returns probability of the positive outcome (over, btts_yes, ah_covers).
        """
        if not self.is_fitted:
            raise RuntimeError(f"XGBPropModel({self.market_name}) not fitted")
        X = features_to_array(features).reshape(1, -1)
        return float(self.model.predict_proba(X)[0, 1])

    def feature_importance(self) -> dict[str, float]:
        """Get feature importance."""
        if not self.is_fitted:
            return {}
        importances = self.model.feature_importances_
        return dict(sorted(
            zip(FEATURE_NAMES, importances),
            key=lambda x: x[1],
            reverse=True,
        ))

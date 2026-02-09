"""Post-hoc calibration for XGBoost probabilities using Platt scaling.

Reduces overconfidence by fitting a logistic regression on top of model outputs.
"""

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from loguru import logger


class ProbabilityCalibrator:
    """Calibrates predicted probabilities to true frequencies.

    Uses Platt scaling (logistic regression) or isotonic regression.
    """

    def __init__(self, method: str = "sigmoid"):
        """
        Args:
            method: 'sigmoid' (Platt) or 'isotonic'
        """
        self.method = method
        self.calibrator = None
        self.is_fitted = False

    def fit(self, probs: np.ndarray, outcomes: np.ndarray) -> "ProbabilityCalibrator":
        """Fit calibrator on validation set.

        Args:
            probs: (N, 3) array of predicted probabilities [home, draw, away]
            outcomes: (N,) array of actual outcomes (0=home, 1=draw, 2=away)
        """
        if len(probs) < 50:
            logger.warning(f"Only {len(probs)} samples for calibration - may not be reliable")
            return self

        # Convert to "decision function" format (logits-like)
        # For each sample, use the predicted probability as confidence score
        # We'll calibrate per-class
        self.per_class_calibrators = []

        for class_idx in range(3):
            # Binary problem: is it class i or not?
            y_binary = (outcomes == class_idx).astype(int)
            probs_class = probs[:, class_idx]

            # Fit logistic regression
            if self.method == "sigmoid":
                cal = LogisticRegression()
                # Reshape for sklearn
                cal.fit(probs_class.reshape(-1, 1), y_binary)
            else:
                # Isotonic regression (more flexible but needs more data)
                from sklearn.isotonic import IsotonicRegression
                cal = IsotonicRegression(out_of_bounds='clip')
                cal.fit(probs_class, y_binary)

            self.per_class_calibrators.append(cal)

        self.is_fitted = True
        logger.info(f"Calibrator fitted on {len(probs)} samples using {self.method}")
        return self

    def calibrate(self, probs: np.ndarray) -> np.ndarray:
        """Apply calibration to probabilities.

        Args:
            probs: (N, 3) or (3,) array of predicted probabilities

        Returns:
            Calibrated probabilities (same shape), normalized to sum to 1
        """
        if not self.is_fitted:
            return probs

        single_pred = probs.ndim == 1
        if single_pred:
            probs = probs.reshape(1, -1)

        calibrated = np.zeros_like(probs)

        for class_idx, cal in enumerate(self.per_class_calibrators):
            probs_class = probs[:, class_idx]

            if self.method == "sigmoid":
                calibrated[:, class_idx] = cal.predict_proba(probs_class.reshape(-1, 1))[:, 1]
            else:
                calibrated[:, class_idx] = cal.predict(probs_class)

        # Normalize to sum to 1
        calibrated = calibrated / calibrated.sum(axis=1, keepdims=True)

        if single_pred:
            return calibrated[0]
        return calibrated


def apply_conservative_calibration(probs: np.ndarray, temperature: float = 1.5) -> np.ndarray:
    """Simple temperature scaling to reduce overconfidence.

    Higher temperature = more uniform predictions (less confident).

    Args:
        probs: (N, 3) or (3,) predicted probabilities
        temperature: T > 1 reduces confidence, T < 1 increases it

    Returns:
        Calibrated probabilities
    """
    single_pred = probs.ndim == 1
    if single_pred:
        probs = probs.reshape(1, -1)

    # Apply temperature scaling
    logits = np.log(probs + 1e-10)  # Avoid log(0)
    scaled_logits = logits / temperature

    # Softmax
    exp_logits = np.exp(scaled_logits - scaled_logits.max(axis=1, keepdims=True))
    calibrated = exp_logits / exp_logits.sum(axis=1, keepdims=True)

    if single_pred:
        return calibrated[0]
    return calibrated

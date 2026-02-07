"""Probability calibration metrics.

The core question: when we predict 70%, does it happen 70% of the time?
"""

from dataclasses import dataclass

import numpy as np
from loguru import logger


@dataclass
class CalibrationReport:
    """Full calibration report for model evaluation."""

    brier_score: float          # Lower is better (0 = perfect, 0.25 = coin flip)
    log_loss: float             # Lower is better (0 = perfect)
    ece: float                  # Expected Calibration Error (lower = better)
    n_predictions: int
    accuracy: float             # % of correct predicted outcomes
    calibration_bins: list[dict]  # Per-bin calibration data

    @property
    def is_acceptable(self) -> bool:
        """Minimum thresholds for production use."""
        return self.brier_score < 0.22 and self.ece < 0.08

    def summary(self) -> str:
        status = "PASS" if self.is_acceptable else "FAIL"
        return (
            f"[{status}] Brier={self.brier_score:.4f} LogLoss={self.log_loss:.4f} "
            f"ECE={self.ece:.4f} Accuracy={self.accuracy:.1%} N={self.n_predictions}"
        )


def brier_score(predicted_probs: np.ndarray, actual_outcomes: np.ndarray) -> float:
    """Brier score for multi-class predictions.

    Args:
        predicted_probs: (N, 3) array of [home, draw, away] probabilities.
        actual_outcomes: (N,) array of outcomes (0=home, 1=draw, 2=away).

    Returns:
        Brier score (lower is better).
    """
    n = len(actual_outcomes)
    one_hot = np.zeros_like(predicted_probs)
    for i in range(n):
        one_hot[i, actual_outcomes[i]] = 1.0
    return float(np.mean(np.sum((predicted_probs - one_hot) ** 2, axis=1)))


def log_loss(predicted_probs: np.ndarray, actual_outcomes: np.ndarray) -> float:
    """Multi-class log loss.

    Args:
        predicted_probs: (N, 3) array of [home, draw, away] probabilities.
        actual_outcomes: (N,) array of outcomes (0=home, 1=draw, 2=away).

    Returns:
        Log loss (lower is better).
    """
    eps = 1e-10
    clipped = np.clip(predicted_probs, eps, 1 - eps)
    n = len(actual_outcomes)
    loss = 0.0
    for i in range(n):
        loss -= np.log(clipped[i, actual_outcomes[i]])
    return float(loss / n)


def expected_calibration_error(
    predicted_probs: np.ndarray,
    actual_outcomes: np.ndarray,
    n_bins: int = 10,
) -> tuple[float, list[dict]]:
    """Expected Calibration Error (ECE).

    Measures how well predicted probabilities match observed frequencies.

    Returns:
        (ece_value, calibration_bins)
    """
    bins = []
    ece = 0.0
    n_total = len(actual_outcomes)

    # Flatten to per-outcome probabilities
    all_probs = predicted_probs.flatten()
    all_correct = np.zeros(len(all_probs))
    for i in range(len(actual_outcomes)):
        for c in range(predicted_probs.shape[1]):
            idx = i * predicted_probs.shape[1] + c
            all_correct[idx] = 1.0 if actual_outcomes[i] == c else 0.0

    bin_edges = np.linspace(0, 1, n_bins + 1)

    for b in range(n_bins):
        mask = (all_probs >= bin_edges[b]) & (all_probs < bin_edges[b + 1])
        if b == n_bins - 1:
            mask = mask | (all_probs == bin_edges[b + 1])

        count = mask.sum()
        if count == 0:
            bins.append({
                "bin_start": float(bin_edges[b]),
                "bin_end": float(bin_edges[b + 1]),
                "count": 0,
                "avg_predicted": 0,
                "avg_actual": 0,
                "gap": 0,
            })
            continue

        avg_pred = float(all_probs[mask].mean())
        avg_actual = float(all_correct[mask].mean())
        gap = abs(avg_pred - avg_actual)

        ece += gap * count / len(all_probs)
        bins.append({
            "bin_start": float(bin_edges[b]),
            "bin_end": float(bin_edges[b + 1]),
            "count": int(count),
            "avg_predicted": round(avg_pred, 4),
            "avg_actual": round(avg_actual, 4),
            "gap": round(gap, 4),
        })

    return float(ece), bins


def evaluate(
    predicted_probs: np.ndarray,
    actual_outcomes: np.ndarray,
) -> CalibrationReport:
    """Run full calibration evaluation.

    Args:
        predicted_probs: (N, 3) array of [home, draw, away] probabilities.
        actual_outcomes: (N,) array with 0=home_win, 1=draw, 2=away_win.
    """
    bs = brier_score(predicted_probs, actual_outcomes)
    ll = log_loss(predicted_probs, actual_outcomes)
    ece, bins = expected_calibration_error(predicted_probs, actual_outcomes)

    predicted_classes = np.argmax(predicted_probs, axis=1)
    accuracy = float((predicted_classes == actual_outcomes).mean())

    report = CalibrationReport(
        brier_score=bs,
        log_loss=ll,
        ece=ece,
        n_predictions=len(actual_outcomes),
        accuracy=accuracy,
        calibration_bins=bins,
    )
    logger.info(report.summary())
    return report

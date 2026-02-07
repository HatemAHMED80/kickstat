"""Tests for calibration metrics."""

import numpy as np
import pytest

from src.evaluation.calibration import brier_score, log_loss, expected_calibration_error


def test_brier_perfect_predictions():
    """Perfect predictions should have Brier score = 0."""
    probs = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
    outcomes = np.array([0, 1, 2])
    assert brier_score(probs, outcomes) == pytest.approx(0.0, abs=1e-10)


def test_brier_worst_predictions():
    """Completely wrong predictions with max confidence should have Brier = 2."""
    probs = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=float)
    outcomes = np.array([0, 1, 2])
    assert brier_score(probs, outcomes) == pytest.approx(2.0, abs=1e-10)


def test_brier_uniform():
    """Uniform predictions (1/3 each) should have known Brier score."""
    probs = np.array([[1/3, 1/3, 1/3]] * 100)
    outcomes = np.random.choice([0, 1, 2], size=100)
    bs = brier_score(probs, outcomes)
    # For 3-class uniform: E[BS] = 2 * (1 - 1/3) * 1/3 + ... ≈ 0.667
    assert 0.5 < bs < 0.8


def test_log_loss_perfect():
    """Near-perfect predictions should have very low log loss."""
    probs = np.array([[0.99, 0.005, 0.005], [0.005, 0.99, 0.005]], dtype=float)
    outcomes = np.array([0, 1])
    ll = log_loss(probs, outcomes)
    assert ll < 0.02


def test_ece_perfect_calibration():
    """Perfectly calibrated predictions should have ECE near 0."""
    # 100 predictions at 0.8 confidence, 80% correct
    np.random.seed(42)
    n = 1000
    probs = np.zeros((n, 3))
    probs[:, 0] = 0.7
    probs[:, 1] = 0.15
    probs[:, 2] = 0.15
    outcomes = np.random.choice([0, 1, 2], size=n, p=[0.7, 0.15, 0.15])
    ece, bins = expected_calibration_error(probs, outcomes)
    assert ece < 0.05  # Should be well-calibrated


def test_remove_margin():
    """Test that margin removal produces fair probabilities."""
    from src.data.odds_api import remove_margin

    fair = remove_margin(1.80, 3.50, 4.00)
    assert fair["home"] + fair["draw"] + fair["away"] == pytest.approx(1.0, abs=1e-6)
    assert fair["overround"] > 1.0  # Should detect overround
    assert fair["home"] > fair["draw"] > fair["away"]

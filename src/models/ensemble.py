"""Ensemble predictor combining Dixon-Coles and ELO.

Weights are optimized during backtesting (Phase 0).
Calibration applied to final ensemble output.
"""

from dataclasses import dataclass

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from loguru import logger

from .dixon_coles import DixonColesModel, MatchPrediction
from .elo import EloRating


@dataclass
class EnsemblePrediction:
    """Combined prediction from multiple models."""

    home_team: str
    away_team: str
    # 1X2
    home_prob: float
    draw_prob: float
    away_prob: float
    # Over/Under (from Dixon-Coles only)
    over_25_prob: float
    btts_prob: float
    # Model agreement
    model_agreement: float
    # Individual model outputs
    dc_probs: dict
    elo_probs: dict
    # Weights used
    weights: dict

    def to_dict(self) -> dict:
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "1x2": {
                "home": round(self.home_prob, 4),
                "draw": round(self.draw_prob, 4),
                "away": round(self.away_prob, 4),
            },
            "over_25": round(self.over_25_prob, 4),
            "btts": round(self.btts_prob, 4),
            "model_agreement": round(self.model_agreement, 4),
            "models": {
                "dixon_coles": self.dc_probs,
                "elo": self.elo_probs,
            },
            "weights": self.weights,
        }


class EnsemblePredictor:
    """Weighted ensemble of Dixon-Coles + ELO.

    Start simple with 2 models. Add XGBoost only if it improves
    Brier score on the walk-forward backtest.
    """

    def __init__(
        self,
        dc_model: DixonColesModel,
        elo_model: EloRating,
        dc_weight: float = 0.65,
        elo_weight: float = 0.35,
    ):
        self.dc = dc_model
        self.elo = elo_model
        self.weights = {"dixon_coles": dc_weight, "elo": elo_weight}

    def predict(self, home_team: str, away_team: str) -> EnsemblePrediction:
        """Generate ensemble prediction."""
        # Dixon-Coles prediction (full markets)
        dc_pred = self.dc.predict(home_team, away_team)
        dc_probs = {"home": dc_pred.home_win, "draw": dc_pred.draw, "away": dc_pred.away_win}

        # ELO prediction (1X2 only)
        elo_probs = self.elo.predict_1x2(home_team, away_team)

        # Weighted average for 1X2
        w_dc = self.weights["dixon_coles"]
        w_elo = self.weights["elo"]

        home = w_dc * dc_probs["home"] + w_elo * elo_probs["home"]
        draw = w_dc * dc_probs["draw"] + w_elo * elo_probs["draw"]
        away = w_dc * dc_probs["away"] + w_elo * elo_probs["away"]

        # Normalize
        total = home + draw + away
        home /= total
        draw /= total
        away /= total

        # Model agreement: 1 = perfect agreement, 0 = maximum disagreement
        probs_dc = np.array([dc_probs["home"], dc_probs["draw"], dc_probs["away"]])
        probs_elo = np.array([elo_probs["home"], elo_probs["draw"], elo_probs["away"]])
        agreement = 1.0 - float(np.sqrt(np.mean((probs_dc - probs_elo) ** 2)))

        return EnsemblePrediction(
            home_team=home_team,
            away_team=away_team,
            home_prob=home,
            draw_prob=draw,
            away_prob=away,
            over_25_prob=dc_pred.over_25,
            btts_prob=dc_pred.btts_yes,
            model_agreement=agreement,
            dc_probs=dc_probs,
            elo_probs=elo_probs,
            weights=self.weights,
        )

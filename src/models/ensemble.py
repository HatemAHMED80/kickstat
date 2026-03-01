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
    """Weighted ensemble of Dixon-Coles + ELO, with optional XGBoost stacking.

    When XGBoost is available and fitted, it can adjust the DC+ELO baseline.
    Falls back to DC+ELO weighted average otherwise.

    xgb_markets: set of outcome classes where XGBoost is allowed to override
    the DC+ELO baseline. For outcomes NOT in this set, DC+ELO is kept pure.
    Example: {"draw"} = XGB only adjusts draw, home/away stay DC+ELO.
    If None, XGBoost overrides all outcomes (legacy behavior).
    """

    def __init__(
        self,
        dc_model: DixonColesModel,
        elo_model: EloRating,
        dc_weight: float = 0.65,
        elo_weight: float = 0.35,
        xgb_model=None,
        xgb_markets: set[str] | None = None,
    ):
        self.dc = dc_model
        self.elo = elo_model
        self.weights = {"dixon_coles": dc_weight, "elo": elo_weight}
        self.xgb = xgb_model
        self.xgb_markets = xgb_markets

    def predict(
        self,
        home_team: str,
        away_team: str,
        match_features: dict[str, float] | None = None,
    ) -> EnsemblePrediction:
        """Generate ensemble prediction.

        If XGBoost model is available and match_features provided,
        uses XGBoost for 1X2. Otherwise falls back to weighted average.
        """
        # Dixon-Coles prediction (always needed for over/under + BTTS)
        dc_pred = self.dc.predict(home_team, away_team)
        dc_probs = {"home": dc_pred.home_win, "draw": dc_pred.draw, "away": dc_pred.away_win}

        # ELO prediction (1X2 only)
        elo_probs = self.elo.predict_1x2(home_team, away_team)

        # Compute DC+ELO baseline (always needed as fallback or for capping)
        w_dc = self.weights["dixon_coles"]
        w_elo = self.weights["elo"]
        base_home = w_dc * dc_probs["home"] + w_elo * elo_probs["home"]
        base_draw = w_dc * dc_probs["draw"] + w_elo * elo_probs["draw"]
        base_away = w_dc * dc_probs["away"] + w_elo * elo_probs["away"]
        base_total = base_home + base_draw + base_away
        base_home /= base_total
        base_draw /= base_total
        base_away /= base_total

        # XGBoost stacking path
        if self.xgb is not None and self.xgb.is_fitted and match_features is not None:
            xgb_probs = self.xgb.predict_proba(match_features)
            xgb_home = float(xgb_probs[0])
            xgb_draw = float(xgb_probs[1])
            xgb_away = float(xgb_probs[2])

            # Selective XGB: only use XGB for specified markets
            if self.xgb_markets is not None:
                home = xgb_home if "home" in self.xgb_markets else base_home
                draw = xgb_draw if "draw" in self.xgb_markets else base_draw
                away = xgb_away if "away" in self.xgb_markets else base_away
            else:
                home, draw, away = xgb_home, xgb_draw, xgb_away

            # Re-normalize
            total = home + draw + away
            home /= total
            draw /= total
            away /= total

            used_weights = {"xgboost": 1.0, "xgb_markets": list(self.xgb_markets or ["home", "draw", "away"])}
        else:
            home = base_home
            draw = base_draw
            away = base_away
            used_weights = self.weights

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
            weights=used_weights,
        )

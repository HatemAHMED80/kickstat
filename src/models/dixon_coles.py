"""Dixon-Coles (1997) football prediction model.

Bivariate Poisson model with low-score correlation correction.
Reference: "Modelling Association Football Scores and Inefficiencies
           in the Football Betting Market" - Dixon & Coles, 1997.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson
from loguru import logger


@dataclass
class TeamRating:
    attack: float = 1.0
    defense: float = 1.0


@dataclass
class MatchResult:
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    date: datetime
    weight: float = 1.0


@dataclass
class MatchPrediction:
    """Complete prediction for a match."""

    home_team: str
    away_team: str
    lambda_home: float
    lambda_away: float
    home_win: float
    draw: float
    away_win: float
    over_15: float
    over_25: float
    over_35: float
    btts_yes: float
    btts_no: float
    score_matrix: np.ndarray = field(repr=False)

    def to_dict(self) -> dict:
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "lambda_home": round(self.lambda_home, 3),
            "lambda_away": round(self.lambda_away, 3),
            "1x2": {
                "home": round(self.home_win, 4),
                "draw": round(self.draw, 4),
                "away": round(self.away_win, 4),
            },
            "over_under": {
                "over_15": round(self.over_15, 4),
                "over_25": round(self.over_25, 4),
                "over_35": round(self.over_35, 4),
            },
            "btts": {
                "yes": round(self.btts_yes, 4),
                "no": round(self.btts_no, 4),
            },
        }


class DixonColesModel:
    """Dixon-Coles bivariate Poisson model.

    Estimates team attack/defense parameters via MLE on historical results.
    Applies rho correction for low-scoring game correlation.
    Uses exponential time decay to weight recent matches more heavily.
    """

    def __init__(
        self,
        max_goals: int = 8,
        half_life_days: int = 180,
        home_advantage: float = 0.25,
        rho: float = -0.13,
    ):
        self.max_goals = max_goals
        self.half_life_days = half_life_days
        self.home_advantage_init = home_advantage
        self.rho_init = rho

        # Fitted parameters
        self.teams: dict[str, TeamRating] = {}
        self.home_advantage: float = home_advantage
        self.rho: float = rho
        self.avg_goals: float = 1.35
        self.is_fitted: bool = False
        self._convergence_info: Optional[str] = None

    def _time_weight(self, match_date: datetime, reference_date: datetime) -> float:
        """Exponential decay weight. Recent matches count more."""
        days_ago = (reference_date - match_date).days
        return math.exp(-math.log(2) * days_ago / self.half_life_days)

    def _tau(
        self,
        home_goals: int,
        away_goals: int,
        lambda_h: float,
        lambda_a: float,
        rho: float,
    ) -> float:
        """Dixon-Coles correction factor for low-scoring outcomes.

        Adjusts the independence assumption for 0-0, 0-1, 1-0, 1-1 scorelines.
        """
        if home_goals == 0 and away_goals == 0:
            return 1 - lambda_h * lambda_a * rho
        elif home_goals == 0 and away_goals == 1:
            return 1 + lambda_h * rho
        elif home_goals == 1 and away_goals == 0:
            return 1 + lambda_a * rho
        elif home_goals == 1 and away_goals == 1:
            return 1 - rho
        return 1.0

    def _score_prob(
        self,
        home_goals: int,
        away_goals: int,
        lambda_h: float,
        lambda_a: float,
        rho: float,
    ) -> float:
        """Probability of a specific scoreline."""
        prob = (
            poisson.pmf(home_goals, lambda_h)
            * poisson.pmf(away_goals, lambda_a)
            * self._tau(home_goals, away_goals, lambda_h, lambda_a, rho)
        )
        return max(prob, 0.0)

    def fit(self, matches: list[MatchResult]) -> "DixonColesModel":
        """Fit model parameters via Maximum Likelihood Estimation.

        Args:
            matches: Historical match results with dates.

        Returns:
            self (fitted model).
        """
        if len(matches) < 50:
            raise ValueError(f"Need >= 50 matches for fitting, got {len(matches)}")

        reference_date = max(m.date for m in matches)

        # Apply time weights
        for m in matches:
            m.weight = self._time_weight(m.date, reference_date)

        # Collect unique teams
        team_names = sorted(
            set(m.home_team for m in matches) | set(m.away_team for m in matches)
        )
        team_idx = {name: i for i, name in enumerate(team_names)}
        n_teams = len(team_names)

        # Calculate average goals (weighted)
        total_weight = sum(m.weight for m in matches)
        self.avg_goals = (
            sum((m.home_goals + m.away_goals) * m.weight for m in matches)
            / (2 * total_weight)
        )

        logger.info(
            f"Fitting Dixon-Coles on {len(matches)} matches, "
            f"{n_teams} teams, avg_goals={self.avg_goals:.3f}"
        )

        # Parameter vector: [attack_0..n, defense_0..n, home_adv, rho]
        n_params = 2 * n_teams + 2
        x0 = np.ones(n_params)
        x0[-2] = self.home_advantage_init
        x0[-1] = self.rho_init

        # Bounds
        bounds = (
            [(0.2, 3.0)] * n_teams      # attacks
            + [(0.2, 3.0)] * n_teams     # defenses
            + [(0.10, 0.45)]             # home advantage (min 0.10 - always exists in football)
            + [(-0.3, 0.0)]              # rho
        )

        def neg_log_likelihood(params):
            attacks = params[:n_teams]
            defenses = params[n_teams : 2 * n_teams]
            home_adv = params[-2]
            rho = params[-1]

            # Normalize: mean attack = 1, mean defense = 1
            attacks = attacks / attacks.mean()
            defenses = defenses / defenses.mean()

            log_lik = 0.0
            for m in matches:
                hi = team_idx[m.home_team]
                ai = team_idx[m.away_team]

                lambda_h = max(
                    self.avg_goals * attacks[hi] * defenses[ai] * (1 + home_adv),
                    0.05,
                )
                lambda_a = max(
                    self.avg_goals * attacks[ai] * defenses[hi],
                    0.05,
                )

                prob = self._score_prob(
                    m.home_goals, m.away_goals, lambda_h, lambda_a, rho
                )
                if prob > 1e-10:
                    log_lik += m.weight * np.log(prob)
                else:
                    log_lik += m.weight * np.log(1e-10)

            return -log_lik

        result = minimize(
            neg_log_likelihood,
            x0,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 2000, "ftol": 1e-8},
        )

        if not result.success:
            logger.warning(f"MLE optimization did not converge: {result.message}")
            self._convergence_info = result.message
        else:
            self._convergence_info = "converged"
            logger.info(f"MLE converged in {result.nit} iterations")

        # Extract fitted parameters
        attacks = result.x[:n_teams]
        defenses = result.x[n_teams : 2 * n_teams]
        attacks = attacks / attacks.mean()
        defenses = defenses / defenses.mean()

        self.teams = {
            name: TeamRating(attack=float(attacks[i]), defense=float(defenses[i]))
            for i, name in enumerate(team_names)
        }
        self.home_advantage = float(result.x[-2])
        self.rho = float(result.x[-1])
        self.is_fitted = True

        logger.info(
            f"Fitted: home_adv={self.home_advantage:.3f}, rho={self.rho:.3f}, "
            f"teams={n_teams}"
        )
        return self

    def predict(self, home_team: str, away_team: str) -> MatchPrediction:
        """Generate full match prediction with score matrix.

        Falls back to average ratings for unknown teams.
        """
        home_r = self.teams.get(home_team, TeamRating())
        away_r = self.teams.get(away_team, TeamRating())

        if home_team not in self.teams:
            logger.warning(f"Unknown team '{home_team}', using default ratings")
        if away_team not in self.teams:
            logger.warning(f"Unknown team '{away_team}', using default ratings")

        lambda_h = max(
            self.avg_goals * home_r.attack * away_r.defense * (1 + self.home_advantage),
            0.05,
        )
        lambda_a = max(
            self.avg_goals * away_r.attack * home_r.defense,
            0.05,
        )

        # Build score matrix
        n = self.max_goals + 1
        matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                matrix[i, j] = self._score_prob(i, j, lambda_h, lambda_a, self.rho)

        # Ensure valid probabilities
        if matrix.sum() > 0:
            matrix = matrix / matrix.sum()

        # Derive market probabilities from score matrix
        home_win = float(np.tril(matrix, k=-1).sum())
        draw = float(np.trace(matrix))
        away_win = float(np.triu(matrix, k=1).sum())

        # Over/Under
        over_15 = over_25 = over_35 = 0.0
        for i in range(n):
            for j in range(n):
                total = i + j
                if total > 1:
                    over_15 += matrix[i, j]
                if total > 2:
                    over_25 += matrix[i, j]
                if total > 3:
                    over_35 += matrix[i, j]

        # BTTS
        btts_yes = float(matrix[1:, 1:].sum())

        return MatchPrediction(
            home_team=home_team,
            away_team=away_team,
            lambda_home=lambda_h,
            lambda_away=lambda_a,
            home_win=home_win,
            draw=draw,
            away_win=away_win,
            over_15=float(over_15),
            over_25=float(over_25),
            over_35=float(over_35),
            btts_yes=btts_yes,
            btts_no=1.0 - btts_yes,
            score_matrix=matrix,
        )

    def get_team_rankings(self) -> list[dict]:
        """Return teams sorted by attack - defense differential."""
        rankings = []
        for name, r in self.teams.items():
            rankings.append({
                "team": name,
                "attack": round(r.attack, 3),
                "defense": round(r.defense, 3),
                "strength": round(r.attack / r.defense, 3),
            })
        return sorted(rankings, key=lambda x: x["strength"], reverse=True)

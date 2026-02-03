"""
Dixon-Coles Model for Football Score Prediction.

An improved Poisson model that corrects for:
1. Correlation between home and away goals (low-scoring games)
2. Time-weighted historical data (recent matches matter more)
3. Attack and defense strength ratings per team

Reference: Dixon & Coles (1997) "Modelling Association Football Scores and Inefficiencies in the Football Betting Market"
"""

import numpy as np
from scipy.stats import poisson
from scipy.optimize import minimize
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import math


@dataclass
class TeamRatings:
    """Attack and defense ratings for a team."""
    attack: float
    defense: float
    home_attack: float = None
    home_defense: float = None
    away_attack: float = None
    away_defense: float = None


@dataclass
class MatchData:
    """Historical match data for model training."""
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    date: datetime
    weight: float = 1.0


class DixonColesModel:
    """
    Dixon-Coles model for predicting football match scores.

    Produces a full probability matrix for all possible scorelines,
    from which all betting markets can be derived.
    """

    def __init__(
        self,
        half_life_days: int = 180,  # Weight decay for old matches
        max_goals: int = 10,         # Maximum goals to consider
        rho_correction: bool = True  # Use Dixon-Coles low-score correction
    ):
        self.half_life_days = half_life_days
        self.max_goals = max_goals
        self.rho_correction = rho_correction

        # Model parameters (fitted)
        self.teams: Dict[str, TeamRatings] = {}
        self.home_advantage: float = 0.25
        self.avg_goals: float = 1.35
        self.rho: float = -0.13  # Low-score correlation parameter

        # Fitted flag
        self._fitted = False

    def _calculate_weight(self, match_date: datetime, reference_date: datetime = None) -> float:
        """Calculate time-decay weight for a match."""
        if reference_date is None:
            reference_date = datetime.now()

        days_ago = (reference_date - match_date).days
        # Exponential decay: weight = 0.5^(days/half_life)
        return math.exp(-math.log(2) * days_ago / self.half_life_days)

    def _tau(self, home_goals: int, away_goals: int, lambda_home: float, lambda_away: float, rho: float) -> float:
        """
        Dixon-Coles correction factor for low-scoring games.

        Adjusts probabilities for 0-0, 0-1, 1-0, and 1-1 scorelines
        which are typically underestimated by independent Poisson.
        """
        if home_goals == 0 and away_goals == 0:
            return 1 - lambda_home * lambda_away * rho
        elif home_goals == 0 and away_goals == 1:
            return 1 + lambda_home * rho
        elif home_goals == 1 and away_goals == 0:
            return 1 + lambda_away * rho
        elif home_goals == 1 and away_goals == 1:
            return 1 - rho
        else:
            return 1.0

    def _score_probability(
        self,
        home_goals: int,
        away_goals: int,
        lambda_home: float,
        lambda_away: float
    ) -> float:
        """Calculate probability of a specific scoreline."""
        # Base Poisson probability
        prob = poisson.pmf(home_goals, lambda_home) * poisson.pmf(away_goals, lambda_away)

        # Apply Dixon-Coles correction
        if self.rho_correction:
            prob *= self._tau(home_goals, away_goals, lambda_home, lambda_away, self.rho)

        return prob

    def _get_lambdas(self, home_team: str, away_team: str) -> Tuple[float, float]:
        """Calculate expected goals (lambda) for each team."""
        home_ratings = self.teams.get(home_team)
        away_ratings = self.teams.get(away_team)

        if home_ratings is None or away_ratings is None:
            # Fallback to average
            return self.avg_goals * 1.1, self.avg_goals * 0.9

        # Expected goals formula:
        # lambda_home = avg_goals * home_attack * away_defense * home_advantage
        # lambda_away = avg_goals * away_attack * home_defense

        lambda_home = (
            self.avg_goals *
            home_ratings.attack *
            away_ratings.defense *
            (1 + self.home_advantage)
        )

        lambda_away = (
            self.avg_goals *
            away_ratings.attack *
            home_ratings.defense
        )

        return lambda_home, lambda_away

    def fit(self, matches: List[MatchData], reference_date: datetime = None) -> 'DixonColesModel':
        """
        Fit the model to historical match data.

        Uses maximum likelihood estimation to find optimal:
        - Attack/defense ratings for each team
        - Home advantage factor
        - Rho (low-score correlation)
        """
        if reference_date is None:
            reference_date = datetime.now()

        # Calculate weights
        for match in matches:
            match.weight = self._calculate_weight(match.date, reference_date)

        # Get unique teams
        teams = set()
        for match in matches:
            teams.add(match.home_team)
            teams.add(match.away_team)
        teams = list(teams)

        # Initialize ratings
        n_teams = len(teams)
        team_to_idx = {team: i for i, team in enumerate(teams)}

        # Initial parameters: [attacks..., defenses..., home_adv, rho]
        # Attacks and defenses initialized to 1.0, home_adv to 0.25, rho to -0.1
        x0 = np.concatenate([
            np.ones(n_teams),      # attacks
            np.ones(n_teams),      # defenses
            [0.25],                # home advantage
            [-0.1]                 # rho
        ])

        def neg_log_likelihood(params):
            """Negative log-likelihood to minimize."""
            attacks = params[:n_teams]
            defenses = params[n_teams:2*n_teams]
            home_adv = params[2*n_teams]
            rho = params[2*n_teams + 1]

            # Constraint: average attack and defense should be 1
            attacks = attacks / np.mean(attacks)
            defenses = defenses / np.mean(defenses)

            log_lik = 0
            for match in matches:
                home_idx = team_to_idx[match.home_team]
                away_idx = team_to_idx[match.away_team]

                lambda_home = self.avg_goals * attacks[home_idx] * defenses[away_idx] * (1 + home_adv)
                lambda_away = self.avg_goals * attacks[away_idx] * defenses[home_idx]

                # Ensure positive lambdas
                lambda_home = max(0.1, lambda_home)
                lambda_away = max(0.1, lambda_away)

                prob = self._score_probability(
                    match.home_goals, match.away_goals,
                    lambda_home, lambda_away
                )

                # Weighted log-likelihood
                if prob > 0:
                    log_lik += match.weight * np.log(prob)

            return -log_lik

        # Optimize
        bounds = (
            [(0.1, 5.0)] * n_teams +  # attacks
            [(0.1, 5.0)] * n_teams +  # defenses
            [(0.0, 0.5)] +            # home advantage
            [(-0.3, 0.0)]             # rho (negative for positive correlation on low scores)
        )

        result = minimize(
            neg_log_likelihood,
            x0,
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': 1000}
        )

        # Extract fitted parameters
        attacks = result.x[:n_teams]
        defenses = result.x[n_teams:2*n_teams]

        # Normalize
        attacks = attacks / np.mean(attacks)
        defenses = defenses / np.mean(defenses)

        self.home_advantage = result.x[2*n_teams]
        self.rho = result.x[2*n_teams + 1]

        # Store team ratings
        self.teams = {}
        for team, idx in team_to_idx.items():
            self.teams[team] = TeamRatings(
                attack=attacks[idx],
                defense=defenses[idx]
            )

        self._fitted = True
        return self

    def predict_score_matrix(self, home_team: str, away_team: str) -> np.ndarray:
        """
        Predict full probability matrix for all scorelines.

        Returns:
            numpy array of shape (max_goals+1, max_goals+1)
            where matrix[i,j] = P(home scores i, away scores j)
        """
        lambda_home, lambda_away = self._get_lambdas(home_team, away_team)

        matrix = np.zeros((self.max_goals + 1, self.max_goals + 1))

        for home_goals in range(self.max_goals + 1):
            for away_goals in range(self.max_goals + 1):
                matrix[home_goals, away_goals] = self._score_probability(
                    home_goals, away_goals,
                    lambda_home, lambda_away
                )

        # Normalize to sum to 1
        matrix = matrix / matrix.sum()

        return matrix

    def predict_1x2(self, home_team: str, away_team: str) -> Dict[str, float]:
        """Predict home/draw/away probabilities."""
        matrix = self.predict_score_matrix(home_team, away_team)

        home_win = np.tril(matrix, k=-1).sum()  # Below diagonal
        draw = np.trace(matrix)                  # Diagonal
        away_win = np.triu(matrix, k=1).sum()   # Above diagonal

        return {
            'home_win': round(home_win, 4),
            'draw': round(draw, 4),
            'away_win': round(away_win, 4)
        }

    def predict_over_under(self, home_team: str, away_team: str, line: float = 2.5) -> Dict[str, float]:
        """Predict over/under probabilities for a given line."""
        matrix = self.predict_score_matrix(home_team, away_team)

        over = 0.0
        under = 0.0

        for home_goals in range(self.max_goals + 1):
            for away_goals in range(self.max_goals + 1):
                total = home_goals + away_goals
                if total > line:
                    over += matrix[home_goals, away_goals]
                elif total < line:
                    under += matrix[home_goals, away_goals]
                # Exactly on line = push (ignored)

        return {
            f'over_{line}': round(over, 4),
            f'under_{line}': round(under, 4)
        }

    def predict_btts(self, home_team: str, away_team: str) -> Dict[str, float]:
        """Predict Both Teams To Score probabilities."""
        matrix = self.predict_score_matrix(home_team, away_team)

        # BTTS Yes = exclude row 0 and column 0
        btts_yes = matrix[1:, 1:].sum()
        btts_no = 1 - btts_yes

        return {
            'btts_yes': round(btts_yes, 4),
            'btts_no': round(btts_no, 4)
        }

    def predict_exact_scores(self, home_team: str, away_team: str, top_n: int = 10) -> List[Dict]:
        """Get top N most likely exact scores."""
        matrix = self.predict_score_matrix(home_team, away_team)

        scores = []
        for home_goals in range(self.max_goals + 1):
            for away_goals in range(self.max_goals + 1):
                scores.append({
                    'score': f'{home_goals}-{away_goals}',
                    'home_goals': home_goals,
                    'away_goals': away_goals,
                    'probability': round(matrix[home_goals, away_goals], 4)
                })

        # Sort by probability descending
        scores.sort(key=lambda x: x['probability'], reverse=True)

        return scores[:top_n]

    def predict_asian_handicap(self, home_team: str, away_team: str, line: float) -> Dict[str, float]:
        """
        Predict Asian Handicap probabilities.

        Example: line = -1.5 means home team -1.5
        """
        matrix = self.predict_score_matrix(home_team, away_team)

        home_covers = 0.0
        away_covers = 0.0

        for home_goals in range(self.max_goals + 1):
            for away_goals in range(self.max_goals + 1):
                # Adjusted margin for home team
                margin = (home_goals - away_goals) + line

                if margin > 0:
                    home_covers += matrix[home_goals, away_goals]
                elif margin < 0:
                    away_covers += matrix[home_goals, away_goals]
                # margin == 0 is a push

        return {
            f'home_{line}': round(home_covers, 4),
            f'away_{-line}': round(away_covers, 4)
        }

    def predict_all_markets(self, home_team: str, away_team: str) -> Dict:
        """Generate predictions for all major betting markets."""
        matrix = self.predict_score_matrix(home_team, away_team)
        lambda_home, lambda_away = self._get_lambdas(home_team, away_team)

        return {
            'expected_goals': {
                'home': round(lambda_home, 2),
                'away': round(lambda_away, 2),
                'total': round(lambda_home + lambda_away, 2)
            },
            '1x2': self.predict_1x2(home_team, away_team),
            'over_under': {
                **self.predict_over_under(home_team, away_team, 1.5),
                **self.predict_over_under(home_team, away_team, 2.5),
                **self.predict_over_under(home_team, away_team, 3.5),
            },
            'btts': self.predict_btts(home_team, away_team),
            'asian_handicap': {
                **self.predict_asian_handicap(home_team, away_team, -0.5),
                **self.predict_asian_handicap(home_team, away_team, -1.5),
                **self.predict_asian_handicap(home_team, away_team, -2.5),
            },
            'exact_scores': self.predict_exact_scores(home_team, away_team, 10),
            'score_matrix': matrix.tolist()
        }

    def set_team_ratings(self, ratings: Dict[str, Dict[str, float]]):
        """
        Manually set team ratings (useful when not enough data to fit).

        Args:
            ratings: Dict of team_name -> {'attack': float, 'defense': float}
        """
        for team, values in ratings.items():
            self.teams[team] = TeamRatings(
                attack=values.get('attack', 1.0),
                defense=values.get('defense', 1.0)
            )
        self._fitted = True

    def get_team_ratings(self) -> Dict[str, Dict[str, float]]:
        """Get current team ratings."""
        return {
            team: {'attack': r.attack, 'defense': r.defense}
            for team, r in self.teams.items()
        }


# Pre-configured ratings for Ligue 1 teams (based on historical xG data)
LIGUE1_RATINGS = {
    'Paris Saint-Germain FC': {'attack': 1.85, 'defense': 0.65},
    'Paris Saint-Germain': {'attack': 1.85, 'defense': 0.65},
    'AS Monaco FC': {'attack': 1.35, 'defense': 0.85},
    'AS Monaco': {'attack': 1.35, 'defense': 0.85},
    'Olympique de Marseille': {'attack': 1.25, 'defense': 0.90},
    'Olympique Marseille': {'attack': 1.25, 'defense': 0.90},
    'Olympique Lyonnais': {'attack': 1.20, 'defense': 0.95},
    'Olympique Lyon': {'attack': 1.20, 'defense': 0.95},
    'LOSC Lille': {'attack': 1.10, 'defense': 0.88},
    'Lille OSC': {'attack': 1.10, 'defense': 0.88},
    'OGC Nice': {'attack': 1.05, 'defense': 0.92},
    'Stade Rennais FC 1901': {'attack': 1.08, 'defense': 0.95},
    'Stade Rennais': {'attack': 1.08, 'defense': 0.95},
    'RC Lens': {'attack': 1.02, 'defense': 0.90},
    'Racing Club de Lens': {'attack': 1.02, 'defense': 0.90},
    'Stade Brestois 29': {'attack': 1.00, 'defense': 1.00},
    'RC Strasbourg Alsace': {'attack': 0.95, 'defense': 1.05},
    'Toulouse FC': {'attack': 0.92, 'defense': 1.02},
    'FC Nantes': {'attack': 0.88, 'defense': 1.08},
    'Montpellier HSC': {'attack': 0.90, 'defense': 1.15},
    'Stade de Reims': {'attack': 0.85, 'defense': 0.98},
    'AJ Auxerre': {'attack': 0.82, 'defense': 1.12},
    'Angers SCO': {'attack': 0.80, 'defense': 1.10},
    'Le Havre AC': {'attack': 0.78, 'defense': 1.15},
    'AS Saint-Étienne': {'attack': 0.75, 'defense': 1.18},
    'FC Metz': {'attack': 0.80, 'defense': 1.12},
    'FC Lorient': {'attack': 0.82, 'defense': 1.08},
}


def get_dixon_coles_model() -> DixonColesModel:
    """Get a pre-configured Dixon-Coles model with Ligue 1 ratings."""
    model = DixonColesModel()
    model.set_team_ratings(LIGUE1_RATINGS)
    return model

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


# =============================================================================
# PRE-CONFIGURED RATINGS FOR ALL MAJOR EUROPEAN LEAGUES
# Based on xG data (attack = xG/avg, defense = xGA/avg, normalized)
# =============================================================================

# Ligue 1 (France)
LIGUE1_RATINGS = {
    # PSG variants
    'Paris Saint-Germain FC': {'attack': 1.638, 'defense': 0.572},
    'Paris Saint-Germain': {'attack': 1.638, 'defense': 0.572},
    'Paris Saint Germain': {'attack': 1.638, 'defense': 0.572},
    # Monaco variants
    'AS Monaco FC': {'attack': 1.395, 'defense': 0.742},
    'AS Monaco': {'attack': 1.395, 'defense': 0.742},
    # Marseille variants
    'Olympique de Marseille': {'attack': 1.331, 'defense': 0.866},
    'Olympique Marseille': {'attack': 1.331, 'defense': 0.866},
    'Marseille': {'attack': 1.331, 'defense': 0.866},
    # Lyon variants
    'Olympique Lyonnais': {'attack': 1.259, 'defense': 0.970},
    'Olympique Lyon': {'attack': 1.259, 'defense': 0.970},
    'Lyon': {'attack': 1.259, 'defense': 0.970},
    # Lille variants
    'LOSC Lille': {'attack': 1.156, 'defense': 0.731},
    'Lille OSC': {'attack': 1.156, 'defense': 0.731},
    'Lille': {'attack': 1.156, 'defense': 0.731},
    # Nice
    'OGC Nice': {'attack': 1.054, 'defense': 0.823},
    'Nice': {'attack': 1.054, 'defense': 0.823},
    # Lens
    'RC Lens': {'attack': 1.001, 'defense': 0.882},
    'Racing Club de Lens': {'attack': 1.001, 'defense': 0.882},
    'Lens': {'attack': 1.001, 'defense': 0.882},
    # Toulouse
    'Toulouse FC': {'attack': 0.971, 'defense': 0.955},
    'Toulouse': {'attack': 0.971, 'defense': 0.955},
    # Rennes
    'Stade Rennais FC 1901': {'attack': 0.960, 'defense': 1.145},
    'Stade Rennais FC': {'attack': 0.960, 'defense': 1.145},
    'Stade Rennais': {'attack': 0.960, 'defense': 1.145},
    'Rennes': {'attack': 0.960, 'defense': 1.145},
    # Strasbourg
    'RC Strasbourg Alsace': {'attack': 0.944, 'defense': 1.060},
    'RC Strasbourg': {'attack': 0.944, 'defense': 1.060},
    'Strasbourg': {'attack': 0.944, 'defense': 1.060},
    # Auxerre
    'AJ Auxerre': {'attack': 0.914, 'defense': 1.095},
    'Auxerre': {'attack': 0.914, 'defense': 1.095},
    # Reims
    'Stade de Reims': {'attack': 0.880, 'defense': 1.036},
    'Reims': {'attack': 0.880, 'defense': 1.036},
    # Brest
    'Stade Brestois 29': {'attack': 0.865, 'defense': 0.932},
    'Brest': {'attack': 0.865, 'defense': 0.932},
    # Nantes
    'FC Nantes': {'attack': 0.823, 'defense': 1.052},
    'Nantes': {'attack': 0.823, 'defense': 1.052},
    # Saint-Etienne
    'AS Saint-Étienne': {'attack': 0.728, 'defense': 1.307},
    'AS Saint-Etienne': {'attack': 0.728, 'defense': 1.307},
    'Saint-Etienne': {'attack': 0.728, 'defense': 1.307},
    # Montpellier
    'Montpellier HSC': {'attack': 0.717, 'defense': 1.361},
    'Montpellier': {'attack': 0.717, 'defense': 1.361},
    # Angers
    'Angers SCO': {'attack': 0.698, 'defense': 1.218},
    'SCO Angers': {'attack': 0.698, 'defense': 1.218},
    'Angers': {'attack': 0.698, 'defense': 1.218},
    # Le Havre
    'Le Havre AC': {'attack': 0.667, 'defense': 1.253},
    'Le Havre': {'attack': 0.667, 'defense': 1.253},
    # Metz (promotion/relegation)
    'FC Metz': {'attack': 0.80, 'defense': 1.12},
    'Metz': {'attack': 0.80, 'defense': 1.12},
    # Lorient (relegated but keeping for reference)
    'FC Lorient': {'attack': 0.82, 'defense': 1.08},
}

# Premier League (England)
PREMIER_LEAGUE_RATINGS = {
    # Manchester City
    'Manchester City FC': {'attack': 1.55, 'defense': 0.52},
    'Manchester City': {'attack': 1.55, 'defense': 0.52},
    'Man City': {'attack': 1.55, 'defense': 0.52},
    # Arsenal
    'Arsenal FC': {'attack': 1.42, 'defense': 0.58},
    'Arsenal': {'attack': 1.42, 'defense': 0.58},
    # Liverpool
    'Liverpool FC': {'attack': 1.48, 'defense': 0.55},
    'Liverpool': {'attack': 1.48, 'defense': 0.55},
    # Chelsea
    'Chelsea FC': {'attack': 1.18, 'defense': 0.78},
    'Chelsea': {'attack': 1.18, 'defense': 0.78},
    # Manchester United
    'Manchester United FC': {'attack': 1.12, 'defense': 0.88},
    'Manchester United': {'attack': 1.12, 'defense': 0.88},
    'Man Utd': {'attack': 1.12, 'defense': 0.88},
    # Tottenham
    'Tottenham Hotspur FC': {'attack': 1.22, 'defense': 0.82},
    'Tottenham Hotspur': {'attack': 1.22, 'defense': 0.82},
    'Tottenham': {'attack': 1.22, 'defense': 0.82},
    'Spurs': {'attack': 1.22, 'defense': 0.82},
    # Newcastle
    'Newcastle United FC': {'attack': 1.15, 'defense': 0.75},
    'Newcastle United': {'attack': 1.15, 'defense': 0.75},
    'Newcastle': {'attack': 1.15, 'defense': 0.75},
    # Aston Villa
    'Aston Villa FC': {'attack': 1.18, 'defense': 0.80},
    'Aston Villa': {'attack': 1.18, 'defense': 0.80},
    # Brighton
    'Brighton & Hove Albion FC': {'attack': 1.10, 'defense': 0.85},
    'Brighton & Hove Albion': {'attack': 1.10, 'defense': 0.85},
    'Brighton': {'attack': 1.10, 'defense': 0.85},
    # West Ham
    'West Ham United FC': {'attack': 1.02, 'defense': 0.95},
    'West Ham United': {'attack': 1.02, 'defense': 0.95},
    'West Ham': {'attack': 1.02, 'defense': 0.95},
    # Crystal Palace
    'Crystal Palace FC': {'attack': 0.92, 'defense': 1.05},
    'Crystal Palace': {'attack': 0.92, 'defense': 1.05},
    # Brentford
    'Brentford FC': {'attack': 1.05, 'defense': 0.98},
    'Brentford': {'attack': 1.05, 'defense': 0.98},
    # Fulham
    'Fulham FC': {'attack': 0.95, 'defense': 1.02},
    'Fulham': {'attack': 0.95, 'defense': 1.02},
    # Wolverhampton
    'Wolverhampton Wanderers FC': {'attack': 0.88, 'defense': 1.08},
    'Wolverhampton': {'attack': 0.88, 'defense': 1.08},
    'Wolves': {'attack': 0.88, 'defense': 1.08},
    # Bournemouth
    'AFC Bournemouth': {'attack': 0.92, 'defense': 1.12},
    'Bournemouth': {'attack': 0.92, 'defense': 1.12},
    # Nottingham Forest
    'Nottingham Forest FC': {'attack': 0.85, 'defense': 1.15},
    'Nottingham Forest': {'attack': 0.85, 'defense': 1.15},
    # Everton
    'Everton FC': {'attack': 0.78, 'defense': 1.18},
    'Everton': {'attack': 0.78, 'defense': 1.18},
    # Leicester
    'Leicester City FC': {'attack': 0.88, 'defense': 1.10},
    'Leicester City': {'attack': 0.88, 'defense': 1.10},
    'Leicester': {'attack': 0.88, 'defense': 1.10},
    # Ipswich
    'Ipswich Town FC': {'attack': 0.75, 'defense': 1.22},
    'Ipswich Town': {'attack': 0.75, 'defense': 1.22},
    'Ipswich': {'attack': 0.75, 'defense': 1.22},
    # Southampton
    'Southampton FC': {'attack': 0.72, 'defense': 1.28},
    'Southampton': {'attack': 0.72, 'defense': 1.28},
}

# La Liga (Spain)
LA_LIGA_RATINGS = {
    # Real Madrid
    'Real Madrid CF': {'attack': 1.52, 'defense': 0.55},
    'Real Madrid': {'attack': 1.52, 'defense': 0.55},
    # Barcelona
    'FC Barcelona': {'attack': 1.58, 'defense': 0.62},
    'Barcelona': {'attack': 1.58, 'defense': 0.62},
    # Atlético Madrid
    'Club Atlético de Madrid': {'attack': 1.15, 'defense': 0.68},
    'Atlético de Madrid': {'attack': 1.15, 'defense': 0.68},
    'Atlético Madrid': {'attack': 1.15, 'defense': 0.68},
    'Atletico Madrid': {'attack': 1.15, 'defense': 0.68},
    # Athletic Bilbao
    'Athletic Club': {'attack': 1.08, 'defense': 0.78},
    'Athletic Bilbao': {'attack': 1.08, 'defense': 0.78},
    # Real Sociedad
    'Real Sociedad de Fútbol': {'attack': 1.05, 'defense': 0.82},
    'Real Sociedad': {'attack': 1.05, 'defense': 0.82},
    # Villarreal
    'Villarreal CF': {'attack': 1.12, 'defense': 0.88},
    'Villarreal': {'attack': 1.12, 'defense': 0.88},
    # Real Betis
    'Real Betis Balompié': {'attack': 1.02, 'defense': 0.92},
    'Real Betis': {'attack': 1.02, 'defense': 0.92},
    'Betis': {'attack': 1.02, 'defense': 0.92},
    # Sevilla
    'Sevilla FC': {'attack': 0.95, 'defense': 0.95},
    'Sevilla': {'attack': 0.95, 'defense': 0.95},
    # Valencia
    'Valencia CF': {'attack': 0.88, 'defense': 1.05},
    'Valencia': {'attack': 0.88, 'defense': 1.05},
    # Girona
    'Girona FC': {'attack': 1.18, 'defense': 0.85},
    'Girona': {'attack': 1.18, 'defense': 0.85},
    # Celta Vigo
    'RC Celta de Vigo': {'attack': 0.92, 'defense': 1.08},
    'Celta de Vigo': {'attack': 0.92, 'defense': 1.08},
    'Celta': {'attack': 0.92, 'defense': 1.08},
    # Mallorca
    'RCD Mallorca': {'attack': 0.82, 'defense': 1.02},
    'Mallorca': {'attack': 0.82, 'defense': 1.02},
    # Rayo Vallecano
    'Rayo Vallecano de Madrid': {'attack': 0.85, 'defense': 1.05},
    'Rayo Vallecano': {'attack': 0.85, 'defense': 1.05},
    'Rayo': {'attack': 0.85, 'defense': 1.05},
    # Getafe
    'Getafe CF': {'attack': 0.75, 'defense': 0.95},
    'Getafe': {'attack': 0.75, 'defense': 0.95},
    # Osasuna
    'CA Osasuna': {'attack': 0.82, 'defense': 1.02},
    'Osasuna': {'attack': 0.82, 'defense': 1.02},
    # Las Palmas
    'UD Las Palmas': {'attack': 0.78, 'defense': 1.15},
    'Las Palmas': {'attack': 0.78, 'defense': 1.15},
    # Alavés
    'Deportivo Alavés': {'attack': 0.72, 'defense': 1.18},
    'Alavés': {'attack': 0.72, 'defense': 1.18},
    'Alaves': {'attack': 0.72, 'defense': 1.18},
    # Espanyol
    'RCD Espanyol de Barcelona': {'attack': 0.75, 'defense': 1.12},
    'RCD Espanyol': {'attack': 0.75, 'defense': 1.12},
    'Espanyol': {'attack': 0.75, 'defense': 1.12},
    # Leganés
    'CD Leganés': {'attack': 0.70, 'defense': 1.20},
    'Leganés': {'attack': 0.70, 'defense': 1.20},
    'Leganes': {'attack': 0.70, 'defense': 1.20},
    # Valladolid
    'Real Valladolid CF': {'attack': 0.68, 'defense': 1.25},
    'Real Valladolid': {'attack': 0.68, 'defense': 1.25},
    'Valladolid': {'attack': 0.68, 'defense': 1.25},
}

# Bundesliga (Germany)
BUNDESLIGA_RATINGS = {
    # Bayern Munich
    'FC Bayern München': {'attack': 1.55, 'defense': 0.58},
    'Bayern Munich': {'attack': 1.55, 'defense': 0.58},
    'Bayern München': {'attack': 1.55, 'defense': 0.58},
    'Bayern': {'attack': 1.55, 'defense': 0.58},
    # Bayer Leverkusen
    'Bayer 04 Leverkusen': {'attack': 1.48, 'defense': 0.52},
    'Bayer Leverkusen': {'attack': 1.48, 'defense': 0.52},
    'Leverkusen': {'attack': 1.48, 'defense': 0.52},
    # Borussia Dortmund
    'Borussia Dortmund': {'attack': 1.35, 'defense': 0.72},
    'Dortmund': {'attack': 1.35, 'defense': 0.72},
    'BVB': {'attack': 1.35, 'defense': 0.72},
    # RB Leipzig
    'RB Leipzig': {'attack': 1.28, 'defense': 0.75},
    'RasenBallsport Leipzig': {'attack': 1.28, 'defense': 0.75},
    'Leipzig': {'attack': 1.28, 'defense': 0.75},
    # Stuttgart
    'VfB Stuttgart': {'attack': 1.22, 'defense': 0.82},
    'Stuttgart': {'attack': 1.22, 'defense': 0.82},
    # Eintracht Frankfurt
    'Eintracht Frankfurt': {'attack': 1.15, 'defense': 0.88},
    'Frankfurt': {'attack': 1.15, 'defense': 0.88},
    # SC Freiburg
    'Sport-Club Freiburg': {'attack': 1.02, 'defense': 0.85},
    'SC Freiburg': {'attack': 1.02, 'defense': 0.85},
    'Freiburg': {'attack': 1.02, 'defense': 0.85},
    # Wolfsburg
    'VfL Wolfsburg': {'attack': 0.95, 'defense': 0.92},
    'Wolfsburg': {'attack': 0.95, 'defense': 0.92},
    # Mönchengladbach
    'Borussia Mönchengladbach': {'attack': 0.92, 'defense': 1.05},
    'Mönchengladbach': {'attack': 0.92, 'defense': 1.05},
    'Gladbach': {'attack': 0.92, 'defense': 1.05},
    # Union Berlin
    '1. FC Union Berlin': {'attack': 0.85, 'defense': 0.95},
    'Union Berlin': {'attack': 0.85, 'defense': 0.95},
    # Werder Bremen
    'SV Werder Bremen': {'attack': 0.88, 'defense': 1.02},
    'Werder Bremen': {'attack': 0.88, 'defense': 1.02},
    'Bremen': {'attack': 0.88, 'defense': 1.02},
    # Mainz
    '1. FSV Mainz 05': {'attack': 0.85, 'defense': 1.05},
    'Mainz 05': {'attack': 0.85, 'defense': 1.05},
    'Mainz': {'attack': 0.85, 'defense': 1.05},
    # Augsburg
    'FC Augsburg': {'attack': 0.82, 'defense': 1.08},
    'Augsburg': {'attack': 0.82, 'defense': 1.08},
    # Hoffenheim
    'TSG 1899 Hoffenheim': {'attack': 0.88, 'defense': 1.12},
    'TSG Hoffenheim': {'attack': 0.88, 'defense': 1.12},
    'Hoffenheim': {'attack': 0.88, 'defense': 1.12},
    # Heidenheim
    '1. FC Heidenheim 1846': {'attack': 0.78, 'defense': 1.08},
    '1. FC Heidenheim': {'attack': 0.78, 'defense': 1.08},
    'Heidenheim': {'attack': 0.78, 'defense': 1.08},
    # Bochum
    'VfL Bochum 1848': {'attack': 0.65, 'defense': 1.28},
    'VfL Bochum': {'attack': 0.65, 'defense': 1.28},
    'Bochum': {'attack': 0.65, 'defense': 1.28},
    # St. Pauli
    'FC St. Pauli 1910': {'attack': 0.72, 'defense': 1.15},
    'FC St. Pauli': {'attack': 0.72, 'defense': 1.15},
    'St. Pauli': {'attack': 0.72, 'defense': 1.15},
    # Holstein Kiel
    'Holstein Kiel': {'attack': 0.70, 'defense': 1.22},
    'Kiel': {'attack': 0.70, 'defense': 1.22},
}

# Serie A (Italy)
SERIE_A_RATINGS = {
    # Inter
    'FC Internazionale Milano': {'attack': 1.42, 'defense': 0.55},
    'Inter Milan': {'attack': 1.42, 'defense': 0.55},
    'Inter': {'attack': 1.42, 'defense': 0.55},
    # AC Milan
    'AC Milan': {'attack': 1.18, 'defense': 0.78},
    'Milan': {'attack': 1.18, 'defense': 0.78},
    # Juventus
    'Juventus FC': {'attack': 1.15, 'defense': 0.72},
    'Juventus': {'attack': 1.15, 'defense': 0.72},
    'Juve': {'attack': 1.15, 'defense': 0.72},
    # Napoli
    'SSC Napoli': {'attack': 1.25, 'defense': 0.68},
    'Napoli': {'attack': 1.25, 'defense': 0.68},
    # Atalanta
    'Atalanta BC': {'attack': 1.35, 'defense': 0.75},
    'Atalanta': {'attack': 1.35, 'defense': 0.75},
    # Roma
    'AS Roma': {'attack': 1.05, 'defense': 0.88},
    'Roma': {'attack': 1.05, 'defense': 0.88},
    # Lazio
    'SS Lazio': {'attack': 1.12, 'defense': 0.92},
    'Lazio': {'attack': 1.12, 'defense': 0.92},
    # Fiorentina
    'ACF Fiorentina': {'attack': 1.08, 'defense': 0.88},
    'Fiorentina': {'attack': 1.08, 'defense': 0.88},
    # Bologna
    'Bologna FC 1909': {'attack': 1.05, 'defense': 0.82},
    'Bologna FC': {'attack': 1.05, 'defense': 0.82},
    'Bologna': {'attack': 1.05, 'defense': 0.82},
    # Torino
    'Torino FC': {'attack': 0.92, 'defense': 0.95},
    'Torino': {'attack': 0.92, 'defense': 0.95},
    # Udinese
    'Udinese Calcio': {'attack': 0.88, 'defense': 1.02},
    'Udinese': {'attack': 0.88, 'defense': 1.02},
    # Genoa
    'Genoa CFC': {'attack': 0.82, 'defense': 1.08},
    'Genoa': {'attack': 0.82, 'defense': 1.08},
    # Cagliari
    'Cagliari Calcio': {'attack': 0.78, 'defense': 1.12},
    'Cagliari': {'attack': 0.78, 'defense': 1.12},
    # Verona
    'Hellas Verona FC': {'attack': 0.75, 'defense': 1.15},
    'Hellas Verona': {'attack': 0.75, 'defense': 1.15},
    'Verona': {'attack': 0.75, 'defense': 1.15},
    # Parma
    'Parma Calcio 1913': {'attack': 0.78, 'defense': 1.10},
    'Parma Calcio': {'attack': 0.78, 'defense': 1.10},
    'Parma': {'attack': 0.78, 'defense': 1.10},
    # Empoli
    'Empoli FC': {'attack': 0.72, 'defense': 1.05},
    'Empoli': {'attack': 0.72, 'defense': 1.05},
    # Como
    'Como 1907': {'attack': 0.70, 'defense': 1.18},
    'Como': {'attack': 0.70, 'defense': 1.18},
    # Lecce
    'US Lecce': {'attack': 0.68, 'defense': 1.15},
    'Lecce': {'attack': 0.68, 'defense': 1.15},
    # Venezia
    'Venezia FC': {'attack': 0.65, 'defense': 1.22},
    'Venezia': {'attack': 0.65, 'defense': 1.22},
    # Monza
    'AC Monza': {'attack': 0.72, 'defense': 1.08},
    'Monza': {'attack': 0.72, 'defense': 1.08},
}

# Combined ratings for all leagues
ALL_RATINGS = {
    **LIGUE1_RATINGS,
    **PREMIER_LEAGUE_RATINGS,
    **LA_LIGA_RATINGS,
    **BUNDESLIGA_RATINGS,
    **SERIE_A_RATINGS,
}


def get_dixon_coles_model(league: str = None) -> DixonColesModel:
    """
    Get a pre-configured Dixon-Coles model with ratings from xG data.

    Args:
        league: Optional league filter ('ligue_1', 'premier_league', 'la_liga', 'bundesliga', 'serie_a')
                If None, loads all leagues.

    Returns:
        Configured DixonColesModel instance
    """
    model = DixonColesModel()

    if league == "ligue_1":
        model.set_team_ratings(LIGUE1_RATINGS)
    elif league == "premier_league":
        model.set_team_ratings(PREMIER_LEAGUE_RATINGS)
    elif league == "la_liga":
        model.set_team_ratings(LA_LIGA_RATINGS)
    elif league == "bundesliga":
        model.set_team_ratings(BUNDESLIGA_RATINGS)
    elif league == "serie_a":
        model.set_team_ratings(SERIE_A_RATINGS)
    else:
        # Load all ratings
        model.set_team_ratings(ALL_RATINGS)

    return model


def get_team_rating(team_name: str) -> dict:
    """
    Get Dixon-Coles rating for a team by name (with fuzzy matching).

    Returns:
        Dict with 'attack' and 'defense' keys, or default values if not found.
    """
    # Direct lookup
    if team_name in ALL_RATINGS:
        return ALL_RATINGS[team_name]

    # Fuzzy matching
    team_lower = team_name.lower()
    for name, rating in ALL_RATINGS.items():
        if name.lower() in team_lower or team_lower in name.lower():
            return rating

    # Default rating for unknown teams
    return {'attack': 1.0, 'defense': 1.0}

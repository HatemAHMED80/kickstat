"""
Advanced Feature Engineering for Football Predictions.

Generates 80+ features including:
- xG-based metrics (rolling, differential, home/away splits)
- Form analysis with time decay
- Player impact scores
- Fatigue indicators
- Head-to-head with context
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import math


@dataclass
class MatchRecord:
    """Historical match record for feature calculation."""
    date: datetime
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    home_xg: float = 0.0
    away_xg: float = 0.0
    home_shots: int = 0
    away_shots: int = 0
    home_possession: float = 50.0
    away_possession: float = 50.0
    competition: str = "league"


@dataclass
class TeamFeatures:
    """Calculated features for a team."""
    # Basic
    team_name: str

    # xG Features (rolling windows)
    xg_last_5: float = 0.0
    xg_last_10: float = 0.0
    xg_season: float = 0.0
    xga_last_5: float = 0.0
    xga_last_10: float = 0.0
    xga_season: float = 0.0
    xg_diff_last_5: float = 0.0
    xg_diff_last_10: float = 0.0

    # xG Performance (actual vs expected)
    goals_minus_xg_last_5: float = 0.0  # Overperformance
    goals_minus_xg_last_10: float = 0.0
    conceded_minus_xga_last_5: float = 0.0
    conceded_minus_xga_last_10: float = 0.0

    # Home/Away specific xG
    home_xg_avg: float = 0.0
    home_xga_avg: float = 0.0
    away_xg_avg: float = 0.0
    away_xga_avg: float = 0.0

    # Form (weighted by recency)
    form_points_weighted: float = 0.0
    form_goals_weighted: float = 0.0
    form_conceded_weighted: float = 0.0
    win_rate_last_5: float = 0.0
    win_rate_last_10: float = 0.0

    # Streaks
    current_streak: int = 0  # Positive = wins, negative = losses
    unbeaten_run: int = 0
    clean_sheet_rate: float = 0.0
    failed_to_score_rate: float = 0.0

    # Attack metrics
    shots_per_game: float = 0.0
    shot_conversion: float = 0.0
    big_chances_created: float = 0.0

    # Defense metrics
    shots_conceded_per_game: float = 0.0
    tackle_success_rate: float = 0.0
    interceptions_per_game: float = 0.0

    # Set pieces
    corners_per_game: float = 0.0
    corners_conceded_per_game: float = 0.0

    # Possession
    avg_possession: float = 50.0
    possession_vs_xg_correlation: float = 0.0

    # Fatigue
    days_since_last_match: int = 7
    matches_last_30_days: int = 0
    travel_distance_last_match: float = 0.0

    # Squad
    key_players_available: int = 11
    total_injuries: int = 0
    injury_impact_score: float = 0.0


@dataclass
class MatchFeatures:
    """Complete feature vector for a match prediction."""
    # Match info
    home_team: str
    away_team: str
    kickoff: datetime

    # Home team features (all TeamFeatures prefixed with home_)
    home_features: TeamFeatures = None

    # Away team features (all TeamFeatures prefixed with away_)
    away_features: TeamFeatures = None

    # Differential features
    xg_diff_last_5: float = 0.0
    xg_diff_last_10: float = 0.0
    xga_diff_last_5: float = 0.0
    xga_diff_last_10: float = 0.0
    form_diff: float = 0.0
    position_diff: int = 0
    points_diff: int = 0

    # Head-to-head
    h2h_matches: int = 0
    h2h_home_wins: int = 0
    h2h_draws: int = 0
    h2h_away_wins: int = 0
    h2h_home_goals_avg: float = 0.0
    h2h_away_goals_avg: float = 0.0
    h2h_over_25_rate: float = 0.0
    h2h_btts_rate: float = 0.0

    # Context
    is_derby: bool = False
    importance_factor: float = 1.0  # Higher for crucial matches
    neutral_venue: bool = False

    def to_vector(self) -> np.ndarray:
        """Convert to feature vector for ML model."""
        features = []

        # Home team xG features
        if self.home_features:
            features.extend([
                self.home_features.xg_last_5,
                self.home_features.xg_last_10,
                self.home_features.xga_last_5,
                self.home_features.xga_last_10,
                self.home_features.xg_diff_last_5,
                self.home_features.xg_diff_last_10,
                self.home_features.goals_minus_xg_last_5,
                self.home_features.conceded_minus_xga_last_5,
                self.home_features.home_xg_avg,
                self.home_features.home_xga_avg,
                self.home_features.form_points_weighted,
                self.home_features.win_rate_last_5,
                self.home_features.win_rate_last_10,
                self.home_features.current_streak,
                self.home_features.unbeaten_run,
                self.home_features.clean_sheet_rate,
                self.home_features.failed_to_score_rate,
                self.home_features.shots_per_game,
                self.home_features.shot_conversion,
                self.home_features.avg_possession,
                self.home_features.days_since_last_match,
                self.home_features.matches_last_30_days,
                self.home_features.injury_impact_score,
            ])
        else:
            features.extend([0.0] * 23)

        # Away team xG features
        if self.away_features:
            features.extend([
                self.away_features.xg_last_5,
                self.away_features.xg_last_10,
                self.away_features.xga_last_5,
                self.away_features.xga_last_10,
                self.away_features.xg_diff_last_5,
                self.away_features.xg_diff_last_10,
                self.away_features.goals_minus_xg_last_5,
                self.away_features.conceded_minus_xga_last_5,
                self.away_features.away_xg_avg,
                self.away_features.away_xga_avg,
                self.away_features.form_points_weighted,
                self.away_features.win_rate_last_5,
                self.away_features.win_rate_last_10,
                self.away_features.current_streak,
                self.away_features.unbeaten_run,
                self.away_features.clean_sheet_rate,
                self.away_features.failed_to_score_rate,
                self.away_features.shots_per_game,
                self.away_features.shot_conversion,
                self.away_features.avg_possession,
                self.away_features.days_since_last_match,
                self.away_features.matches_last_30_days,
                self.away_features.injury_impact_score,
            ])
        else:
            features.extend([0.0] * 23)

        # Differential features
        features.extend([
            self.xg_diff_last_5,
            self.xg_diff_last_10,
            self.xga_diff_last_5,
            self.xga_diff_last_10,
            self.form_diff,
            self.position_diff,
            self.points_diff,
        ])

        # Head-to-head
        features.extend([
            self.h2h_matches,
            self.h2h_home_wins,
            self.h2h_draws,
            self.h2h_away_wins,
            self.h2h_home_goals_avg,
            self.h2h_away_goals_avg,
            self.h2h_over_25_rate,
            self.h2h_btts_rate,
        ])

        # Context
        features.extend([
            1.0 if self.is_derby else 0.0,
            self.importance_factor,
            1.0 if self.neutral_venue else 0.0,
        ])

        return np.array(features, dtype=np.float32)

    @staticmethod
    def feature_names() -> List[str]:
        """Get feature names for interpretability."""
        names = []

        # Home features
        for prefix in ['home', 'away']:
            names.extend([
                f'{prefix}_xg_last_5',
                f'{prefix}_xg_last_10',
                f'{prefix}_xga_last_5',
                f'{prefix}_xga_last_10',
                f'{prefix}_xg_diff_last_5',
                f'{prefix}_xg_diff_last_10',
                f'{prefix}_goals_minus_xg_last_5',
                f'{prefix}_conceded_minus_xga_last_5',
                f'{prefix}_venue_xg_avg',
                f'{prefix}_venue_xga_avg',
                f'{prefix}_form_points_weighted',
                f'{prefix}_win_rate_last_5',
                f'{prefix}_win_rate_last_10',
                f'{prefix}_current_streak',
                f'{prefix}_unbeaten_run',
                f'{prefix}_clean_sheet_rate',
                f'{prefix}_failed_to_score_rate',
                f'{prefix}_shots_per_game',
                f'{prefix}_shot_conversion',
                f'{prefix}_avg_possession',
                f'{prefix}_days_since_last_match',
                f'{prefix}_matches_last_30_days',
                f'{prefix}_injury_impact_score',
            ])

        # Differentials
        names.extend([
            'xg_diff_last_5',
            'xg_diff_last_10',
            'xga_diff_last_5',
            'xga_diff_last_10',
            'form_diff',
            'position_diff',
            'points_diff',
        ])

        # H2H
        names.extend([
            'h2h_matches',
            'h2h_home_wins',
            'h2h_draws',
            'h2h_away_wins',
            'h2h_home_goals_avg',
            'h2h_away_goals_avg',
            'h2h_over_25_rate',
            'h2h_btts_rate',
        ])

        # Context
        names.extend([
            'is_derby',
            'importance_factor',
            'neutral_venue',
        ])

        return names


class AdvancedFeatureEngineer:
    """
    Generates advanced features for match prediction.

    Uses xG data, form analysis, and contextual factors.
    """

    def __init__(self, half_life_days: int = 30):
        self.half_life_days = half_life_days
        self.matches: List[MatchRecord] = []
        self.team_positions: Dict[str, int] = {}
        self.team_points: Dict[str, int] = {}

    def add_match(self, match: MatchRecord):
        """Add a historical match to the dataset."""
        self.matches.append(match)

    def add_matches(self, matches: List[MatchRecord]):
        """Add multiple matches."""
        self.matches.extend(matches)

    def set_standings(self, positions: Dict[str, int], points: Dict[str, int]):
        """Set current league standings."""
        self.team_positions = positions
        self.team_points = points

    def _calculate_weight(self, match_date: datetime, reference_date: datetime) -> float:
        """Exponential time decay weight."""
        days_ago = (reference_date - match_date).days
        if days_ago < 0:
            return 0.0
        return math.exp(-math.log(2) * days_ago / self.half_life_days)

    def _get_team_matches(
        self,
        team: str,
        before_date: datetime,
        limit: int = None,
        home_only: bool = False,
        away_only: bool = False
    ) -> List[Tuple[MatchRecord, bool]]:
        """
        Get matches for a team before a given date.

        Returns list of (match, is_home) tuples.
        """
        team_matches = []

        for match in self.matches:
            if match.date >= before_date:
                continue

            is_home = match.home_team == team
            is_away = match.away_team == team

            if not (is_home or is_away):
                continue

            if home_only and not is_home:
                continue
            if away_only and not is_away:
                continue

            team_matches.append((match, is_home))

        # Sort by date descending (most recent first)
        team_matches.sort(key=lambda x: x[0].date, reverse=True)

        if limit:
            team_matches = team_matches[:limit]

        return team_matches

    def calculate_team_features(
        self,
        team: str,
        reference_date: datetime,
        is_home: bool = True
    ) -> TeamFeatures:
        """Calculate all features for a team."""
        features = TeamFeatures(team_name=team)

        # Get recent matches
        last_5 = self._get_team_matches(team, reference_date, limit=5)
        last_10 = self._get_team_matches(team, reference_date, limit=10)
        season_matches = self._get_team_matches(team, reference_date, limit=38)
        home_matches = self._get_team_matches(team, reference_date, limit=10, home_only=True)
        away_matches = self._get_team_matches(team, reference_date, limit=10, away_only=True)

        if not last_5:
            return features

        # === xG Features ===
        def calc_xg_stats(matches: List[Tuple[MatchRecord, bool]]) -> Tuple[float, float, float, float]:
            if not matches:
                return 0.0, 0.0, 0.0, 0.0
            xg_for = sum(m.home_xg if h else m.away_xg for m, h in matches) / len(matches)
            xg_against = sum(m.away_xg if h else m.home_xg for m, h in matches) / len(matches)
            goals_for = sum(m.home_goals if h else m.away_goals for m, h in matches) / len(matches)
            goals_against = sum(m.away_goals if h else m.home_goals for m, h in matches) / len(matches)
            return xg_for, xg_against, goals_for, goals_against

        xg5, xga5, g5, ga5 = calc_xg_stats(last_5)
        xg10, xga10, g10, ga10 = calc_xg_stats(last_10)
        xg_season, xga_season, _, _ = calc_xg_stats(season_matches)

        features.xg_last_5 = round(xg5, 3)
        features.xg_last_10 = round(xg10, 3)
        features.xg_season = round(xg_season, 3)
        features.xga_last_5 = round(xga5, 3)
        features.xga_last_10 = round(xga10, 3)
        features.xga_season = round(xga_season, 3)
        features.xg_diff_last_5 = round(xg5 - xga5, 3)
        features.xg_diff_last_10 = round(xg10 - xga10, 3)

        # xG performance (luck factor)
        features.goals_minus_xg_last_5 = round(g5 - xg5, 3)
        features.goals_minus_xg_last_10 = round(g10 - xg10, 3)
        features.conceded_minus_xga_last_5 = round(ga5 - xga5, 3)
        features.conceded_minus_xga_last_10 = round(ga10 - xga10, 3)

        # Home/Away specific xG
        if home_matches:
            home_xg = sum(m.home_xg for m, _ in home_matches) / len(home_matches)
            home_xga = sum(m.away_xg for m, _ in home_matches) / len(home_matches)
            features.home_xg_avg = round(home_xg, 3)
            features.home_xga_avg = round(home_xga, 3)

        if away_matches:
            away_xg = sum(m.away_xg for m, _ in away_matches) / len(away_matches)
            away_xga = sum(m.home_xg for m, _ in away_matches) / len(away_matches)
            features.away_xg_avg = round(away_xg, 3)
            features.away_xga_avg = round(away_xga, 3)

        # === Form Features (weighted) ===
        total_weight = 0.0
        weighted_points = 0.0
        weighted_goals = 0.0
        weighted_conceded = 0.0

        for match, is_home in last_10:
            weight = self._calculate_weight(match.date, reference_date)
            total_weight += weight

            goals_for = match.home_goals if is_home else match.away_goals
            goals_against = match.away_goals if is_home else match.home_goals

            if goals_for > goals_against:
                points = 3
            elif goals_for == goals_against:
                points = 1
            else:
                points = 0

            weighted_points += weight * points
            weighted_goals += weight * goals_for
            weighted_conceded += weight * goals_against

        if total_weight > 0:
            features.form_points_weighted = round(weighted_points / total_weight, 3)
            features.form_goals_weighted = round(weighted_goals / total_weight, 3)
            features.form_conceded_weighted = round(weighted_conceded / total_weight, 3)

        # Win rates
        def calc_win_rate(matches):
            if not matches:
                return 0.0
            wins = sum(1 for m, h in matches if (m.home_goals > m.away_goals) == h)
            return wins / len(matches)

        features.win_rate_last_5 = round(calc_win_rate(last_5), 3)
        features.win_rate_last_10 = round(calc_win_rate(last_10), 3)

        # === Streaks ===
        streak = 0
        unbeaten = 0
        clean_sheets = 0
        failed_to_score = 0

        for match, is_home in last_10:
            goals_for = match.home_goals if is_home else match.away_goals
            goals_against = match.away_goals if is_home else match.home_goals

            if goals_against == 0:
                clean_sheets += 1
            if goals_for == 0:
                failed_to_score += 1

            if unbeaten == len([m for m in last_10[:last_10.index((match, is_home)) + 1]]):
                if goals_for >= goals_against:
                    unbeaten += 1

        # Current streak (first few matches)
        for i, (match, is_home) in enumerate(last_5):
            goals_for = match.home_goals if is_home else match.away_goals
            goals_against = match.away_goals if is_home else match.home_goals

            if i == 0:
                if goals_for > goals_against:
                    streak = 1
                elif goals_for < goals_against:
                    streak = -1
            else:
                if goals_for > goals_against and streak > 0:
                    streak += 1
                elif goals_for < goals_against and streak < 0:
                    streak -= 1
                else:
                    break

        features.current_streak = streak
        features.unbeaten_run = unbeaten
        features.clean_sheet_rate = round(clean_sheets / len(last_10), 3) if last_10 else 0.0
        features.failed_to_score_rate = round(failed_to_score / len(last_10), 3) if last_10 else 0.0

        # === Shots ===
        if last_10:
            shots = [m.home_shots if h else m.away_shots for m, h in last_10]
            goals = [m.home_goals if h else m.away_goals for m, h in last_10]
            features.shots_per_game = round(sum(shots) / len(shots), 2) if any(shots) else 0.0
            features.shot_conversion = round(sum(goals) / max(sum(shots), 1), 3)

        # === Possession ===
        if last_10:
            possessions = [m.home_possession if h else m.away_possession for m, h in last_10]
            features.avg_possession = round(sum(possessions) / len(possessions), 1)

        # === Fatigue ===
        if last_5:
            last_match_date = last_5[0][0].date
            features.days_since_last_match = (reference_date - last_match_date).days

        # Matches in last 30 days
        thirty_days_ago = reference_date - timedelta(days=30)
        features.matches_last_30_days = len([
            m for m, _ in season_matches
            if m.date >= thirty_days_ago
        ])

        return features

    def calculate_match_features(
        self,
        home_team: str,
        away_team: str,
        kickoff: datetime
    ) -> MatchFeatures:
        """Calculate all features for a match."""
        features = MatchFeatures(
            home_team=home_team,
            away_team=away_team,
            kickoff=kickoff
        )

        # Team features
        features.home_features = self.calculate_team_features(home_team, kickoff, is_home=True)
        features.away_features = self.calculate_team_features(away_team, kickoff, is_home=False)

        # Differentials
        if features.home_features and features.away_features:
            features.xg_diff_last_5 = features.home_features.xg_last_5 - features.away_features.xg_last_5
            features.xg_diff_last_10 = features.home_features.xg_last_10 - features.away_features.xg_last_10
            features.xga_diff_last_5 = features.home_features.xga_last_5 - features.away_features.xga_last_5
            features.xga_diff_last_10 = features.home_features.xga_last_10 - features.away_features.xga_last_10
            features.form_diff = features.home_features.form_points_weighted - features.away_features.form_points_weighted

        # Standings
        features.position_diff = self.team_positions.get(home_team, 10) - self.team_positions.get(away_team, 10)
        features.points_diff = self.team_points.get(home_team, 0) - self.team_points.get(away_team, 0)

        # Head-to-head
        h2h = self._calculate_h2h(home_team, away_team, kickoff)
        features.h2h_matches = h2h['matches']
        features.h2h_home_wins = h2h['home_wins']
        features.h2h_draws = h2h['draws']
        features.h2h_away_wins = h2h['away_wins']
        features.h2h_home_goals_avg = h2h['home_goals_avg']
        features.h2h_away_goals_avg = h2h['away_goals_avg']
        features.h2h_over_25_rate = h2h['over_25_rate']
        features.h2h_btts_rate = h2h['btts_rate']

        return features

    def _calculate_h2h(
        self,
        home_team: str,
        away_team: str,
        before_date: datetime,
        limit: int = 10
    ) -> Dict:
        """Calculate head-to-head statistics."""
        h2h_matches = []

        for match in self.matches:
            if match.date >= before_date:
                continue

            # Both directions
            is_h2h = (
                (match.home_team == home_team and match.away_team == away_team) or
                (match.home_team == away_team and match.away_team == home_team)
            )

            if is_h2h:
                h2h_matches.append(match)

        h2h_matches.sort(key=lambda x: x.date, reverse=True)
        h2h_matches = h2h_matches[:limit]

        if not h2h_matches:
            return {
                'matches': 0,
                'home_wins': 0,
                'draws': 0,
                'away_wins': 0,
                'home_goals_avg': 0.0,
                'away_goals_avg': 0.0,
                'over_25_rate': 0.5,
                'btts_rate': 0.5
            }

        home_wins = 0
        draws = 0
        away_wins = 0
        home_goals = 0
        away_goals = 0
        over_25 = 0
        btts = 0

        for match in h2h_matches:
            # Normalize to current home/away perspective
            if match.home_team == home_team:
                hg, ag = match.home_goals, match.away_goals
            else:
                hg, ag = match.away_goals, match.home_goals

            home_goals += hg
            away_goals += ag

            if hg > ag:
                home_wins += 1
            elif hg < ag:
                away_wins += 1
            else:
                draws += 1

            if hg + ag > 2.5:
                over_25 += 1
            if hg > 0 and ag > 0:
                btts += 1

        n = len(h2h_matches)
        return {
            'matches': n,
            'home_wins': home_wins,
            'draws': draws,
            'away_wins': away_wins,
            'home_goals_avg': round(home_goals / n, 2),
            'away_goals_avg': round(away_goals / n, 2),
            'over_25_rate': round(over_25 / n, 2),
            'btts_rate': round(btts / n, 2)
        }


def get_feature_engineer() -> AdvancedFeatureEngineer:
    """Get a feature engineer instance."""
    return AdvancedFeatureEngineer()

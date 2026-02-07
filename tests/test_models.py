"""Tests for prediction models."""

import numpy as np
import pytest
from datetime import datetime, timedelta

from src.models.dixon_coles import DixonColesModel, MatchResult
from src.models.elo import EloRating, EloMatch


def _make_matches(n: int = 200) -> list[MatchResult]:
    """Generate synthetic match data for testing."""
    np.random.seed(42)
    teams = [f"Team_{i}" for i in range(10)]
    matches = []
    base_date = datetime(2024, 1, 1)

    for i in range(n):
        home = teams[i % len(teams)]
        away = teams[(i + 3) % len(teams)]
        if home == away:
            away = teams[(i + 5) % len(teams)]
        matches.append(MatchResult(
            home_team=home,
            away_team=away,
            home_goals=int(np.random.poisson(1.4)),
            away_goals=int(np.random.poisson(1.1)),
            date=base_date + timedelta(days=i),
        ))
    return matches


class TestDixonColes:
    def test_fit_convergence(self):
        """Model should converge on synthetic data."""
        model = DixonColesModel()
        matches = _make_matches(200)
        model.fit(matches)
        assert model.is_fitted
        assert model._convergence_info == "converged"

    def test_fit_too_few_matches(self):
        """Should raise on insufficient data."""
        model = DixonColesModel()
        with pytest.raises(ValueError, match="Need >= 50"):
            model.fit(_make_matches(30))

    def test_predictions_sum_to_one(self):
        """1X2 probabilities must sum to 1."""
        model = DixonColesModel()
        model.fit(_make_matches(200))
        pred = model.predict("Team_0", "Team_1")
        total = pred.home_win + pred.draw + pred.away_win
        assert total == pytest.approx(1.0, abs=1e-4)

    def test_score_matrix_valid(self):
        """Score matrix should be valid probability distribution."""
        model = DixonColesModel()
        model.fit(_make_matches(200))
        pred = model.predict("Team_0", "Team_1")
        assert pred.score_matrix.sum() == pytest.approx(1.0, abs=1e-4)
        assert (pred.score_matrix >= 0).all()

    def test_btts_consistent(self):
        """BTTS yes + no should equal 1."""
        model = DixonColesModel()
        model.fit(_make_matches(200))
        pred = model.predict("Team_0", "Team_1")
        assert pred.btts_yes + pred.btts_no == pytest.approx(1.0, abs=1e-4)

    def test_over_under_ordering(self):
        """Over 1.5 >= Over 2.5 >= Over 3.5."""
        model = DixonColesModel()
        model.fit(_make_matches(200))
        pred = model.predict("Team_0", "Team_1")
        assert pred.over_15 >= pred.over_25 >= pred.over_35

    def test_unknown_team_fallback(self):
        """Unknown teams should use default ratings."""
        model = DixonColesModel()
        model.fit(_make_matches(200))
        pred = model.predict("Unknown_FC", "Team_0")
        assert 0 < pred.home_win < 1
        assert 0 < pred.draw < 1


class TestElo:
    def test_initial_rating(self):
        """New teams should start at 1500."""
        elo = EloRating()
        assert elo.get_rating("New_Team") == 1500

    def test_winner_gains_rating(self):
        """Winner should gain ELO points."""
        elo = EloRating()
        elo.update(EloMatch("A", "B", 3, 0))
        assert elo.get_rating("A") > 1500
        assert elo.get_rating("B") < 1500

    def test_draw_minimal_change(self):
        """Draw between equal teams should cause minimal change."""
        elo = EloRating()
        elo.update(EloMatch("A", "B", 1, 1))
        # Home team expected to win slightly, so draw = slight loss for home
        assert abs(elo.get_rating("A") - 1500) < 20

    def test_predict_1x2_sums_to_one(self):
        """1X2 predictions must sum to 1."""
        elo = EloRating()
        elo.ratings = {"A": 1600, "B": 1400}
        pred = elo.predict_1x2("A", "B")
        total = pred["home"] + pred["draw"] + pred["away"]
        assert total == pytest.approx(1.0, abs=1e-4)

    def test_stronger_team_favored(self):
        """Higher-rated team should be predicted to win more often."""
        elo = EloRating()
        elo.ratings = {"Strong": 1700, "Weak": 1300}
        pred = elo.predict_1x2("Strong", "Weak")
        assert pred["home"] > pred["away"]

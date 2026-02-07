"""Walk-forward backtesting for football prediction models.

The only honest way to evaluate a prediction model:
train on past, predict future, never peek ahead.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
from loguru import logger

from ..models.dixon_coles import DixonColesModel, MatchResult
from ..models.elo import EloRating, EloMatch
from ..models.ensemble import EnsemblePredictor
from .calibration import evaluate, CalibrationReport


@dataclass
class BettingResult:
    """Result of a single simulated bet."""

    match_date: datetime
    home_team: str
    away_team: str
    market: str               # "home", "draw", "away", "over25", "btts"
    model_prob: float
    fair_bookmaker_prob: float  # After margin removal
    edge_pct: float
    best_odds: float
    actual_outcome: str       # "home", "draw", "away"
    won: bool
    pnl: float                # Profit/loss on unit stake


@dataclass
class BacktestReport:
    """Full backtest results."""

    calibration: CalibrationReport
    total_matches: int
    total_edges_found: int
    betting_results: list[BettingResult] = field(repr=False)

    @property
    def roi(self) -> float:
        if not self.betting_results:
            return 0.0
        total_pnl = sum(b.pnl for b in self.betting_results)
        return total_pnl / len(self.betting_results)

    @property
    def win_rate(self) -> float:
        if not self.betting_results:
            return 0.0
        wins = sum(1 for b in self.betting_results if b.won)
        return wins / len(self.betting_results)

    @property
    def avg_edge(self) -> float:
        if not self.betting_results:
            return 0.0
        return float(np.mean([b.edge_pct for b in self.betting_results]))

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "BACKTEST RESULTS",
            "=" * 60,
            self.calibration.summary(),
            f"Matches predicted: {self.total_matches}",
            f"Edges found (>5%): {self.total_edges_found}",
            f"Bets simulated:    {len(self.betting_results)}",
            f"Win rate:          {self.win_rate:.1%}",
            f"Average edge:      {self.avg_edge:.1f}%",
            f"ROI (flat stake):  {self.roi:.1%}",
            "=" * 60,
        ]

        # GO/NO-GO
        go = (
            self.calibration.is_acceptable
            and self.roi > -0.02
            and len(self.betting_results) >= 100
        )
        lines.append(f"GO/NO-GO: {'GO' if go else 'NO-GO'}")
        if not go:
            if not self.calibration.is_acceptable:
                lines.append("  - Calibration below threshold")
            if self.roi <= -0.02:
                lines.append(f"  - ROI too low ({self.roi:.1%})")
            if len(self.betting_results) < 100:
                lines.append(f"  - Insufficient sample ({len(self.betting_results)} bets)")

        return "\n".join(lines)


class WalkForwardBacktest:
    """Walk-forward backtesting engine.

    For each matchday:
    1. Train model on ALL matches before that matchday
    2. Predict upcoming matches
    3. Compare predictions to bookmaker odds
    4. Record results after match finishes
    """

    def __init__(
        self,
        min_training_matches: int = 100,
        min_edge_pct: float = 5.0,
        dc_weight: float = 0.65,
        elo_weight: float = 0.35,
    ):
        self.min_training = min_training_matches
        self.min_edge = min_edge_pct
        self.dc_weight = dc_weight
        self.elo_weight = elo_weight

    def run(
        self,
        all_matches: list[dict],
        odds_data: Optional[dict] = None,
    ) -> BacktestReport:
        """Run walk-forward backtest.

        Args:
            all_matches: List of match dicts with keys:
                home_team, away_team, home_score, away_score, kickoff, matchday
            odds_data: Optional dict mapping match_key to odds dict with
                home_odds, draw_odds, away_odds (for edge calculation)

        Returns:
            BacktestReport with full results.
        """
        # Sort by date
        matches = sorted(all_matches, key=lambda m: m["kickoff"])
        n = len(matches)
        logger.info(f"Starting walk-forward backtest on {n} matches")

        all_probs = []
        all_outcomes = []
        betting_results = []
        edges_found = 0

        for i in range(self.min_training, n):
            # Training data: everything before this match
            train_matches = matches[:i]
            test_match = matches[i]

            # Build training MatchResults for Dixon-Coles
            dc_train = [
                MatchResult(
                    home_team=m["home_team"],
                    away_team=m["away_team"],
                    home_goals=m["home_score"],
                    away_goals=m["away_score"],
                    date=datetime.fromisoformat(m["kickoff"].replace("Z", "+00:00"))
                    if isinstance(m["kickoff"], str)
                    else m["kickoff"],
                )
                for m in train_matches
            ]

            # Fit Dixon-Coles
            dc = DixonColesModel()
            try:
                dc.fit(dc_train)
            except ValueError as e:
                continue

            # Fit ELO
            elo = EloRating()
            for m in train_matches:
                elo.update(EloMatch(
                    home_team=m["home_team"],
                    away_team=m["away_team"],
                    home_goals=m["home_score"],
                    away_goals=m["away_score"],
                ))

            # Predict
            ensemble = EnsemblePredictor(dc, elo, self.dc_weight, self.elo_weight)
            pred = ensemble.predict(test_match["home_team"], test_match["away_team"])

            # Record prediction
            probs = np.array([pred.home_prob, pred.draw_prob, pred.away_prob])
            all_probs.append(probs)

            # Actual outcome
            hs, as_ = test_match["home_score"], test_match["away_score"]
            if hs > as_:
                outcome = 0  # home win
            elif hs == as_:
                outcome = 1  # draw
            else:
                outcome = 2  # away win
            all_outcomes.append(outcome)

            # Edge calculation (if odds available)
            match_key = f"{test_match['home_team']}_vs_{test_match['away_team']}"
            if odds_data and match_key in odds_data:
                odds = odds_data[match_key]
                from ..data.odds_api import remove_margin

                fair = remove_margin(
                    odds.get("home_odds", 0),
                    odds.get("draw_odds", 0),
                    odds.get("away_odds", 0),
                )

                markets = [
                    ("home", pred.home_prob, fair["home"], odds.get("home_odds", 0)),
                    ("draw", pred.draw_prob, fair["draw"], odds.get("draw_odds", 0)),
                    ("away", pred.away_prob, fair["away"], odds.get("away_odds", 0)),
                ]

                for market_name, model_p, fair_p, best_odds in markets:
                    if fair_p <= 0:
                        continue
                    edge = ((model_p - fair_p) / fair_p) * 100

                    if edge >= self.min_edge:
                        edges_found += 1
                        won = (
                            (market_name == "home" and outcome == 0)
                            or (market_name == "draw" and outcome == 1)
                            or (market_name == "away" and outcome == 2)
                        )
                        pnl = (best_odds - 1.0) if won else -1.0

                        betting_results.append(BettingResult(
                            match_date=datetime.fromisoformat(
                                test_match["kickoff"].replace("Z", "+00:00")
                            ) if isinstance(test_match["kickoff"], str)
                            else test_match["kickoff"],
                            home_team=test_match["home_team"],
                            away_team=test_match["away_team"],
                            market=market_name,
                            model_prob=model_p,
                            fair_bookmaker_prob=fair_p,
                            edge_pct=edge,
                            best_odds=best_odds,
                            actual_outcome=["home", "draw", "away"][outcome],
                            won=won,
                            pnl=pnl,
                        ))

        # Calibration report
        if len(all_probs) < 10:
            raise ValueError(f"Too few predictions ({len(all_probs)}) for evaluation")

        probs_array = np.array(all_probs)
        outcomes_array = np.array(all_outcomes)
        calibration = evaluate(probs_array, outcomes_array)

        report = BacktestReport(
            calibration=calibration,
            total_matches=len(all_probs),
            total_edges_found=edges_found,
            betting_results=betting_results,
        )

        logger.info(report.summary())
        return report

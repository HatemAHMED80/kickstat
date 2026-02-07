"""
Closing Line Value (CLV) Tracker.

Tracks and analyzes the edge between our predictions and market closing lines.
CLV is the gold standard for measuring betting model quality.

A positive CLV means you're consistently beating the market's final assessment.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from loguru import logger


@dataclass
class BetRecord:
    """Record of a bet placed."""
    match_id: int
    match_date: datetime
    home_team: str
    away_team: str
    market: str  # '1x2_home', '1x2_draw', '1x2_away', 'over_25', 'under_25', 'btts_yes', 'btts_no'
    selection: str  # What was bet on

    # Our prediction
    model_probability: float
    model_odds: float  # Fair odds from model = 1/prob

    # Odds when bet was placed
    opening_odds: float
    bet_odds: float
    stake: float

    # Closing line (when available)
    closing_odds: float = None
    closing_probability: float = None

    # Result
    won: bool = None
    profit: float = None

    # CLV metrics (calculated after closing line is known)
    clv_percentage: float = None  # (bet_odds - closing_odds) / closing_odds * 100
    edge_vs_closing: float = None  # model_prob - closing_prob

    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def calculate_clv(self):
        """Calculate CLV once closing odds are available."""
        if self.closing_odds and self.bet_odds:
            # CLV = (bet_odds - closing_odds) / closing_odds * 100
            self.clv_percentage = (self.bet_odds - self.closing_odds) / self.closing_odds * 100

            # Implied probability comparison
            self.closing_probability = 1 / self.closing_odds
            self.edge_vs_closing = self.model_probability - self.closing_probability

    def calculate_result(self, outcome: bool):
        """Calculate result after match is finished."""
        self.won = outcome
        if outcome:
            self.profit = self.stake * (self.bet_odds - 1)
        else:
            self.profit = -self.stake


@dataclass
class CLVStats:
    """Aggregated CLV statistics."""
    period: str  # 'daily', 'weekly', 'monthly', 'all_time'
    start_date: datetime
    end_date: datetime

    # Volume
    total_bets: int
    total_stake: float

    # CLV metrics
    avg_clv: float  # Average CLV percentage
    positive_clv_rate: float  # % of bets with positive CLV
    total_clv_units: float  # Sum of CLV * stake

    # Performance
    win_rate: float
    total_profit: float
    roi: float  # Return on investment

    # By market
    clv_by_market: Dict[str, float]
    profit_by_market: Dict[str, float]

    # Model quality
    brier_score: float = None  # Lower is better
    log_loss: float = None


class CLVTracker:
    """
    Tracks and analyzes Closing Line Value.

    CLV is the most important metric for long-term profitability:
    - Positive CLV = beating the market
    - Consistent +EV even when losing streaks occur
    """

    def __init__(self, storage_path: str = "data/clv"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.bets: List[BetRecord] = []
        self._load_history()

    def _load_history(self):
        """Load betting history from storage."""
        history_file = self.storage_path / "bet_history.json"
        if history_file.exists():
            try:
                with open(history_file) as f:
                    data = json.load(f)
                    for item in data:
                        item['match_date'] = datetime.fromisoformat(item['match_date'])
                        item['created_at'] = datetime.fromisoformat(item['created_at'])
                        self.bets.append(BetRecord(**item))
                logger.info(f"Loaded {len(self.bets)} historical bets")
            except Exception as e:
                logger.error(f"Failed to load bet history: {e}")

    def _save_history(self):
        """Save betting history to storage."""
        history_file = self.storage_path / "bet_history.json"
        try:
            data = []
            for bet in self.bets:
                d = asdict(bet)
                d['match_date'] = bet.match_date.isoformat()
                d['created_at'] = bet.created_at.isoformat()
                data.append(d)

            with open(history_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save bet history: {e}")

    def record_bet(
        self,
        match_id: int,
        match_date: datetime,
        home_team: str,
        away_team: str,
        market: str,
        selection: str,
        model_probability: float,
        bet_odds: float,
        stake: float,
        opening_odds: float = None
    ) -> BetRecord:
        """Record a new bet."""
        bet = BetRecord(
            match_id=match_id,
            match_date=match_date,
            home_team=home_team,
            away_team=away_team,
            market=market,
            selection=selection,
            model_probability=model_probability,
            model_odds=1 / model_probability if model_probability > 0 else 100,
            opening_odds=opening_odds or bet_odds,
            bet_odds=bet_odds,
            stake=stake
        )

        self.bets.append(bet)
        self._save_history()

        logger.info(
            f"Recorded bet: {home_team} vs {away_team} | "
            f"{market} @ {bet_odds} | Model: {model_probability:.1%}"
        )

        return bet

    def update_closing_odds(self, match_id: int, market: str, closing_odds: float):
        """Update closing odds for a bet."""
        for bet in self.bets:
            if bet.match_id == match_id and bet.market == market:
                bet.closing_odds = closing_odds
                bet.calculate_clv()

                logger.info(
                    f"Updated CLV for match {match_id} {market}: "
                    f"Bet @ {bet.bet_odds} → Close @ {closing_odds} = "
                    f"CLV {bet.clv_percentage:+.2f}%"
                )

        self._save_history()

    def update_result(self, match_id: int, market: str, won: bool):
        """Update bet result after match."""
        for bet in self.bets:
            if bet.match_id == match_id and bet.market == market:
                bet.calculate_result(won)

        self._save_history()

    def get_stats(
        self,
        period: str = 'all_time',
        market: str = None
    ) -> CLVStats:
        """Calculate CLV statistics for a period."""
        now = datetime.now()

        # Filter by period
        if period == 'daily':
            start_date = now - timedelta(days=1)
        elif period == 'weekly':
            start_date = now - timedelta(weeks=1)
        elif period == 'monthly':
            start_date = now - timedelta(days=30)
        elif period == 'yearly':
            start_date = now - timedelta(days=365)
        else:
            start_date = datetime.min

        filtered_bets = [
            b for b in self.bets
            if b.match_date >= start_date
            and (market is None or b.market == market)
        ]

        if not filtered_bets:
            return CLVStats(
                period=period,
                start_date=start_date,
                end_date=now,
                total_bets=0,
                total_stake=0,
                avg_clv=0,
                positive_clv_rate=0,
                total_clv_units=0,
                win_rate=0,
                total_profit=0,
                roi=0,
                clv_by_market={},
                profit_by_market={}
            )

        # Calculate stats
        total_stake = sum(b.stake for b in filtered_bets)

        # CLV stats (only for bets with closing odds)
        clv_bets = [b for b in filtered_bets if b.clv_percentage is not None]
        if clv_bets:
            avg_clv = sum(b.clv_percentage for b in clv_bets) / len(clv_bets)
            positive_clv_rate = sum(1 for b in clv_bets if b.clv_percentage > 0) / len(clv_bets)
            total_clv_units = sum(b.clv_percentage * b.stake / 100 for b in clv_bets)
        else:
            avg_clv = 0
            positive_clv_rate = 0
            total_clv_units = 0

        # Results stats (only for settled bets)
        settled_bets = [b for b in filtered_bets if b.won is not None]
        if settled_bets:
            win_rate = sum(1 for b in settled_bets if b.won) / len(settled_bets)
            total_profit = sum(b.profit for b in settled_bets)
            roi = total_profit / sum(b.stake for b in settled_bets) * 100
        else:
            win_rate = 0
            total_profit = 0
            roi = 0

        # By market breakdown
        clv_by_market = {}
        profit_by_market = {}

        markets = set(b.market for b in filtered_bets)
        for m in markets:
            market_bets = [b for b in clv_bets if b.market == m]
            if market_bets:
                clv_by_market[m] = sum(b.clv_percentage for b in market_bets) / len(market_bets)

            settled_market = [b for b in settled_bets if b.market == m]
            if settled_market:
                profit_by_market[m] = sum(b.profit for b in settled_market)

        return CLVStats(
            period=period,
            start_date=start_date,
            end_date=now,
            total_bets=len(filtered_bets),
            total_stake=total_stake,
            avg_clv=avg_clv,
            positive_clv_rate=positive_clv_rate,
            total_clv_units=total_clv_units,
            win_rate=win_rate,
            total_profit=total_profit,
            roi=roi,
            clv_by_market=clv_by_market,
            profit_by_market=profit_by_market
        )

    def get_recent_bets(self, limit: int = 20) -> List[BetRecord]:
        """Get most recent bets."""
        return sorted(self.bets, key=lambda b: b.created_at, reverse=True)[:limit]

    def calculate_expected_roi(self) -> float:
        """
        Calculate expected ROI based on CLV.

        Rule of thumb: 1% CLV ≈ 1% ROI long-term
        """
        stats = self.get_stats('all_time')
        return stats.avg_clv

    def generate_report(self) -> Dict:
        """Generate comprehensive CLV report."""
        all_time = self.get_stats('all_time')
        monthly = self.get_stats('monthly')
        weekly = self.get_stats('weekly')

        return {
            'summary': {
                'total_bets': all_time.total_bets,
                'total_staked': all_time.total_stake,
                'total_profit': all_time.total_profit,
                'roi': all_time.roi,
                'avg_clv': all_time.avg_clv,
                'expected_long_term_roi': self.calculate_expected_roi()
            },
            'periods': {
                'all_time': asdict(all_time),
                'monthly': asdict(monthly),
                'weekly': asdict(weekly)
            },
            'by_market': all_time.clv_by_market,
            'recent_bets': [asdict(b) for b in self.get_recent_bets(10)],
            'assessment': self._assess_performance(all_time)
        }

    def _assess_performance(self, stats: CLVStats) -> Dict:
        """Assess model performance based on CLV."""
        if stats.total_bets < 100:
            confidence = 'low'
            message = "Need more bets for reliable assessment (min 100)"
        else:
            confidence = 'high'

            if stats.avg_clv > 3:
                message = "Excellent edge - model is significantly beating the market"
            elif stats.avg_clv > 1:
                message = "Good edge - model is profitable long-term"
            elif stats.avg_clv > 0:
                message = "Slight edge - marginal profitability expected"
            elif stats.avg_clv > -1:
                message = "Break-even - no significant edge detected"
            else:
                message = "Negative edge - model is underperforming the market"

        return {
            'confidence': confidence,
            'message': message,
            'avg_clv': stats.avg_clv,
            'sample_size': stats.total_bets,
            'profitable': stats.avg_clv > 0
        }


# Singleton
_tracker: Optional[CLVTracker] = None


def get_clv_tracker() -> CLVTracker:
    """Get CLV tracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = CLVTracker()
    return _tracker

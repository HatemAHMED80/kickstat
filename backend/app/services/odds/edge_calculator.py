"""
Edge Calculator Service

Calculates the edge (advantage) between model probabilities and bookmaker odds.
This is the core logic that powers Kickstat's value detection.
"""

from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.database import (
    Match,
    Prediction,
    MatchOdds,
    EdgeCalculation,
)


# Risk level thresholds
RISK_THRESHOLDS = {
    "safe": {"min_prob": 55, "min_edge": 5},
    "medium": {"min_prob": 25, "max_prob": 55, "min_edge": 5},
    "risky": {"max_prob": 25, "min_edge": 8},
}


class EdgeCalculator:
    """
    Calculate betting edges by comparing model probabilities with bookmaker odds.

    The edge represents how much the market undervalues a particular outcome.
    A positive edge means the true probability is higher than what the odds suggest.
    """

    def calculate_implied_probability(self, decimal_odds: float) -> float:
        """
        Convert decimal odds to implied probability.

        Args:
            decimal_odds: Decimal odds (e.g., 2.00 for even money)

        Returns:
            Implied probability as a percentage (0-100)
        """
        if decimal_odds <= 1:
            return 100.0
        return (1 / decimal_odds) * 100

    def calculate_edge(
        self, model_prob: float, bookmaker_prob: float
    ) -> float:
        """
        Calculate the edge percentage.

        Edge = (model_prob - bookmaker_prob) / bookmaker_prob * 100

        A positive edge means the model thinks the outcome is more likely
        than the bookmaker does - this is where value exists.

        Args:
            model_prob: Model's probability (0-100)
            bookmaker_prob: Bookmaker's implied probability (0-100)

        Returns:
            Edge as a percentage (can be negative)
        """
        if bookmaker_prob <= 0:
            return 0.0

        edge = ((model_prob - bookmaker_prob) / bookmaker_prob) * 100
        return round(edge, 2)

    def calculate_kelly_stake(
        self,
        model_prob: float,
        decimal_odds: float,
        fraction: float = 0.25,
    ) -> float:
        """
        Calculate recommended stake using Kelly Criterion.

        The Kelly formula: f* = (bp - q) / b
        where:
        - b = decimal odds - 1
        - p = probability of winning
        - q = probability of losing (1 - p)

        We use fractional Kelly (default 25%) to reduce variance.

        Args:
            model_prob: Model's probability (0-100)
            decimal_odds: Decimal odds
            fraction: Fraction of Kelly to use (default 0.25 = quarter Kelly)

        Returns:
            Recommended stake as fraction of bankroll (0-1)
        """
        if decimal_odds <= 1 or model_prob <= 0:
            return 0.0

        p = model_prob / 100
        q = 1 - p
        b = decimal_odds - 1

        kelly = (b * p - q) / b

        # Apply fractional Kelly and cap at 10% max
        stake = max(0, min(kelly * fraction, 0.10))

        return round(stake, 4)

    def classify_risk(self, model_prob: float, edge: float) -> str:
        """
        Classify the risk level of an opportunity.

        Args:
            model_prob: Model's probability (0-100)
            edge: Edge percentage

        Returns:
            Risk level: "safe", "medium", or "risky"
        """
        if model_prob >= RISK_THRESHOLDS["safe"]["min_prob"] and edge >= RISK_THRESHOLDS["safe"]["min_edge"]:
            return "safe"
        elif model_prob >= RISK_THRESHOLDS["medium"]["min_prob"] and edge >= RISK_THRESHOLDS["medium"]["min_edge"]:
            return "medium"
        else:
            return "risky"

    def calculate_confidence(self, model_prob: float, edge: float) -> float:
        """
        Calculate a confidence score for the opportunity.

        Higher probability + higher edge = higher confidence.

        Args:
            model_prob: Model's probability (0-100)
            edge: Edge percentage

        Returns:
            Confidence score (0-100)
        """
        # Base confidence from probability (40% weight)
        prob_score = model_prob * 0.4

        # Edge contribution (60% weight, capped at 30% edge)
        edge_score = min(edge, 30) / 30 * 60

        confidence = prob_score + edge_score
        return round(min(confidence, 100), 1)

    def find_edges_for_match(
        self,
        db: Session,
        match: Match,
        prediction: Prediction,
        min_edge: float = 5.0,
    ) -> list[EdgeCalculation]:
        """
        Find all betting edges for a match.

        Compares model probabilities against all available bookmaker odds.

        Args:
            db: Database session
            match: The match to analyze
            prediction: The model's prediction for this match
            min_edge: Minimum edge to consider (default 5%)

        Returns:
            List of EdgeCalculation objects for edges above threshold
        """
        # Get all odds for this match
        odds_list = (
            db.query(MatchOdds)
            .filter(MatchOdds.match_id == match.id)
            .all()
        )

        if not odds_list:
            logger.debug(f"No odds found for match {match.id}")
            return []

        edges = []

        # Check 1X2 markets
        markets = [
            ("1x2_home", prediction.home_win_prob, "home_win_odds"),
            ("1x2_draw", prediction.draw_prob, "draw_odds"),
            ("1x2_away", prediction.away_win_prob, "away_win_odds"),
        ]

        for market, model_prob, odds_field in markets:
            best_edge = self._find_best_edge_for_market(
                odds_list, market, model_prob, odds_field, min_edge
            )
            if best_edge:
                best_edge.match_id = match.id
                best_edge.prediction_id = prediction.id
                edges.append(best_edge)

        # TODO: Add over/under, BTTS markets when predictions support them

        return edges

    def _find_best_edge_for_market(
        self,
        odds_list: list[MatchOdds],
        market: str,
        model_prob: float,
        odds_field: str,
        min_edge: float,
    ) -> Optional[EdgeCalculation]:
        """
        Find the best edge for a specific market across all bookmakers.

        Args:
            odds_list: List of MatchOdds from different bookmakers
            market: Market identifier (e.g., "1x2_home")
            model_prob: Model's probability for this outcome
            odds_field: Field name in MatchOdds (e.g., "home_win_odds")
            min_edge: Minimum edge threshold

        Returns:
            EdgeCalculation if edge found, None otherwise
        """
        best_edge = None
        best_edge_pct = min_edge

        for odds in odds_list:
            decimal_odds = getattr(odds, odds_field)
            if not decimal_odds or decimal_odds <= 1:
                continue

            bookmaker_prob = self.calculate_implied_probability(decimal_odds)
            edge = self.calculate_edge(model_prob, bookmaker_prob)

            if edge >= best_edge_pct:
                best_edge_pct = edge
                best_edge = EdgeCalculation(
                    market=market,
                    model_probability=model_prob,
                    bookmaker_probability=bookmaker_prob,
                    edge_percentage=edge,
                    best_odds=decimal_odds,
                    bookmaker_name=odds.bookmaker,
                    risk_level=self.classify_risk(model_prob, edge),
                    kelly_stake=self.calculate_kelly_stake(model_prob, decimal_odds),
                    confidence=self.calculate_confidence(model_prob, edge),
                    calculated_at=datetime.utcnow(),
                )

        return best_edge

    def calculate_and_store_edges(
        self,
        db: Session,
        match: Match,
        prediction: Prediction,
        min_edge: float = 5.0,
    ) -> list[EdgeCalculation]:
        """
        Calculate edges for a match and store them in the database.

        Args:
            db: Database session
            match: The match to analyze
            prediction: The model's prediction
            min_edge: Minimum edge threshold

        Returns:
            List of stored EdgeCalculation objects
        """
        # Delete existing edges for this match
        db.query(EdgeCalculation).filter(
            EdgeCalculation.match_id == match.id
        ).delete()

        # Calculate new edges
        edges = self.find_edges_for_match(db, match, prediction, min_edge)

        # Store in database
        for edge in edges:
            db.add(edge)

        db.commit()

        # Refresh to get IDs
        for edge in edges:
            db.refresh(edge)

        logger.info(f"Calculated {len(edges)} edges for match {match.id}")
        return edges

    def get_top_opportunities(
        self,
        db: Session,
        limit: int = 20,
        min_edge: float = 5.0,
        risk_level: Optional[str] = None,
    ) -> list[EdgeCalculation]:
        """
        Get the top betting opportunities across all upcoming matches.

        Args:
            db: Database session
            limit: Maximum number of opportunities to return
            min_edge: Minimum edge percentage
            risk_level: Filter by risk level ("safe", "medium", "risky")

        Returns:
            List of EdgeCalculation objects sorted by edge
        """
        query = (
            db.query(EdgeCalculation)
            .join(Match)
            .filter(
                EdgeCalculation.edge_percentage >= min_edge,
                Match.status == "scheduled",
                Match.kickoff > datetime.utcnow(),
            )
        )

        if risk_level:
            query = query.filter(EdgeCalculation.risk_level == risk_level)

        opportunities = (
            query
            .order_by(EdgeCalculation.edge_percentage.desc())
            .limit(limit)
            .all()
        )

        return opportunities


# Singleton instance
_edge_calculator: Optional[EdgeCalculator] = None


def get_edge_calculator() -> EdgeCalculator:
    """Get or create the EdgeCalculator singleton."""
    global _edge_calculator
    if _edge_calculator is None:
        _edge_calculator = EdgeCalculator()
    return _edge_calculator

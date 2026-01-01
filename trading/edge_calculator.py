"""
Edge Calculator - Detects trading opportunities.

"Edge" is the difference between what we think something is worth
(fair price) and what the market is offering (market price).

Example:
- We calculate Team 1 has 60% chance to win (fair price = 0.60)
- Market is selling Team 1 YES shares at 0.55
- Edge = 0.60 - 0.55 = 0.05 (5 cents or 5%)
- This is a BUY opportunity!

The edge calculator:
1. Compares fair price vs market price
2. Determines if edge exceeds our minimum threshold
3. Recommends BUY or SELL
4. Calculates confidence in the signal
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from config.settings import get_config
from core import OrderSide, TradingSignal, MarketPrice, ProbabilityEstimate

logger = logging.getLogger(__name__)
config = get_config()


@dataclass
class EdgeOpportunity:
    """
    Represents a detected trading opportunity.
    
    Attributes:
        has_edge: Whether there's a tradeable edge
        side: BUY or SELL recommendation
        edge: Size of the edge (e.g., 0.05 = 5%)
        fair_price: Our calculated fair price
        market_price: Current market price
        confidence: How confident we are (0 to 1)
        reason: Human-readable explanation
    """
    has_edge: bool
    side: Optional[OrderSide]
    edge: float
    fair_price: float
    market_price: float
    confidence: float
    reason: str


class EdgeCalculator:
    """
    Calculates trading edge and generates signals.
    
    Usage:
        calculator = EdgeCalculator()
        
        # Check for opportunity
        opportunity = calculator.calculate_edge(
            fair_price=0.60,
            market_bid=0.54,
            market_ask=0.56
        )
        
        if opportunity.has_edge:
            print(f"Trade: {opportunity.side} with {opportunity.edge:.1%} edge")
    """
    
    def __init__(self):
        """Initialize the edge calculator."""
        # Minimum edge required to trade (from config)
        self.min_edge = config.trading.min_edge
        
        # Additional safety margin for slippage
        self.slippage_buffer = 0.005  # 0.5%
        
        logger.debug(f"EdgeCalculator initialized with min_edge={self.min_edge}")
    
    def calculate_edge(
        self,
        fair_price: float,
        market_bid: float,
        market_ask: float,
        confidence: float = 0.7
    ) -> EdgeOpportunity:
        """
        Calculate if there's a trading edge.
        
        Args:
            fair_price: Our calculated fair price (0 to 1)
            market_bid: Best bid price (what we can sell at)
            market_ask: Best ask price (what we can buy at)
            confidence: Confidence in our fair price estimate
            
        Returns:
            EdgeOpportunity with trade recommendation
        """
        # Validate inputs
        if not (0 < fair_price < 1):
            return EdgeOpportunity(
                has_edge=False,
                side=None,
                edge=0,
                fair_price=fair_price,
                market_price=(market_bid + market_ask) / 2,
                confidence=0,
                reason="Invalid fair price"
            )
        
        # Calculate edges for both directions
        # BUY edge: fair price - ask price (buy at ask, expect value at fair)
        buy_edge = fair_price - market_ask
        
        # SELL edge: bid price - fair price (sell at bid, expect value at fair)
        sell_edge = market_bid - fair_price
        
        # Determine best opportunity
        if buy_edge > sell_edge and buy_edge > 0:
            # BUY opportunity
            edge = buy_edge
            side = OrderSide.BUY
            market_price = market_ask
            
        elif sell_edge > buy_edge and sell_edge > 0:
            # SELL opportunity
            edge = sell_edge
            side = OrderSide.SELL
            market_price = market_bid
            
        else:
            # No edge
            return EdgeOpportunity(
                has_edge=False,
                side=None,
                edge=max(buy_edge, sell_edge),
                fair_price=fair_price,
                market_price=(market_bid + market_ask) / 2,
                confidence=confidence,
                reason="No positive edge"
            )
        
        # Adjust edge for confidence
        # Lower confidence = we need more edge to justify trade
        adjusted_min_edge = self.min_edge / confidence
        
        # Check if edge exceeds minimum
        if edge < adjusted_min_edge:
            return EdgeOpportunity(
                has_edge=False,
                side=side,
                edge=edge,
                fair_price=fair_price,
                market_price=market_price,
                confidence=confidence,
                reason=f"Edge {edge:.3f} below minimum {adjusted_min_edge:.3f}"
            )
        
        # Check if edge exceeds slippage buffer
        if edge < self.slippage_buffer:
            return EdgeOpportunity(
                has_edge=False,
                side=side,
                edge=edge,
                fair_price=fair_price,
                market_price=market_price,
                confidence=confidence,
                reason=f"Edge {edge:.3f} below slippage buffer {self.slippage_buffer:.3f}"
            )
        
        # We have a tradeable edge!
        reason = (
            f"{side.value} opportunity: fair={fair_price:.3f}, "
            f"market={market_price:.3f}, edge={edge:.3f} ({edge*100:.1f}%)"
        )
        
        logger.info(f"Edge detected: {reason}")
        
        return EdgeOpportunity(
            has_edge=True,
            side=side,
            edge=edge,
            fair_price=fair_price,
            market_price=market_price,
            confidence=confidence,
            reason=reason
        )
    
    def calculate_edge_simple(
        self,
        fair_price: float,
        market_price: float,
        confidence: float = 0.7
    ) -> EdgeOpportunity:
        """
        Simplified edge calculation using single market price.
        
        Assumes we can both buy and sell at market_price (no spread).
        Use this for quick calculations or when spread is negligible.
        
        Args:
            fair_price: Our calculated fair price
            market_price: Current market mid-price
            confidence: Confidence in our estimate
            
        Returns:
            EdgeOpportunity with trade recommendation
        """
        # Use market price for both bid and ask (no spread)
        return self.calculate_edge(
            fair_price=fair_price,
            market_bid=market_price,
            market_ask=market_price,
            confidence=confidence
        )
    
    def create_trading_signal(
        self,
        match_id: str,
        opportunity: EdgeOpportunity,
        recommended_size: float = 0.0
    ) -> TradingSignal:
        """
        Create a TradingSignal from an EdgeOpportunity.
        
        Args:
            match_id: The match identifier
            opportunity: The detected opportunity
            recommended_size: Recommended position size
            
        Returns:
            TradingSignal object
        """
        return TradingSignal(
            timestamp=datetime.now(),
            match_id=match_id,
            fair_price=opportunity.fair_price,
            market_price=opportunity.market_price,
            edge=opportunity.edge,
            side=opportunity.side,
            recommended_size=recommended_size,
            confidence=opportunity.confidence
        )
    
    def get_edge_quality(self, edge: float) -> str:
        """
        Categorize the quality of an edge.
        
        Args:
            edge: The edge value
            
        Returns:
            Quality category string
        """
        if edge < 0.01:
            return "none"
        elif edge < 0.02:
            return "marginal"
        elif edge < 0.03:
            return "decent"
        elif edge < 0.05:
            return "good"
        elif edge < 0.08:
            return "great"
        else:
            return "exceptional"
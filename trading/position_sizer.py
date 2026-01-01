"""
Position Sizer - Determines optimal bet size using Kelly Criterion.

The Kelly Criterion is a formula that calculates the optimal bet size
to maximize long-term growth while managing risk.

Formula: f* = (bp - q) / b

Where:
- f* = fraction of bankroll to bet
- b = odds received (decimal - 1)
- p = probability of winning
- q = probability of losing (1 - p)

Example:
- We think Team 1 has 60% chance to win (p = 0.6)
- Market is offering 2.0 decimal odds (b = 1.0)
- Kelly fraction = (1.0 * 0.6 - 0.4) / 1.0 = 0.2 (20%)

We use "fractional Kelly" (typically 1/4 Kelly) for safety,
because the full Kelly can be too aggressive.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from config.settings import get_config

logger = logging.getLogger(__name__)
config = get_config()


@dataclass
class PositionSize:
    """
    Recommended position size.
    
    Attributes:
        size_dollars: Dollar amount to bet
        size_shares: Number of shares to buy/sell
        size_percent: Percentage of bankroll
        kelly_fraction: Full Kelly percentage
        is_valid: Whether the size is valid (non-zero)
        reason: Explanation of the calculation
    """
    size_dollars: float
    size_shares: float
    size_percent: float
    kelly_fraction: float
    is_valid: bool
    reason: str


class PositionSizer:
    """
    Calculates optimal position sizes using Kelly Criterion.
    
    Usage:
        sizer = PositionSizer(bankroll=1000.0)
        
        size = sizer.calculate_kelly_size(
            win_probability=0.60,
            odds=2.0,  # Decimal odds
            confidence=0.8
        )
        
        print(f"Bet ${size.size_dollars:.2f}")
    """
    
    def __init__(self, bankroll: float = None):
        """
        Initialize the position sizer.
        
        Args:
            bankroll: Starting bankroll in dollars.
                     If None, uses config default.
        """
        self.bankroll = bankroll or config.trading.initial_bankroll
        
        # Kelly fraction (use fractional Kelly for safety)
        self.kelly_multiplier = config.trading.kelly_fraction  # e.g., 0.25 for quarter Kelly
        
        # Maximum bet as percentage of bankroll
        self.max_bet_percent = config.trading.max_stake_percent  # e.g., 0.05 for 5%
        
        # Minimum bet size
        self.min_bet_dollars = config.trading.min_trade_size  # e.g., $5
        
        # Maximum position (number of shares)
        self.max_position = config.trading.max_position  # e.g., 100 shares
        
        logger.debug(
            f"PositionSizer initialized: bankroll=${self.bankroll:.2f}, "
            f"kelly_mult={self.kelly_multiplier}, max_bet={self.max_bet_percent:.0%}"
        )
    
    def update_bankroll(self, new_bankroll: float):
        """Update the current bankroll."""
        self.bankroll = new_bankroll
        logger.debug(f"Bankroll updated to ${self.bankroll:.2f}")
    
    def calculate_kelly_size(
        self,
        win_probability: float,
        odds: float,
        confidence: float = 1.0,
        current_position: float = 0.0
    ) -> PositionSize:
        """
        Calculate position size using Kelly Criterion.
        
        Args:
            win_probability: Probability of winning (0 to 1)
            odds: Decimal odds offered (e.g., 2.0 means 2x payout)
            confidence: Confidence in our probability estimate (0 to 1)
            current_position: Current position size in shares
            
        Returns:
            PositionSize with recommended bet
        """
        # Validate inputs
        if not (0 < win_probability < 1):
            return PositionSize(
                size_dollars=0,
                size_shares=0,
                size_percent=0,
                kelly_fraction=0,
                is_valid=False,
                reason=f"Invalid win probability: {win_probability}"
            )
        
        if odds <= 1:
            return PositionSize(
                size_dollars=0,
                size_shares=0,
                size_percent=0,
                kelly_fraction=0,
                is_valid=False,
                reason=f"Invalid odds: {odds} (must be > 1)"
            )
        
        # Calculate Kelly fraction
        # f* = (bp - q) / b
        # where b = odds - 1, p = win_prob, q = 1 - p
        b = odds - 1  # Net odds
        p = win_probability
        q = 1 - p
        
        kelly_full = (b * p - q) / b
        
        # If Kelly is negative, don't bet
        if kelly_full <= 0:
            return PositionSize(
                size_dollars=0,
                size_shares=0,
                size_percent=0,
                kelly_fraction=kelly_full,
                is_valid=False,
                reason=f"Negative edge (Kelly={kelly_full:.3f})"
            )
        
        # Apply Kelly multiplier (fractional Kelly)
        kelly_adjusted = kelly_full * self.kelly_multiplier
        
        # Apply confidence adjustment
        # Lower confidence = smaller bet
        kelly_adjusted *= confidence
        
        # Cap at maximum bet percentage
        bet_percent = min(kelly_adjusted, self.max_bet_percent)
        
        # Calculate dollar amount
        bet_dollars = self.bankroll * bet_percent
        
        # Apply minimum bet
        if bet_dollars < self.min_bet_dollars:
            return PositionSize(
                size_dollars=0,
                size_shares=0,
                size_percent=0,
                kelly_fraction=kelly_full,
                is_valid=False,
                reason=f"Bet ${bet_dollars:.2f} below minimum ${self.min_bet_dollars:.2f}"
            )
        
        # Calculate shares (price is implicitly in the odds)
        # For prediction markets, price = 1/odds for the winning side
        implied_price = 1 / odds
        shares = bet_dollars / implied_price
        
        # Check position limits
        total_position = current_position + shares
        if total_position > self.max_position:
            # Reduce to fit within limit
            shares = self.max_position - current_position
            bet_dollars = shares * implied_price
            bet_percent = bet_dollars / self.bankroll
            
            if shares <= 0:
                return PositionSize(
                    size_dollars=0,
                    size_shares=0,
                    size_percent=0,
                    kelly_fraction=kelly_full,
                    is_valid=False,
                    reason=f"At maximum position ({self.max_position} shares)"
                )
        
        reason = (
            f"Kelly={kelly_full:.1%} × {self.kelly_multiplier} × conf={confidence:.0%} "
            f"= {bet_percent:.1%} of bankroll"
        )
        
        logger.debug(f"Position size: ${bet_dollars:.2f} ({shares:.1f} shares) - {reason}")
        
        return PositionSize(
            size_dollars=bet_dollars,
            size_shares=shares,
            size_percent=bet_percent,
            kelly_fraction=kelly_full,
            is_valid=True,
            reason=reason
        )
    
    def calculate_size_from_edge(
        self,
        edge: float,
        market_price: float,
        confidence: float = 1.0,
        current_position: float = 0.0
    ) -> PositionSize:
        """
        Calculate position size from edge and market price.
        
        This is a convenience method that converts edge to probability and odds.
        
        Args:
            edge: Our edge (fair_price - market_price for BUY)
            market_price: Current market price
            confidence: Confidence in our estimate
            current_position: Current position size
            
        Returns:
            PositionSize with recommended bet
        """
        # Fair price = market price + edge
        fair_price = market_price + edge
        
        # Ensure valid range
        fair_price = max(0.01, min(0.99, fair_price))
        
        # For a BUY at market_price, winning pays 1.0 and we risk market_price
        # Decimal odds = 1 / market_price
        odds = 1 / market_price
        
        return self.calculate_kelly_size(
            win_probability=fair_price,
            odds=odds,
            confidence=confidence,
            current_position=current_position
        )
    
    def calculate_fixed_size(
        self,
        percent_of_bankroll: float = 0.02,
        market_price: float = 0.5
    ) -> PositionSize:
        """
        Calculate a fixed percentage bet size.
        
        Use this for simpler strategies that don't use Kelly.
        
        Args:
            percent_of_bankroll: Percentage to bet (e.g., 0.02 for 2%)
            market_price: Market price (to calculate shares)
            
        Returns:
            PositionSize with fixed bet
        """
        # Cap at maximum
        percent = min(percent_of_bankroll, self.max_bet_percent)
        
        bet_dollars = self.bankroll * percent
        
        # Check minimum
        if bet_dollars < self.min_bet_dollars:
            bet_dollars = 0
            shares = 0
            is_valid = False
            reason = f"Fixed bet ${bet_dollars:.2f} below minimum"
        else:
            shares = bet_dollars / market_price
            is_valid = True
            reason = f"Fixed {percent:.1%} of bankroll"
        
        return PositionSize(
            size_dollars=bet_dollars,
            size_shares=shares,
            size_percent=percent,
            kelly_fraction=0,  # Not using Kelly
            is_valid=is_valid,
            reason=reason
        )
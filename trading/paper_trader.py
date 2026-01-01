"""
Paper Trader - Simulates trading without real money.

Paper trading is essential for:
1. Testing your strategy before risking real money
2. Debugging and improving your system
3. Building confidence in your approach
4. Tracking performance metrics

This paper trader:
- Executes simulated trades
- Tracks positions and P&L
- Records trade history
- Calculates performance metrics
"""

import logging
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from config.settings import get_config
from core import (
    OrderSide, TradeStatus, Trade, Position, TradingSignal
)
from .edge_calculator import EdgeCalculator, EdgeOpportunity
from .position_sizer import PositionSizer, PositionSize

logger = logging.getLogger(__name__)
config = get_config()


@dataclass
class TradingStats:
    """Trading performance statistics."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    total_pnl: float = 0.0
    total_volume: float = 0.0
    
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    @property
    def win_rate(self) -> float:
        """Percentage of winning trades."""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades
    
    @property
    def average_pnl(self) -> float:
        """Average P&L per trade."""
        if self.total_trades == 0:
            return 0.0
        return self.total_pnl / self.total_trades
    
    @property
    def profit_factor(self) -> float:
        """Ratio of gross profits to gross losses."""
        # This requires tracking gross wins/losses separately
        # Simplified version
        if self.losing_trades == 0:
            return float('inf') if self.winning_trades > 0 else 0.0
        return self.winning_trades / self.losing_trades


class PaperTrader:
    """
    Paper trading system for simulated trading.
    
    Usage:
        trader = PaperTrader(initial_bankroll=1000.0)
        
        # Check for opportunity and trade
        signal = trader.evaluate_opportunity(
            match_id="match_001",
            fair_price=0.60,
            market_price=0.55
        )
        
        if signal and signal.side:
            trade = trader.execute_trade(signal)
            print(f"Executed: {trade}")
        
        # Later, close the position
        pnl = trader.close_position("match_001", settlement_price=1.0)
        
        # Check stats
        print(trader.get_stats_summary())
    """
    
    def __init__(self, initial_bankroll: float = None):
        """
        Initialize the paper trader.
        
        Args:
            initial_bankroll: Starting bankroll in dollars
        """
        self.initial_bankroll = initial_bankroll or config.trading.initial_bankroll
        self.bankroll = self.initial_bankroll
        
        # Components
        self.edge_calculator = EdgeCalculator()
        self.position_sizer = PositionSizer(self.bankroll)
        
        # State
        self.positions: Dict[str, Position] = {}  # market_id -> Position
        self.trades: List[Trade] = []
        self.stats = TradingStats()
        
        # Settings
        self.min_edge = config.trading.min_edge
        self.trade_cooldown_ms = config.trading.trade_cooldown_ms
        
        # Track last trade time per market
        self._last_trade_time: Dict[str, datetime] = {}
        
        logger.info(f"PaperTrader initialized with ${self.bankroll:.2f} bankroll")
    
    def evaluate_opportunity(
        self,
        match_id: str,
        fair_price: float,
        market_price: float,
        confidence: float = 0.7,
        market_bid: float = None,
        market_ask: float = None
    ) -> Optional[TradingSignal]:
        """
        Evaluate a potential trading opportunity.
        
        Args:
            match_id: Match identifier
            fair_price: Our calculated fair price
            market_price: Current market mid-price
            confidence: Confidence in our estimate
            market_bid: Best bid price (optional)
            market_ask: Best ask price (optional)
            
        Returns:
            TradingSignal if there's an opportunity, None otherwise
        """
        # Use bid/ask if provided, otherwise use market_price for both
        bid = market_bid if market_bid is not None else market_price
        ask = market_ask if market_ask is not None else market_price
        
        # Calculate edge
        opportunity = self.edge_calculator.calculate_edge(
            fair_price=fair_price,
            market_bid=bid,
            market_ask=ask,
            confidence=confidence
        )
        
        if not opportunity.has_edge:
            logger.debug(f"No edge: {opportunity.reason}")
            return None
        
        # Check cooldown
        if not self._check_cooldown(match_id):
            logger.debug(f"Trade cooldown active for {match_id}")
            return None
        
        # Calculate position size
        current_pos = self._get_current_position_size(match_id)
        
        size = self.position_sizer.calculate_size_from_edge(
            edge=opportunity.edge,
            market_price=opportunity.market_price,
            confidence=confidence,
            current_position=current_pos
        )
        
        if not size.is_valid:
            logger.debug(f"Invalid size: {size.reason}")
            return None
        
        # Create signal
        signal = self.edge_calculator.create_trading_signal(
            match_id=match_id,
            opportunity=opportunity,
            recommended_size=size.size_shares
        )
        
        logger.info(
            f"Signal: {signal.side.value} {size.size_shares:.1f} shares | "
            f"Edge: {opportunity.edge:.3f} | Size: ${size.size_dollars:.2f}"
        )
        
        return signal
    
    def execute_trade(
        self,
        signal: TradingSignal,
        market_id: str = None
    ) -> Optional[Trade]:
        """
        Execute a paper trade.
        
        Args:
            signal: The trading signal to execute
            market_id: Market identifier (defaults to match_id)
            
        Returns:
            Executed Trade object, or None if failed
        """
        if not signal.side or signal.recommended_size <= 0:
            logger.warning("Invalid signal for execution")
            return None
        
        market_id = market_id or signal.match_id
        
        # Create trade
        trade = Trade(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(),
            market_id=market_id,
            token_id=f"{market_id}_token",
            side=signal.side,
            size=signal.recommended_size,
            price=signal.market_price,
            fair_price=signal.fair_price,
            edge=signal.edge,
            status=TradeStatus.FILLED,  # Paper trades fill instantly
            filled_size=signal.recommended_size,
            filled_price=signal.market_price,
            is_paper=True
        )
        
        # Update position
        self._update_position(trade)
        
        # Update bankroll (deduct cost)
        cost = trade.size * trade.price
        if trade.side == OrderSide.BUY:
            self.bankroll -= cost
        else:
            self.bankroll += cost
        
        # Update position sizer
        self.position_sizer.update_bankroll(self.bankroll)
        
        # Record trade
        self.trades.append(trade)
        self.stats.total_trades += 1
        self.stats.total_volume += cost
        
        # Update cooldown
        self._last_trade_time[market_id] = datetime.now()
        
        logger.info(
            f"Trade executed: {trade.side.value} {trade.size:.1f} @ {trade.price:.3f} | "
            f"Bankroll: ${self.bankroll:.2f}"
        )
        
        return trade
    
    def close_position(
        self,
        market_id: str,
        settlement_price: float
    ) -> float:
        """
        Close a position at settlement price.
        
        Args:
            market_id: The market to close
            settlement_price: Final settlement price (0 or 1 for binary markets)
            
        Returns:
            Realized P&L from closing the position
        """
        if market_id not in self.positions:
            logger.warning(f"No position to close for {market_id}")
            return 0.0
        
        position = self.positions[market_id]
        
        if position.size == 0:
            del self.positions[market_id]
            return 0.0
        
        # Calculate P&L
        # For a LONG position: PnL = size * (settlement - avg_price)
        # For a SHORT position: PnL = size * (avg_price - settlement)
        if position.size > 0:
            # Long position
            pnl = position.size * (settlement_price - position.avg_price)
        else:
            # Short position
            pnl = abs(position.size) * (position.avg_price - settlement_price)
        
        # Update stats
        self.stats.total_pnl += pnl
        
        if pnl > 0:
            self.stats.winning_trades += 1
            self.stats.largest_win = max(self.stats.largest_win, pnl)
        elif pnl < 0:
            self.stats.losing_trades += 1
            self.stats.largest_loss = min(self.stats.largest_loss, pnl)
        
        # Update bankroll
        # Add back the original cost plus P&L
        original_cost = abs(position.size) * position.avg_price
        self.bankroll += original_cost + pnl
        self.position_sizer.update_bankroll(self.bankroll)
        
        # Remove position
        del self.positions[market_id]
        
        logger.info(
            f"Position closed: {market_id} | "
            f"Settlement: {settlement_price:.2f} | "
            f"PnL: ${pnl:.2f} | "
            f"Bankroll: ${self.bankroll:.2f}"
        )
        
        return pnl
    
    def get_position(self, market_id: str) -> Optional[Position]:
        """Get current position for a market."""
        return self.positions.get(market_id)
    
    def get_all_positions(self) -> Dict[str, Position]:
        """Get all open positions."""
        return self.positions.copy()
    
    def get_unrealized_pnl(self, market_id: str, current_price: float) -> float:
        """Calculate unrealized P&L for a position."""
        position = self.positions.get(market_id)
        if not position or position.size == 0:
            return 0.0
        
        if position.size > 0:
            return position.size * (current_price - position.avg_price)
        else:
            return abs(position.size) * (position.avg_price - current_price)
    
    def get_total_unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        """Calculate total unrealized P&L across all positions."""
        total = 0.0
        for market_id, position in self.positions.items():
            if market_id in current_prices:
                total += self.get_unrealized_pnl(market_id, current_prices[market_id])
        return total
    
    def get_stats_summary(self) -> str:
        """Get a summary of trading statistics."""
        return (
            f"Trading Stats:\n"
            f"  Bankroll: ${self.bankroll:.2f} (started: ${self.initial_bankroll:.2f})\n"
            f"  Total P&L: ${self.stats.total_pnl:.2f} ({self.stats.total_pnl/self.initial_bankroll*100:+.1f}%)\n"
            f"  Total Trades: {self.stats.total_trades}\n"
            f"  Win Rate: {self.stats.win_rate:.1%}\n"
            f"  Avg P&L/Trade: ${self.stats.average_pnl:.2f}\n"
            f"  Largest Win: ${self.stats.largest_win:.2f}\n"
            f"  Largest Loss: ${self.stats.largest_loss:.2f}\n"
            f"  Open Positions: {len(self.positions)}"
        )
    
    def get_trade_history(self, limit: int = None) -> List[Trade]:
        """Get trade history, most recent first."""
        trades = sorted(self.trades, key=lambda t: t.timestamp, reverse=True)
        if limit:
            trades = trades[:limit]
        return trades
    
    def reset(self):
        """Reset the trader to initial state."""
        self.bankroll = self.initial_bankroll
        self.positions.clear()
        self.trades.clear()
        self.stats = TradingStats()
        self._last_trade_time.clear()
        self.position_sizer.update_bankroll(self.bankroll)
        
        logger.info("PaperTrader reset to initial state")
    
    # ================================================================
    # PRIVATE METHODS
    # ================================================================
    
    def _check_cooldown(self, market_id: str) -> bool:
        """Check if enough time has passed since last trade."""
        if market_id not in self._last_trade_time:
            return True
        
        elapsed = (datetime.now() - self._last_trade_time[market_id]).total_seconds() * 1000
        return elapsed >= self.trade_cooldown_ms
    
    def _get_current_position_size(self, market_id: str) -> float:
        """Get current position size for a market."""
        position = self.positions.get(market_id)
        return position.size if position else 0.0
    
    def _update_position(self, trade: Trade):
        """Update position based on trade."""
        market_id = trade.market_id
        
        if market_id not in self.positions:
            self.positions[market_id] = Position(
                market_id=market_id,
                token_id=trade.token_id,
                size=0,
                avg_price=0
            )
        
        position = self.positions[market_id]
        
        # Calculate new position
        if trade.side == OrderSide.BUY:
            # Adding to long position
            new_size = position.size + trade.filled_size
            if position.size >= 0:
                # Already long or flat - average in
                total_cost = (position.size * position.avg_price) + (trade.filled_size * trade.filled_price)
                position.avg_price = total_cost / new_size if new_size > 0 else 0
            else:
                # Was short, now closing/reversing
                position.avg_price = trade.filled_price
            position.size = new_size
            
        else:  # SELL
            # Reducing long or going short
            new_size = position.size - trade.filled_size
            if position.size <= 0:
                # Already short or flat - average in
                total_cost = (abs(position.size) * position.avg_price) + (trade.filled_size * trade.filled_price)
                position.avg_price = total_cost / abs(new_size) if new_size != 0 else 0
            else:
                # Was long, now closing/reversing
                if new_size < 0:
                    position.avg_price = trade.filled_price
            position.size = new_size
        
        # Update current price
        position.current_price = trade.filled_price
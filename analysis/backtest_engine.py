"""
Backtest Engine - Runs trading strategy over historical data.

Backtesting is essential for:
1. Validating strategy logic before risking real money
2. Estimating expected performance metrics
3. Identifying weaknesses and edge cases
4. Optimizing parameters

The engine:
- Processes historical matches tick by tick
- Simulates trading decisions at each tick
- Tracks positions, P&L, and performance metrics
- Generates detailed reports
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import statistics

from core import OrderSide, Trade, TradeStatus
from trading import PaperTrader
from .historical_data import HistoricalMatch, HistoricalTick

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """Record of a trade made during backtesting."""
    match_id: str
    tick_number: int
    game_time: int
    side: OrderSide
    size: float
    entry_price: float
    fair_price: float
    edge: float
    exit_price: Optional[float] = None
    pnl: Optional[float] = None


@dataclass
class BacktestResult:
    """Results from backtesting a single match."""
    match_id: str
    team1_name: str
    team2_name: str
    winner: int
    duration_minutes: float
    
    # Trading results
    trades: List[BacktestTrade] = field(default_factory=list)
    final_pnl: float = 0.0
    
    # Position at end
    final_position: float = 0.0
    final_position_value: float = 0.0


@dataclass
class BacktestMetrics:
    """
    Comprehensive performance metrics from backtesting.
    """
    # Basic stats
    total_matches: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # P&L
    total_pnl: float = 0.0
    average_pnl_per_match: float = 0.0
    average_pnl_per_trade: float = 0.0
    
    # Win rates
    win_rate: float = 0.0
    match_win_rate: float = 0.0  # % of matches with positive P&L
    
    # Risk metrics
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    
    # Trade stats
    average_edge: float = 0.0
    average_position_size: float = 0.0
    trades_per_match: float = 0.0
    
    # Largest trades
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    # Returns
    total_return_percent: float = 0.0
    
    def summary(self) -> str:
        """Generate summary string."""
        return f"""
========================================
BACKTEST RESULTS SUMMARY
========================================
Matches Analyzed: {self.total_matches}
Total Trades: {self.total_trades}
Trades per Match: {self.trades_per_match:.1f}

PERFORMANCE:
  Total P&L: ${self.total_pnl:.2f}
  Total Return: {self.total_return_percent:.1f}%
  Avg P&L/Match: ${self.average_pnl_per_match:.2f}
  Avg P&L/Trade: ${self.average_pnl_per_trade:.2f}

WIN RATES:
  Trade Win Rate: {self.win_rate:.1%}
  Match Win Rate: {self.match_win_rate:.1%}

RISK METRICS:
  Max Drawdown: ${self.max_drawdown:.2f} ({self.max_drawdown_percent:.1f}%)
  Sharpe Ratio: {self.sharpe_ratio:.2f}
  Profit Factor: {self.profit_factor:.2f}

TRADE DETAILS:
  Average Edge: {self.average_edge:.3f} ({self.average_edge*100:.1f}%)
  Avg Position: {self.average_position_size:.1f} shares
  Largest Win: ${self.largest_win:.2f}
  Largest Loss: ${self.largest_loss:.2f}
========================================
"""


class BacktestEngine:
    """
    Engine for backtesting trading strategies.
    
    Usage:
        engine = BacktestEngine(initial_bankroll=1000.0)
        
        # Run backtest on historical data
        results = engine.run_backtest(historical_matches)
        
        # Get metrics
        metrics = engine.calculate_metrics(results)
        print(metrics.summary())
    """
    
    def __init__(
        self,
        initial_bankroll: float = 1000.0,
        min_edge: float = 0.015,
        confidence: float = 0.75
    ):
        """
        Initialize the backtest engine.
        
        Args:
            initial_bankroll: Starting capital
            min_edge: Minimum edge required to trade
            confidence: Confidence level for position sizing
        """
        self.initial_bankroll = initial_bankroll
        self.min_edge = min_edge
        self.confidence = confidence
        
        # Will be created for each backtest
        self.trader: Optional[PaperTrader] = None
        
        logger.info(
            f"BacktestEngine initialized: bankroll=${initial_bankroll}, "
            f"min_edge={min_edge}, confidence={confidence}"
        )
    
    def run_backtest(
        self,
        matches: List[HistoricalMatch],
        verbose: bool = False
    ) -> List[BacktestResult]:
        """
        Run backtest over historical matches.
        
        Args:
            matches: List of historical matches to test
            verbose: If True, print progress
            
        Returns:
            List of BacktestResult for each match
        """
        results = []
        
        # Create fresh trader
        self.trader = PaperTrader(initial_bankroll=self.initial_bankroll)
        
        for i, match in enumerate(matches):
            result = self._backtest_match(match)
            results.append(result)
            
            if verbose and (i + 1) % 10 == 0:
                print(f"Processed {i + 1}/{len(matches)} matches, "
                      f"Bankroll: ${self.trader.bankroll:.2f}")
        
        logger.info(f"Backtest complete: {len(matches)} matches processed")
        return results
    
    def _backtest_match(self, match: HistoricalMatch) -> BacktestResult:
        """Backtest a single match."""
        trades = []
        position = 0.0
        avg_entry = 0.0
        
        # Process each tick
        for tick_num, tick in enumerate(match.ticks):
            # Check for trading opportunity
            trade = self._evaluate_tick(
                match_id=match.match_id,
                tick=tick,
                tick_number=tick_num,
                current_position=position
            )
            
            if trade:
                trades.append(trade)
                
                # Update position
                if trade.side == OrderSide.BUY:
                    # Calculate new average entry
                    total_cost = position * avg_entry + trade.size * trade.entry_price
                    position += trade.size
                    avg_entry = total_cost / position if position > 0 else 0
                else:
                    position -= trade.size
                    if position <= 0:
                        avg_entry = 0
        
        # Settle position at match end
        settlement_price = 1.0 if match.winner == 1 else 0.0
        
        # Calculate P&L for each trade
        total_pnl = 0.0
        for trade in trades:
            trade.exit_price = settlement_price
            if trade.side == OrderSide.BUY:
                trade.pnl = trade.size * (settlement_price - trade.entry_price)
            else:
                trade.pnl = trade.size * (trade.entry_price - settlement_price)
            total_pnl += trade.pnl
        
        # Update trader bankroll
        self.trader.bankroll += total_pnl
        
        return BacktestResult(
            match_id=match.match_id,
            team1_name=match.team1_name,
            team2_name=match.team2_name,
            winner=match.winner,
            duration_minutes=match.duration_minutes,
            trades=trades,
            final_pnl=total_pnl,
            final_position=position,
            final_position_value=position * settlement_price
        )
    
    def _evaluate_tick(
        self,
        match_id: str,
        tick: HistoricalTick,
        tick_number: int,
        current_position: float
    ) -> Optional[BacktestTrade]:
        """Evaluate a tick for trading opportunity."""
        
        # Calculate edge
        # For BUY: edge = fair_price - market_price (we think it's undervalued)
        # For SELL: edge = market_price - fair_price (we think it's overvalued)
        
        buy_edge = tick.fair_price - tick.market_price
        sell_edge = tick.market_price - tick.fair_price
        
        # Determine direction
        if buy_edge > sell_edge and buy_edge > self.min_edge:
            side = OrderSide.BUY
            edge = buy_edge
        elif sell_edge > buy_edge and sell_edge > self.min_edge:
            side = OrderSide.SELL
            edge = sell_edge
        else:
            return None
        
        # Position limits
        max_position = 100.0
        
        if side == OrderSide.BUY and current_position >= max_position:
            return None
        if side == OrderSide.SELL and current_position <= -max_position:
            return None
        
        # Calculate position size (simplified Kelly)
        # Size proportional to edge
        base_size = 10.0  # Base position size
        size_multiplier = min(edge / 0.02, 3.0)  # Scale by edge, cap at 3x
        size = base_size * size_multiplier * self.confidence
        
        # Apply position limit
        if side == OrderSide.BUY:
            size = min(size, max_position - current_position)
        else:
            size = min(size, max_position + current_position)
        
        if size < 1.0:
            return None
        
        return BacktestTrade(
            match_id=match_id,
            tick_number=tick_number,
            game_time=tick.game_time_seconds,
            side=side,
            size=size,
            entry_price=tick.market_price,
            fair_price=tick.fair_price,
            edge=edge
        )
    
    def calculate_metrics(
        self,
        results: List[BacktestResult]
    ) -> BacktestMetrics:
        """
        Calculate comprehensive metrics from backtest results.
        
        Args:
            results: List of BacktestResult from run_backtest
            
        Returns:
            BacktestMetrics with all performance statistics
        """
        metrics = BacktestMetrics()
        
        if not results:
            return metrics
        
        # Basic counts
        metrics.total_matches = len(results)
        
        all_trades = []
        match_pnls = []
        
        for result in results:
            all_trades.extend(result.trades)
            match_pnls.append(result.final_pnl)
        
        metrics.total_trades = len(all_trades)
        
        if metrics.total_trades == 0:
            return metrics
        
        # Win/loss counts
        trade_pnls = [t.pnl for t in all_trades if t.pnl is not None]
        metrics.winning_trades = sum(1 for p in trade_pnls if p > 0)
        metrics.losing_trades = sum(1 for p in trade_pnls if p < 0)
        
        # P&L metrics
        metrics.total_pnl = sum(trade_pnls)
        metrics.average_pnl_per_match = metrics.total_pnl / metrics.total_matches
        metrics.average_pnl_per_trade = metrics.total_pnl / metrics.total_trades
        
        # Win rates
        metrics.win_rate = metrics.winning_trades / metrics.total_trades
        metrics.match_win_rate = sum(1 for p in match_pnls if p > 0) / metrics.total_matches
        
        # Trades per match
        metrics.trades_per_match = metrics.total_trades / metrics.total_matches
        
        # Average edge and position
        edges = [t.edge for t in all_trades]
        sizes = [t.size for t in all_trades]
        metrics.average_edge = sum(edges) / len(edges)
        metrics.average_position_size = sum(sizes) / len(sizes)
        
        # Largest win/loss
        if trade_pnls:
            metrics.largest_win = max(trade_pnls) if max(trade_pnls) > 0 else 0
            metrics.largest_loss = min(trade_pnls) if min(trade_pnls) < 0 else 0
        
        # Total return
        metrics.total_return_percent = (metrics.total_pnl / self.initial_bankroll) * 100
        
        # Max drawdown
        metrics.max_drawdown, metrics.max_drawdown_percent = self._calculate_max_drawdown(
            match_pnls
        )
        
        # Sharpe ratio
        metrics.sharpe_ratio = self._calculate_sharpe_ratio(match_pnls)
        
        # Profit factor
        gross_profit = sum(p for p in trade_pnls if p > 0)
        gross_loss = abs(sum(p for p in trade_pnls if p < 0))
        metrics.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        return metrics
    
    def _calculate_max_drawdown(
        self,
        pnls: List[float]
    ) -> Tuple[float, float]:
        """Calculate maximum drawdown from P&L series."""
        if not pnls:
            return 0.0, 0.0
        
        cumulative = []
        running_total = self.initial_bankroll
        
        for pnl in pnls:
            running_total += pnl
            cumulative.append(running_total)
        
        # Calculate drawdown at each point
        peak = cumulative[0]
        max_dd = 0.0
        max_dd_percent = 0.0
        
        for value in cumulative:
            if value > peak:
                peak = value
            
            drawdown = peak - value
            drawdown_percent = drawdown / peak if peak > 0 else 0
            
            if drawdown > max_dd:
                max_dd = drawdown
                max_dd_percent = drawdown_percent
        
        return max_dd, max_dd_percent * 100
    
    def _calculate_sharpe_ratio(
        self,
        pnls: List[float],
        risk_free_rate: float = 0.0
    ) -> float:
        """
        Calculate Sharpe ratio.
        
        Sharpe = (mean return - risk free rate) / std deviation
        """
        if len(pnls) < 2:
            return 0.0
        
        mean_pnl = statistics.mean(pnls)
        std_pnl = statistics.stdev(pnls)
        
        if std_pnl == 0:
            return 0.0
        
        # Annualize (assuming ~250 trading days, ~5 matches per day)
        # This is rough approximation
        sharpe = (mean_pnl - risk_free_rate) / std_pnl
        
        return sharpe
    
    def get_equity_curve(
        self,
        results: List[BacktestResult]
    ) -> List[Tuple[int, float]]:
        """
        Get equity curve from results.
        
        Returns list of (match_number, bankroll) tuples.
        """
        curve = [(0, self.initial_bankroll)]
        bankroll = self.initial_bankroll
        
        for i, result in enumerate(results):
            bankroll += result.final_pnl
            curve.append((i + 1, bankroll))
        
        return curve
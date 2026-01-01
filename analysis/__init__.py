"""
Analysis module - Backtesting and performance analysis.

Usage:
    from analysis import HistoricalDataGenerator, BacktestEngine
    
    # Generate test data
    generator = HistoricalDataGenerator(game="lol")
    matches = generator.generate_matches(count=100)
    
    # Run backtest
    engine = BacktestEngine(initial_bankroll=1000.0)
    results = engine.run_backtest(matches)
    
    # Get metrics
    metrics = engine.calculate_metrics(results)
    print(metrics.summary())
"""

from .historical_data import (
    HistoricalDataGenerator,
    HistoricalMatch,
    HistoricalTick,
)
from .backtest_engine import (
    BacktestEngine,
    BacktestResult,
    BacktestTrade,
    BacktestMetrics,
)

__all__ = [
    # Historical data
    "HistoricalDataGenerator",
    "HistoricalMatch",
    "HistoricalTick",
    # Backtesting
    "BacktestEngine",
    "BacktestResult",
    "BacktestTrade",
    "BacktestMetrics",
]
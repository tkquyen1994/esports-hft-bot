"""
Storage module - Database and logging systems.

Usage:
    # Setup logging first
    from storage import setup_logging
    setup_logging(log_level="INFO")
    
    # Use repositories for data storage
    from storage import TradeRepository, MatchRepository
    
    trade_repo = TradeRepository()
    trade_repo.save_trade(trade)
    
    stats = trade_repo.get_statistics()
    print(trade_repo.generate_report())
"""

from .database import DatabaseManager
from .logger import TradingLogger, setup_logging, get_logger
from .trade_repository import TradeRepository, MatchRepository, EventRepository

__all__ = [
    # Database
    "DatabaseManager",
    # Logging
    "TradingLogger",
    "setup_logging",
    "get_logger",
    # Repositories
    "TradeRepository",
    "MatchRepository",
    "EventRepository",
]
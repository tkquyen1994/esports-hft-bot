"""
Logging System - Structured logging for the trading bot.

Provides:
- Console output with colors
- File logging with rotation
- Different log levels (DEBUG, INFO, WARNING, ERROR)
- Structured format for easy parsing

Log files are stored in the 'logs' directory.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional


# ANSI color codes for console output
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""
    
    LEVEL_COLORS = {
        logging.DEBUG: Colors.GRAY,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.MAGENTA,
    }
    
    def format(self, record):
        # Add color to level name
        color = self.LEVEL_COLORS.get(record.levelno, Colors.WHITE)
        record.levelname = f"{color}{record.levelname:<8}{Colors.RESET}"
        
        # Add color to logger name
        record.name = f"{Colors.CYAN}{record.name}{Colors.RESET}"
        
        return super().format(record)


class TradingLogger:
    """
    Centralized logging system for the trading bot.
    
    Usage:
        # Setup logging once at startup
        TradingLogger.setup(log_level="INFO", log_dir="logs")
        
        # Then use standard logging anywhere
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Bot started")
        logger.warning("Low edge detected")
        logger.error("Connection failed")
    """
    
    _initialized = False
    
    @classmethod
    def setup(
        cls,
        log_level: str = "INFO",
        log_dir: str = "logs",
        console_output: bool = True,
        file_output: bool = True,
        max_file_size_mb: int = 10,
        backup_count: int = 5
    ):
        """
        Setup the logging system.
        
        Args:
            log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
            log_dir: Directory for log files
            console_output: Enable console logging
            file_output: Enable file logging
            max_file_size_mb: Max size of each log file in MB
            backup_count: Number of backup files to keep
        """
        if cls._initialized:
            return
        
        # Create log directory
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG)
            
            console_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            console_handler.setFormatter(ColoredFormatter(
                console_format,
                datefmt="%H:%M:%S"
            ))
            
            root_logger.addHandler(console_handler)
        
        # File handler - main log
        if file_output:
            main_log_file = log_path / "trading.log"
            file_handler = RotatingFileHandler(
                main_log_file,
                maxBytes=max_file_size_mb * 1024 * 1024,
                backupCount=backup_count
            )
            file_handler.setLevel(logging.DEBUG)
            
            file_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
            file_handler.setFormatter(logging.Formatter(
                file_format,
                datefmt="%Y-%m-%d %H:%M:%S"
            ))
            
            root_logger.addHandler(file_handler)
            
            # Error log - errors only
            error_log_file = log_path / "errors.log"
            error_handler = RotatingFileHandler(
                error_log_file,
                maxBytes=max_file_size_mb * 1024 * 1024,
                backupCount=backup_count
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(logging.Formatter(
                file_format,
                datefmt="%Y-%m-%d %H:%M:%S"
            ))
            
            root_logger.addHandler(error_handler)
            
            # Trade log - trades only
            trade_logger = logging.getLogger("trades")
            trade_log_file = log_path / "trades.log"
            trade_handler = RotatingFileHandler(
                trade_log_file,
                maxBytes=max_file_size_mb * 1024 * 1024,
                backupCount=backup_count
            )
            trade_handler.setLevel(logging.INFO)
            trade_handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            ))
            trade_logger.addHandler(trade_handler)
        
        cls._initialized = True
        
        # Log startup
        logger = logging.getLogger(__name__)
        logger.info(f"Logging initialized: level={log_level}, dir={log_dir}")
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get a logger with the given name."""
        return logging.getLogger(name)
    
    @classmethod
    def log_trade(
        cls,
        side: str,
        size: float,
        price: float,
        edge: float,
        match_id: str,
        pnl: Optional[float] = None
    ):
        """
        Log a trade to the dedicated trade log.
        
        Args:
            side: BUY or SELL
            size: Position size
            price: Execution price
            edge: Edge at time of trade
            match_id: Match identifier
            pnl: Realized P&L (if available)
        """
        trade_logger = logging.getLogger("trades")
        
        pnl_str = f"PnL=${pnl:.2f}" if pnl is not None else "PnL=pending"
        
        trade_logger.info(
            f"{side} | Size={size:.1f} | Price=${price:.3f} | "
            f"Edge={edge:.2%} | Match={match_id} | {pnl_str}"
        )
    
    @classmethod
    def log_event(
        cls,
        event_type: str,
        team: int,
        context: str,
        match_id: str,
        prob_change: float
    ):
        """
        Log a game event.
        
        Args:
            event_type: Type of event (kill, tower, etc.)
            team: Team number (1 or 2)
            context: Event context
            match_id: Match identifier
            prob_change: Probability change from event
        """
        logger = logging.getLogger("events")
        
        logger.debug(
            f"EVENT | {event_type} | Team {team} | {context} | "
            f"Match={match_id} | ProbΔ={prob_change:+.3f}"
        )
    
    @classmethod
    def log_performance(
        cls,
        metric_name: str,
        metric_value: float,
        context: str = ""
    ):
        """
        Log a performance metric.
        
        Args:
            metric_name: Name of the metric
            metric_value: Value of the metric
            context: Additional context
        """
        logger = logging.getLogger("performance")
        
        logger.info(f"METRIC | {metric_name}={metric_value:.4f} | {context}")


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs"
):
    """
    Convenience function to setup logging.
    
    Usage:
        from storage.logger import setup_logging
        setup_logging(log_level="DEBUG")
    """
    TradingLogger.setup(log_level=log_level, log_dir=log_dir)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.
    
    Usage:
        from storage.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Hello!")
    """
    return logging.getLogger(name)
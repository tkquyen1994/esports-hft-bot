"""
Trading module - Edge detection, position sizing, order management, and risk.

Usage:
    from trading import EdgeCalculator, PositionSizer, PaperTrader
    from trading import OrderManager, RiskManager
"""

from .edge_calculator import EdgeCalculator, EdgeOpportunity
from .position_sizer import PositionSizer, PositionSize
from .paper_trader import PaperTrader, TradingStats
from .order_manager import OrderManager, OrderRequest, OrderResponse, OrderResult
from .risk_manager import RiskManager, RiskLimits, RiskLevel, TradingState

__all__ = [
    # Edge detection
    "EdgeCalculator",
    "EdgeOpportunity",
    # Position sizing
    "PositionSizer",
    "PositionSize",
    # Paper trading
    "PaperTrader",
    "TradingStats",
    # Order management
    "OrderManager",
    "OrderRequest",
    "OrderResponse",
    "OrderResult",
    # Risk management
    "RiskManager",
    "RiskLimits",
    "RiskLevel",
    "TradingState",
]
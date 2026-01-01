"""
Risk Manager - Safety controls for live trading.

Features:
- Position limits
- Loss limits (daily, per-trade)
- Exposure monitoring
- Circuit breakers
- Kill switch
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from config.settings import get_config

logger = logging.getLogger(__name__)
config = get_config()


class RiskLevel(Enum):
    """Risk level indicators."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TradingState(Enum):
    """Trading state."""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    KILLED = "killed"  # Emergency stop


@dataclass
class RiskLimits:
    """Risk limit configuration."""
    max_position_per_market: float = 500.0
    max_total_exposure: float = 2000.0
    max_daily_loss: float = 100.0
    max_trade_loss: float = 50.0
    max_drawdown_percent: float = 10.0
    max_trades_per_hour: int = 50
    max_open_orders: int = 20


@dataclass
class RiskMetrics:
    """Current risk metrics."""
    total_exposure: float = 0.0
    daily_pnl: float = 0.0
    daily_trades: int = 0
    hourly_trades: int = 0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    open_positions: int = 0
    open_orders: int = 0
    
    # Peak tracking for drawdown
    peak_equity: float = 0.0


class RiskManager:
    """
    Manages trading risk and safety controls.
    
    Usage:
        risk = RiskManager(initial_equity=1000.0)
        
        # Check if trade is allowed
        allowed, reason = risk.check_trade(
            size=10.0,
            price=0.55,
            market_id="..."
        )
        
        if not allowed:
            print(f"Trade blocked: {reason}")
        
        # Update after trade
        risk.record_trade(pnl=5.0)
        
        # Check risk level
        if risk.get_risk_level() == RiskLevel.CRITICAL:
            risk.emergency_stop()
    """
    
    def __init__(
        self,
        initial_equity: float = 1000.0,
        limits: RiskLimits = None
    ):
        """
        Initialize risk manager.
        
        Args:
            initial_equity: Starting account equity
            limits: Risk limit configuration
        """
        self.initial_equity = initial_equity
        self.current_equity = initial_equity
        self.limits = limits or RiskLimits()
        
        # State
        self.state = TradingState.ACTIVE
        self.metrics = RiskMetrics(peak_equity=initial_equity)
        
        # Position tracking
        self.positions: Dict[str, float] = {}  # market_id -> size * price
        
        # Trade history for rate limiting
        self._trade_times: List[datetime] = []
        
        # Daily reset tracking
        self._last_daily_reset = datetime.now().date()
        
        logger.info(f"RiskManager initialized: equity=${initial_equity:.2f}")
    
    def check_trade(
        self,
        size: float,
        price: float,
        market_id: str,
        side: str = "BUY"
    ) -> tuple[bool, str]:
        """
        Check if a trade is allowed.
        
        Args:
            size: Trade size
            price: Trade price
            market_id: Market identifier
            side: "BUY" or "SELL"
            
        Returns:
            Tuple of (allowed, reason)
        """
        # Check trading state
        if self.state != TradingState.ACTIVE:
            return False, f"Trading is {self.state.value}"
        
        # Check daily reset
        self._check_daily_reset()
        
        trade_value = size * price
        
        # Check per-market position limit
        current_exposure = self.positions.get(market_id, 0)
        new_exposure = current_exposure + trade_value if side == "BUY" else current_exposure - trade_value
        
        if abs(new_exposure) > self.limits.max_position_per_market:
            return False, f"Would exceed market position limit: ${abs(new_exposure):.2f}"
        
        # Check total exposure limit
        total_new_exposure = self.metrics.total_exposure + trade_value
        if total_new_exposure > self.limits.max_total_exposure:
            return False, f"Would exceed total exposure limit: ${total_new_exposure:.2f}"
        
        # Check daily loss limit
        if self.metrics.daily_pnl < -self.limits.max_daily_loss:
            return False, f"Daily loss limit reached: ${self.metrics.daily_pnl:.2f}"
        
        # Check max potential loss
        max_loss = trade_value  # Worst case: total loss
        if max_loss > self.limits.max_trade_loss:
            return False, f"Potential loss too high: ${max_loss:.2f}"
        
        # Check drawdown
        if self.metrics.current_drawdown > self.limits.max_drawdown_percent:
            return False, f"Max drawdown exceeded: {self.metrics.current_drawdown:.1f}%"
        
        # Check trade rate limits
        if not self._check_rate_limit():
            return False, "Trade rate limit exceeded"
        
        return True, "OK"
    
    def record_trade(
        self,
        market_id: str,
        size: float,
        price: float,
        side: str,
        pnl: float = 0.0
    ):
        """
        Record a completed trade.
        
        Args:
            market_id: Market identifier
            size: Trade size
            price: Trade price
            side: "BUY" or "SELL"
            pnl: Realized P&L from trade
        """
        trade_value = size * price
        
        # Update position
        if side == "BUY":
            self.positions[market_id] = self.positions.get(market_id, 0) + trade_value
        else:
            self.positions[market_id] = self.positions.get(market_id, 0) - trade_value
        
        # Update exposure
        self.metrics.total_exposure = sum(abs(v) for v in self.positions.values())
        
        # Update P&L
        self.metrics.daily_pnl += pnl
        self.current_equity += pnl
        
        # Update drawdown
        if self.current_equity > self.metrics.peak_equity:
            self.metrics.peak_equity = self.current_equity
        
        drawdown = self.metrics.peak_equity - self.current_equity
        self.metrics.current_drawdown = (drawdown / self.metrics.peak_equity) * 100
        self.metrics.max_drawdown = max(self.metrics.max_drawdown, self.metrics.current_drawdown)
        
        # Update trade counts
        self.metrics.daily_trades += 1
        self._trade_times.append(datetime.now())
        
        # Check for automatic pause
        self._check_auto_pause()
        
        logger.debug(f"Trade recorded: {side} ${trade_value:.2f}, P&L: ${pnl:.2f}")
    
    def close_position(self, market_id: str, pnl: float):
        """Record closing a position."""
        if market_id in self.positions:
            del self.positions[market_id]
        
        self.metrics.total_exposure = sum(abs(v) for v in self.positions.values())
        self.metrics.daily_pnl += pnl
        self.current_equity += pnl
        
        # Update peak and drawdown
        if self.current_equity > self.metrics.peak_equity:
            self.metrics.peak_equity = self.current_equity
        
        drawdown = self.metrics.peak_equity - self.current_equity
        self.metrics.current_drawdown = (drawdown / self.metrics.peak_equity) * 100
    
    def get_risk_level(self) -> RiskLevel:
        """Get current risk level."""
        # Check multiple factors
        
        # Drawdown
        if self.metrics.current_drawdown > 8:
            return RiskLevel.CRITICAL
        elif self.metrics.current_drawdown > 5:
            return RiskLevel.HIGH
        elif self.metrics.current_drawdown > 2:
            return RiskLevel.MEDIUM
        
        # Daily loss
        daily_loss_pct = abs(self.metrics.daily_pnl) / self.initial_equity * 100
        if daily_loss_pct > 8:
            return RiskLevel.CRITICAL
        elif daily_loss_pct > 5:
            return RiskLevel.HIGH
        elif daily_loss_pct > 2:
            return RiskLevel.MEDIUM
        
        # Exposure
        exposure_pct = self.metrics.total_exposure / self.initial_equity * 100
        if exposure_pct > 150:
            return RiskLevel.HIGH
        elif exposure_pct > 100:
            return RiskLevel.MEDIUM
        
        return RiskLevel.LOW
    
    def pause_trading(self, reason: str = "Manual pause"):
        """Pause trading."""
        self.state = TradingState.PAUSED
        logger.warning(f"Trading PAUSED: {reason}")
    
    def resume_trading(self):
        """Resume trading."""
        if self.state == TradingState.PAUSED:
            self.state = TradingState.ACTIVE
            logger.info("Trading RESUMED")
    
    def emergency_stop(self, reason: str = "Emergency"):
        """Emergency stop all trading."""
        self.state = TradingState.KILLED
        logger.critical(f"EMERGENCY STOP: {reason}")
    
    def _check_rate_limit(self) -> bool:
        """Check if trade rate is within limits."""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        # Count trades in last hour
        self._trade_times = [t for t in self._trade_times if t > one_hour_ago]
        self.metrics.hourly_trades = len(self._trade_times)
        
        return self.metrics.hourly_trades < self.limits.max_trades_per_hour
    
    def _check_daily_reset(self):
        """Check if daily stats should be reset."""
        today = datetime.now().date()
        
        if today > self._last_daily_reset:
            self.metrics.daily_pnl = 0.0
            self.metrics.daily_trades = 0
            self._last_daily_reset = today
            logger.info("Daily risk metrics reset")
    
    def _check_auto_pause(self):
        """Check if trading should auto-pause."""
        risk_level = self.get_risk_level()
        
        if risk_level == RiskLevel.CRITICAL:
            self.pause_trading("Critical risk level reached")
    
    def get_summary(self) -> str:
        """Get risk summary."""
        return f"""
Risk Summary:
  State: {self.state.value}
  Risk Level: {self.get_risk_level().value}
  
  Equity: ${self.current_equity:.2f} (started: ${self.initial_equity:.2f})
  Daily P&L: ${self.metrics.daily_pnl:.2f}
  
  Total Exposure: ${self.metrics.total_exposure:.2f}
  Open Positions: {len(self.positions)}
  
  Current Drawdown: {self.metrics.current_drawdown:.1f}%
  Max Drawdown: {self.metrics.max_drawdown:.1f}%
  
  Daily Trades: {self.metrics.daily_trades}
  Hourly Trades: {self.metrics.hourly_trades}
"""
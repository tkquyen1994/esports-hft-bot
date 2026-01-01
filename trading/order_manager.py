"""
Order Manager - Handles order placement with safety checks.

Features:
- Order validation
- Size limits
- Rate limiting
- Order tracking
- Fill monitoring
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from config.settings import get_config
from connectors.polymarket_client import (
    PolymarketClient,
    PolymarketOrder,
    OrderSide,
    OrderType,
    OrderStatus
)

logger = logging.getLogger(__name__)
config = get_config()


class OrderResult(Enum):
    """Result of order operation."""
    SUCCESS = "success"
    REJECTED = "rejected"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class OrderRequest:
    """Request to place an order."""
    token_id: str
    side: OrderSide
    price: float
    size: float
    order_type: OrderType = OrderType.LIMIT
    
    # Metadata
    market_id: str = ""
    reason: str = ""
    fair_price: float = 0.0
    edge: float = 0.0


@dataclass
class OrderResponse:
    """Response from order operation."""
    result: OrderResult
    order: Optional[PolymarketOrder] = None
    message: str = ""
    request: Optional[OrderRequest] = None


class OrderManager:
    """
    Manages order placement with safety controls.
    
    Usage:
        manager = OrderManager()
        await manager.start()
        
        # Place order
        response = await manager.place_order(OrderRequest(
            token_id="...",
            side=OrderSide.BUY,
            price=0.55,
            size=10.0
        ))
        
        if response.result == OrderResult.SUCCESS:
            print(f"Order placed: {response.order.order_id}")
        
        await manager.stop()
    """
    
    def __init__(self):
        """Initialize the order manager."""
        self.client = PolymarketClient()
        
        # Settings
        self.max_order_size = config.polymarket.max_order_size
        self.min_order_size = config.polymarket.min_order_size
        self.max_position_size = config.polymarket.max_position_size
        self.max_open_orders = config.polymarket.max_open_orders
        
        # State
        self.open_orders: Dict[str, PolymarketOrder] = {}
        self.positions: Dict[str, float] = {}  # token_id -> size
        self.daily_pnl: float = 0.0
        self.daily_volume: float = 0.0
        
        # Rate limiting
        self._last_order_time = datetime.min
        self._min_order_interval = timedelta(seconds=1)
        
        # Order history
        self.order_history: List[OrderResponse] = []
        
        self._running = False
        
        logger.info("OrderManager initialized")
    
    async def start(self):
        """Start the order manager."""
        if not await self.client.connect():
            logger.error("Failed to connect to Polymarket")
            return False
        
        # Load existing positions
        await self._load_positions()
        
        # Load open orders
        await self._load_open_orders()
        
        self._running = True
        logger.info(f"OrderManager started: {len(self.open_orders)} open orders")
        
        return True
    
    async def stop(self):
        """Stop the order manager."""
        self._running = False
        await self.client.disconnect()
        logger.info("OrderManager stopped")
    
    async def _load_positions(self):
        """Load current positions from Polymarket."""
        try:
            positions = await self.client.get_positions()
            
            for pos in positions:
                self.positions[pos.token_id] = pos.size
            
            logger.info(f"Loaded {len(self.positions)} positions")
            
        except Exception as e:
            logger.error(f"Failed to load positions: {e}")
    
    async def _load_open_orders(self):
        """Load open orders from Polymarket."""
        try:
            orders = await self.client.get_open_orders()
            
            for order in orders:
                self.open_orders[order.order_id] = order
            
            logger.info(f"Loaded {len(self.open_orders)} open orders")
            
        except Exception as e:
            logger.error(f"Failed to load open orders: {e}")
    
    async def place_order(self, request: OrderRequest) -> OrderResponse:
        """
        Place an order with validation and safety checks.
        
        Args:
            request: Order request details
            
        Returns:
            OrderResponse with result
        """
        # Validate request
        validation = self._validate_order(request)
        if validation:
            return OrderResponse(
                result=OrderResult.REJECTED,
                message=validation,
                request=request
            )
        
        # Rate limiting
        await self._rate_limit()
        
        try:
            # Place order
            order = await self.client.place_order(
                token_id=request.token_id,
                side=request.side,
                price=request.price,
                size=request.size,
                order_type=request.order_type
            )
            
            if order:
                # Track order
                self.open_orders[order.order_id] = order
                
                # Update position tracking
                if request.side == OrderSide.BUY:
                    self.positions[request.token_id] = (
                        self.positions.get(request.token_id, 0) + request.size
                    )
                else:
                    self.positions[request.token_id] = (
                        self.positions.get(request.token_id, 0) - request.size
                    )
                
                # Update volume
                self.daily_volume += request.size * request.price
                
                response = OrderResponse(
                    result=OrderResult.SUCCESS,
                    order=order,
                    message="Order placed successfully",
                    request=request
                )
                
                logger.info(
                    f"Order placed: {request.side.value} {request.size} @ "
                    f"${request.price:.3f} | ID: {order.order_id}"
                )
                
            else:
                response = OrderResponse(
                    result=OrderResult.FAILED,
                    message="Order placement failed",
                    request=request
                )
                
                logger.warning("Order placement failed")
            
            self.order_history.append(response)
            return response
            
        except Exception as e:
            logger.error(f"Order error: {e}")
            
            response = OrderResponse(
                result=OrderResult.FAILED,
                message=str(e),
                request=request
            )
            
            self.order_history.append(response)
            return response
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order to cancel
            
        Returns:
            True if cancelled successfully
        """
        try:
            success = await self.client.cancel_order(order_id)
            
            if success and order_id in self.open_orders:
                del self.open_orders[order_id]
                logger.info(f"Order cancelled: {order_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Cancel error: {e}")
            return False
    
    async def cancel_all_orders(self) -> int:
        """Cancel all open orders."""
        try:
            count = await self.client.cancel_all_orders()
            self.open_orders.clear()
            logger.info(f"Cancelled {count} orders")
            return count
            
        except Exception as e:
            logger.error(f"Cancel all error: {e}")
            return 0
    
    def _validate_order(self, request: OrderRequest) -> Optional[str]:
        """
        Validate an order request.
        
        Returns:
            Error message if invalid, None if valid
        """
        # Check if trading is enabled
        if not config.polymarket.enabled:
            return "Polymarket trading is disabled"
        
        # Validate price
        if not 0.01 <= request.price <= 0.99:
            return f"Invalid price: {request.price} (must be 0.01-0.99)"
        
        # Validate size
        if request.size < self.min_order_size:
            return f"Size too small: {request.size} (min: {self.min_order_size})"
        
        if request.size > self.max_order_size:
            return f"Size too large: {request.size} (max: {self.max_order_size})"
        
        # Check position limits
        current_position = self.positions.get(request.token_id, 0)
        
        if request.side == OrderSide.BUY:
            new_position = current_position + request.size
        else:
            new_position = current_position - request.size
        
        if abs(new_position) > self.max_position_size:
            return f"Would exceed position limit: {new_position} (max: {self.max_position_size})"
        
        # Check open order limit
        if len(self.open_orders) >= self.max_open_orders:
            return f"Too many open orders: {len(self.open_orders)} (max: {self.max_open_orders})"
        
        # Check daily loss limit
        if self.daily_pnl < -config.polymarket.max_daily_loss:
            return f"Daily loss limit reached: ${self.daily_pnl:.2f}"
        
        return None
    
    async def _rate_limit(self):
        """Apply rate limiting between orders."""
        now = datetime.now()
        elapsed = now - self._last_order_time
        
        if elapsed < self._min_order_interval:
            wait_time = (self._min_order_interval - elapsed).total_seconds()
            await asyncio.sleep(wait_time)
        
        self._last_order_time = datetime.now()
    
    def get_position(self, token_id: str) -> float:
        """Get current position for a token."""
        return self.positions.get(token_id, 0)
    
    def get_all_positions(self) -> Dict[str, float]:
        """Get all positions."""
        return self.positions.copy()
    
    def get_open_orders_count(self) -> int:
        """Get number of open orders."""
        return len(self.open_orders)
    
    def reset_daily_stats(self):
        """Reset daily statistics."""
        self.daily_pnl = 0.0
        self.daily_volume = 0.0
        logger.info("Daily stats reset")
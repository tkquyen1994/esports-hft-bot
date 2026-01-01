"""
Market Monitor - Continuously monitors Polymarket markets and prices.

Features:
- Real-time price tracking
- Order book monitoring
- Market event detection
- Price change alerts
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field

from .polymarket_client import (
    PolymarketClient,
    PolymarketMarket,
    OrderBook
)

logger = logging.getLogger(__name__)


@dataclass
class MarketSnapshot:
    """Snapshot of market state at a point in time."""
    timestamp: datetime
    market_id: str
    question: str
    
    # Prices
    yes_price: float
    no_price: float
    mid_price: float
    spread: float
    
    # Order book depth
    bid_depth: float  # Total size on bid side
    ask_depth: float  # Total size on ask side
    
    # Changes
    price_change: float = 0.0  # Change since last snapshot
    volume_change: float = 0.0


@dataclass
class MonitoredMarket:
    """A market being monitored."""
    market: PolymarketMarket
    token_id: str  # Which token we're tracking (YES or NO)
    
    # Price history
    price_history: List[float] = field(default_factory=list)
    
    # Order book
    last_book: Optional[OrderBook] = None
    
    # Stats
    update_count: int = 0
    last_update: Optional[datetime] = None


class MarketMonitor:
    """
    Monitors Polymarket markets in real-time.
    
    Usage:
        monitor = MarketMonitor()
        
        # Add markets to monitor
        await monitor.add_market(market, "YES")
        
        # Register callback for price updates
        monitor.on_price_update(my_callback)
        
        # Start monitoring
        await monitor.start()
        
        # Get current snapshot
        snapshot = monitor.get_snapshot(market_id)
        
        # Stop
        await monitor.stop()
    """
    
    def __init__(
        self,
        update_interval_seconds: float = 5.0,
        price_history_length: int = 100
    ):
        """
        Initialize the market monitor.
        
        Args:
            update_interval_seconds: How often to poll prices
            price_history_length: How many prices to keep in history
        """
        self.update_interval = update_interval_seconds
        self.history_length = price_history_length
        
        self.client = PolymarketClient()
        self.markets: Dict[str, MonitoredMarket] = {}
        
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._price_callbacks: List[Callable] = []
        self._book_callbacks: List[Callable] = []
        
        logger.info("MarketMonitor initialized")
    
    async def start(self):
        """Start the market monitor."""
        if not await self.client.connect():
            logger.error("Failed to connect to Polymarket")
            return False
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        logger.info(f"MarketMonitor started, tracking {len(self.markets)} markets")
        return True
    
    async def stop(self):
        """Stop the market monitor."""
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        await self.client.disconnect()
        logger.info("MarketMonitor stopped")
    
    async def add_market(
        self,
        market: PolymarketMarket,
        outcome: str = "YES"
    ):
        """
        Add a market to monitor.
        
        Args:
            market: The market to monitor
            outcome: "YES" or "NO" - which token to track
        """
        token_id = market.token_id_yes if outcome == "YES" else market.token_id_no
        
        self.markets[market.condition_id] = MonitoredMarket(
            market=market,
            token_id=token_id
        )
        
        logger.info(f"Added market: {market.question[:50]}...")
    
    async def remove_market(self, market_id: str):
        """Remove a market from monitoring."""
        if market_id in self.markets:
            del self.markets[market_id]
            logger.info(f"Removed market: {market_id}")
    
    def on_price_update(self, callback: Callable):
        """Register callback for price updates."""
        self._price_callbacks.append(callback)
    
    def on_order_book_update(self, callback: Callable):
        """Register callback for order book updates."""
        self._book_callbacks.append(callback)
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self._update_all_markets()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(1)
    
    async def _update_all_markets(self):
        """Update all monitored markets."""
        for market_id, monitored in self.markets.items():
            try:
                await self._update_market(monitored)
            except Exception as e:
                logger.warning(f"Failed to update {market_id}: {e}")
    
    async def _update_market(self, monitored: MonitoredMarket):
        """Update a single market."""
        # Get order book
        book = await self.client.get_order_book(monitored.token_id)
        
        if not book:
            return
        
        # Calculate price change
        old_price = monitored.price_history[-1] if monitored.price_history else book.mid_price
        price_change = book.mid_price - old_price
        
        # Update history
        monitored.price_history.append(book.mid_price)
        if len(monitored.price_history) > self.history_length:
            monitored.price_history = monitored.price_history[-self.history_length:]
        
        # Update stats
        monitored.last_book = book
        monitored.update_count += 1
        monitored.last_update = datetime.now()
        
        # Create snapshot
        snapshot = MarketSnapshot(
            timestamp=datetime.now(),
            market_id=monitored.market.condition_id,
            question=monitored.market.question,
            yes_price=book.mid_price if monitored.token_id == monitored.market.token_id_yes else 1 - book.mid_price,
            no_price=1 - book.mid_price if monitored.token_id == monitored.market.token_id_yes else book.mid_price,
            mid_price=book.mid_price,
            spread=book.spread,
            bid_depth=sum(size for _, size in book.bids),
            ask_depth=sum(size for _, size in book.asks),
            price_change=price_change
        )
        
        # Notify callbacks
        for callback in self._price_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(snapshot)
                else:
                    callback(snapshot)
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
        for callback in self._book_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(monitored.market.condition_id, book)
                else:
                    callback(monitored.market.condition_id, book)
            except Exception as e:
                logger.error(f"Book callback error: {e}")
    
    def get_snapshot(self, market_id: str) -> Optional[MarketSnapshot]:
        """Get current snapshot for a market."""
        if market_id not in self.markets:
            return None
        
        monitored = self.markets[market_id]
        
        if not monitored.last_book:
            return None
        
        book = monitored.last_book
        
        return MarketSnapshot(
            timestamp=monitored.last_update or datetime.now(),
            market_id=market_id,
            question=monitored.market.question,
            yes_price=book.mid_price if monitored.token_id == monitored.market.token_id_yes else 1 - book.mid_price,
            no_price=1 - book.mid_price if monitored.token_id == monitored.market.token_id_yes else book.mid_price,
            mid_price=book.mid_price,
            spread=book.spread,
            bid_depth=sum(size for _, size in book.bids),
            ask_depth=sum(size for _, size in book.asks)
        )
    
    def get_price_history(self, market_id: str) -> List[float]:
        """Get price history for a market."""
        if market_id in self.markets:
            return self.markets[market_id].price_history.copy()
        return []
    
    def get_all_snapshots(self) -> Dict[str, MarketSnapshot]:
        """Get snapshots for all markets."""
        snapshots = {}
        for market_id in self.markets:
            snapshot = self.get_snapshot(market_id)
            if snapshot:
                snapshots[market_id] = snapshot
        return snapshots
"""
Polymarket Client - Interfaces with Polymarket's CLOB API.

This client handles:
- Authentication via API keys and wallet signatures
- Market discovery and data fetching
- Order book queries
- Order placement and management
- Position tracking

Polymarket uses a Central Limit Order Book (CLOB) for trading.
All trades settle on Polygon network using USDC.

IMPORTANT: This involves real money. Use with caution.
"""

import os
import time
import hmac
import hashlib
import base64
import logging
import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from config.settings import get_config

logger = logging.getLogger(__name__)
config = get_config()


class OrderSide(Enum):
    """Order side."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type."""
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


@dataclass
class PolymarketMarket:
    """Represents a Polymarket market."""
    condition_id: str
    question: str
    description: str
    
    # Token IDs for YES and NO outcomes
    token_id_yes: str
    token_id_no: str
    
    # Current prices
    yes_price: float
    no_price: float
    
    # Market metadata
    volume: float
    liquidity: float
    end_date: Optional[datetime]
    
    # Category/tags
    category: str
    tags: List[str]
    
    # Status
    is_active: bool
    is_resolved: bool
    resolution: Optional[str]  # "YES", "NO", or None


@dataclass
class OrderBook:
    """Order book for a market."""
    token_id: str
    
    # Bids (buy orders) - list of (price, size) tuples
    bids: List[Tuple[float, float]]
    
    # Asks (sell orders) - list of (price, size) tuples
    asks: List[Tuple[float, float]]
    
    # Computed values
    best_bid: float = 0.0
    best_ask: float = 1.0
    spread: float = 1.0
    mid_price: float = 0.5
    
    def __post_init__(self):
        """Calculate derived values."""
        if self.bids:
            self.best_bid = max(b[0] for b in self.bids)
        if self.asks:
            self.best_ask = min(a[0] for a in self.asks)
        
        self.spread = self.best_ask - self.best_bid
        self.mid_price = (self.best_bid + self.best_ask) / 2


@dataclass
class PolymarketOrder:
    """Represents an order on Polymarket."""
    order_id: str
    market_id: str
    token_id: str
    side: OrderSide
    order_type: OrderType
    price: float
    size: float
    filled_size: float
    status: OrderStatus
    created_at: datetime
    updated_at: datetime


@dataclass
class PolymarketPosition:
    """Represents a position on Polymarket."""
    market_id: str
    token_id: str
    side: str  # "YES" or "NO"
    size: float
    avg_price: float
    current_price: float
    unrealized_pnl: float


class PolymarketClient:
    """
    Client for Polymarket's CLOB API.
    
    Usage:
        client = PolymarketClient()
        
        # Initialize and connect
        await client.connect()
        
        # Find esports markets
        markets = await client.search_markets("league of legends")
        
        # Get order book
        book = await client.get_order_book(token_id)
        
        # Place order
        order = await client.place_order(
            token_id=token_id,
            side=OrderSide.BUY,
            price=0.55,
            size=10.0
        )
        
        # Cleanup
        await client.disconnect()
    """
    
    # API endpoints
    BASE_URL = "https://clob.polymarket.com"
    GAMMA_URL = "https://gamma-api.polymarket.com"
    
    def __init__(self):
        """Initialize the Polymarket client."""
        self.api_key = config.polymarket.api_key
        self.api_secret = config.polymarket.api_secret
        self.passphrase = config.polymarket.passphrase
        self.private_key = os.getenv("POLYMARKET_PRIVATE_KEY", "")
        self.wallet_address = os.getenv("POLYMARKET_WALLET_ADDRESS", "")
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._connected = False
        
        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 0.1  # 100ms between requests
        
        # Cache
        self._market_cache: Dict[str, PolymarketMarket] = {}
        self._cache_ttl = 60  # seconds
        self._cache_times: Dict[str, float] = {}
        
        logger.info("PolymarketClient initialized")
    
    @property
    def is_configured(self) -> bool:
        """Check if client is properly configured."""
        return bool(
            self.api_key and
            self.api_secret and
            self.passphrase and
            self.private_key and
            self.wallet_address
        )
    
    async def connect(self) -> bool:
        """
        Connect to Polymarket API.
        
        Returns:
            True if connection successful
        """
        if not self.is_configured:
            logger.error("Polymarket not configured - check .env file")
            return False
        
        try:
            self._session = aiohttp.ClientSession()
            
            # Test connection
            async with self._session.get(f"{self.BASE_URL}/") as response:
                if response.status == 200:
                    self._connected = True
                    logger.info("Connected to Polymarket API")
                    return True
                else:
                    logger.error(f"Connection failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Polymarket API."""
        if self._session:
            await self._session.close()
            self._session = None
        
        self._connected = False
        logger.info("Disconnected from Polymarket API")
    
    def _generate_signature(
        self,
        timestamp: str,
        method: str,
        path: str,
        body: str = ""
    ) -> str:
        """
        Generate API signature for authentication.
        
        Args:
            timestamp: Unix timestamp string
            method: HTTP method (GET, POST, etc.)
            path: Request path
            body: Request body (for POST)
            
        Returns:
            Base64-encoded signature
        """
        message = timestamp + method.upper() + path + body
        
        signature = hmac.new(
            base64.b64decode(self.api_secret),
            message.encode('utf-8'),
            hashlib.sha256
        )
        
        return base64.b64encode(signature.digest()).decode('utf-8')
    
    def _get_auth_headers(
        self,
        method: str,
        path: str,
        body: str = ""
    ) -> Dict[str, str]:
        """Get authentication headers for API request."""
        timestamp = str(int(time.time()))
        signature = self._generate_signature(timestamp, method, path, body)
        
        return {
            "POLY_API_KEY": self.api_key,
            "POLY_SIGNATURE": signature,
            "POLY_TIMESTAMP": timestamp,
            "POLY_PASSPHRASE": self.passphrase,
            "Content-Type": "application/json"
        }
    
    async def _request(
        self,
        method: str,
        path: str,
        params: Dict = None,
        body: Dict = None,
        authenticated: bool = False
    ) -> Optional[Dict]:
        """
        Make API request with rate limiting.
        
        Args:
            method: HTTP method
            path: API path
            params: Query parameters
            body: Request body
            authenticated: Whether to include auth headers
            
        Returns:
            Response JSON or None on error
        """
        if not self._session:
            logger.error("Not connected")
            return None
        
        # Rate limiting
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)
        
        url = f"{self.BASE_URL}{path}"
        
        headers = {}
        body_str = ""
        
        if authenticated:
            if body:
                import json
                body_str = json.dumps(body)
            headers = self._get_auth_headers(method, path, body_str)
        
        try:
            if method.upper() == "GET":
                async with self._session.get(url, params=params, headers=headers) as response:
                    self._last_request_time = time.time()
                    
                    if response.status == 200:
                        return await response.json()
                    else:
                        error = await response.text()
                        logger.error(f"API error {response.status}: {error}")
                        return None
                        
            elif method.upper() == "POST":
                async with self._session.post(url, json=body, headers=headers) as response:
                    self._last_request_time = time.time()
                    
                    if response.status in [200, 201]:
                        return await response.json()
                    else:
                        error = await response.text()
                        logger.error(f"API error {response.status}: {error}")
                        return None
                        
            elif method.upper() == "DELETE":
                async with self._session.delete(url, headers=headers) as response:
                    self._last_request_time = time.time()
                    
                    if response.status in [200, 204]:
                        return {"success": True}
                    else:
                        error = await response.text()
                        logger.error(f"API error {response.status}: {error}")
                        return None
                        
        except Exception as e:
            logger.error(f"Request error: {e}")
            return None
    
    # ================================================================
    # MARKET DISCOVERY
    # ================================================================
    
    async def get_markets(
        self,
        limit: int = 100,
        active_only: bool = True
    ) -> List[PolymarketMarket]:
        """
        Get list of markets.
        
        Args:
            limit: Maximum number of markets
            active_only: Only return active markets
            
        Returns:
            List of PolymarketMarket objects
        """
        params = {"limit": limit}
        if active_only:
            params["active"] = "true"
        
        data = await self._request("GET", "/markets", params=params)
        
        if not data:
            return []
        
        markets = []
        for item in data.get("markets", []):
            try:
                market = self._parse_market(item)
                if market:
                    markets.append(market)
            except Exception as e:
                logger.warning(f"Failed to parse market: {e}")
        
        return markets
    
    async def search_markets(
        self,
        query: str,
        limit: int = 50
    ) -> List[PolymarketMarket]:
        """
        Search for markets by keyword.
        
        Args:
            query: Search query (e.g., "league of legends", "esports")
            limit: Maximum results
            
        Returns:
            List of matching markets
        """
        # Use Gamma API for search
        try:
            async with self._session.get(
                f"{self.GAMMA_URL}/markets",
                params={"q": query, "limit": limit}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    markets = []
                    
                    for item in data:
                        try:
                            market = self._parse_gamma_market(item)
                            if market:
                                markets.append(market)
                        except Exception as e:
                            logger.warning(f"Failed to parse market: {e}")
                    
                    return markets
                else:
                    return []
                    
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    async def get_esports_markets(self) -> List[PolymarketMarket]:
        """
        Get esports-related markets.
        
        Returns:
            List of esports markets
        """
        # Search for common esports terms
        search_terms = [
            "league of legends",
            "LoL",
            "dota",
            "csgo",
            "valorant",
            "esports",
            "worlds championship"
        ]
        
        all_markets = []
        seen_ids = set()
        
        for term in search_terms:
            markets = await self.search_markets(term, limit=20)
            
            for market in markets:
                if market.condition_id not in seen_ids:
                    all_markets.append(market)
                    seen_ids.add(market.condition_id)
            
            await asyncio.sleep(0.2)  # Rate limit
        
        return all_markets
    
    async def get_market(self, condition_id: str) -> Optional[PolymarketMarket]:
        """
        Get a specific market by condition ID.
        
        Args:
            condition_id: The market condition ID
            
        Returns:
            PolymarketMarket or None
        """
        # Check cache
        if condition_id in self._market_cache:
            cache_age = time.time() - self._cache_times.get(condition_id, 0)
            if cache_age < self._cache_ttl:
                return self._market_cache[condition_id]
        
        data = await self._request("GET", f"/markets/{condition_id}")
        
        if data:
            market = self._parse_market(data)
            if market:
                self._market_cache[condition_id] = market
                self._cache_times[condition_id] = time.time()
                return market
        
        return None
    
    def _parse_market(self, data: Dict) -> Optional[PolymarketMarket]:
        """Parse market data from CLOB API."""
        try:
            tokens = data.get("tokens", [])
            yes_token = next((t for t in tokens if t.get("outcome") == "Yes"), None)
            no_token = next((t for t in tokens if t.get("outcome") == "No"), None)
            
            if not yes_token or not no_token:
                return None
            
            return PolymarketMarket(
                condition_id=data.get("condition_id", ""),
                question=data.get("question", ""),
                description=data.get("description", ""),
                token_id_yes=yes_token.get("token_id", ""),
                token_id_no=no_token.get("token_id", ""),
                yes_price=float(yes_token.get("price", 0.5)),
                no_price=float(no_token.get("price", 0.5)),
                volume=float(data.get("volume", 0)),
                liquidity=float(data.get("liquidity", 0)),
                end_date=None,  # Parse if available
                category=data.get("category", ""),
                tags=data.get("tags", []),
                is_active=data.get("active", False),
                is_resolved=data.get("closed", False),
                resolution=data.get("resolution")
            )
        except Exception as e:
            logger.warning(f"Parse error: {e}")
            return None
    
    def _parse_gamma_market(self, data: Dict) -> Optional[PolymarketMarket]:
        """Parse market data from Gamma API."""
        try:
            return PolymarketMarket(
                condition_id=data.get("conditionId", ""),
                question=data.get("question", ""),
                description=data.get("description", ""),
                token_id_yes=data.get("clobTokenIds", ["", ""])[0],
                token_id_no=data.get("clobTokenIds", ["", ""])[1] if len(data.get("clobTokenIds", [])) > 1 else "",
                yes_price=float(data.get("outcomePrices", ["0.5", "0.5"])[0]),
                no_price=float(data.get("outcomePrices", ["0.5", "0.5"])[1]) if len(data.get("outcomePrices", [])) > 1 else 0.5,
                volume=float(data.get("volume", 0)),
                liquidity=float(data.get("liquidity", 0)),
                end_date=None,
                category=data.get("category", ""),
                tags=data.get("tags", []),
                is_active=data.get("active", True),
                is_resolved=data.get("closed", False),
                resolution=None
            )
        except Exception as e:
            logger.warning(f"Parse error: {e}")
            return None
    
    # ================================================================
    # ORDER BOOK
    # ================================================================
    
    async def get_order_book(
        self,
        token_id: str,
        depth: int = 20
    ) -> Optional[OrderBook]:
        """
        Get order book for a token.
        
        Args:
            token_id: The token ID (YES or NO)
            depth: Number of price levels
            
        Returns:
            OrderBook or None
        """
        data = await self._request(
            "GET",
            f"/book",
            params={"token_id": token_id}
        )
        
        if not data:
            return None
        
        try:
            bids = [
                (float(b["price"]), float(b["size"]))
                for b in data.get("bids", [])[:depth]
            ]
            
            asks = [
                (float(a["price"]), float(a["size"]))
                for a in data.get("asks", [])[:depth]
            ]
            
            return OrderBook(
                token_id=token_id,
                bids=bids,
                asks=asks
            )
            
        except Exception as e:
            logger.error(f"Order book parse error: {e}")
            return None
    
    async def get_mid_price(self, token_id: str) -> Optional[float]:
        """Get mid price for a token."""
        book = await self.get_order_book(token_id, depth=1)
        return book.mid_price if book else None
    
    async def get_best_prices(
        self,
        token_id: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Get best bid and ask prices.
        
        Returns:
            Tuple of (best_bid, best_ask)
        """
        book = await self.get_order_book(token_id, depth=1)
        if book:
            return book.best_bid, book.best_ask
        return None, None
    
    # ================================================================
    # ORDERS
    # ================================================================
    
    async def place_order(
        self,
        token_id: str,
        side: OrderSide,
        price: float,
        size: float,
        order_type: OrderType = OrderType.LIMIT
    ) -> Optional[PolymarketOrder]:
        """
        Place an order.
        
        Args:
            token_id: Token to trade
            side: BUY or SELL
            price: Order price (0.01 to 0.99)
            size: Order size in shares
            order_type: LIMIT or MARKET
            
        Returns:
            PolymarketOrder or None on failure
        """
        if not self.is_configured:
            logger.error("Client not configured for trading")
            return None
        
        # Validate price
        if not 0.01 <= price <= 0.99:
            logger.error(f"Invalid price: {price}")
            return None
        
        # Validate size
        if size <= 0:
            logger.error(f"Invalid size: {size}")
            return None
        
        body = {
            "tokenID": token_id,
            "side": side.value,
            "price": str(price),
            "size": str(size),
            "type": order_type.value
        }
        
        # This is a simplified version - real implementation
        # requires signing with your wallet private key
        data = await self._request(
            "POST",
            "/order",
            body=body,
            authenticated=True
        )
        
        if data:
            return self._parse_order(data)
        
        return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order to cancel
            
        Returns:
            True if cancelled successfully
        """
        data = await self._request(
            "DELETE",
            f"/order/{order_id}",
            authenticated=True
        )
        
        return data is not None and data.get("success", False)
    
    async def cancel_all_orders(self) -> int:
        """
        Cancel all open orders.
        
        Returns:
            Number of orders cancelled
        """
        data = await self._request(
            "DELETE",
            "/orders",
            authenticated=True
        )
        
        if data:
            return data.get("cancelled", 0)
        return 0
    
    async def get_order(self, order_id: str) -> Optional[PolymarketOrder]:
        """Get order by ID."""
        data = await self._request(
            "GET",
            f"/order/{order_id}",
            authenticated=True
        )
        
        if data:
            return self._parse_order(data)
        return None
    
    async def get_open_orders(self) -> List[PolymarketOrder]:
        """Get all open orders."""
        data = await self._request(
            "GET",
            "/orders",
            params={"status": "OPEN"},
            authenticated=True
        )
        
        if data:
            return [
                self._parse_order(o)
                for o in data.get("orders", [])
                if self._parse_order(o)
            ]
        return []
    
    def _parse_order(self, data: Dict) -> Optional[PolymarketOrder]:
        """Parse order data."""
        try:
            return PolymarketOrder(
                order_id=data.get("id", ""),
                market_id=data.get("market", ""),
                token_id=data.get("tokenID", ""),
                side=OrderSide(data.get("side", "BUY")),
                order_type=OrderType(data.get("type", "LIMIT")),
                price=float(data.get("price", 0)),
                size=float(data.get("size", 0)),
                filled_size=float(data.get("filledSize", 0)),
                status=OrderStatus(data.get("status", "PENDING")),
                created_at=datetime.fromisoformat(data["createdAt"]) if "createdAt" in data else datetime.now(),
                updated_at=datetime.fromisoformat(data["updatedAt"]) if "updatedAt" in data else datetime.now()
            )
        except Exception as e:
            logger.warning(f"Order parse error: {e}")
            return None
    
    # ================================================================
    # POSITIONS
    # ================================================================
    
    async def get_positions(self) -> List[PolymarketPosition]:
        """Get all positions."""
        data = await self._request(
            "GET",
            "/positions",
            authenticated=True
        )
        
        if not data:
            return []
        
        positions = []
        for item in data.get("positions", []):
            try:
                pos = PolymarketPosition(
                    market_id=item.get("market", ""),
                    token_id=item.get("tokenID", ""),
                    side=item.get("outcome", "YES"),
                    size=float(item.get("size", 0)),
                    avg_price=float(item.get("avgPrice", 0)),
                    current_price=float(item.get("currentPrice", 0)),
                    unrealized_pnl=float(item.get("unrealizedPnl", 0))
                )
                positions.append(pos)
            except Exception as e:
                logger.warning(f"Position parse error: {e}")
        
        return positions
    
    async def get_balance(self) -> float:
        """Get USDC balance."""
        data = await self._request(
            "GET",
            "/balance",
            authenticated=True
        )
        
        if data:
            return float(data.get("balance", 0))
        return 0.0
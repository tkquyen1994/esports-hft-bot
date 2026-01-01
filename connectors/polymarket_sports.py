"""
Polymarket Sports Client - Specifically for esports/LoL markets.

Polymarket has sports betting under a different API structure.
This client targets: polymarket.com/sports/league-of-legends/games

Usage:
    client = PolymarketSportsClient()
    await client.connect()
    
    # Get LoL markets
    markets = await client.get_lol_markets()
    
    # Get specific match
    match = await client.get_match("lol-ig1-lng-2026-01-02")
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SportsMarket:
    """A sports betting market on Polymarket."""
    event_slug: str
    event_url: str
    question: str
    description: str
    
    # Teams/Outcomes
    team1_name: str
    team2_name: str
    
    # Token IDs for betting
    team1_token_id: str
    team2_token_id: str
    
    # Current odds/prices
    team1_price: float  # Probability team 1 wins
    team2_price: float  # Probability team 2 wins
    
    # Market info
    volume: float
    liquidity: float
    start_time: Optional[datetime]
    
    # Status
    is_active: bool
    is_resolved: bool
    winner: Optional[str]


@dataclass 
class OrderBookLevel:
    """A price level in the order book."""
    price: float
    size: float


@dataclass
class SportsOrderBook:
    """Order book for a sports market."""
    token_id: str
    bids: List[OrderBookLevel]  # Buy orders
    asks: List[OrderBookLevel]  # Sell orders
    
    @property
    def best_bid(self) -> float:
        return max((b.price for b in self.bids), default=0.0)
    
    @property
    def best_ask(self) -> float:
        return min((a.price for a in self.asks), default=1.0)
    
    @property
    def spread(self) -> float:
        return self.best_ask - self.best_bid
    
    @property
    def mid_price(self) -> float:
        return (self.best_bid + self.best_ask) / 2


class PolymarketSportsClient:
    """
    Client for Polymarket Sports/Esports betting.
    
    This targets the sports section of Polymarket which has
    esports markets including League of Legends.
    """
    
    # API Endpoints
    BASE_URL = "https://polymarket.com"
    CLOB_URL = "https://clob.polymarket.com"
    STRAPI_URL = "https://strapi-matic.polymarket.com"
    
    def __init__(self):
        """Initialize the sports client."""
        self._session: Optional[aiohttp.ClientSession] = None
        self._connected = False
        
        # Rate limiting
        self._last_request = 0
        self._min_interval = 0.2  # 200ms between requests
        
        # Cache
        self._markets_cache: Dict[str, SportsMarket] = {}
        
        logger.info("PolymarketSportsClient initialized")
    
    async def connect(self) -> bool:
        """Connect to Polymarket."""
        try:
            self._session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "application/json",
                }
            )
            
            # Test connection
            async with self._session.get(f"{self.CLOB_URL}/") as response:
                if response.status == 200:
                    self._connected = True
                    logger.info("Connected to Polymarket Sports")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Polymarket."""
        if self._session:
            await self._session.close()
            self._session = None
        self._connected = False
        logger.info("Disconnected from Polymarket Sports")
    
    async def _rate_limit(self):
        """Apply rate limiting."""
        import time
        now = time.time()
        elapsed = now - self._last_request
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_request = time.time()
    
    async def get_lol_markets(self) -> List[SportsMarket]:
        """
        Get all League of Legends markets.
        
        Returns:
            List of LoL betting markets
        """
        await self._rate_limit()
        
        try:
            # Try the events API
            url = f"{self.STRAPI_URL}/events"
            params = {
                "slug_contains": "lol",
                "_limit": 50,
                "active": "true"
            }
            
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_events(data)
                else:
                    logger.warning(f"Events API returned {response.status}")
            
            # Fallback: try markets endpoint
            return await self._fetch_lol_from_markets()
            
        except Exception as e:
            logger.error(f"Failed to get LoL markets: {e}")
            return []
    
    async def _fetch_lol_from_markets(self) -> List[SportsMarket]:
        """Fetch LoL markets from the markets endpoint."""
        try:
            url = f"{self.STRAPI_URL}/markets"
            params = {
                "slug_contains": "lol",
                "_limit": 50
            }
            
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_markets(data)
            
            return []
            
        except Exception as e:
            logger.error(f"Markets fetch failed: {e}")
            return []
    
    async def get_event_by_slug(self, slug: str) -> Optional[SportsMarket]:
        """
        Get a specific event/match by its slug.
        
        Args:
            slug: Event slug (e.g., "lol-ig1-lng-2026-01-02")
            
        Returns:
            SportsMarket or None
        """
        await self._rate_limit()
        
        try:
            # Try direct event lookup
            url = f"{self.STRAPI_URL}/events"
            params = {"slug": slug}
            
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:
                        markets = self._parse_events(data)
                        return markets[0] if markets else None
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get event {slug}: {e}")
            return None
    
    async def get_order_book(self, token_id: str) -> Optional[SportsOrderBook]:
        """
        Get order book for a token.
        
        Args:
            token_id: The token ID to get order book for
            
        Returns:
            SportsOrderBook or None
        """
        await self._rate_limit()
        
        try:
            url = f"{self.CLOB_URL}/book"
            params = {"token_id": token_id}
            
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_order_book(token_id, data)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get order book: {e}")
            return None
    
    async def get_price(self, token_id: str) -> Optional[float]:
        """Get current mid price for a token."""
        book = await self.get_order_book(token_id)
        return book.mid_price if book else None
    
    def _parse_events(self, data: List[Dict]) -> List[SportsMarket]:
        """Parse events data into SportsMarket objects."""
        markets = []
        
        for event in data:
            try:
                market = self._parse_single_event(event)
                if market:
                    markets.append(market)
            except Exception as e:
                logger.warning(f"Failed to parse event: {e}")
        
        return markets
    
    def _parse_single_event(self, event: Dict) -> Optional[SportsMarket]:
        """Parse a single event."""
        try:
            slug = event.get("slug", "")
            question = event.get("title", event.get("question", ""))
            description = event.get("description", "")
            
            # Get markets/outcomes within the event
            markets = event.get("markets", [])
            
            if not markets:
                return None
            
            # For a match, typically 2 outcomes (team1 wins, team2 wins)
            outcomes = markets[0].get("outcomes", []) if markets else []
            
            if len(outcomes) < 2:
                # Try clobTokenIds
                token_ids = markets[0].get("clobTokenIds", [])
                outcome_prices = markets[0].get("outcomePrices", [])
                
                team1_token = token_ids[0] if len(token_ids) > 0 else ""
                team2_token = token_ids[1] if len(token_ids) > 1 else ""
                team1_price = float(outcome_prices[0]) if len(outcome_prices) > 0 else 0.5
                team2_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0.5
                
                # Try to extract team names from title
                team1_name = "Team 1"
                team2_name = "Team 2"
                
                if " vs " in question.lower():
                    parts = question.lower().split(" vs ")
                    team1_name = parts[0].strip().upper()
                    team2_name = parts[1].split()[0].strip().upper() if parts[1] else "Team 2"
            else:
                team1_name = outcomes[0].get("title", "Team 1")
                team2_name = outcomes[1].get("title", "Team 2")
                team1_token = outcomes[0].get("clobTokenId", "")
                team2_token = outcomes[1].get("clobTokenId", "")
                team1_price = float(outcomes[0].get("price", 0.5))
                team2_price = float(outcomes[1].get("price", 0.5))
            
            return SportsMarket(
                event_slug=slug,
                event_url=f"{self.BASE_URL}/event/{slug}",
                question=question,
                description=description,
                team1_name=team1_name,
                team2_name=team2_name,
                team1_token_id=team1_token,
                team2_token_id=team2_token,
                team1_price=team1_price,
                team2_price=team2_price,
                volume=float(event.get("volume", 0)),
                liquidity=float(event.get("liquidity", 0)),
                start_time=None,  # Parse if available
                is_active=event.get("active", True),
                is_resolved=event.get("closed", False),
                winner=event.get("winner")
            )
            
        except Exception as e:
            logger.warning(f"Parse error: {e}")
            return None
    
    def _parse_markets(self, data: List[Dict]) -> List[SportsMarket]:
        """Parse markets data."""
        markets = []
        
        for item in data:
            try:
                slug = item.get("slug", "")
                if "lol" not in slug.lower():
                    continue
                
                question = item.get("question", "")
                
                token_ids = item.get("clobTokenIds", [])
                prices = item.get("outcomePrices", [])
                
                market = SportsMarket(
                    event_slug=slug,
                    event_url=f"{self.BASE_URL}/event/{slug}",
                    question=question,
                    description=item.get("description", ""),
                    team1_name="Team 1",
                    team2_name="Team 2",
                    team1_token_id=token_ids[0] if token_ids else "",
                    team2_token_id=token_ids[1] if len(token_ids) > 1 else "",
                    team1_price=float(prices[0]) if prices else 0.5,
                    team2_price=float(prices[1]) if len(prices) > 1 else 0.5,
                    volume=float(item.get("volume", 0)),
                    liquidity=float(item.get("liquidity", 0)),
                    start_time=None,
                    is_active=item.get("active", True),
                    is_resolved=item.get("closed", False),
                    winner=None
                )
                markets.append(market)
                
            except Exception as e:
                logger.warning(f"Market parse error: {e}")
        
        return markets
    
    def _parse_order_book(self, token_id: str, data: Dict) -> SportsOrderBook:
        """Parse order book data."""
        bids = [
            OrderBookLevel(price=float(b["price"]), size=float(b["size"]))
            for b in data.get("bids", [])
        ]
        
        asks = [
            OrderBookLevel(price=float(a["price"]), size=float(a["size"]))
            for a in data.get("asks", [])
        ]
        
        return SportsOrderBook(
            token_id=token_id,
            bids=bids,
            asks=asks
        )
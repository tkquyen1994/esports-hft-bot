"""
Polymarket LoL Trading Client - WORKING VERSION

This client successfully connects to Polymarket and fetches:
- LoL match markets (IG vs LNG, etc.)
- Live prices from CLOB API
- Order book depth
- All token IDs needed for trading

Usage:
    python polymarket_lol_client.py
"""

import asyncio
import aiohttp
import json
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from datetime import datetime


@dataclass
class OrderBookLevel:
    """A price level in the order book."""
    price: float
    size: float


@dataclass
class OrderBook:
    """Order book for a market."""
    token_id: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: str = ""
    
    @property
    def best_bid(self) -> float:
        return self.bids[0].price if self.bids else 0.0
    
    @property
    def best_ask(self) -> float:
        return self.asks[0].price if self.asks else 1.0
    
    @property
    def spread(self) -> float:
        return self.best_ask - self.best_bid
    
    @property
    def mid_price(self) -> float:
        return (self.best_bid + self.best_ask) / 2
    
    @property
    def bid_depth(self) -> float:
        return sum(b.size for b in self.bids)
    
    @property
    def ask_depth(self) -> float:
        return sum(a.size for a in self.asks)


@dataclass
class LoLMarket:
    """A LoL betting market on Polymarket."""
    # Event info
    event_slug: str
    event_title: str
    start_time: str
    
    # Market info
    market_id: str
    market_question: str
    condition_id: str
    
    # Teams/Outcomes
    team1_name: str
    team2_name: str
    
    # Token IDs (needed for trading)
    team1_token_id: str
    team2_token_id: str
    
    # Prices
    team1_price: float
    team2_price: float
    
    # Market stats
    volume: float = 0.0
    liquidity: float = 0.0
    
    @property
    def url(self) -> str:
        return f"https://polymarket.com/event/{self.event_slug}"


class PolymarketLoLClient:
    """
    Client for Polymarket LoL/Esports markets.
    
    Usage:
        client = PolymarketLoLClient()
        
        # Get all LoL markets
        markets = await client.get_lol_markets()
        
        # Get specific match
        ig_lng = await client.get_match("lol-ig1-lng-2026-01-02")
        
        # Get live price
        price = await client.get_price(market.team1_token_id)
        
        # Get order book
        book = await client.get_orderbook(market.team1_token_id)
    """
    
    GAMMA_URL = "https://gamma-api.polymarket.com"
    CLOB_URL = "https://clob.polymarket.com"
    LOL_SERIES_ID = "10311"
    
    def __init__(self):
        """Initialize client."""
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def get_lol_markets(self, active_only: bool = True) -> List[LoLMarket]:
        """
        Get all LoL markets.
        
        Returns:
            List of LoLMarket objects
        """
        session = await self._get_session()
        
        params = {
            "series_id": self.LOL_SERIES_ID,
            "limit": "100",
            "order": "startTime",
            "ascending": "true"
        }
        
        if active_only:
            params["active"] = "true"
            params["closed"] = "false"
        
        url = f"{self.GAMMA_URL}/events"
        
        markets = []
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    events = await response.json()
                    
                    for event in events:
                        event_markets = self._parse_event(event)
                        markets.extend(event_markets)
        except Exception as e:
            print(f"Error fetching markets: {e}")
        
        return markets
    
    async def get_match(self, slug: str) -> Optional[List[LoLMarket]]:
        """
        Get markets for a specific match by slug.
        
        Args:
            slug: Event slug (e.g., "lol-ig1-lng-2026-01-02")
            
        Returns:
            List of markets for that match
        """
        session = await self._get_session()
        
        url = f"{self.GAMMA_URL}/events"
        params = {"slug": slug}
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    events = await response.json()
                    
                    if events:
                        return self._parse_event(events[0])
        except Exception as e:
            print(f"Error fetching match: {e}")
        
        return None
    
    async def get_price(self, token_id: str, side: str = "buy") -> Optional[float]:
        """
        Get current price for a token.
        
        Args:
            token_id: The CLOB token ID
            side: "buy" or "sell"
            
        Returns:
            Current price or None
        """
        session = await self._get_session()
        
        url = f"{self.CLOB_URL}/price"
        params = {"token_id": token_id, "side": side}
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data.get("price", 0))
        except Exception as e:
            print(f"Error fetching price: {e}")
        
        return None
    
    async def get_orderbook(self, token_id: str) -> Optional[OrderBook]:
        """
        Get order book for a token.
        
        Args:
            token_id: The CLOB token ID
            
        Returns:
            OrderBook object or None
        """
        session = await self._get_session()
        
        url = f"{self.CLOB_URL}/book"
        params = {"token_id": token_id}
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    bids = [
                        OrderBookLevel(
                            price=float(b.get("price", 0)),
                            size=float(b.get("size", 0))
                        )
                        for b in data.get("bids", [])
                    ]
                    
                    asks = [
                        OrderBookLevel(
                            price=float(a.get("price", 0)),
                            size=float(a.get("size", 0))
                        )
                        for a in data.get("asks", [])
                    ]
                    
                    return OrderBook(
                        token_id=token_id,
                        bids=bids,
                        asks=asks,
                        timestamp=data.get("timestamp", "")
                    )
        except Exception as e:
            print(f"Error fetching orderbook: {e}")
        
        return None
    
    async def get_both_orderbooks(self, market: LoLMarket) -> Tuple[Optional[OrderBook], Optional[OrderBook]]:
        """
        Get order books for both sides of a market.
        
        Returns:
            Tuple of (team1_book, team2_book)
        """
        book1 = await self.get_orderbook(market.team1_token_id)
        book2 = await self.get_orderbook(market.team2_token_id)
        return book1, book2
    
    def _parse_event(self, event: Dict) -> List[LoLMarket]:
        """Parse event data into LoLMarket objects."""
        markets = []
        
        event_slug = event.get("slug", "")
        event_title = event.get("title", "Unknown")
        start_time = event.get("startTime", "")
        
        for mkt in event.get("markets", []):
            try:
                # Parse JSON strings
                outcomes = mkt.get("outcomes", "[]")
                prices = mkt.get("outcomePrices", "[]")
                tokens = mkt.get("clobTokenIds", "[]")
                
                if isinstance(outcomes, str):
                    outcomes = json.loads(outcomes)
                if isinstance(prices, str):
                    prices = json.loads(prices)
                if isinstance(tokens, str):
                    tokens = json.loads(tokens)
                
                if len(outcomes) >= 2 and len(prices) >= 2 and len(tokens) >= 2:
                    market = LoLMarket(
                        event_slug=event_slug,
                        event_title=event_title,
                        start_time=start_time,
                        market_id=mkt.get("id", ""),
                        market_question=mkt.get("question", ""),
                        condition_id=mkt.get("conditionId", ""),
                        team1_name=outcomes[0],
                        team2_name=outcomes[1],
                        team1_token_id=tokens[0],
                        team2_token_id=tokens[1],
                        team1_price=float(prices[0]),
                        team2_price=float(prices[1]),
                        volume=float(mkt.get("volumeNum", mkt.get("volume", 0)) or 0),
                        liquidity=float(mkt.get("liquidityNum", mkt.get("liquidity", 0)) or 0)
                    )
                    markets.append(market)
            except Exception as e:
                print(f"Error parsing market: {e}")
        
        return markets


async def main():
    """Demo the client."""
    
    print("=" * 70)
    print("POLYMARKET LOL CLIENT - DEMO")
    print("=" * 70)
    
    client = PolymarketLoLClient()
    
    try:
        # Get all LoL markets
        print("\n1. Fetching all LoL markets...")
        markets = await client.get_lol_markets()
        
        print(f"   Found {len(markets)} markets\n")
        
        # Group by event
        events = {}
        for m in markets:
            if m.event_slug not in events:
                events[m.event_slug] = []
            events[m.event_slug].append(m)
        
        for slug, event_markets in events.items():
            print(f"\n📊 {event_markets[0].event_title}")
            print(f"   URL: {event_markets[0].url}")
            print(f"   Start: {event_markets[0].start_time}")
            print(f"   Markets: {len(event_markets)}")
        
        # Find IG vs LNG
        ig_lng = [m for m in markets if "ig" in m.event_slug.lower() and "lng" in m.event_slug.lower()]
        
        if ig_lng:
            print("\n" + "=" * 70)
            print("🎮 IG vs LNG MATCH DETAILS")
            print("=" * 70)
            
            # Main match market (BO5)
            main_market = next((m for m in ig_lng if "BO5" in m.market_question), ig_lng[0])
            
            print(f"\nMain Market: {main_market.market_question}")
            print(f"URL: {main_market.url}")
            
            # Get live prices
            print("\n2. Fetching live prices...")
            price1 = await client.get_price(main_market.team1_token_id)
            price2 = await client.get_price(main_market.team2_token_id)
            
            print(f"\n   Current Prices:")
            print(f"   {main_market.team1_name}: ${price1:.3f} ({price1*100:.1f}%)" if price1 else f"   {main_market.team1_name}: N/A")
            print(f"   {main_market.team2_name}: ${price2:.3f} ({price2*100:.1f}%)" if price2 else f"   {main_market.team2_name}: N/A")
            
            # Get order book
            print("\n3. Fetching order book...")
            book = await client.get_orderbook(main_market.team1_token_id)
            
            if book:
                print(f"\n   {main_market.team1_name} Order Book:")
                print(f"   Best Bid: ${book.best_bid:.3f}")
                print(f"   Best Ask: ${book.best_ask:.3f}")
                print(f"   Spread: ${book.spread:.4f} ({book.spread*100:.2f}%)")
                print(f"   Mid Price: ${book.mid_price:.3f}")
                print(f"   Bid Depth: {book.bid_depth:.1f} shares")
                print(f"   Ask Depth: {book.ask_depth:.1f} shares")
                
                print(f"\n   Top 5 Bids:")
                for b in book.bids[:5]:
                    print(f"      ${b.price:.3f} x {b.size:.1f}")
                
                print(f"\n   Top 5 Asks:")
                for a in book.asks[:5]:
                    print(f"      ${a.price:.3f} x {a.size:.1f}")
            
            # Show all markets for the match
            print("\n" + "-" * 70)
            print("ALL MARKETS FOR IG vs LNG:")
            print("-" * 70)
            
            for m in ig_lng:
                print(f"\n   {m.market_question}")
                print(f"   {m.team1_name}: ${m.team1_price:.2f} | {m.team2_name}: ${m.team2_price:.2f}")
                print(f"   Volume: ${m.volume:,.0f} | Liquidity: ${m.liquidity:,.0f}")
                print(f"   Token IDs:")
                print(f"     {m.team1_name}: {m.team1_token_id}")
                print(f"     {m.team2_name}: {m.team2_token_id}")
        
    finally:
        await client.close()
    
    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

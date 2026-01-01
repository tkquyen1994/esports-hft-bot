"""
Fetch LoL Markets from Polymarket - V2

Properly extracts token IDs and fetches order books.
"""

import asyncio
import aiohttp
import json
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class LoLMarket:
    """A LoL market on Polymarket."""
    event_slug: str
    event_title: str
    market_question: str
    
    team1_name: str
    team2_name: str
    team1_token_id: str
    team2_token_id: str
    team1_price: float
    team2_price: float
    
    condition_id: str = ""
    start_time: str = ""


async def fetch_lol_markets() -> List[LoLMarket]:
    """Fetch League of Legends markets from Polymarket."""
    
    print("=" * 70)
    print("FETCHING LOL MARKETS FROM POLYMARKET")
    print("=" * 70)
    
    markets = []
    
    async with aiohttp.ClientSession() as session:
        
        # Fetch LoL events using series_id
        print("\nFetching LoL events (series_id=10311)...")
        
        url = "https://gamma-api.polymarket.com/events"
        params = {
            "series_id": "10311",
            "active": "true",
            "closed": "false",
            "limit": "50",
            "order": "startTime",
            "ascending": "true"
        }
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    events = await response.json()
                    print(f"Found {len(events)} LoL events!\n")
                    
                    for event in events:
                        event_slug = event.get("slug", "")
                        event_title = event.get("title", "Unknown")
                        start_time = event.get("startTime", "TBD")
                        
                        print(f"Event: {event_title}")
                        print(f"  Slug: {event_slug}")
                        print(f"  Start: {start_time}")
                        
                        # Process markets within event
                        event_markets = event.get("markets", [])
                        
                        for mkt in event_markets:
                            question = mkt.get("question", "")
                            condition_id = mkt.get("conditionId", "")
                            
                            # Get outcomes and prices
                            outcomes = mkt.get("outcomes", "[]")
                            prices = mkt.get("outcomePrices", "[]")
                            clob_token_ids = mkt.get("clobTokenIds", [])
                            
                            # Parse JSON strings if needed
                            if isinstance(outcomes, str):
                                try:
                                    outcomes = json.loads(outcomes)
                                except:
                                    outcomes = []
                            
                            if isinstance(prices, str):
                                try:
                                    prices = json.loads(prices)
                                except:
                                    prices = []
                            
                            # Ensure clob_token_ids is a list
                            if isinstance(clob_token_ids, str):
                                try:
                                    clob_token_ids = json.loads(clob_token_ids)
                                except:
                                    clob_token_ids = []
                            
                            if len(outcomes) >= 2 and len(prices) >= 2 and len(clob_token_ids) >= 2:
                                market = LoLMarket(
                                    event_slug=event_slug,
                                    event_title=event_title,
                                    market_question=question,
                                    team1_name=outcomes[0],
                                    team2_name=outcomes[1],
                                    team1_token_id=str(clob_token_ids[0]),
                                    team2_token_id=str(clob_token_ids[1]),
                                    team1_price=float(prices[0]),
                                    team2_price=float(prices[1]),
                                    condition_id=condition_id,
                                    start_time=start_time
                                )
                                markets.append(market)
                                
                                print(f"\n  Market: {question}")
                                print(f"    {outcomes[0]}: ${float(prices[0]):.3f} ({float(prices[0])*100:.1f}%)")
                                print(f"      Token: {clob_token_ids[0]}")
                                print(f"    {outcomes[1]}: ${float(prices[1]):.3f} ({float(prices[1])*100:.1f}%)")
                                print(f"      Token: {clob_token_ids[1]}")
                            else:
                                print(f"\n  Market: {question} (incomplete data)")
                                print(f"    Outcomes: {outcomes}")
                                print(f"    Prices: {prices}")
                                print(f"    Token IDs: {clob_token_ids}")
                        
                        print()
                else:
                    print(f"Error: Status {response.status}")
                    
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
    
    return markets


async def get_orderbook(session: aiohttp.ClientSession, token_id: str) -> Optional[Dict]:
    """Get order book for a specific token."""
    
    url = "https://clob.polymarket.com/book"
    params = {"token_id": token_id}
    
    try:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"  Order book error: Status {response.status}")
                text = await response.text()
                print(f"  Response: {text[:200]}")
    except Exception as e:
        print(f"  Order book error: {e}")
    
    return None


async def get_price(session: aiohttp.ClientSession, token_id: str, side: str = "buy") -> Optional[float]:
    """Get current price for a token."""
    
    url = "https://clob.polymarket.com/price"
    params = {"token_id": token_id, "side": side}
    
    try:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return float(data.get("price", 0))
    except:
        pass
    
    return None


async def display_market_details(market: LoLMarket):
    """Display detailed market information with order book."""
    
    print("\n" + "=" * 70)
    print(f"MARKET: {market.market_question}")
    print("=" * 70)
    
    print(f"\nEvent: {market.event_title}")
    print(f"Start Time: {market.start_time}")
    print(f"URL: https://polymarket.com/event/{market.event_slug}")
    
    print(f"\nCurrent Prices (from Gamma API):")
    print(f"  {market.team1_name}: ${market.team1_price:.3f} ({market.team1_price*100:.1f}%)")
    print(f"  {market.team2_name}: ${market.team2_price:.3f} ({market.team2_price*100:.1f}%)")
    
    print(f"\nToken IDs:")
    print(f"  {market.team1_name}: {market.team1_token_id}")
    print(f"  {market.team2_name}: {market.team2_token_id}")
    
    async with aiohttp.ClientSession() as session:
        
        # Get live prices from CLOB
        print(f"\nFetching live prices from CLOB API...")
        
        price1 = await get_price(session, market.team1_token_id, "buy")
        price2 = await get_price(session, market.team2_token_id, "buy")
        
        if price1 is not None:
            print(f"  {market.team1_name} buy price: ${price1:.3f}")
        if price2 is not None:
            print(f"  {market.team2_name} buy price: ${price2:.3f}")
        
        # Get order books
        print(f"\nFetching order book for {market.team1_name}...")
        book1 = await get_orderbook(session, market.team1_token_id)
        
        if book1:
            bids = book1.get("bids", [])
            asks = book1.get("asks", [])
            
            print(f"\n  {market.team1_name} Order Book:")
            
            if bids:
                best_bid = float(bids[0].get("price", 0))
                print(f"  BIDS (buy orders):")
                for bid in bids[:5]:
                    p = float(bid.get("price", 0))
                    s = float(bid.get("size", 0))
                    print(f"    ${p:.3f} x {s:.1f}")
            else:
                print(f"  No bids")
                best_bid = 0
            
            if asks:
                best_ask = float(asks[0].get("price", 0))
                print(f"  ASKS (sell orders):")
                for ask in asks[:5]:
                    p = float(ask.get("price", 0))
                    s = float(ask.get("size", 0))
                    print(f"    ${p:.3f} x {s:.1f}")
            else:
                print(f"  No asks")
                best_ask = 1.0
            
            if bids and asks:
                spread = best_ask - best_bid
                mid = (best_bid + best_ask) / 2
                print(f"\n  Summary:")
                print(f"    Best Bid: ${best_bid:.3f}")
                print(f"    Best Ask: ${best_ask:.3f}")
                print(f"    Spread: ${spread:.4f} ({spread*100:.2f}%)")
                print(f"    Mid Price: ${mid:.3f}")


async def main():
    """Main function."""
    
    # Fetch all LoL markets
    markets = await fetch_lol_markets()
    
    if not markets:
        print("\nNo markets found!")
        return
    
    print("\n" + "=" * 70)
    print(f"FOUND {len(markets)} TRADEABLE MARKETS")
    print("=" * 70)
    
    # Group by event
    events = {}
    for m in markets:
        if m.event_slug not in events:
            events[m.event_slug] = []
        events[m.event_slug].append(m)
    
    for slug, event_markets in events.items():
        print(f"\n{event_markets[0].event_title}")
        print(f"  URL: https://polymarket.com/event/{slug}")
        print(f"  Markets: {len(event_markets)}")
        
        for m in event_markets:
            print(f"    - {m.market_question}")
            print(f"      {m.team1_name}: ${m.team1_price:.2f} | {m.team2_name}: ${m.team2_price:.2f}")
    
    # Show detailed view of the main IG vs LNG match
    ig_lng_markets = [m for m in markets if "ig" in m.event_slug.lower() and "lng" in m.event_slug.lower()]
    
    if ig_lng_markets:
        # Find the main BO5 market (not individual games)
        main_market = next((m for m in ig_lng_markets if "BO5" in m.market_question or "Game" not in m.market_question), ig_lng_markets[0])
        
        print("\n\n" + "=" * 70)
        print("DETAILED VIEW: IG vs LNG MAIN MARKET")
        print("=" * 70)
        
        await display_market_details(main_market)
        
        # Also show Game 1 market
        game1_market = next((m for m in ig_lng_markets if "Game 1" in m.market_question), None)
        if game1_market:
            print("\n\n" + "=" * 70)
            print("DETAILED VIEW: IG vs LNG GAME 1")
            print("=" * 70)
            await display_market_details(game1_market)


if __name__ == "__main__":
    asyncio.run(main())
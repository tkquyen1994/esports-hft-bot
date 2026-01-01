"""
Debug: View raw LoL market data from Polymarket
"""

import asyncio
import aiohttp
import json


async def debug_lol_markets():
    """Debug LoL market data."""
    
    print("=" * 70)
    print("DEBUG: RAW LOL MARKET DATA")
    print("=" * 70)
    
    async with aiohttp.ClientSession() as session:
        
        url = "https://gamma-api.polymarket.com/events"
        params = {
            "series_id": "10311",
            "active": "true",
            "closed": "false",
            "limit": "5"
        }
        
        async with session.get(url, params=params) as response:
            if response.status == 200:
                events = await response.json()
                
                # Look at first event
                if events:
                    event = events[0]
                    
                    print(f"\nEvent Title: {event.get('title')}")
                    print(f"Event Slug: {event.get('slug')}")
                    
                    # Look at first market
                    markets = event.get("markets", [])
                    if markets:
                        market = markets[0]
                        
                        print(f"\n--- MARKET DATA ---")
                        print(f"Question: {market.get('question')}")
                        print(f"Condition ID: {market.get('conditionId')}")
                        
                        # Raw clobTokenIds
                        clob_tokens = market.get("clobTokenIds")
                        print(f"\nclobTokenIds type: {type(clob_tokens)}")
                        print(f"clobTokenIds raw: {clob_tokens}")
                        
                        # Parse if string
                        if isinstance(clob_tokens, str):
                            try:
                                clob_tokens = json.loads(clob_tokens)
                                print(f"clobTokenIds parsed: {clob_tokens}")
                            except:
                                print("Failed to parse as JSON")
                        
                        # If it's a list
                        if isinstance(clob_tokens, list):
                            print(f"\nToken ID list length: {len(clob_tokens)}")
                            for i, token in enumerate(clob_tokens):
                                print(f"  Token {i}: {token}")
                                print(f"    Type: {type(token)}")
                                print(f"    Length: {len(str(token))}")
                        
                        # Outcomes and prices
                        outcomes = market.get("outcomes")
                        prices = market.get("outcomePrices")
                        
                        print(f"\noutcomes type: {type(outcomes)}")
                        print(f"outcomes raw: {outcomes}")
                        
                        print(f"\noutcomePrices type: {type(prices)}")
                        print(f"outcomePrices raw: {prices}")
                        
                        # Try fetching order book with first token
                        if isinstance(clob_tokens, list) and len(clob_tokens) > 0:
                            token_id = clob_tokens[0]
                            
                            print(f"\n--- TESTING ORDER BOOK ---")
                            print(f"Using token: {token_id}")
                            
                            book_url = "https://clob.polymarket.com/book"
                            
                            async with session.get(book_url, params={"token_id": token_id}) as book_response:
                                print(f"Order book status: {book_response.status}")
                                
                                if book_response.status == 200:
                                    book_data = await book_response.json()
                                    print(f"Order book data: {json.dumps(book_data, indent=2)[:500]}")
                                else:
                                    error = await book_response.text()
                                    print(f"Error response: {error}")
                            
                            # Try price endpoint
                            print(f"\n--- TESTING PRICE ---")
                            price_url = "https://clob.polymarket.com/price"
                            
                            async with session.get(price_url, params={"token_id": token_id, "side": "buy"}) as price_response:
                                print(f"Price status: {price_response.status}")
                                
                                if price_response.status == 200:
                                    price_data = await price_response.json()
                                    print(f"Price data: {price_data}")
                                else:
                                    error = await price_response.text()
                                    print(f"Error: {error}")
                        
                        # Print full market JSON for reference
                        print(f"\n--- FULL MARKET JSON ---")
                        print(json.dumps(market, indent=2)[:2000])
            else:
                print(f"Error: {response.status}")


if __name__ == "__main__":
    asyncio.run(debug_lol_markets())
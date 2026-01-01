#!/usr/bin/env python3
"""Check what historical data we can access from PandaScore."""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("PANDASCORE_API_KEY")
BASE_URL = "https://api.pandascore.co"

headers = {"Authorization": f"Bearer {API_KEY}"}

print("=" * 60)
print("CHECKING HISTORICAL DATA AVAILABILITY")
print("=" * 60)

# 1. Get recent past matches
print("\n📍 Recent completed LoL matches:")
print("-" * 50)

resp = requests.get(
    f"{BASE_URL}/lol/matches/past",
    headers=headers,
    params={"per_page": 10, "sort": "-end_at"},
    timeout=10
)

if resp.status_code == 200:
    matches = resp.json()
    for m in matches[:10]:
        name = m.get("name", "?")
        league = m.get("league", {}).get("name", "?")
        end_at = m.get("end_at", "?")[:10] if m.get("end_at") else "?"
        winner = m.get("winner", {})
        winner_name = winner.get("name", "TBD") if winner else "TBD"
        
        # Get scores
        results = m.get("results", [])
        if len(results) >= 2:
            score = f"{results[0].get('score', 0)}-{results[1].get('score', 0)}"
        else:
            score = "?-?"
        
        print(f"  {end_at} | {league[:15]:15} | {name[:30]:30} | {score} | W:{winner_name[:10]}")
else:
    print(f"  Error: {resp.status_code}")

# 2. Check if we can get match details with games
print("\n📍 Checking match detail access:")
print("-" * 50)

if resp.status_code == 200 and matches:
    test_match = matches[0]
    match_id = test_match.get("id")
    
    detail_resp = requests.get(
        f"{BASE_URL}/lol/matches/{match_id}",
        headers=headers,
        timeout=10
    )
    
    if detail_resp.status_code == 200:
        detail = detail_resp.json()
        print(f"  ✅ Can access match details")
        print(f"  Match: {detail.get('name')}")
        
        games = detail.get("games", [])
        print(f"  Games in match: {len(games)}")
        
        if games:
            game = games[0]
            print(f"  Game 1 data available:")
            print(f"    - winner: {game.get('winner', {}).get('name', '?') if game.get('winner') else '?'}")
            print(f"    - length: {game.get('length', '?')}s")
            print(f"    - detailed_stats: {game.get('detailed_stats', False)}")
    else:
        print(f"  ❌ Cannot access match details: {detail_resp.status_code}")

# 3. Check for tournaments/leagues we can backtest
print("\n📍 Available leagues for backtesting:")
print("-" * 50)

resp = requests.get(
    f"{BASE_URL}/lol/leagues",
    headers=headers,
    params={"per_page": 20},
    timeout=10
)

if resp.status_code == 200:
    leagues = resp.json()
    major_leagues = [l for l in leagues if l.get("name") in [
        "LCK", "LPL", "LEC", "LCS", "Worlds", "MSI", "LCK CL", "EMEA Masters"
    ]]
    
    for league in major_leagues[:10]:
        name = league.get("name", "?")
        league_id = league.get("id")
        print(f"  {name:20} (id: {league_id})")

# 4. Check a specific past tournament
print("\n📍 Recent tournaments with matches:")
print("-" * 50)

resp = requests.get(
    f"{BASE_URL}/lol/tournaments/past",
    headers=headers,
    params={"per_page": 5, "sort": "-end_at"},
    timeout=10
)

if resp.status_code == 200:
    tournaments = resp.json()
    for t in tournaments:
        name = t.get("name", "?")
        league = t.get("league", {}).get("name", "?")
        matches_count = len(t.get("matches", []))
        print(f"  {league:15} | {name[:35]:35} | {matches_count} matches")

print("\n" + "=" * 60)

#!/usr/bin/env python3
"""
Test LoL Esports Live Stats API

This script checks:
1. What matches are currently live
2. If IG vs LNG match is available
3. If live stats are available for the match
"""

import requests
import json
from datetime import datetime

# API Configuration
ESPORTS_API = "https://esports-api.lolesports.com/persisted/gw"
LIVE_STATS_API = "https://feed.lolesports.com/livestats/v1"
API_KEY = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"

HEADERS = {
    "x-api-key": API_KEY
}


def get_live_matches():
    """Get currently live matches."""
    print("=" * 60)
    print("CHECKING LIVE MATCHES")
    print("=" * 60)
    
    url = f"{ESPORTS_API}/getLive"
    params = {"hl": "en-US"}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            events = data.get("data", {}).get("schedule", {}).get("events", [])
            
            if not events:
                print("No live matches right now.")
                return []
            
            print(f"\nFound {len(events)} live event(s):\n")
            
            matches = []
            for event in events:
                match = event.get("match", {})
                teams = match.get("teams", [])
                league = event.get("league", {})
                
                if len(teams) >= 2:
                    team1 = teams[0].get("name", "TBD")
                    team2 = teams[1].get("name", "TBD")
                    score1 = teams[0].get("result", {}).get("gameWins", 0)
                    score2 = teams[1].get("result", {}).get("gameWins", 0)
                    
                    match_id = match.get("id", "")
                    league_name = league.get("name", "Unknown")
                    
                    print(f"  {team1} vs {team2}")
                    print(f"  Score: {score1} - {score2}")
                    print(f"  League: {league_name}")
                    print(f"  Match ID: {match_id}")
                    print()
                    
                    matches.append({
                        "match_id": match_id,
                        "team1": team1,
                        "team2": team2,
                        "league": league_name
                    })
            
            return matches
        else:
            print(f"Error: {response.text}")
            return []
            
    except Exception as e:
        print(f"Error: {e}")
        return []


def get_schedule():
    """Get upcoming matches to find IG vs LNG."""
    print("\n" + "=" * 60)
    print("SEARCHING FOR IG vs LNG MATCH")
    print("=" * 60)
    
    url = f"{ESPORTS_API}/getSchedule"
    params = {"hl": "en-US"}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            events = data.get("data", {}).get("schedule", {}).get("events", [])
            
            print(f"\nSearching through {len(events)} events...")
            
            for event in events:
                match = event.get("match", {})
                teams = match.get("teams", [])
                
                if len(teams) >= 2:
                    team1 = teams[0].get("name", "").lower()
                    team2 = teams[1].get("name", "").lower()
                    
                    # Look for IG vs LNG
                    has_ig = "invictus" in team1 or "invictus" in team2 or team1 == "ig" or team2 == "ig"
                    has_lng = "lng" in team1 or "lng" in team2
                    
                    if has_ig and has_lng:
                        match_id = match.get("id", "")
                        state = event.get("state", "")
                        start_time = event.get("startTime", "")
                        league = event.get("league", {}).get("name", "")
                        
                        print(f"\n✓ FOUND: {teams[0].get('name')} vs {teams[1].get('name')}")
                        print(f"  Match ID: {match_id}")
                        print(f"  State: {state}")
                        print(f"  Start Time: {start_time}")
                        print(f"  League: {league}")
                        
                        return match_id
            
            print("\nIG vs LNG match not found in schedule.")
            print("It may be listed under a different tournament or not yet scheduled.")
            return None
        else:
            print(f"Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None


def get_event_details(match_id):
    """Get game IDs for a match."""
    print(f"\n" + "=" * 60)
    print(f"GETTING EVENT DETAILS FOR MATCH {match_id}")
    print("=" * 60)
    
    url = f"{ESPORTS_API}/getEventDetails"
    params = {"hl": "en-US", "id": match_id}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            event = data.get("data", {}).get("event", {})
            match = event.get("match", {})
            games = match.get("games", [])
            
            print(f"\nFound {len(games)} game(s):")
            
            game_ids = []
            for game in games:
                game_id = game.get("id", "")
                state = game.get("state", "")
                number = game.get("number", 0)
                
                print(f"  Game {number}: ID={game_id}, State={state}")
                game_ids.append({"id": game_id, "number": number, "state": state})
            
            return game_ids
        else:
            print(f"Error: {response.text}")
            return []
            
    except Exception as e:
        print(f"Error: {e}")
        return []


def get_live_stats(game_id):
    """Get live stats for a game."""
    print(f"\n" + "=" * 60)
    print(f"GETTING LIVE STATS FOR GAME {game_id}")
    print("=" * 60)
    
    url = f"{LIVE_STATS_API}/window/{game_id}"
    
    try:
        response = requests.get(url)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            game_state = "unknown"
            frames = data.get("frames", [])
            
            if frames:
                latest = frames[-1]
                game_state = latest.get("gameState", "unknown")
                
                blue = latest.get("blueTeam", {})
                red = latest.get("redTeam", {})
                
                print(f"\n✓ LIVE STATS AVAILABLE!")
                print(f"  Game State: {game_state}")
                print(f"\n  Blue Team:")
                print(f"    Kills: {blue.get('totalKills', 0)}")
                print(f"    Gold: {blue.get('totalGold', 0)}")
                print(f"    Towers: {blue.get('towers', 0)}")
                print(f"    Dragons: {blue.get('dragons', [])}")
                print(f"    Barons: {blue.get('barons', 0)}")
                
                print(f"\n  Red Team:")
                print(f"    Kills: {red.get('totalKills', 0)}")
                print(f"    Gold: {red.get('totalGold', 0)}")
                print(f"    Towers: {red.get('towers', 0)}")
                print(f"    Dragons: {red.get('dragons', [])}")
                print(f"    Barons: {red.get('barons', 0)}")
                
                return data
            else:
                print("No frames available yet.")
                return None
                
        elif response.status_code == 404:
            print("Live stats not available for this game.")
            print("This could mean:")
            print("  - Game hasn't started yet")
            print("  - Game is from a region without live stats (e.g., LPL)")
            return None
        else:
            print(f"Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None


def get_leagues():
    """Get list of leagues to find LPL."""
    print("\n" + "=" * 60)
    print("CHECKING AVAILABLE LEAGUES")
    print("=" * 60)
    
    url = f"{ESPORTS_API}/getLeagues"
    params = {"hl": "en-US"}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            leagues = data.get("data", {}).get("leagues", [])
            
            print(f"\nFound {len(leagues)} leagues:")
            
            lpl_id = None
            for league in leagues:
                name = league.get("name", "")
                league_id = league.get("id", "")
                region = league.get("region", "")
                
                # Show Chinese leagues
                if "lpl" in name.lower() or "china" in region.lower() or "demacia" in name.lower():
                    print(f"  * {name} (ID: {league_id}, Region: {region})")
                    if "lpl" in name.lower():
                        lpl_id = league_id
            
            return lpl_id
        else:
            print(f"Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    print("\n" + "=" * 60)
    print("LOL ESPORTS API TEST")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    
    # 1. Check for live matches
    live_matches = get_live_matches()
    
    # 2. Check leagues
    lpl_id = get_leagues()
    
    # 3. Search for IG vs LNG
    match_id = get_schedule()
    
    # 4. If found, get event details
    if match_id:
        games = get_event_details(match_id)
        
        # 5. Try to get live stats for any game
        if games:
            for game in games:
                if game.get("state") in ["inProgress", "in_game"]:
                    get_live_stats(game["id"])
                    break
            else:
                print("\nNo games currently in progress.")
                print("Will test with first game ID when match starts.")
                if games:
                    get_live_stats(games[0]["id"])
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("""
The LoL Esports API provides:
✓ Match schedules and IDs
✓ Real-time game state (kills, gold, dragons, barons, towers)
✓ No rate limits mentioned
✓ Free public API key

IMPORTANT NOTE FOR LPL:
The documentation mentions LPL (China) matches may have limited
live stats because they run on Tencent's infrastructure, not Riot's.

For tonight's IG vs LNG match:
- If live stats work: Bot will auto-detect all game events
- If live stats don't work: Bot falls back to manual input

Run this script again when the match starts to verify live stats!
""")


if __name__ == "__main__":
    main()

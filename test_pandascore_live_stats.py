import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("PANDASCORE_API_KEY")
MATCH_ID = 1280749  # IG vs LNG

print(f"Fetching live stats for Match ID: {MATCH_ID}\n")

headers = {"Authorization": f"Bearer {API_KEY}"}

# Get match details
url = f"https://api.pandascore.co/lol/matches/{MATCH_ID}"
response = requests.get(url, headers=headers)

if response.status_code == 200:
    match = response.json()
    
    print("=" * 50)
    print("MATCH INFO")
    print("=" * 50)
    
    opponents = match.get("opponents", [])
    if len(opponents) >= 2:
        t1 = opponents[0].get("opponent", {})
        t2 = opponents[1].get("opponent", {})
        print(f"Teams: {t1.get('name')} vs {t2.get('name')}")
    
    print(f"League: {match.get('league', {}).get('name')}")
    print(f"Series: Best of {match.get('number_of_games')}")
    print(f"Status: {match.get('status')}")
    
    # Get current score
    results = match.get("results", [])
    if results:
        print(f"\nSeries Score:")
        for r in results:
            team_id = r.get("team_id")
            score = r.get("score", 0)
            # Find team name
            for opp in opponents:
                if opp.get("opponent", {}).get("id") == team_id:
                    print(f"  {opp.get('opponent', {}).get('acronym')}: {score}")
    
    # Get games
    games = match.get("games", [])
    print(f"\nGames played: {len(games)}")
    
    for game in games:
        print(f"\n--- Game {game.get('position')} ---")
        print(f"Status: {game.get('status')}")
        print(f"Game ID: {game.get('id')}")
        
        if game.get('status') == 'running':
            print("🔴 THIS GAME IS LIVE!")
            
            # Try to get detailed game stats
            game_id = game.get('id')
            game_url = f"https://api.pandascore.co/lol/games/{game_id}"
            game_resp = requests.get(game_url, headers=headers)
            
            if game_resp.status_code == 200:
                game_data = game_resp.json()
                
                teams = game_data.get("teams", [])
                for team in teams:
                    print(f"\n  {team.get('acronym')} ({team.get('color')} side):")
                    print(f"    Kills: {team.get('kills', 'N/A')}")
                    print(f"    Towers: {team.get('tower_kills', 'N/A')}")
                    print(f"    Dragons: {team.get('dragon_kills', 'N/A')}")
                    print(f"    Barons: {team.get('baron_kills', 'N/A')}")
                    print(f"    Gold: {team.get('gold_earned', 'N/A')}")
        
        elif game.get('status') == 'finished':
            winner = game.get('winner', {})
            print(f"Winner: {winner.get('acronym', 'Unknown')}")

else:
    print(f"Error: {response.status_code}")
    print(response.text)

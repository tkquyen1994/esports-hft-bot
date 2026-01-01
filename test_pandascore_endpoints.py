import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("PANDASCORE_API_KEY")
headers = {"Authorization": f"Bearer {API_KEY}"}

print("Testing PandaScore API endpoints...\n")

endpoints = [
    ("Running matches", "https://api.pandascore.co/lol/matches/running"),
    ("Upcoming matches", "https://api.pandascore.co/lol/matches/upcoming?per_page=3"),
    ("Past matches", "https://api.pandascore.co/lol/matches/past?per_page=3"),
    ("Match details", "https://api.pandascore.co/lol/matches/1280749"),
    ("Leagues", "https://api.pandascore.co/lol/leagues"),
    ("Teams", "https://api.pandascore.co/lol/teams?per_page=3"),
    ("Live events", "https://api.pandascore.co/lives"),
]

for name, url in endpoints:
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        status = "✅" if resp.status_code == 200 else f"❌ {resp.status_code}"
        print(f"{status} {name}")
        
        # Show sample data for successful requests
        if resp.status_code == 200 and name == "Running matches":
            data = resp.json()
            if data:
                print(f"   Found {len(data)} live match(es)")
    except Exception as e:
        print(f"❌ {name}: {e}")

print("\n" + "=" * 50)
print("If Match details shows 403, you need a paid plan")
print("for live in-game statistics.")
print("=" * 50)

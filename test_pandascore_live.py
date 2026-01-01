import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("PANDASCORE_API_KEY")
if not API_KEY:
    print("❌ PANDASCORE_API_KEY not set in .env")
    exit(1)

print("Checking PandaScore for live LoL matches...\n")

url = "https://api.pandascore.co/lol/matches/running"
headers = {"Authorization": f"Bearer {API_KEY}"}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    matches = response.json()
    if matches:
        for match in matches:
            t1 = match.get("opponents", [{}])[0].get("opponent", {}).get("acronym", "?")
            t2 = match.get("opponents", [{}])[1].get("opponent", {}).get("acronym", "?") if len(match.get("opponents", [])) > 1 else "?"
            league = match.get("league", {}).get("name", "Unknown")
            print(f"🎮 LIVE: {t1} vs {t2} ({league})")
            print(f"   Match ID: {match.get('id')}")
            print(f"   Status: {match.get('status')}")
            print()
    else:
        print("No live matches found on PandaScore")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)

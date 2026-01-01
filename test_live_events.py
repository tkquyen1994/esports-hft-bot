import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("PANDASCORE_API_KEY")
headers = {"Authorization": f"Bearer {API_KEY}"}

print("Checking Live Events endpoint for IG vs LNG...\n")

# Check /lives endpoint
resp = requests.get("https://api.pandascore.co/lives", headers=headers)

if resp.status_code == 200:
    data = resp.json()
    print(f"Found {len(data)} live event(s):\n")
    print(json.dumps(data, indent=2))
else:
    print(f"Error: {resp.status_code}")

print("\n" + "=" * 50)

# Also check running matches for all available fields
print("\nChecking Running Matches for available data...\n")
resp2 = requests.get("https://api.pandascore.co/lol/matches/running", headers=headers)

if resp2.status_code == 200:
    matches = resp2.json()
    if matches:
        print(json.dumps(matches[0], indent=2))

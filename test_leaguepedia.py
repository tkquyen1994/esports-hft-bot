import requests

print("Checking Leaguepedia for live data...\n")

# Leaguepedia API endpoint
url = "https://lol.fandom.com/api.php"
params = {
    "action": "cargoquery",
    "tables": "MatchSchedule",
    "fields": "Team1,Team2,DateTime_UTC,BestOf,Winner,Tab",
    "where": 'DateTime_UTC >= "2026-01-01" AND DateTime_UTC <= "2026-01-02"',
    "format": "json",
    "limit": "10"
}

try:
    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        results = data.get("cargoquery", [])
        if results:
            print(f"Found {len(results)} recent matches:")
            for r in results[:5]:
                m = r.get("title", {})
                print(f"  {m.get('Team1')} vs {m.get('Team2')} - Winner: {m.get('Winner', 'TBD')}")
        else:
            print("No matches found")
    else:
        print(f"Error: {resp.status_code}")
except Exception as e:
    print(f"Error: {e}")

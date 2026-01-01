#!/usr/bin/env python3
"""
Test Chinese APIs v2 - Focus on working endpoints
"""

import requests
import json
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://lpl.qq.com/",
}

print("🇨🇳 Testing Chinese APIs v2 - Finding Live Data\n")

# 1. QQ Esports - Search for recent matches (2025/2026)
print("=" * 60)
print("1. QQ Esports - Searching for Demacia Cup / Recent matches")
print("=" * 60)

# Try different search parameters
searches = [
    {"p1": "", "p6": "3", "p8": "8", "page": "1", "pagesize": "10"},  # Recent
    {"p1": "德玛西亚", "p6": "3", "page": "1", "pagesize": "10"},  # Demacia in Chinese
    {"p1": "IG", "p6": "3", "page": "1", "pagesize": "10"},  # Search IG
    {"p1": "LNG", "p6": "3", "page": "1", "pagesize": "10"},  # Search LNG
]

for params in searches:
    try:
        resp = requests.get(
            "https://apps.game.qq.com/lol/match/apis/searchBMatchInfo.php",
            params=params,
            headers=HEADERS,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("msg", {}).get("result", [])
            if results:
                print(f"\nSearch params: {params.get('p1', 'default')}")
                print(f"Found {len(results)} matches")
                for m in results[:3]:
                    print(f"  - {m.get('bMatchName', '?')}: {m.get('MatchDate', '?')}")
    except Exception as e:
        print(f"Error: {e}")

# 2. Score.gg - Try correct endpoint
print("\n" + "=" * 60)
print("2. Score.gg - Testing match endpoints")
print("=" * 60)

scoregg_urls = [
    "https://www.scoregg.com/services/api_url.php?api_path=/services/match/web_lol_match_list.php&date=2026-01-01",
    "https://www.scoregg.com/services/api_url.php?api_path=/services/match/web_lol_match_list.php&tournamentID=",
    "https://img.scoregg.com/lol/schedule/2026/01/01.json",
    "https://www.scoregg.com/services/match/web_lol_live_match.php",
]

for url in scoregg_urls:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        print(f"\n{url[:60]}...")
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            try:
                data = resp.json()
                print(f"Keys: {list(data.keys()) if isinstance(data, dict) else f'Array[{len(data)}]'}")
                if data and data != {"code": "40303", "message": "参数错误", "data": [], "task_data": {}, "badge": [], "event": []}:
                    print(f"Data: {json.dumps(data, ensure_ascii=False)[:500]}")
            except:
                print(f"Response: {resp.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

# 3. Try different LPL website structures
print("\n" + "=" * 60)
print("3. LPL Website - Different URL patterns")
print("=" * 60)

lpl_urls = [
    "https://lpl.qq.com/es/data/schedule/2026/1.json",
    "https://lpl.qq.com/es/data/match/live.json",
    "https://lpl.qq.com/es/stats/match.json",
    "https://open.tjstats.com/match/lol/match/list",  # TJ Stats (common Chinese esports data)
]

for url in lpl_urls:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        print(f"\n{url}")
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            try:
                data = resp.json()
                print(f"✅ JSON! Keys: {list(data.keys()) if isinstance(data, dict) else f'Array[{len(data)}]'}")
                print(f"Sample: {json.dumps(data, ensure_ascii=False)[:400]}")
            except:
                print(f"HTML/Text response")
    except Exception as e:
        print(f"Error: {type(e).__name__}")

# 4. Try Douyu (another streaming platform)
print("\n" + "=" * 60)
print("4. Douyu Esports API")
print("=" * 60)

douyu_urls = [
    "https://www.douyu.com/japi/weblist/apinc/getC2List?shortName=lol&offset=0&limit=20",
    "https://open.douyucdn.cn/api/RoomApi/room/668",  # LPL room
]

for url in douyu_urls:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        print(f"\n{url[:60]}...")
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            try:
                data = resp.json()
                print(f"✅ JSON! Sample: {json.dumps(data, ensure_ascii=False)[:400]}")
            except:
                pass
    except Exception as e:
        print(f"Error: {type(e).__name__}")

# 5. Check if any stream has live stats overlay data
print("\n" + "=" * 60)
print("5. Stream overlay / Stats APIs")
print("=" * 60)

overlay_urls = [
    "https://ddragon.leagueoflegends.com/cdn/14.1.1/data/en_US/champion.json",  # Just to test connectivity
    "https://feed.lolesports.com/livestats/v1/window/1",  # Try a random game ID
]

for url in overlay_urls:
    try:
        resp = requests.get(url, timeout=10)
        print(f"\n{url[:60]}...")
        print(f"Status: {resp.status_code}")
    except Exception as e:
        print(f"Error: {type(e).__name__}")

print("\n" + "=" * 60)
print("COMPLETE")
print("=" * 60)

#!/usr/bin/env python3
"""
Test all Chinese LoL esports data sources
"""

import requests
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Referer": "https://lpl.qq.com/",
}

def test_endpoint(name, url, params=None):
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"URL: {url[:80]}...")
    print('='*60)
    
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        print(f"Status: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('content-type', 'unknown')}")
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                print(f"✅ JSON Response!")
                print(f"Keys: {list(data.keys()) if isinstance(data, dict) else f'Array[{len(data)}]'}")
                
                # Pretty print first part
                formatted = json.dumps(data, indent=2, ensure_ascii=False)
                if len(formatted) > 1500:
                    print(f"\nData (truncated):\n{formatted[:1500]}...")
                else:
                    print(f"\nData:\n{formatted}")
                return data
            except json.JSONDecodeError:
                print(f"Response (not JSON): {resp.text[:500]}...")
        else:
            print(f"❌ Failed: {resp.text[:200]}")
    except requests.exceptions.Timeout:
        print("❌ Timeout")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return None


print("\n" + "🇨🇳"*20)
print("TESTING CHINESE LOL ESPORTS APIs")
print("🇨🇳"*20)

# 1. LPL Official Schedule
test_endpoint(
    "LPL Schedule API",
    "https://lpl.qq.com/web202301/data/schedule/schedule_list.json"
)

# 2. QQ Esports Match Search
test_endpoint(
    "QQ Esports Match Search",
    "https://apps.game.qq.com/lol/match/apis/searchBMatchInfo.php",
    params={"p1": "", "p6": "3", "page": "1", "pagesize": "10"}
)

# 3. LPL Live Data
test_endpoint(
    "LPL Live Match Data",
    "https://lpl.qq.com/web202301/data/live/live_data.json"
)

# 4. Demacia Cup specific
test_endpoint(
    "Demacia Cup Schedule",
    "https://lpl.qq.com/web202301/data/schedule/match_list_9989.json"
)

# 5. TGA (Tencent Games Arena)
test_endpoint(
    "TGA Live API",
    "https://tga.qq.com/api/home/live"
)

# 6. Huya LPL Room Info
test_endpoint(
    "Huya LPL Room",
    "https://www.huya.com/cache.php",
    params={"m": "Live", "do": "profileRoom", "pid": "1346609596"}
)

# 7. Bilibili Esports
test_endpoint(
    "Bilibili Esports",
    "https://api.bilibili.com/x/esports/live/recommend"
)

# 8. Scoregg (Chinese esports site)
test_endpoint(
    "Score.gg Live",
    "https://www.scoregg.com/services/api_url.php",
    params={"api_path": "/services/match/web_lol_match_info.php", "method": "GET"}
)

# 9. Wanplus (Chinese esports stats site)
test_endpoint(
    "Wanplus Live",
    "https://www.wanplus.com/ajax/schedule/list",
    params={"game": "2", "time": "2026-01-01"}
)

# 10. Direct LPL match endpoint
test_endpoint(
    "LPL Match Detail",
    "https://lpl.qq.com/web202301/data/match/match_1280749.json"
)

print("\n" + "="*60)
print("TESTING COMPLETE")
print("="*60)

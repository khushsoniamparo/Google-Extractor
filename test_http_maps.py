import asyncio
import httpx
import re

async def test_search():
    lat = 40.7128
    lng = -74.0060
    url = f"https://www.google.com/maps/search/pizza/@{lat},{lng},14z"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br"
    }
    cookies = {
        "CONSENT": "YES+cb.20230101-00-p0.en+FX+449"
    }
    
    async with httpx.AsyncClient(http2=True) as client:
        resp = await client.get(url, headers=headers, cookies=cookies)
        content = resp.text
        if 'window.APP_INITIALIZATION_STATE' in content:
            print("Found APP_INITIALIZATION_STATE")
            match = re.search(r'window\.APP_INITIALIZATION_STATE=\[\[\[(.*?)\]\]\];', content)
            if match:
                print("Extracted successfully!")
            else:
                print("Regex match failed but substring exists.")
        else:
            print("Still not found")
        with open("output2_raw.txt", "w", encoding="utf-8") as f:
            f.write(content[:10000])

asyncio.run(test_search())

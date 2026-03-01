import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def test():
    url = "https://www.google.com/maps/search/pizza/@40.7128,-74.0060,14z"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            text = await resp.text()
            print("Length:", len(text))
            with open("test_mobile.html", "w", encoding='utf-8') as f:
                f.write(text)

asyncio.run(test())

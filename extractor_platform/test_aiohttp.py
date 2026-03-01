import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def test():
    url = "https://www.google.com/search?tbm=lcl&q=pizza&rlm=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            text = await resp.text()
            soup = BeautifulSoup(text, 'html.parser')
            # Look for local pack titles
            titles = soup.find_all('div', class_=lambda c: c and 'OSrXXb' in c)
            for t in titles[:5]:
                print(t.text)
            print("Length of html:", len(text))
            
            with open("test_lcl.html", "w", encoding='utf-8') as f:
                f.write(text)

asyncio.run(test())

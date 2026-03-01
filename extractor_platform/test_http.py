import asyncio
import aiohttp
from scraper.pipeline import http_one, parse_html, _cookie_str, ensure_cookies

async def test():
    await ensure_cookies()
    print("Cookies:", bool(_cookie_str))
    sem = asyncio.Semaphore(5)
    
    # Try an HTTP request for a valid search term: "coffee shops" at Jaipur
    # Jaipur lat/lng: 26.9124, 75.7873
    async with aiohttp.ClientSession() as session:
        places, method = await http_one(
            session, 
            26.9124, 75.7873, 
            15, "coffee shops", 
            sem
        )
        print("Method:", method)
        print("Places found:", len(places))
        if places:
            print("First place:", places[0])
            
asyncio.run(test())

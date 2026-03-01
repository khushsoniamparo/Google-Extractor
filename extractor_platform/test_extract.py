import asyncio
import time
from playwright.async_api import async_playwright

async def test():
    t0 = time.time()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto('https://www.google.com/maps/search/pizza/@40.7128,-74.0060,14z', wait_until='domcontentloaded')
        await page.wait_for_timeout(2000)
        
        cards = await page.evaluate('''() => {
            return document.querySelectorAll('div[role="feed"] > div > div[jsaction]').length;
        }''')
        print(f"Loaded {cards} cards initially in {time.time()-t0:.2f}s")
        
        await context.close()

asyncio.run(test())

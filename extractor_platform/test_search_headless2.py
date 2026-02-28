import os
import django
import asyncio
from playwright.async_api import async_playwright

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from scraper.search import search_grid_cell
from scraper.grid import GridCell

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-gpu',
            ]
        )
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US'
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            window.chrome = {runtime: {}};
        """)
        
        page = await context.new_page()
        cell = GridCell(center_lat=34.0522, center_lng=-118.2437, zoom=14, index=0, min_lat=0, max_lat=0, min_lng=0, max_lng=0)
        url = f"https://www.google.com/maps/search/restaurants/@{cell.center_lat},{cell.center_lng},{cell.zoom}z?hl=en"
        
        print("Goto URL:", url)
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        except Exception as e:
            print("GOTO EXCEPTION:", e)
        
        print("Waiting to see what loads...")
        # wait to see if results eventually load
        for _ in range(10):
            await page.wait_for_timeout(1000)
            c = await page.locator('div[role="feed"]').count()
            if c > 0:
                print("FEED APPEARED!")
                break
            
        await page.screenshot(path="debug_headless2.png")
        print("SCREENSHOT SAVED")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())

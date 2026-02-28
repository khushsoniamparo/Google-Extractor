import os
import django
import asyncio
from playwright.async_api import async_playwright

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from scraper.search import search_grid_cell
from scraper.grid import GridCell
from scraper.extractor import extract_place

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        cell = GridCell(
            center_lat=34.0522, 
            center_lng=-118.2437, 
            zoom=14, 
            index=0,
            min_lat=0, max_lat=0, min_lng=0, max_lng=0
        )
        res = await search_grid_cell(browser, cell, 'plumbers in los angeles')
        print("SEARCH YIELDED:", len(res))
        if res:
            url = res[0]
            print("EXTRACTING:", url)
            
            context = await browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US'
            )
            page = await context.new_page()
            await page.goto(url, wait_until='domcontentloaded', timeout=25000)
            await page.wait_for_timeout(5000)
            await page.screenshot(path="debug_real_extract.png")
            
            # Check for name specifically
            el = page.locator('h1.DUwDvf').first
            if await el.count() > 0:
                print("H1.DUwDvf:", await el.text_content())
            else:
                print("NO h1.DUwDvf")
            await context.close()
            
            extracted = await extract_place(browser, url)
            print("EXTRACT RESULT:", extracted)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())

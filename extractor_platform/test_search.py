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
        browser = await p.chromium.launch(headless=False)
        cell = GridCell(
            center_lat=34.0522, 
            center_lng=-118.2437, 
            zoom=14, 
            index=0,
            min_lat=0, max_lat=0, min_lng=0, max_lng=0
        )
        res = await search_grid_cell(browser, cell, 'plumbers in los angeles')
        print("SEARCH RESULT:", len(res))
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())

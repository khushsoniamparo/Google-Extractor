import os
import django
import asyncio
from playwright.async_api import async_playwright

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from scraper.extractor import extract_place

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # use a valid pizza hut link or any place link
        url = "https://www.google.com/maps/place/Pizza+Hut/@34.0531548,-118.2618635,15z/data=!4m7!3m6!1s0x80c2c75a4dcd7f27:0x5eac53a391cb459c!8m2!3d34.0531548!4d-118.2618635"
        
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US'
        )
        page = await context.new_page()
        await page.goto(url, wait_until='domcontentloaded', timeout=25000)
        await page.wait_for_timeout(5000)
        
        await page.screenshot(path="debug_extract.png")
        
        # Test original logic
        el = page.locator('h1.DUwDvf').first
        if await el.count() > 0:
            print("Found h1.DUwDvf:", await el.text_content())
        else:
            print("NOT FOUND h1.DUwDvf")
            
        el2 = page.locator('h1').first
        if await el2.count() > 0:
            print("Found h1:", await el2.text_content())
        else:
            print("NOT FOUND h1")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())

# tools/harvest_cookies.py
import asyncio
import os
import re
from playwright.async_api import async_playwright

async def harvest():
    print("🚀 Starting Automatic Cookie Harvester...")
    print("⚠️ A browser window will open. Please wait...")
    
    async with async_playwright() as p:
        # We use HEADED mode so it looks like a real human to Google
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # Visit Google and do a real search to trigger high-trust cookies
            await page.goto("https://www.google.com/search?q=business+jaipur", wait_until="load")
            
            # Wait a few seconds for all the security handshakes to finish
            print("⏳ Authenticating with Google Maps...")
            await asyncio.sleep(8)
            
            # Extract the raw cookie string
            cookies = await context.cookies()
            cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            
            if "NID" not in cookie_string and "GSID" not in cookie_string:
                print("❌ Failed to get high-trust cookies. Try searching manually in the window that opened.")
                return

            print(f"✅ Harvested {len(cookies)} cookies!")
            
            # Now, update pipeline.py automatically
            pipeline_path = os.path.abspath("scraper/pipeline.py")
            with open(pipeline_path, "r", encoding='utf-8') as f:
                content = f.read()
            
            # Replace the placeholder with the real string
            new_content = re.sub(
                r'MANUAL_COOKIES = ".*?"', 
                f'MANUAL_COOKIES = "{cookie_string}"', 
                content
            )
            
            with open(pipeline_path, "w", encoding='utf-8') as f:
                f.write(new_content)
                
            print("🎉 Success! cookies saved to scraper/pipeline.py")
            print("💪 You can now run your scraper.")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(harvest())

# scraper/extractor.py
import re
import asyncio
import structlog
from playwright.async_api import Browser

log = structlog.get_logger()


def extract_place_id(url: str) -> str:
    match = re.search(r'place/([^/]+)/', url)
    return match.group(1) if match else url[-20:]


def extract_coords(url: str):
    match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url)
    if match:
        return match.group(1), match.group(2)
    return '', ''


async def extract_place(browser: Browser, url: str) -> dict:
    """
    Visit one Google Maps place page.
    Extract all available data.
    """
    context = await browser.new_context(
        viewport={'width': 1366, 'height': 768},
        user_agent=(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        locale='en-US',
    )

    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = {runtime: {}};
    """)

    page = await context.new_page()

    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=25000)
        
        try:
            btn = page.locator('button:has-text("Accept all")').first
            if await btn.count() > 0:
                await btn.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass

        try:
            await page.wait_for_selector('h1.DUwDvf, h1', timeout=10000)
        except Exception:
            pass
        
        await page.wait_for_timeout(500)

        async def safe_text(*selectors) -> str:
            for sel in selectors:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0:
                        text = await el.text_content()
                        if text and text.strip():
                            return text.strip()
                except Exception:
                    pass
            return ''

        async def safe_attr(selector: str, attr: str) -> str:
            try:
                el = page.locator(selector).first
                if await el.count() > 0:
                    val = await el.get_attribute(attr)
                    return (val or '').strip()
            except Exception:
                pass
            return ''

        # Core fields
        name = await safe_text('h1.DUwDvf', 'h1')
        category = await safe_text('button.DkEaL', 'span.mgr77e')
        address = await safe_text(
            'button[data-item-id="address"] div.fontBodyMedium',
            'button[data-tooltip="Copy address"]'
        )
        phone = await safe_text(
            'button[data-item-id*="phone:tel"] div.fontBodyMedium',
            'button[data-tooltip="Copy phone number"]'
        )
        website = await safe_attr(
            'a[data-item-id="authority"]', 'href'
        )
        rating = await safe_text(
            'div.F7nice span[aria-hidden="true"]',
            'span.ceNzKf'
        )
        review_count_raw = await safe_text(
            'div.F7nice span[aria-label*="review"]',
            'span.RDApEe'
        )
        review_count = re.sub(r'[^\d,]', '', review_count_raw)

        # Opening hours
        hours = []
        try:
            hours_rows = await page.locator(
                'table.eK4R0e tr'
            ).all()
            for row in hours_rows:
                text = (await row.text_content() or '').strip()
                if text:
                    hours.append(text)
        except Exception:
            pass

        # Coordinates from final URL
        lat, lng = extract_coords(page.url)

        # Place ID
        place_id = extract_place_id(url)

        if not name:
            return None

        return {
            'place_id': place_id,
            'name': name,
            'category': category,
            'address': address,
            'phone': phone,
            'website': website,
            'rating': rating,
            'review_count': review_count,
            'latitude': lat,
            'longitude': lng,
            'opening_hours': ' | '.join(hours),
            'maps_url': page.url,
        }

    except Exception as e:
        log.error("extractor.failed", url=url, error=str(e))
        return None

    finally:
        await context.close()

# scraper/search.py
import asyncio
import re
import structlog
from playwright.async_api import Browser
from urllib.parse import quote

log = structlog.get_logger()


async def search_grid_cell(browser, cell, keyword):
    """
    Search one grid cell and extract ALL data directly
    from the search results page — no separate detail visits.
    Uses the exact same approach Apify uses.
    """
    # This URL format forces Google Maps to search
    # within a specific lat/lng viewport
    url = (
        f"https://www.google.com/maps/search/{quote(keyword)}"
        f"/@{cell.center_lat},{cell.center_lng},14z"
    )

    context = await browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent=(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        locale='en-US',
    )

    # Block unnecessary resources — faster loading
    await context.route(
        "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,otf}",
        lambda route: route.abort()
    )

    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        window.chrome = {runtime: {}};
    """)

    page = await context.new_page()
    places = []

    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(1500)

        # Handle cookie consent
        try:
            btn = page.locator('button:has-text("Accept all")').first
            if await btn.count() > 0:
                await btn.click()
                await page.wait_for_timeout(800)
        except Exception:
            pass

        # Wait for results feed
        try:
            await page.wait_for_selector(
                'div[role="feed"]', timeout=10000
            )
        except Exception:
            log.warning("search.no_feed", cell=cell.index)
            return []

        # Scroll aggressively to load all 120 results
        no_change = 0
        last_count = 0

        for _ in range(25):  # Max 25 scroll attempts
            await page.evaluate("""
                const feed = document.querySelector('div[role="feed"]');
                if (feed) feed.scrollTop += 5000;
            """)
            await page.wait_for_timeout(500)

            # Check end of results
            page_content = await page.content()
            if "you've reached the end of the list" in page_content.lower():
                break

            current = await page.locator(
                'div[role="feed"] > div'
            ).count()

            if current == last_count:
                no_change += 1
                if no_change >= 4:
                    break
            else:
                no_change = 0
                last_count = current

        # Extract ALL place data directly from cards
        places = await extract_from_cards(page, cell)
        log.info("search.done",
                 cell=cell.index,
                 found=len(places),
                 lat=cell.center_lat,
                 lng=cell.center_lng)

    except Exception as e:
        log.error("search.error", cell=cell.index, error=str(e))

    finally:
        await context.close()

    return places


async def extract_from_cards(page, cell) -> list:
    """
    Extract all data directly from search result cards.
    Same fields as Apify — no detail page visits needed.
    """
    places = []

    cards = await page.locator(
        'div[role="feed"] > div > div[jsaction]'
    ).all()

    for card in cards:
        try:
            # Name
            name_el = card.locator('div.qBF1Pd, span.fontHeadlineSmall')
            name = ''
            if await name_el.count() > 0:
                name = (await name_el.first.text_content() or '').strip()

            if not name:
                continue

            # Rating
            rating = ''
            rating_el = card.locator('span.MW4etd')
            if await rating_el.count() > 0:
                rating = (await rating_el.first.text_content() or '').strip()

            # Review count
            reviews = ''
            reviews_el = card.locator('span.UY7F9')
            if await reviews_el.count() > 0:
                raw = (await reviews_el.first.text_content() or '').strip()
                reviews = re.sub(r'[^\d,]', '', raw)

            # Address + category (in the subtitle lines)
            lines = await card.locator(
                'div.W4Efsd'
            ).all_text_contents()
            clean_lines = [
                l.strip() for l in lines if l.strip()
            ]

            category = clean_lines[0] if clean_lines else ''
            address = ''
            phone = ''

            for line in clean_lines[1:]:
                # Phone detection
                if re.search(r'[\+\d][\d\s\-]{7,}', line):
                    phone = line.strip()
                elif line and not address:
                    address = line.strip()

            # Maps URL + place_id + lat/lng
            link_el = card.locator('a[href*="/maps/place/"]')
            maps_url = ''
            place_id = ''
            lat = None
            lng = None
            if await link_el.count() > 0:
                href = await link_el.first.get_attribute('href') or ''
                maps_url = href
                # Extract place_id from URL
                match = re.search(r'place/([^/]+)/', href)
                if match:
                    place_id = match.group(1)
                
                # Try to extract precise lat/lng from the @lat,lng portion or fallback to data=!3d...
                coord_match = re.search(r'@([-\d\.]+),([-\d\.]+)', href)
                if coord_match:
                    try:
                        lat = float(coord_match.group(1))
                        lng = float(coord_match.group(2))
                    except ValueError:
                        pass
                
                if not lat or not lng:
                    # Alternative payload structure
                    coord_match2 = re.search(r'!3d([-\d\.]+)!4d([-\d\.]+)', href)
                    if coord_match2:
                        try:
                            lat = float(coord_match2.group(1))
                            lng = float(coord_match2.group(2))
                        except ValueError:
                            pass
            
            # Use Fallback grid cell coords
            if not lat or not lng:
                 lat = cell.center_lat
                 lng = cell.center_lng

            # Website (sometimes shown directly on card)
            website = ''
            web_el = card.locator('a[data-item-id="authority"]')
            if await web_el.count() > 0:
                website = await web_el.get_attribute('href') or ''

            places.append({
                'place_id': place_id or name,
                'name': name,
                'category': category,
                'street': address,
                'phone': phone,
                'website': website,
                'rating': rating,
                'review_count': reviews,
                'maps_url': maps_url,
                'latitude': lat,
                'longitude': lng,
            })

        except Exception as e:
            log.warning("card.parse_error", error=str(e))
            continue

    return places

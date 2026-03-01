import asyncio
import re
import structlog
from playwright.async_api import Browser
from urllib.parse import quote

log = structlog.get_logger()

async def search_grid_cell(context, cell, keyword):
    """
    Ultra-fast Playwright extraction.
    Takes 2-3 seconds per grid.
    """
    url = (
        f"https://www.google.com/maps/search/{quote(keyword)}"
        f"/@{cell.center_lat},{cell.center_lng},{cell.zoom}z"
    )

    page = await context.new_page()
    places = []
    
    start_time = asyncio.get_event_loop().time()

    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=15000)
        
        # Fast async scrolling evaluated directly in V8
        await page.evaluate("""
            async () => {
                let feed = null;
                // Wait up to 3 seconds for feed to appear dynamically
                for(let i=0; i<30; i++) {
                    feed = document.querySelector('div[role="feed"]');
                    if(feed) break;
                    await new Promise(r => setTimeout(r, 100));
                }
                
                if (!feed) return; // feed not found, blocked or empty
                
                let lastScrollHeight = 0;
                let noChangeCount = 0;
                
                await new Promise((resolve) => {
                    const timer = setInterval(() => {
                        feed = document.querySelector('div[role="feed"]');
                        if (!feed) { clearInterval(timer); return resolve(); }
                        
                        feed.scrollTop += 5000;
                        
                        if (feed.scrollHeight === lastScrollHeight) {
                            // Wait up to ~1.5 seconds (30 * 50ms) for the next XHR to load
                            noChangeCount++;
                            if (noChangeCount >= 30) {
                                clearInterval(timer);
                                resolve();
                            }
                        } else {
                            noChangeCount = 0;
                            lastScrollHeight = feed.scrollHeight;
                        }
                        
                        if (document.body.innerText.includes("you've reached the end of the list")) {
                            clearInterval(timer);
                            resolve();
                        }
                    }, 50); 
                });
            }
        """)

        places = await extract_from_cards(page, cell)
        
        elapsed = asyncio.get_event_loop().time() - start_time
        log.info("cell.http", 
                 cell=cell.index, 
                 method="playwright", 
                 found=len(places), 
                 elapsed=f"{elapsed:.1f}",
                 lat=cell.center_lat,
                 lng=cell.center_lng)

    except Exception as e:
        elapsed = asyncio.get_event_loop().time() - start_time
        log.error("cell.http", 
                  cell=cell.index, 
                  method="error", 
                  found=0, 
                  elapsed=f"{elapsed:.1f}", 
                  error=str(e))

    finally:
        await page.close()

    return places


async def extract_from_cards(page, cell) -> list:
    """
    Evaluate extraction entirely inside the browser.
    """
    return await page.evaluate(f"""
        () => {{
            const cards = Array.from(document.querySelectorAll('div[role="feed"] > div > div[jsaction]'));
            const places = [];
            
            for (const card of cards) {{
                try {{
                    const nameEl = card.querySelector('div.qBF1Pd, span.fontHeadlineSmall') || card.querySelector('.fontHeadlineSmall');
                    if (!nameEl) continue;
                    const name = nameEl.innerText.trim();
                    if (!name) continue;

                    const ratingEl = card.querySelector('span.MW4etd');
                    const rating = ratingEl ? ratingEl.innerText.trim() : '';

                    const reviewEl = card.querySelector('span.UY7F9') || card.querySelector('[aria-label*="reviews"]');
                    let reviews = '';
                    if (reviewEl) {{
                        reviews = reviewEl.innerText.replace(/[^\\d]/g, '');
                    }}

                    const textLines = Array.from(card.querySelectorAll('div.W4Efsd')).map(e => e.innerText.trim());
                    const uniqueLines = [...new Set(textLines)].filter(Boolean);
                    
                    const category = uniqueLines[0] || '';
                    let address = '';
                    let phone = '';

                    for (let i = 1; i < uniqueLines.length; i++) {{
                        const line = uniqueLines[i];
                        if (/[\\+\\d][\\d\\s\\-]{{7,}}/.test(line)) {{
                            phone = line;
                        }} else if (!address && line.length > 3 && !line.includes('·')) {{
                            address = line;
                        }}
                    }}

                    const linkEl = card.querySelector('a[href*="/maps/place/"]');
                    let maps_url = '';
                    let place_id = name;
                    let lat = {cell.center_lat};
                    let lng = {cell.center_lng};

                    if (linkEl && linkEl.href) {{
                        maps_url = linkEl.href;
                        const match = maps_url.match(/place\\/([^\\/]+)\\//);
                        if (match) place_id = match[1];
                        
                        const coordMatch = maps_url.match(/@([-\\d\\.]+),([-\\d\\.]+)/);
                        if (coordMatch) {{
                            lat = parseFloat(coordMatch[1]);
                            lng = parseFloat(coordMatch[2]);
                        }} else {{
                            const coordMatch2 = maps_url.match(/!3d([-\\d\\.]+)!4d([-\\d\\.]+)/);
                            if (coordMatch2) {{
                                lat = parseFloat(coordMatch2[1]);
                                lng = parseFloat(coordMatch2[2]);
                            }}
                        }}
                    }}

                    const webEl = card.querySelector('a[data-item-id="authority"]');
                    const website = webEl ? webEl.href : '';

                    places.push({{
                        place_id: place_id,
                        name: name,
                        category: category,
                        street: address,
                        phone: phone,
                        website: website,
                        rating: rating,
                        review_count: reviews,
                        maps_url: maps_url,
                        latitude: lat,
                        longitude: lng
                    }});
                }} catch(e) {{
                    console.error(e);
                }}
            }}
            return places;
        }}
    """)

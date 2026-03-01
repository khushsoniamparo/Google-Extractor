# scraper/pipeline.py
# ─────────────────────────────────────────────────────────────────
# ALL STRATEGIES × ALL CELLS × ALL ZOOMS — SIMULTANEOUSLY
#
# 8×8 grid × 4 zoom levels = 256 HTTP requests firing at once
# Expected time: 60-90 seconds total (no proxies)
# Expected time: 10-20 seconds total (with 50 proxies)
# ─────────────────────────────────────────────────────────────────
import asyncio
import aiohttp
import re
import json
import random
import hashlib
import os
import time
import structlog
from urllib.parse import quote
from playwright.async_api import async_playwright

log = structlog.get_logger()

# ── CONFIGURATION ──────────────────────────────────────────────────
# All zoom levels searched simultaneously per cell
ZOOM_LEVELS = [13, 14, 15, 16]

# How many HTTP requests fire at the same time
# 8×8 grid × 4 zooms = 256 tasks — semaphore controls batching
HTTP_CONCURRENCY   = 30   # Safe without proxies
PLAYWRIGHT_CONCURRENCY = 5

# Cache
CACHE_DIR = 'scraper_cache'
CACHE_TTL = 3600 * 6
os.makedirs(CACHE_DIR, exist_ok=True)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

# ── COOKIES ────────────────────────────────────────────────────────
COOKIE_FILE = 'google_cookies.json'
COOKIE_TTL  = 3600 * 2
_cookie_str = ''


def _cookies_fresh():
    if not os.path.exists(COOKIE_FILE):
        return False
    return (time.time() - os.path.getmtime(COOKIE_FILE)) < COOKIE_TTL


def _load_cookie_str():
    global _cookie_str
    try:
        with open(COOKIE_FILE) as f:
            cookies = json.load(f)
        _cookie_str = '; '.join(
            f"{c['name']}={c['value']}"
            for c in cookies
            if 'google' in c.get('domain', '')
        )
        log.info('cookies.loaded', chars=len(_cookie_str))
    except Exception:
        _cookie_str = ''


async def _harvest_cookies():
    """Use Playwright once to get real Google cookies."""
    global _cookie_str
    log.info('cookies.harvesting')

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        ctx = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            locale='en-US',
            user_agent=USER_AGENTS[0],
        )
        page = await ctx.new_page()

        await page.goto(
            'https://www.google.com/maps/search/restaurant',
            wait_until='domcontentloaded',
            timeout=25000
        )
        await page.wait_for_timeout(2500)

        try:
            btn = page.locator('button:has-text("Accept all")').first
            if await btn.count() > 0:
                await btn.click()
                await page.wait_for_timeout(800)
        except Exception:
            pass

        await page.wait_for_timeout(1500)
        cookies = await ctx.cookies()
        await browser.close()

    with open(COOKIE_FILE, 'w') as f:
        json.dump(cookies, f)

    _cookie_str = '; '.join(
        f"{c['name']}={c['value']}"
        for c in cookies
        if 'google' in c.get('domain', '')
    )
    log.info('cookies.harvested', count=len(cookies))


async def ensure_cookies():
    global _cookie_str
    if _cookies_fresh() and not _cookie_str:
        _load_cookie_str()
    if not _cookie_str:
        await _harvest_cookies()


# ── CACHE ──────────────────────────────────────────────────────────
def _ckey(lat, lng, zoom, kw):
    return hashlib.md5(
        f"{round(lat,4)}:{round(lng,4)}:{zoom}:{kw.lower()}".encode()
    ).hexdigest()


def cache_get(lat, lng, zoom, kw):
    path = os.path.join(CACHE_DIR, _ckey(lat, lng, zoom, kw) + '.json')
    if not os.path.exists(path):
        return None
    if time.time() - os.path.getmtime(path) > CACHE_TTL:
        os.remove(path)
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def cache_set(lat, lng, zoom, kw, places):
    path = os.path.join(CACHE_DIR, _ckey(lat, lng, zoom, kw) + '.json')
    try:
        with open(path, 'w') as f:
            json.dump(places, f, ensure_ascii=False)
    except Exception:
        pass


# ── HTML PARSER ────────────────────────────────────────────────────
def parse_html(html: str) -> list:
    places = []
    seen = set()

    place_ids = list(dict.fromkeys(
        re.findall(r'ChIJ[a-zA-Z0-9_\-]{10,40}', html)
    ))

    for pid in place_ids[:120]:
        if pid in seen:
            continue
        seen.add(pid)

        idx = html.find(pid)
        if idx == -1:
            continue

        before = html[max(0, idx - 600):idx]
        after  = html[idx:idx + 800]
        ctx    = before + after

        # Name
        name = ''
        nm = re.search(
            r'"([A-Za-z0-9][^"]{3,80})"[^"]{0,200}' + re.escape(pid),
            html[max(0, idx - 400):idx + 50]
        )
        if nm:
            name = nm.group(1).strip()
        if not name:
            candidates = [
                s for s in re.findall(r'"([A-Za-z][^"]{4,60})"', before[-300:])
                if not s.startswith('http') and '\\' not in s
            ]
            if candidates:
                name = candidates[-1]

        if not name or len(name) < 3:
            continue

        phone_m  = re.search(r'(\+?[0-9][0-9\s\-\(\)]{8,18}[0-9])', ctx)
        rating_m = re.search(r'"([1-5]\.[0-9])"', ctx)
        review_m = re.search(r'"(\d{1,6})"(?=[^"]{0,30}"review)', ctx)
        web_m    = re.search(
            r'"(https?://(?!(?:www\.google|maps\.google|goo\.gl|googleapis|gstatic))[^"]{5,120})"',
            ctx
        )

        places.append({
            'place_id':     pid,
            'name':         name,
            'phone':        phone_m.group(1).strip() if phone_m else '',
            'website':      web_m.group(1) if web_m else '',
            'rating':       rating_m.group(1) if rating_m else '',
            'review_count': review_m.group(1) if review_m else '',
            'street': '', 'city': '', 'state': '',
            'category': '', 'latitude': '', 'longitude': '',
            'maps_url': (
                f'https://www.google.com/maps/search/?api=1'
                f'&query={quote(name)}&query_place_id={pid}'
            ),
        })

    return places


# ── HTTP SEARCH (one cell, one zoom) ──────────────────────────────
async def http_one(session, lat, lng, zoom, keyword, sem) -> tuple:
    """
    Single HTTP request for one cell at one zoom level.
    Returns (places, method_string)
    """
    cached = cache_get(lat, lng, zoom, keyword)
    if cached is not None:
        return cached, 'cache'

    url = (
        f'https://www.google.com/maps/search/'
        f'{quote(keyword)}'
        f'/@{lat},{lng},{zoom}z'
    )

    async with sem:
        # Small random stagger — avoids burst fingerprint
        await asyncio.sleep(random.uniform(0.02, 0.15))

        try:
            async with session.get(
                url,
                headers={
                    'User-Agent': random.choice(USER_AGENTS),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Cookie': _cookie_str,
                },
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=True,
                ssl=False,
            ) as resp:

                if resp.status != 200:
                    return [], f'http_{resp.status}'

                html = await resp.text(encoding='utf-8', errors='replace')

                low = html.lower()
                if any(x in low for x in [
                    'unusual traffic', 'captcha',
                    'before you continue', 'not a robot'
                ]):
                    return [], 'blocked'

                if 'ChIJ' not in html:
                    return [], 'no_data'

                places = parse_html(html)
                if places:
                    cache_set(lat, lng, zoom, keyword, places)
                    return places, 'http'
                return [], 'parse_failed'

        except asyncio.TimeoutError:
            return [], 'timeout'
        except Exception as e:
            return [], f'err:{str(e)[:30]}'


# ── PLAYWRIGHT FALLBACK (one cell, one zoom) ──────────────────────
async def playwright_one(browser, lat, lng, zoom, keyword, sem) -> list:
    url = (
        f'https://www.google.com/maps/search/'
        f'{quote(keyword)}'
        f'/@{lat},{lng},{zoom}z'
    )

    async with sem:
        ctx = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent=random.choice(USER_AGENTS),
            locale='en-US',
        )
        await ctx.route(
            '**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,css}',
            lambda r: r.abort()
        )
        await ctx.add_init_script("""
            Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
            window.chrome={runtime:{}};
        """)

        page = await ctx.new_page()
        places = []

        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=25000)
            await page.wait_for_timeout(1200)

            try:
                btn = page.locator('button:has-text("Accept all")').first
                if await btn.count() > 0:
                    await btn.click()
                    await page.wait_for_timeout(500)
            except Exception:
                pass

            try:
                await page.wait_for_selector('div[role="feed"]', timeout=7000)
            except Exception:
                return []

            no_change = 0
            last = 0
            for _ in range(18):
                await page.evaluate("""
                    const f=document.querySelector('div[role="feed"]');
                    if(f) f.scrollTop+=4000;
                """)
                await page.wait_for_timeout(350)
                content = await page.content()
                if "you've reached the end" in content.lower():
                    break
                cur = await page.locator('div[role="feed"] > div').count()
                if cur == last:
                    no_change += 1
                    if no_change >= 3:
                        break
                else:
                    no_change = 0
                    last = cur

            cards = await page.locator(
                'div[role="feed"] > div > div[jsaction]'
            ).all()

            for card in cards:
                try:
                    name_el = card.locator(
                        'div.qBF1Pd, span.fontHeadlineSmall'
                    ).first
                    name = ''
                    if await name_el.count() > 0:
                        name = (await name_el.text_content() or '').strip()
                    if not name:
                        continue

                    rating_el = card.locator('span.MW4etd').first
                    rating = ''
                    if await rating_el.count() > 0:
                        rating = (await rating_el.text_content() or '').strip()

                    reviews_el = card.locator('span.UY7F9').first
                    reviews = ''
                    if await reviews_el.count() > 0:
                        reviews = re.sub(
                            r'[^\d,]',
                            '',
                            (await reviews_el.text_content() or '')
                        )

                    lines = await card.locator(
                        'div.W4Efsd'
                    ).all_text_contents()
                    lines = [l.strip() for l in lines if l.strip()]
                    category = lines[0] if lines else ''
                    phone = address = ''
                    for line in lines[1:]:
                        if re.search(r'[\+\d][\d\s\-]{7,}', line):
                            phone = line
                        elif not address:
                            address = line

                    link_el = card.locator(
                        'a[href*="/maps/place/"]'
                    ).first
                    maps_url = place_id = ''
                    if await link_el.count() > 0:
                        href = await link_el.get_attribute('href') or ''
                        maps_url = href
                        m = re.search(r'place/([^/]+)/', href)
                        if m:
                            place_id = m.group(1)

                    places.append({
                        'place_id': place_id or name,
                        'name': name, 'category': category,
                        'street': address, 'city': '', 'state': '',
                        'phone': phone, 'website': '',
                        'rating': rating, 'review_count': reviews,
                        'latitude': '', 'longitude': '',
                        'maps_url': maps_url,
                    })
                except Exception:
                    continue

        except Exception as e:
            log.error('playwright.error', error=str(e)[:60])
        finally:
            await ctx.close()

        return places


# ── DEDUP HELPER ───────────────────────────────────────────────────
def _dedup_key(p: dict) -> str:
    return (
        p.get('name', '').lower().strip()
        + p.get('street', '').lower()[:15]
        + p.get('place_id', '')[-8:]
    )


# ── MAIN PIPELINE ──────────────────────────────────────────────────
async def run_keyword_pipeline(keyword_job_id: int):
    """
    For each grid cell: fires ALL zoom levels simultaneously via HTTP.
    Every unique (cell, zoom) pair = one independent request.
    Failed pairs fall back to Playwright.
    """
    from jobs.models import KeywordJob, Place
    from django.utils import timezone

    kj = await KeywordJob.objects.select_related('bulk_job').aget(
        id=keyword_job_id
    )
    location  = kj.bulk_job.location
    grid_size = kj.bulk_job.grid_size
    keyword   = kj.keyword
    t0        = time.time()

    try:
        # ── Step 1: Cookies ───────────────────────────────────────
        kj.status = 'fetching_boundary'
        kj.status_message = 'Getting Google session...'
        await kj.asave()
        await ensure_cookies()

        # ── Step 2: Boundary ──────────────────────────────────────
        kj.status_message = f'Finding boundary for {location}...'
        await kj.asave()
        
        from asgiref.sync import sync_to_async
        boundary = await sync_to_async(_get_boundary)(location)

        # ── Step 3: Build ALL (cell × zoom) tasks ─────────────────
        kj.status = 'building_grid'
        cells = _build_grid(boundary, grid_size)
        
        lat_diff = boundary['max_lat'] - boundary['min_lat']
        lng_diff = boundary['max_lng'] - boundary['min_lng']
        area = lat_diff * lng_diff
        
        if area > 4.0: # Huge state/country
            zoom_levels = [10, 11, 12, 13]
        elif area > 1.0: # Medium state
            zoom_levels = [11, 12, 13, 14]
        elif area > 0.1: # Large city/county
            zoom_levels = [12, 13, 14, 15]
        else: # City/Town/Neighborhood
            zoom_levels = [13, 14, 15, 16]

        # Every cell × every zoom = one search task
        all_tasks = [
            {'cell_idx': c['idx'], 'lat': c['lat'],
             'lng': c['lng'], 'zoom': z}
            for c in cells
            for z in zoom_levels
        ]

        kj.total_cells  = len(cells)
        kj.status_message = (
            f'Grid: {grid_size}×{grid_size} = {len(cells)} cells × '
            f'{len(zoom_levels)} zooms = {len(all_tasks)} total searches'
        )
        await kj.asave()

        log.info('pipeline.start',
                 keyword=keyword,
                 cells=len(cells),
                 zooms=zoom_levels,
                 total_tasks=len(all_tasks))

        # ── Step 4: ALL tasks fire simultaneously ─────────────────
        kj.status = 'searching'
        kj.status_message = (
            f'⚡ Firing {len(all_tasks)} parallel searches...'
        )
        await kj.asave()

        seen      = {}    # place_id → place dict (best version)
        failed    = []    # (task, reason) pairs for Playwright
        stats     = {'http': 0, 'cache': 0, 'blocked': 0,
                     'no_data': 0, 'other': 0}

        # Track which cells have been completed (for progress)
        cells_done_set = set()

        http_sem = asyncio.Semaphore(HTTP_CONCURRENCY)
        saved_count = 0

        connector = aiohttp.TCPConnector(
            limit=HTTP_CONCURRENCY + 10,
            ttl_dns_cache=300,
            use_dns_cache=True,
            family=2,
        )

        async with aiohttp.ClientSession(connector=connector) as session:

            async def run_task(task):
                nonlocal saved_count
                places, method = await http_one(
                    session,
                    task['lat'], task['lng'],
                    task['zoom'], keyword,
                    http_sem
                )

                # Track stats
                if method == 'cache':
                    stats['cache'] += 1
                elif method == 'http':
                    stats['http'] += 1
                elif method == 'blocked':
                    stats['blocked'] += 1
                    failed.append(task)
                elif method == 'no_data':
                    stats['no_data'] += 1
                else:
                    stats['other'] += 1
                    failed.append(task)

                # Merge results — keep richest version of each place
                for p in places:
                    key = p.get('place_id') or _dedup_key(p)
                    if not p['name'] or not key:
                        continue
                    if key not in seen:
                        seen[key] = p
                        try:
                            await Place.objects.acreate(
                                keyword_job=kj, **p
                            )
                            saved_count += 1
                        except Exception:
                            pass
                    else:
                        # Update existing with richer data
                        existing = seen[key]
                        updated = False
                        for field in ['phone', 'website', 'rating',
                                      'review_count', 'street', 'category']:
                            if p.get(field) and not existing.get(field):
                                existing[field] = p[field]
                                updated = True
                        if updated:
                            try:
                                await Place.objects.filter(
                                    keyword_job=kj,
                                    place_id=key
                                ).aupdate(**{
                                    f: existing[f]
                                    for f in ['phone', 'website', 'rating',
                                              'review_count', 'street', 'category']
                                    if existing.get(f)
                                })
                            except Exception:
                                pass

                # Mark cell done when all its zooms complete
                cells_done_set.add(task['cell_idx'])
                kj.cells_done    = len(cells_done_set)
                kj.total_extracted = saved_count
                kj.status_message  = (
                    f'⚡ {len(cells_done_set)}/{len(cells)} cells | '
                    f'{saved_count} found | '
                    f'HTTP:{stats["http"]} Cache:{stats["cache"]} '
                    f'Blocked:{stats["blocked"]}'
                )
                await kj.asave()

                log.info('task.done',
                         cell=task['cell_idx'],
                         zoom=task['zoom'],
                         method=method,
                         found=len(places))

            # FIRE ALL TASKS AT ONCE
            t_http = time.time()
            await asyncio.gather(
                *[run_task(t) for t in all_tasks],
                return_exceptions=True
            )
            http_time = round(time.time() - t_http, 1)

        log.info('http.phase.complete',
                 time_sec=http_time,
                 found=saved_count,
                 failed_tasks=len(failed),
                 stats=stats)

        # ── Step 5: Playwright for failed tasks ───────────────────
        if failed:
            kj.status_message = (
                f'🌐 Browser fallback: {len(failed)} searches | '
                f'{saved_count} found so far'
            )
            await kj.asave()

            pw_sem = asyncio.Semaphore(PLAYWRIGHT_CONCURRENCY)
            t_pw = time.time()
            pw_count = 0

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

                async def run_playwright_task(task):
                    nonlocal saved_count, pw_count
                    places = await playwright_one(
                        browser,
                        task['lat'], task['lng'],
                        task['zoom'], keyword,
                        pw_sem
                    )
                    pw_count += len(places)

                    for p in places:
                        key = p.get('place_id') or _dedup_key(p)
                        if not p['name'] or not key or key in seen:
                            continue
                        seen[key] = p
                        try:
                            await Place.objects.acreate(keyword_job=kj, **p)
                            saved_count += 1
                        except Exception:
                            pass

                    kj.total_extracted = saved_count
                    kj.status_message  = (
                        f'🌐 Browser: {saved_count} total found'
                    )
                    await kj.asave()

                await asyncio.gather(
                    *[run_playwright_task(t) for t in failed],
                    return_exceptions=True
                )
                await browser.close()

            log.info('playwright.phase.complete',
                     time_sec=round(time.time() - t_pw, 1),
                     found=pw_count)

        # ── Done ──────────────────────────────────────────────────
        total_time = round(time.time() - t0, 1)
        http_success_pct = round(
            (stats['http'] + stats['cache'])
            / max(len(all_tasks), 1) * 100
        )

        kj.status          = 'completed'
        kj.total_extracted = saved_count
        kj.status_message  = (
            f'✓ {saved_count} places in {total_time}s | '
            f'HTTP success: {http_success_pct}% | '
            f'{len(zoom_levels)} zoom levels searched'
        )
        kj.completed_at = timezone.now()
        await kj.asave()

        log.info('pipeline.complete',
                 keyword=keyword,
                 total=saved_count,
                 time_sec=total_time,
                 http_pct=http_success_pct,
                 zoom_levels=zoom_levels)

    except Exception as e:
        kj.status         = 'failed'
        kj.error_message  = str(e)
        kj.status_message = f'Failed: {str(e)}'
        await kj.asave()
        log.error('pipeline.failed', keyword=keyword, error=str(e))
        raise


# ── BOUNDARY ───────────────────────────────────────────────────────
def _get_boundary(location: str) -> dict:
    try:
        from jobs.models import CachedBoundary
        cb = CachedBoundary.objects.get(location__iexact=location.strip())
        return {
            'min_lat': cb.min_lat, 'max_lat': cb.max_lat,
            'min_lng': cb.min_lng, 'max_lng': cb.max_lng,
        }
    except Exception:
        pass

    import requests
    resp = requests.get(
        'https://nominatim.openstreetmap.org/search',
        params={'q': location, 'format': 'json', 'limit': 1},
        headers={'User-Agent': 'DataMine/1.0'},
        timeout=10
    )
    data = resp.json()
    if not data:
        raise Exception(f'Location not found: {location}')

    bb = data[0]['boundingbox']
    boundary = {
        'min_lat': float(bb[0]), 'max_lat': float(bb[1]),
        'min_lng': float(bb[2]), 'max_lng': float(bb[3]),
    }

    try:
        from jobs.models import CachedBoundary
        CachedBoundary.objects.get_or_create(
            location=location.strip(),
            defaults={
                **boundary,
                'display_name': data[0].get('display_name', '')
            }
        )
    except Exception:
        pass

    return boundary


# ── GRID ───────────────────────────────────────────────────────────
def _build_grid(boundary: dict, grid_size: int) -> list:
    min_lat, max_lat = boundary['min_lat'], boundary['max_lat']
    min_lng, max_lng = boundary['min_lng'], boundary['max_lng']
    lat_step = (max_lat - min_lat) / grid_size
    lng_step = (max_lng - min_lng) / grid_size

    cells = []
    for i in range(grid_size):
        for j in range(grid_size):
            cells.append({
                'lat':  min_lat + (i + 0.5) * lat_step,
                'lng':  min_lng + (j + 0.5) * lng_step,
                'idx':  i * grid_size + j,
            })
    return cells

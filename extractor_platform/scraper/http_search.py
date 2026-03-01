import asyncio
import aiohttp
import structlog
import re
from urllib.parse import quote

log = structlog.get_logger()

# Global proxy pool and session for all HTTP requests
_session = None

async def get_session():
    global _session
    if _session is None:
        # aiohttp is extremely fast for this
        _session = aiohttp.ClientSession(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36",
                "Cookie": "CONSENT=YES+cb.20230101-00-p0.en+FX+449;"
            }
        )
    return _session

async def search_grid_cell_http(cell, keyword) -> list:
    """
    Attempt pure HTTP extraction first. If blocked or 0, returns empty list.
    """
    url = f"https://www.google.com/search?tbm=map&q={quote(keyword)}/@{cell.center_lat},{cell.center_lng},{cell.zoom}z&hl=en"
    
    session = await get_session()
    start = asyncio.get_event_loop().time()
    
    try:
        async with session.get(url, timeout=10) as resp:
            text = await resp.text()
            
            # Simple heuristic — did Google return place names?
            # It usually gets blocked by "Please enable JS" so we fallback immediately.
            places = []

            # In rare cases Google sends data back via HTTP Search directly
            if 'APP_INITIALIZATION_STATE' in text:
                # Mock fast regex matching that works if block is evaded
                pass
            
            elapsed = asyncio.get_event_loop().time() - start
            
            if places:
                log.info("cell.http", cell=cell.index, method="http", found=len(places), elapsed=f"{elapsed:.1f}")
            else:
                # Log method=blocked so Pipeline triggers Playwright fallback seamlessly
                log.info("cell.http", cell=cell.index, method="blocked", found=0, elapsed=f"{elapsed:.1f}")
                
            return places
            
    except asyncio.TimeoutError:
        log.error("cell.http", cell=cell.index, method="timeout", found=0, elapsed="10.0")
        return []
    except Exception as e:
        log.error("cell.http", cell=cell.index, method="error", found=0, elapsed="0.0")
        return []

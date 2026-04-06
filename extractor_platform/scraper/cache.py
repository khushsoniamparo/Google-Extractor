# scraper/cache.py
import os
import json
import time
import hashlib
import structlog
from pathlib import Path

from django.conf import settings

log = structlog.get_logger()

async def get_cached_results(keyword: str, location: str, cell_idx: int):
    """
    Check if we have results for this exact cell in the Postgres DB.
    Returns: list of places or None
    """
    from jobs.models import ScraperCache
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        # Check cache within last 24 hours
        cutoff = timezone.now() - timedelta(hours=24)
        cached = await ScraperCache.objects.filter(
            keyword=keyword.lower(),
            location=location.lower(),
            cell_index=cell_idx,
            scraped_at__gte=cutoff
        ).afirst()
        
        if cached:
            log.info("cache.hit", keyword=keyword, cell=cell_idx)
            return cached.results_json
    except Exception as e:
        log.warning("cache.read_error", error=str(e))
            
    return None

async def set_cached_results(keyword: str, location: str, cell_idx: int, results: list):
    """Save results to Postgres DB."""
    if not results:
        return
        
    from jobs.models import ScraperCache
    try:
        # Update or create cache for this cell
        await ScraperCache.objects.aupdate_or_create(
            keyword=keyword.lower(),
            location=location.lower(),
            cell_index=cell_idx,
            defaults={'results_json': results}
        )
        log.debug("cache.saved", keyword=keyword, cell=cell_idx)
    except Exception as e:
        log.warning("cache.save_error", error=str(e))

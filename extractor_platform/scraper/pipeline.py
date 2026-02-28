# scraper/pipeline.py
import asyncio
import structlog
from playwright.async_api import async_playwright
from .boundary import get_city_boundary
from .grid import build_grid
from .search import search_grid_cell

from .concurrency import get_optimal_concurrency

log = structlog.get_logger()

# Used limits from system memory
limits = get_optimal_concurrency()
PARALLEL_CELLS = limits['playwright']


async def run_keyword_pipeline(keyword_job_id: int, context):
    """
    Runs the full grid search for ONE keyword.
    Called in parallel for each keyword in a BulkJob.
    """
    from jobs.models import KeywordJob, Place
    from django.utils import timezone

    kj = await KeywordJob.objects.select_related('bulk_job').aget(id=keyword_job_id)
    location = kj.bulk_job.location
    grid_size = kj.bulk_job.grid_size

    try:
        # Phase 1 — Boundary
        kj.status = 'fetching_boundary'
        kj.status_message = f'Finding boundary for {location}...'
        await kj.asave()

        boundary = get_city_boundary(location)

        # Phase 2 — Grid
        kj.status = 'building_grid'
        cells = build_grid(boundary, grid_size)
        kj.total_cells = len(cells)
        kj.status_message = (
            f'{len(cells)} cells — '
            f'up to {len(cells) * 120} results possible'
        )
        await kj.asave()

        # Phase 3 — Search
        kj.status = 'searching'
        await kj.asave()

        semaphore = asyncio.Semaphore(PARALLEL_CELLS)
        saved_count = 0
        from .db_writer import AsyncDBWriter
        writer = AsyncDBWriter(keyword_job_id=kj.id, batch_size=50)

        from jobs.models import SearchedCell

        def cell_key(cell) -> str:
            return f"{round(cell.center_lat, 5)}:{round(cell.center_lng, 5)}:{cell.zoom}"

        async def search_and_save(cell):
            nonlocal saved_count
            key = cell_key(cell)
            
            # Skip if already done
            if await SearchedCell.objects.filter(
                keyword_job=kj,
                cell_key=key
            ).aexists():
                kj.cells_done += 1
                return

            async with semaphore:
                places = await search_grid_cell(
                    context, cell, kj.keyword
                )
                for place in places:
                    if writer.add(place):
                        saved_count += 1
                
                # Mark done
                await SearchedCell.objects.acreate(
                    keyword_job=kj,
                    cell_key=key,
                    results_count=len(places)
                )
                
                kj.cells_done += 1
                kj.total_extracted = writer.count
                kj.status_message = (
                    f'Searched {kj.cells_done}/{kj.total_cells} cells '
                    f'— {saved_count} places found'
                )
                await kj.asave()

        await asyncio.gather(
            *[search_and_save(cell) for cell in cells],
            return_exceptions=True
        )

        writer.stop()
        kj.total_extracted = writer.count

        kj.status = 'completed'
        kj.status_message = f'Done! {saved_count} places extracted.'
        kj.total_extracted = saved_count
        kj.completed_at = timezone.now()
        await kj.asave()

        log.info("keyword.done",
                 keyword=kj.keyword,
                 total=saved_count)

    except Exception as e:
        kj.status = 'failed'
        kj.error_message = str(e)
        kj.status_message = f'Failed: {str(e)}'
        await kj.asave()
        log.error("keyword.failed",
                  keyword=kj.keyword, error=str(e))

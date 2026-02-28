# jobs/tasks.py
import threading
import asyncio
import structlog
from playwright.async_api import async_playwright

log = structlog.get_logger()

class SharedBrowserPool:
    """
    One browser instance shared across all keyword jobs.
    Each keyword gets its own context (isolated session).
    Much lower RAM than one browser per keyword.
    """

    def __init__(self):
        self.browser = None
        self.playwright = None

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-gpu',
            ]
        )

    async def new_context(self):
        return await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            locale='en-US',
        )

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


def start_bulk_job(bulk_job_id: int):
    """
    Launches ALL keyword jobs in parallel using a shared browser.
    """
    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_bulk_job_async(bulk_job_id))
        except Exception as e:
            log.error("bulk.failed", bulk_job_id=bulk_job_id, error=str(e))
        finally:
            loop.close()

    threading.Thread(target=run_in_thread, daemon=True).start()


async def run_bulk_job_async(bulk_job_id: int):
    from jobs.models import BulkJob
    from django.utils import timezone
    from scraper.pipeline import run_keyword_pipeline

    bulk_job = await BulkJob.objects.prefetch_related(
        'keyword_jobs'
    ).aget(id=bulk_job_id)

    bulk_job.status = 'running'
    bulk_job.status_message = (
        f'Running {bulk_job.keyword_jobs.count()} '
        f'keywords in parallel...'
    )
    await bulk_job.asave()

    pool = SharedBrowserPool()
    await pool.start()

    async def process_keyword(kj):
        context = await pool.new_context()
        
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

        try:
            await run_keyword_pipeline(kj.id, context)
        finally:
            await context.close()

    tasks = [process_keyword(kj) async for kj in bulk_job.keyword_jobs.all()]
    await asyncio.gather(*tasks, return_exceptions=True)

    await pool.stop()

    await bulk_job.arefresh_from_db()
    bulk_job.status = 'completed'
    
    total_extr = sum([kj.total_extracted async for kj in bulk_job.keyword_jobs.all()])

    bulk_job.status_message = (
        f'All keywords done. '
        f'{total_extr} total places.'
    )
    bulk_job.completed_at = timezone.now()
    await bulk_job.asave()
    log.info("bulk.completed",
             bulk_job_id=bulk_job_id,
             total=total_extr)

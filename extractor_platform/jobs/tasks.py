# jobs/tasks.py
import threading
import asyncio
import structlog

log = structlog.get_logger()


def run_keyword_job(keyword_job_id: int):
    """Runs one keyword pipeline in its own event loop."""
    from scraper.pipeline import run_keyword_pipeline

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            run_keyword_pipeline(keyword_job_id)
        )
    except Exception as e:
        log.error("thread.failed",
                  keyword_job_id=keyword_job_id, error=str(e))
    finally:
        loop.close()


def start_bulk_job(bulk_job_id: int):
    """
    Launches ALL keyword jobs in parallel threads.
    Each keyword = its own thread = runs simultaneously.
    """
    from jobs.models import BulkJob
    from django.utils import timezone

    bulk_job = BulkJob.objects.prefetch_related(
        'keyword_jobs'
    ).get(id=bulk_job_id)

    bulk_job.status = 'running'
    bulk_job.status_message = (
        f'Running {bulk_job.keyword_jobs.count()} '
        f'keywords in parallel...'
    )
    bulk_job.save()

    threads = []
    for kj in bulk_job.keyword_jobs.all():
        t = threading.Thread(
            target=run_keyword_job,
            args=(kj.id,),
            daemon=True
        )
        t.start()
        threads.append(t)
        log.info("thread.started", keyword=kj.keyword)

    # Monitor completion in a separate thread
    def monitor():
        for t in threads:
            t.join()
        bulk_job.refresh_from_db()
        bulk_job.status = 'completed'
        bulk_job.status_message = (
            f'All keywords done. '
            f'{bulk_job.total_extracted} total places.'
        )
        bulk_job.completed_at = timezone.now()
        bulk_job.save()
        log.info("bulk.completed",
                 bulk_job_id=bulk_job_id,
                 total=bulk_job.total_extracted)

    threading.Thread(target=monitor, daemon=True).start()

import asyncio
import threading
from queue import Queue

class AsyncDBWriter:
    """
    Collects results in memory, writes to DB in batches.
    Never blocks the scraping loop.
    """

    def __init__(self, keyword_job_id: int, batch_size: int = 50):
        self.keyword_job_id = keyword_job_id
        self.batch_size = batch_size
        self.queue = Queue()
        self.seen = set()
        self.count = 0
        self._start_writer()

    def _start_writer(self):
        """Background thread that drains queue and writes to DB."""
        def writer_loop():
            batch = []
            while True:
                try:
                    item = self.queue.get(timeout=2.0)
                    if item is None:  # Poison pill — stop signal
                        if batch:
                            self._flush(batch)
                        break
                    batch.append(item)
                    if len(batch) >= self.batch_size:
                        self._flush(batch)
                        batch = []
                except Exception:
                    # Timeout reading from queue, flush what we have
                    if batch:
                        self._flush(batch)
                        batch = []

        self.thread = threading.Thread(
            target=writer_loop, daemon=True
        )
        self.thread.start()

    def _flush(self, batch: list):
        """Write a batch to DB in one transaction."""
        from jobs.models import Place
        from django.db import transaction

        try:
            with transaction.atomic():
                Place.objects.bulk_create(
                    [Place(keyword_job_id=self.keyword_job_id, **p)
                     for p in batch],
                    ignore_conflicts=True,
                )
            self.count += len(batch)
        except Exception as e:
            pass  # Log error

    def add(self, place: dict) -> bool:
        """Add a place — returns True if new, False if duplicate."""
        key = (
            place.get('name', '').lower().strip()
            + place.get('street', '').lower()[:15]
        )
        if key in self.seen or not place.get('name'):
            return False
        self.seen.add(key)
        self.queue.put(place)
        return True

    def stop(self):
        """Signal writer to finish and wait for it."""
        self.queue.put(None)
        self.thread.join(timeout=10)
        return self.count

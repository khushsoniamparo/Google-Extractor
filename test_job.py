import os
import django
import sys
import asyncio

sys.path.append(os.path.join(os.path.dirname(__file__), 'extractor_platform'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from jobs.tasks import run_bulk_job_async
asyncio.run(run_bulk_job_async(9))

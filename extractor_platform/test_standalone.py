import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "extractor_platform.settings")
django.setup()

import asyncio
from scraper.http_search import search_grid_cell

class MockCell:
    index = 1
    id = 1
    center_lat = 40.7128
    center_lng = -74.0060

async def test():
    res = await search_grid_cell(None, MockCell(), 'pizza')
    print('Found places:', len(res))

asyncio.run(test())

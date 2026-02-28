# scraper/concurrency.py
import psutil
import asyncio

def get_optimal_concurrency() -> dict:
    """
    Calculate safe concurrency based on current system resources.
    """
    ram = psutil.virtual_memory()
    cpu = psutil.cpu_count(logical=False)
    ram_available_gb = ram.available / (1024 ** 3)

    # Each HTTP request uses ~5MB RAM
    # Each Playwright context uses ~150MB RAM
    http_limit = min(50, int(ram_available_gb * 8))
    playwright_limit = min(8, max(2, int(ram_available_gb / 0.3)))

    return {
        'http': http_limit,
        'playwright': playwright_limit,
        'recommended_grid': 8 if ram_available_gb > 4 else 5,
    }

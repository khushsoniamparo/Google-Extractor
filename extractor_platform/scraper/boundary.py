# scraper/boundary.py
import requests
import structlog

log = structlog.get_logger()


def get_city_boundary(location: str) -> dict:
    from jobs.models import CachedBoundary

    # Check DB cache first
    try:
        cached = CachedBoundary.objects.get(
            location__iexact=location.strip()
        )
        return {
            'min_lat': cached.min_lat,
            'max_lat': cached.max_lat,
            'min_lng': cached.min_lng,
            'max_lng': cached.max_lng,
            'display_name': cached.display_name,
        }
    except CachedBoundary.DoesNotExist:
        pass

    # Not cached — fetch from OpenStreetMap
    boundary = _fetch_from_osm(location)

    # Save for next time
    CachedBoundary.objects.create(
        location=location.strip(),
        **boundary
    )
    return boundary


def _fetch_from_osm(location: str) -> dict:
    """
    Gets the bounding box of any city in the world
    using Nominatim (OpenStreetMap) — completely free.
    Returns: {min_lat, max_lat, min_lng, max_lng}
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': location,
        'format': 'json',
        'limit': 1,
        'featuretype': 'city',
    }
    headers = {
        'User-Agent': 'ExtractorPlatform/1.0'
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()

        if not data:
            # Try without featuretype restriction
            params.pop('featuretype')
            response = requests.get(url, params=params, headers=headers, timeout=10)
            data = response.json()

        if not data:
            raise Exception(f"Location not found: {location}")

        bbox = data[0]['boundingbox']
        # bbox = [min_lat, max_lat, min_lng, max_lng]
        result = {
            'min_lat': float(bbox[0]),
            'max_lat': float(bbox[1]),
            'min_lng': float(bbox[2]),
            'max_lng': float(bbox[3]),
            'display_name': data[0]['display_name'],
        }

        log.info("boundary.fetched",
                 location=location,
                 bbox=result)
        return result

    except Exception as e:
        log.error("boundary.failed", location=location, error=str(e))
        raise

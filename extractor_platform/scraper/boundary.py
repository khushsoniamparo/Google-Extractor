# scraper/boundary.py
import requests
import structlog

log = structlog.get_logger()


def get_city_boundary(location: str) -> dict:
    """
    Gets the most comprehensive bounding box for a location.
    Checks Postgres LocationCache first, fallbacks to Nominatim.
    """
    from jobs.models import LocationCache
    
    # 1. CHECK CACHE
    cached = LocationCache.objects.filter(query=location.lower()).first()
    if cached:
        log.info("boundary.cache_hit", location=location)
        return {
            'min_lat': cached.min_lat,
            'max_lat': cached.max_lat,
            'min_lng': cached.min_lng,
            'max_lng': cached.max_lng,
            'display_name': cached.display_name,
            'radius_meters': cached.radius_meters,
            'center_lat': cached.center_lat,
            'center_lng': cached.center_lng
        }

    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'ExtractorPlatform/1.0'}
    
    variants = [location, f"{location} district", f"{location} city"]
    best_result = None
    max_area = -1

    for q in variants:
        try:
            params = {'q': q, 'format': 'json', 'limit': 1}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            data = response.json()
            
            if data:
                bbox = data[0]['boundingbox']
                # Rough area calculation
                area = (float(bbox[1]) - float(bbox[0])) * (float(bbox[3]) - float(bbox[2]))
                if area > max_area:
                    max_area = area
                    best_result = {
                        'min_lat': float(bbox[0]),
                        'max_lat': float(bbox[1]),
                        'min_lng': float(bbox[2]),
                        'max_lng': float(bbox[3]),
                        'display_name': data[0]['display_name'],
                        'area': area
                    }
        except Exception as e:
            continue

    if not best_result:
        raise Exception(f"Location not found: {location}")

    # Calculate center and radius
    center_lat = (best_result['min_lat'] + best_result['max_lat']) / 2
    center_lng = (best_result['min_lng'] + best_result['max_lng']) / 2
    
    import math
    lat_dist = abs(best_result['max_lat'] - best_result['min_lat']) * 111000
    lng_dist = abs(best_result['max_lng'] - best_result['min_lng']) * 111000 * math.cos(math.radians(center_lat))
    radius_meters = max(int(math.sqrt(lat_dist**2 + lng_dist**2) / 2 * 1.2), 5000)
    
    # 2. SAVE TO CACHE
    LocationCache.objects.create(
        query=location.lower(),
        display_name=best_result['display_name'],
        min_lat=best_result['min_lat'],
        max_lat=best_result['max_lat'],
        min_lng=best_result['min_lng'],
        max_lng=best_result['max_lng'],
        center_lat=center_lat,
        center_lng=center_lng,
        radius_meters=radius_meters
    )

    return {**best_result, 'center_lat': center_lat, 'center_lng': center_lng, 'radius_meters': radius_meters}

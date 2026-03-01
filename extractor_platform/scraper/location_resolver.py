import math
import structlog
import requests
from django.utils import timezone

log = structlog.get_logger()

def _fetch_cities(boundary):
    min_lat, max_lat = boundary['min_lat'], boundary['max_lat']
    min_lng, max_lng = boundary['min_lng'], boundary['max_lng']
    query = f"""
    [out:json][timeout:25];
    (
      node["place"="city"]({min_lat},{min_lng},{max_lat},{max_lng});
      node["place"="town"]({min_lat},{min_lng},{max_lat},{max_lng});
    );
    out body;
    """
    try:
        resp = requests.post("https://overpass-api.de/api/interpreter", data={'data': query})
        if resp.status_code != 200:
            return []
        
        cities = []
        for el in resp.json().get('elements', []):
            if 'tags' in el and 'name' in el['tags']:
                cities.append({
                    'name': el['tags']['name'],
                    'lat': el['lat'],
                    'lng': el['lon'],
                    'is_city': True
                })
        return cities
    except:
        return []

def resolve_location(location: str) -> dict:
    # 1. Get Boundary
    resp = requests.get(
        'https://nominatim.openstreetmap.org/search',
        params={'q': location, 'format': 'json', 'limit': 1, 'addressdetails': 1},
        headers={'User-Agent': 'DataMine/1.0'},
        timeout=10
    )
    data = resp.json()
    if not data:
        raise Exception(f'Location not found: {location}')
    
    place = data[0]
    bb = place['boundingbox']
    boundary = {
        'min_lat': float(bb[0]), 'max_lat': float(bb[1]),
        'min_lng': float(bb[2]), 'max_lng': float(bb[3]),
    }
    
    lat_diff = boundary['max_lat'] - boundary['min_lat']
    lng_diff = boundary['max_lng'] - boundary['min_lng']
    area = lat_diff * lng_diff
    
    place_type = place.get('class', '')
    place_type_detail = place.get('type', '')
    
    is_state = area > 1.0 or place_type_detail in ['state', 'country', 'administrative']
    
    if not is_state:
        # Small area (city / town)
        return {
            'location': location,
            'type': 'city',
            'area': area,
            'search_points': [
                {
                    'name': location,
                    'lat': float(place['lat']),
                    'lng': float(place['lon']),
                    'is_city': True
                }
            ],
            'boundary': boundary
        }
    
    # Large area (state)
    cities = _fetch_cities(boundary)
    log.info('resolve.cities_found', state=location, count=len(cities))
    
    # Sort cities logically or limit to 50
    cities = cities[:50]
    
    # gap points
    gap_points = []
    grid_size = min(6, max(2, int(math.ceil(math.sqrt(area) * 2))))
    lat_step = lat_diff / grid_size
    lng_step = lng_diff / grid_size
    
    for i in range(grid_size):
        for j in range(grid_size):
            p_lat = boundary['min_lat'] + (i + 0.5) * lat_step
            p_lng = boundary['min_lng'] + (j + 0.5) * lng_step
            
            near_city = False
            for c in cities:
                if math.hypot(c['lat'] - p_lat, c['lng'] - p_lng) < 0.2:
                    near_city = True
                    break
            if not near_city:
                gap_points.append({
                    'name': f"Gap {i}-{j}",
                    'lat': p_lat,
                    'lng': p_lng,
                    'is_city': False
                })

    log.info('resolve.gap_points', count=len(gap_points))
                
    all_points = cities + gap_points
    if not all_points:
        all_points = [{'name': location, 'lat': float(place['lat']), 'lng': float(place['lon']), 'is_city': True}]
        
    log.info('resolve.total_points', total=len(all_points), cities=len(cities), grid_fills=len(gap_points))
    log.info('resolve.detected', location=location, type='state', area=area)
        
    return {
        'location': location,
        'type': 'state',
        'area': area,
        'search_points': all_points,
        'boundary': boundary
    }

def resolve_location_cached(location: str) -> dict:
    from jobs.models import CachedLocationResolution
    try:
        clr = CachedLocationResolution.objects.get(location__iexact=location.strip())
        return clr.data
    except Exception:
        data = resolve_location(location)
        CachedLocationResolution.objects.create(
            location=location.strip(),
            data=data
        )
        return data

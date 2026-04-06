import math
import structlog
import requests
from django.utils import timezone
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import unary_union

log = structlog.get_logger()

class SearchArea:
    def __init__(self, name, lat, lng, shape_type='circle', radius_km=5.0, polygon_coords=None):
        self.name = name
        self.lat = lat
        self.lng = lng
        self.shape_type = shape_type
        self.radius_km = radius_km
        self.polygon_coords = polygon_coords
        self.shape = None
        
        if shape_type == 'circle':
            # Create a localized circle in degrees approx
            # 0.01 degrees is ~1.1km
            deg_radius = radius_km / 111.32
            self.shape = Point(lng, lat).buffer(deg_radius)
        elif shape_type == 'polygon' and polygon_coords:
            self.shape = Polygon(polygon_coords)

    @property
    def bounds(self):
        if not self.shape: return (self.lat, self.lat, self.lng, self.lng)
        return self.shape.bounds # (min_lng, min_lat, max_lng, max_lat)

def get_collective_boundary(areas: list) -> dict:
    if not areas: return None
    min_lng = min(a.bounds[0] for a in areas)
    min_lat = min(a.bounds[1] for a in areas)
    max_lng = min(a.bounds[2] for a in areas)
    max_lat = min(a.bounds[3] for a in areas)
    return {'min_lat': min_lat, 'max_lat': max_lat, 'min_lng': min_lng, 'max_lng': max_lng}

def resolve_to_search_areas(location: str) -> list:
    """
    Resolves a location string to a list of SearchArea objects.
    - If it's a city: returns one circle area.
    - If it's a state: returns multiple city-based areas.
    """
    # 1. Get location info from OSM Nominatim
    try:
        resp = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': location, 'format': 'json', 'limit': 1},
            headers={'User-Agent': 'Google-Extractor-Agent/1.0'},
            timeout=10
        )
        data = resp.json()
    except Exception as e:
        log.error('geofence.osm_query_failed', error=str(e))
        return [SearchArea(location, 0, 0)] # Fallback

    if not data:
        # Fallback to simple point if not found
        return [SearchArea(location, 0, 0)]

    place = data[0]
    osm_type = place.get('type', '')
    osm_class = place.get('class', '')
    lat, lon = float(place['lat']), float(place['lon'])
    
    # Check if it's a state/administrative region
    is_large_region = osm_type in ['state', 'province', 'country'] or osm_class == 'boundary' and place.get('importance', 0) > 0.6
    
    if not is_large_region:
        # Default city radius
        radius = 5.0
        if "bhilwara" in location.lower(): radius = 9.0
        return [SearchArea(location, lat, lon, shape_type='circle', radius_km=radius)]

    # LARGE REGION (State) CASE
    # Fetch major cities in this region using Overpass
    bb = place.get('boundingbox')
    if not bb: return [SearchArea(location, lat, lon)]
    
    overpass_query = f"""
    [out:json][timeout:25];
    (
      node["place"~"city|town"]({bb[0]},{bb[2]},{bb[1]},{bb[3]});
    );
    out body 20;
    """
    try:
        r = requests.post("https://overpass-api.de/api/interpreter", data={'data': overpass_query})
        elements = r.json().get('elements', [])
        areas = []
        for el in elements:
            name = el.get('tags', {}).get('name', 'Unknown')
            areas.append(SearchArea(name, el['lat'], el['lon'], shape_type='circle', radius_km=6.0))
        
        if not areas:
            return [SearchArea(location, lat, lon)]
        return areas
    except:
        return [SearchArea(location, lat, lon)]

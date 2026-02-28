# scraper/grid.py
from dataclasses import dataclass
from typing import List
import structlog

log = structlog.get_logger()


@dataclass
class GridCell:
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float
    center_lat: float
    center_lng: float
    zoom: int = 14
    index: int = 0


def build_grid(boundary: dict, grid_size: int = 5) -> List[GridCell]:
    """
    Divides a city boundary into grid_size x grid_size cells.

    grid_size=5  → 25 cells  → up to 3,000 results
    grid_size=8  → 64 cells  → up to 7,680 results
    grid_size=10 → 100 cells → up to 12,000 results
    grid_size=15 → 225 cells → up to 27,000 results

    Each cell = one Google Maps search = up to 120 results.
    """
    min_lat = boundary['min_lat']
    max_lat = boundary['max_lat']
    min_lng = boundary['min_lng']
    max_lng = boundary['max_lng']

    lat_step = (max_lat - min_lat) / grid_size
    lng_step = (max_lng - min_lng) / grid_size

    cells = []
    index = 0

    for i in range(grid_size):
        for j in range(grid_size):
            cell_min_lat = min_lat + i * lat_step
            cell_max_lat = min_lat + (i + 1) * lat_step
            cell_min_lng = min_lng + j * lng_step
            cell_max_lng = min_lng + (j + 1) * lng_step

            center_lat = (cell_min_lat + cell_max_lat) / 2
            center_lng = (cell_min_lng + cell_max_lng) / 2

            cells.append(GridCell(
                min_lat=cell_min_lat,
                max_lat=cell_max_lat,
                min_lng=cell_min_lng,
                max_lng=cell_max_lng,
                center_lat=center_lat,
                center_lng=center_lng,
                index=index,
            ))
            index += 1

    log.info("grid.built",
             grid_size=grid_size,
             total_cells=len(cells),
             max_possible_results=len(cells) * 120)
    return cells

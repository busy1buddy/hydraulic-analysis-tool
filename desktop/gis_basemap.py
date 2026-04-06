"""
GIS Basemap — OpenStreetMap Tile Layer
=======================================
Provides a lightweight OpenStreetMap tile background for the network canvas.
Uses urllib only (no contextily/pyproj dependency). Tiles are cached to disk
to minimise network requests.

Coordinate system:
- EPANET models use arbitrary X/Y coordinates. If coordinates look like they
  are in a projected CRS (e.g., MGA Zone 55 with easting ~300000-700000 and
  northing ~5000000-7000000), this module projects them to lat/lon for tile
  fetching. Otherwise it treats them as lat/lon directly.
- For models with arbitrary coordinates (e.g., tutorial networks with small
  X/Y), GIS basemap is not meaningful and will show a "no basemap" message.

Tile source: OpenStreetMap standard tiles (https://tile.openstreetmap.org/)
Usage complies with OSM Tile Usage Policy — requests include User-Agent header.
"""

import os
import math
import hashlib
import urllib.request
from typing import Optional, Tuple, List

import numpy as np

import logging

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtGui import QImage, QPixmap
    from PyQt6.QtCore import Qt
    HAS_QT = True
except ImportError:
    HAS_QT = False


# OSM Tile URL template
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = "EPANET-HydraulicAnalysisTool/1.2 (educational; contact: noreply@example.com)"

# Tile cache directory
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         '.tile_cache')


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _is_mga_coordinates(x_range: Tuple[float, float],
                        y_range: Tuple[float, float]) -> bool:
    """Heuristic: detect if coordinates look like MGA2020 (Australian UTM)."""
    x_min, x_max = x_range
    y_min, y_max = y_range
    # MGA easting: 100000-900000, northing: 1000000-10000000
    if 100000 < x_min < 900000 and 100000 < x_max < 900000:
        if 1000000 < y_min < 10000000 and 1000000 < y_max < 10000000:
            return True
    return False


def _is_latlon_coordinates(x_range: Tuple[float, float],
                           y_range: Tuple[float, float]) -> bool:
    """Heuristic: detect if coordinates look like lat/lon."""
    x_min, x_max = x_range
    y_min, y_max = y_range
    if -180 <= x_min <= 180 and -180 <= x_max <= 180:
        if -90 <= y_min <= 90 and -90 <= y_max <= 90:
            return True
    return False


def detect_coordinate_system(node_positions: dict) -> str:
    """
    Detect coordinate system from node positions.

    Returns: 'mga', 'latlon', or 'arbitrary'
    """
    if not node_positions:
        return 'arbitrary'

    xs = [p[0] for p in node_positions.values()]
    ys = [p[1] for p in node_positions.values()]
    x_range = (min(xs), max(xs))
    y_range = (min(ys), max(ys))

    if _is_mga_coordinates(x_range, y_range):
        return 'mga'
    if _is_latlon_coordinates(x_range, y_range):
        return 'latlon'
    return 'arbitrary'


def mga_to_latlon(easting: float, northing: float, zone: int = 55) -> Tuple[float, float]:
    """
    Convert MGA2020 (UTM) to WGS84 lat/lon.
    Simplified conversion using Karney's method approximation.
    Accurate to ~1m for Australian coordinates.

    Parameters
    ----------
    easting : float
        MGA easting in metres
    northing : float
        MGA northing in metres
    zone : int
        UTM zone number (default 55 for eastern Australia)

    Returns (lat, lon) in decimal degrees.
    """
    # UTM parameters
    k0 = 0.9996
    a = 6378137.0  # WGS84 semi-major axis
    f = 1 / 298.257223563
    e = math.sqrt(2 * f - f ** 2)
    e2 = e ** 2
    e_prime2 = e2 / (1 - e2)

    # Remove false easting/northing
    # Southern hemisphere uses 10,000,000 m false northing
    x = easting - 500000.0
    y = northing - 10000000.0

    # Central meridian
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)

    M = y / k0
    mu = M / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))

    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu))

    N1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2)
    T1 = math.tan(phi1) ** 2
    C1 = e_prime2 * math.cos(phi1) ** 2
    R1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5
    D = x / (N1 * k0)

    lat = phi1 - (N1 * math.tan(phi1) / R1) * (
        D ** 2 / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * e_prime2) * D ** 4 / 24
        + (61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2
           - 252 * e_prime2 - 3 * C1 ** 2) * D ** 6 / 720
    )

    lon = lon0 + (D - (1 + 2 * T1 + C1) * D ** 3 / 6
                  + (5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2
                     + 8 * e_prime2 + 24 * T1 ** 2) * D ** 5 / 120) / math.cos(phi1)

    return math.degrees(lat), math.degrees(lon)


def latlon_to_tile(lat: float, lon: float, zoom: int) -> Tuple[int, int]:
    """Convert lat/lon to OSM tile (x, y) at given zoom level."""
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    lat_rad = math.radians(lat)
    y = int((1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n)
    return x, y


def tile_to_latlon(x: int, y: int, zoom: int) -> Tuple[float, float]:
    """Convert OSM tile (x, y) back to lat/lon (top-left corner)."""
    n = 2 ** zoom
    lon = x / n * 360 - 180
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_rad)
    return lat, lon


def fetch_tile(z: int, x: int, y: int) -> Optional[bytes]:
    """Fetch a single OSM tile, using disk cache."""
    _ensure_cache_dir()
    cache_key = f"{z}_{x}_{y}"
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.png")

    # Check cache
    if os.path.exists(cache_path):
        with open(cache_path, 'rb') as f:
            return f.read()

    # Fetch from network
    url = TILE_URL.format(z=z, x=x, y=y)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
        # Cache to disk
        with open(cache_path, 'wb') as f:
            f.write(data)
        return data
    except (KeyError, AttributeError, ValueError):
        return None


def compute_basemap_bounds(node_positions: dict, coord_system: str,
                           mga_zone: int = 55) -> Optional[dict]:
    """
    Compute lat/lon bounds for the network's extent.

    Returns dict with 'min_lat', 'max_lat', 'min_lon', 'max_lon', 'zoom'
    or None if coordinates are arbitrary.
    """
    if not node_positions or coord_system == 'arbitrary':
        return None

    if coord_system == 'mga':
        latlons = [mga_to_latlon(x, y, mga_zone) for x, y in node_positions.values()]
    else:
        # latlon: X=lon, Y=lat (EPANET convention)
        latlons = [(y, x) for x, y in node_positions.values()]

    lats = [ll[0] for ll in latlons]
    lons = [ll[1] for ll in latlons]

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    # Add 10% padding
    lat_pad = (max_lat - min_lat) * 0.1 or 0.005
    lon_pad = (max_lon - min_lon) * 0.1 or 0.005
    min_lat -= lat_pad
    max_lat += lat_pad
    min_lon -= lon_pad
    max_lon += lon_pad

    # Choose zoom level: aim for ~4-8 tiles across the extent
    for zoom in range(18, 5, -1):
        x1, y1 = latlon_to_tile(max_lat, min_lon, zoom)
        x2, y2 = latlon_to_tile(min_lat, max_lon, zoom)
        n_tiles = (abs(x2 - x1) + 1) * (abs(y2 - y1) + 1)
        if n_tiles <= 16:
            break

    return {
        'min_lat': min_lat, 'max_lat': max_lat,
        'min_lon': min_lon, 'max_lon': max_lon,
        'zoom': zoom,
    }


def fetch_basemap_tiles(bounds: dict) -> List[dict]:
    """
    Fetch all tiles covering the given bounds.

    Returns list of dicts: {'z', 'x', 'y', 'data', 'lat_tl', 'lon_tl', 'lat_br', 'lon_br'}
    """
    z = bounds['zoom']
    x1, y1 = latlon_to_tile(bounds['max_lat'], bounds['min_lon'], z)
    x2, y2 = latlon_to_tile(bounds['min_lat'], bounds['max_lon'], z)

    tiles = []
    for tx in range(min(x1, x2), max(x1, x2) + 1):
        for ty in range(min(y1, y2), max(y1, y2) + 1):
            data = fetch_tile(z, tx, ty)
            if data:
                lat_tl, lon_tl = tile_to_latlon(tx, ty, z)
                lat_br, lon_br = tile_to_latlon(tx + 1, ty + 1, z)
                tiles.append({
                    'z': z, 'x': tx, 'y': ty,
                    'data': data,
                    'lat_tl': lat_tl, 'lon_tl': lon_tl,
                    'lat_br': lat_br, 'lon_br': lon_br,
                })
    return tiles

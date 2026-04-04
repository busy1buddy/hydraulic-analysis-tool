"""
Tests for GIS Basemap Module (C3)
===================================
Tests coordinate detection, MGA-to-latlon conversion, tile math.
Network tile fetching is mocked to avoid external HTTP calls in CI.
"""

import os
import sys
import math
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from desktop.gis_basemap import (
    detect_coordinate_system,
    mga_to_latlon,
    latlon_to_tile,
    tile_to_latlon,
    compute_basemap_bounds,
    _is_mga_coordinates,
    _is_latlon_coordinates,
)


class TestCoordinateDetection:
    """Tests for coordinate system heuristic detection."""

    def test_mga_coordinates(self):
        """MGA Zone 55 coordinates should be detected."""
        positions = {
            'J1': (321000, 5813000),
            'J2': (322000, 5814000),
        }
        assert detect_coordinate_system(positions) == 'mga'

    def test_latlon_coordinates(self):
        """Lat/lon coordinates should be detected."""
        positions = {
            'J1': (144.9, -37.8),
            'J2': (145.0, -37.7),
        }
        assert detect_coordinate_system(positions) == 'latlon'

    def test_arbitrary_coordinates(self):
        """Small local coordinates should be detected as arbitrary."""
        positions = {
            'J1': (0, 0),
            'J2': (100, 50),
            'J3': (200, 100),
        }
        assert detect_coordinate_system(positions) == 'arbitrary'

    def test_empty_positions(self):
        assert detect_coordinate_system({}) == 'arbitrary'

    def test_mga_heuristic(self):
        assert _is_mga_coordinates((300000, 600000), (5800000, 6200000))
        assert not _is_mga_coordinates((0, 100), (0, 50))

    def test_latlon_heuristic(self):
        assert _is_latlon_coordinates((144, 146), (-38, -37))
        assert not _is_latlon_coordinates((300000, 600000), (5800000, 6200000))


class TestMGAConversion:
    """Tests for MGA2020 to WGS84 conversion."""

    def test_melbourne_cbd(self):
        """Melbourne CBD: MGA55 ~321680E 5811600N -> ~-37.81, 144.96."""
        lat, lon = mga_to_latlon(321680, 5811600, zone=55)
        assert abs(lat - (-37.81)) < 0.02
        assert abs(lon - 144.96) < 0.02

    def test_sydney_cbd(self):
        """Sydney CBD: MGA56 ~334000E 6251000N -> ~-33.87, 151.21."""
        lat, lon = mga_to_latlon(334000, 6251000, zone=56)
        assert abs(lat - (-33.87)) < 0.02
        assert abs(lon - 151.21) < 0.02

    def test_perth_cbd(self):
        """Perth CBD: MGA50 ~392000E 6463000N -> ~-31.95, 115.86."""
        lat, lon = mga_to_latlon(392000, 6463000, zone=50)
        assert abs(lat - (-31.95)) < 0.05
        assert abs(lon - 115.86) < 0.05


class TestTileMath:
    """Tests for OSM tile coordinate conversions."""

    def test_tile_at_zoom_0(self):
        """At zoom 0, entire world is one tile (0,0)."""
        x, y = latlon_to_tile(0, 0, 0)
        assert x == 0
        assert y == 0

    def test_tile_roundtrip(self):
        """Converting tile back to lat/lon should give the top-left corner."""
        z = 15
        x, y = latlon_to_tile(-37.81, 144.96, z)
        lat, lon = tile_to_latlon(x, y, z)
        # Should be close to original (within one tile)
        assert abs(lat - (-37.81)) < 0.01
        assert abs(lon - 144.96) < 0.01

    def test_zoom_increases_tile_count(self):
        """Higher zoom = more tiles for same area."""
        lat, lon = -37.81, 144.96
        x10, y10 = latlon_to_tile(lat, lon, 10)
        x15, y15 = latlon_to_tile(lat, lon, 15)
        assert x15 > x10
        assert y15 > y10


class TestBasemapBounds:
    """Tests for basemap bounds computation."""

    def test_arbitrary_returns_none(self):
        positions = {'J1': (0, 0), 'J2': (100, 50)}
        result = compute_basemap_bounds(positions, 'arbitrary')
        assert result is None

    def test_latlon_returns_bounds(self):
        positions = {
            'J1': (144.9, -37.85),
            'J2': (145.1, -37.75),
        }
        bounds = compute_basemap_bounds(positions, 'latlon')
        assert bounds is not None
        assert bounds['min_lon'] < 144.9
        assert bounds['max_lon'] > 145.1
        assert 'zoom' in bounds
        assert 5 < bounds['zoom'] <= 18

    def test_mga_returns_bounds(self):
        positions = {
            'J1': (321000, 5811000),
            'J2': (322000, 5812000),
        }
        bounds = compute_basemap_bounds(positions, 'mga', mga_zone=55)
        assert bounds is not None
        assert bounds['min_lat'] < bounds['max_lat']
        assert bounds['min_lon'] < bounds['max_lon']

    def test_empty_returns_none(self):
        assert compute_basemap_bounds({}, 'latlon') is None

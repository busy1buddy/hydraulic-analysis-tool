"""
Unit tests for ``epanet_api/terrain.py``.

Recommendation #4 from the multi-agent review plan: TerrainMixin had no
dedicated test file. These tests cover:

- CSV import round-trip (XYZ format, header row)
- ``get_ground_elevation`` returns None when no terrain is loaded
- Nearest-neighbour search within 50 m radius
- Default depth-of-cover constant (0.75 m, WSAA standard)
- ``get_path_hgl`` with provided steady-state results
- ``suggest_air_valves`` / ``suggest_scour_valves`` find local maxima/minima
- Vacuum / cavitation zone detection
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Initial state and constants
# ---------------------------------------------------------------------------

def test_terrain_initial_state(api_instance):
    """Fresh API: no terrain data loaded; defaults match documented constants."""
    assert api_instance._terrain_data is None
    assert api_instance._default_depth_of_cover == pytest.approx(0.75)


def test_get_ground_elevation_returns_none_without_terrain(api_instance):
    assert api_instance.get_ground_elevation(0, 0) is None
    assert api_instance.get_ground_elevation(123.4, -567.8) is None


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------

def _write_xyz(path: Path, rows: list[tuple[float, float, float]]):
    path.write_text(
        "Easting,Northing,Elevation\n"
        + "\n".join(f"{x},{y},{z}" for x, y, z in rows),
        encoding='utf-8',
    )


def test_import_terrain_from_csv_roundtrip(api_instance, tmp_path):
    csv_path = tmp_path / 'terrain.csv'
    rows = [(0.0, 0.0, 100.0), (10.0, 0.0, 105.0), (0.0, 10.0, 102.0), (20.0, 20.0, 110.0)]
    _write_xyz(csv_path, rows)

    ok = api_instance.import_terrain_from_csv(str(csv_path))
    assert ok is True
    assert api_instance._terrain_data is not None
    assert api_instance._terrain_data.shape == (4, 3)
    np.testing.assert_allclose(api_instance._terrain_data[0], [0.0, 0.0, 100.0])


def test_import_terrain_from_csv_missing_file_returns_false(api_instance):
    assert api_instance.import_terrain_from_csv('/nonexistent/path.csv') is False
    assert api_instance._terrain_data is None  # state untouched


def test_get_ground_elevation_nearest_neighbour(api_instance, tmp_path):
    csv_path = tmp_path / 'terrain.csv'
    rows = [(0.0, 0.0, 100.0), (10.0, 0.0, 105.0), (0.0, 10.0, 102.0), (20.0, 20.0, 110.0)]
    _write_xyz(csv_path, rows)
    api_instance.import_terrain_from_csv(str(csv_path))

    # Exact match — returns the elevation
    assert api_instance.get_ground_elevation(0.0, 0.0) == pytest.approx(100.0)
    # Near (10, 0) — picks (10, 0, 105)
    assert api_instance.get_ground_elevation(11.0, 1.0) == pytest.approx(105.0)


def test_get_ground_elevation_outside_search_radius_returns_none(api_instance, tmp_path):
    csv_path = tmp_path / 'terrain.csv'
    _write_xyz(csv_path, [(0.0, 0.0, 100.0)])
    api_instance.import_terrain_from_csv(str(csv_path))

    # 50 m search radius — point at (1000, 1000) should return None
    assert api_instance.get_ground_elevation(1000.0, 1000.0) is None


# ---------------------------------------------------------------------------
# get_path_hgl
# ---------------------------------------------------------------------------

def test_get_path_hgl_returns_none_without_results(loaded_network):
    assert loaded_network.get_path_hgl(['J1', 'J2'], None) is None


def test_get_path_hgl_combines_pressure_and_elevation(loaded_network):
    """HGL[i] = pressure[i] + elevation[i]."""
    results = loaded_network.run_steady_state(save_plot=False)
    junctions = list(loaded_network.wn.junction_name_list)[:3]
    hgl = loaded_network.get_path_hgl(junctions, results)

    assert hgl is not None
    assert len(hgl) == len(junctions)
    # Sanity: each HGL value should equal pressure + elevation
    pressures = results.get('pressures', {})
    for i, jid in enumerate(junctions):
        node = loaded_network.wn.get_node(jid)
        p_avg = pressures.get(jid, {}).get('avg_m', 0)
        expected = p_avg + node.elevation
        assert hgl[i] == pytest.approx(expected, rel=1e-3)


# ---------------------------------------------------------------------------
# Air valve / scour valve / vacuum / cavitation suggestions
# ---------------------------------------------------------------------------

def _profile(elev, hgl=None):
    """Construct a minimal profile dict the helpers expect."""
    chainage = list(range(0, 100 * len(elev), 100))
    p = {
        'chainage': chainage,
        'elevation': elev,
        'labels': [f"N{i}" for i in range(len(elev))],
    }
    if hgl is not None:
        p['hgl'] = hgl
    return p


def test_suggest_scour_valves_finds_local_minimum(loaded_network):
    profile = _profile([100, 95, 90, 95, 100])  # valley at index 2
    suggestions = loaded_network.suggest_scour_valves(profile)
    assert len(suggestions) == 1
    assert suggestions[0]['elevation'] == 90


def test_suggest_scour_valves_too_short(loaded_network):
    assert loaded_network.suggest_scour_valves(_profile([100])) == []
    assert loaded_network.suggest_scour_valves(_profile([100, 90])) == []


def test_suggest_air_valves_handles_no_network(loaded_network):
    """Even when the per-node lookup fails, returns suggestions for peaks."""
    profile = _profile([90, 95, 100, 95, 90])  # peak at index 2
    suggestions = loaded_network.suggest_air_valves(profile)
    assert len(suggestions) == 1
    assert suggestions[0]['elevation'] == 100


def test_detect_vacuum_zones_when_hgl_below_pipe(loaded_network):
    profile = _profile(
        elev=[100, 100, 100, 100, 100],
        hgl=[105, 90, 85, 95, 105],   # vacuum at indices 1-3
    )
    zones = loaded_network.detect_vacuum_zones(profile)
    assert len(zones) == 1
    start, end = zones[0]
    assert start == 100
    assert end == 400


def test_detect_vacuum_zones_no_hgl_returns_empty(loaded_network):
    profile = _profile([100, 95, 90])
    assert loaded_network.detect_vacuum_zones(profile) == []


def test_detect_cavitation_risk_when_pressure_below_minus_eight(loaded_network):
    profile = _profile(
        elev=[100, 100, 100, 100],
        hgl=[105, 91, 105, 105],   # pressure at index 1 = -9 m → cavitation risk
    )
    risks = loaded_network.detect_cavitation_risk(profile)
    assert len(risks) == 1


def test_detect_cavitation_risk_safe_profile_returns_empty(loaded_network):
    profile = _profile(
        elev=[100, 100, 100],
        hgl=[110, 105, 102],   # all pressures non-negative
    )
    assert loaded_network.detect_cavitation_risk(profile) == []

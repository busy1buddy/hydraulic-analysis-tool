"""
Tests for Surge Protection Design Assistant (I5)
==================================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


@pytest.fixture
def api_with_network():
    api = HydraulicAPI()
    api.create_network(
        name='surge_test',
        junctions=[
            {'id': 'J1', 'elevation': 50, 'demand': 10.0, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 70, 'demand': 5.0, 'x': 500, 'y': 0},
            {'id': 'J3', 'elevation': 30, 'demand': 8.0, 'x': 1000, 'y': 0},
        ],
        reservoirs=[{'id': 'R1', 'head': 100, 'x': -200, 'y': 0}],
        pipes=[
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 1000,
             'diameter': 300, 'roughness': 130},
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 800,
             'diameter': 250, 'roughness': 130},
            {'id': 'P3', 'start': 'J2', 'end': 'J3', 'length': 600,
             'diameter': 200, 'roughness': 130},
        ],
    )
    return api


class TestSurgeProtection:
    """Tests for surge protection design API."""

    def test_low_surge_no_protection(self, api_with_network):
        """Surge < 30 m should not require protection."""
        results = {
            'max_surge_m': 15.0,
            'max_surge_kPa': 147,
            'junctions': {},
        }
        recs = api_with_network.design_surge_protection(results)
        assert recs['surge_vessel'] is None
        assert len(recs['air_valves']) == 0
        assert recs['slow_valve'] is None
        assert 'no protection required' in recs['summary'][0].lower()

    def test_high_surge_produces_recommendations(self, api_with_network):
        """Surge > 30 m should produce all three recommendation types."""
        results = {
            'max_surge_m': 80.0,
            'max_surge_kPa': 785,
            'junctions': {
                'J1': {'head': [100, 180, 90]},
                'J2': {'head': [80, 160, 70]},
            },
        }
        recs = api_with_network.design_surge_protection(results)
        assert recs['surge_vessel'] is not None
        assert recs['surge_vessel']['volume_m3'] > 0
        assert len(recs['air_valves']) > 0
        assert recs['slow_valve'] is not None

    def test_surge_vessel_has_required_fields(self, api_with_network):
        results = {'max_surge_m': 50, 'max_surge_kPa': 490, 'junctions': {}}
        recs = api_with_network.design_surge_protection(results)
        sv = recs['surge_vessel']
        assert sv is not None
        assert 'volume_m3' in sv
        assert 'pressure_rating_kPa' in sv
        assert 'location' in sv
        assert 'basis' in sv

    def test_slow_valve_closure_time(self, api_with_network):
        """Closure time should be >= 2L/a (critical period)."""
        results = {'max_surge_m': 50, 'max_surge_kPa': 490, 'junctions': {}}
        recs = api_with_network.design_surge_protection(results)
        scv = recs['slow_valve']
        assert scv is not None
        assert scv['recommended_closure_s'] >= scv['critical_period_s']
        # Critical period = 2L/a
        total_L = sum(api_with_network.wn.get_link(pid).length
                      for pid in api_with_network.wn.pipe_name_list)
        expected_tc = 2 * total_L / 1100  # wave speed default
        assert abs(scv['critical_period_s'] - expected_tc) < 0.5

    def test_air_valves_at_high_points(self, api_with_network):
        """Air valves should be recommended at highest-elevation nodes."""
        results = {'max_surge_m': 60, 'max_surge_kPa': 589, 'junctions': {}}
        recs = api_with_network.design_surge_protection(results)
        # J2 at 70m is the highest junction
        av_nodes = [av['node'] for av in recs['air_valves']]
        assert 'J2' in av_nodes

    def test_summary_list_populated(self, api_with_network):
        results = {'max_surge_m': 50, 'max_surge_kPa': 490, 'junctions': {}}
        recs = api_with_network.design_surge_protection(results)
        assert len(recs['summary']) >= 2  # at least vessel + valve

    def test_no_network_returns_error(self):
        api = HydraulicAPI()
        recs = api.design_surge_protection({'max_surge_m': 50})
        assert 'error' in recs

    def test_pressure_rating_includes_safety_factor(self, api_with_network):
        """Vessel pressure rating should be 1.5x surge."""
        results = {'max_surge_m': 60, 'max_surge_kPa': 589, 'junctions': {}}
        recs = api_with_network.design_surge_protection(results)
        assert recs['surge_vessel']['pressure_rating_kPa'] >= 589 * 1.4

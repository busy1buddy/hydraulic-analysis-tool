"""
Tests for Network Skeletonisation (J4) and Sensitivity Analysis (J7)
=====================================================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


@pytest.fixture
def api_with_dead_ends():
    """Network with dead-end branches for skeletonisation testing."""
    api = HydraulicAPI()
    api.create_network(
        name='skel_test',
        junctions=[
            {'id': 'J1', 'elevation': 50, 'demand': 5.0, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 55, 'demand': 3.0, 'x': 200, 'y': 0},
            {'id': 'J3', 'elevation': 52, 'demand': 0, 'x': 100, 'y': 100},  # dead end, no demand
            {'id': 'J4', 'elevation': 53, 'demand': 0, 'x': 300, 'y': 0},    # series node, no demand
            {'id': 'J5', 'elevation': 48, 'demand': 2.0, 'x': 500, 'y': 0},
        ],
        reservoirs=[{'id': 'R1', 'head': 100, 'x': -200, 'y': 0}],
        pipes=[
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
             'diameter': 300, 'roughness': 130},
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 400,
             'diameter': 250, 'roughness': 130},
            {'id': 'P3', 'start': 'J1', 'end': 'J3', 'length': 100,
             'diameter': 80, 'roughness': 130},   # dead end, small
            {'id': 'P4', 'start': 'J2', 'end': 'J4', 'length': 200,
             'diameter': 200, 'roughness': 130},
            {'id': 'P5', 'start': 'J4', 'end': 'J5', 'length': 300,
             'diameter': 200, 'roughness': 130},
        ],
    )
    return api


class TestSkeletonisation:

    def test_dead_end_detected(self, api_with_dead_ends):
        result = api_with_dead_ends.skeletonise(min_diameter_mm=100)
        dead_ends = result['dead_end_removals']
        # J3 is dead-end with DN80 < 100mm threshold
        assert any(d['node'] == 'J3' for d in dead_ends)

    def test_series_merge_detected(self, api_with_dead_ends):
        result = api_with_dead_ends.skeletonise()
        merges = result['series_merges']
        # J4 is series (2 pipes, no demand)
        assert any(m['node'] == 'J4' for m in merges)

    def test_equivalent_pipe_length(self, api_with_dead_ends):
        result = api_with_dead_ends.skeletonise()
        j4_merge = [m for m in result['series_merges'] if m['node'] == 'J4']
        assert len(j4_merge) == 1
        # P4 (200m) + P5 (300m) = 500m
        assert abs(j4_merge[0]['equivalent_length_m'] - 500) < 0.1

    def test_before_after_counts(self, api_with_dead_ends):
        result = api_with_dead_ends.skeletonise(min_diameter_mm=100)
        assert result['before']['nodes'] == 5
        assert result['before']['pipes'] == 5
        assert result['after']['nodes'] < result['before']['nodes']
        assert result['after']['pipes'] < result['before']['pipes']

    def test_reduction_percentage(self, api_with_dead_ends):
        result = api_with_dead_ends.skeletonise(min_diameter_mm=100)
        assert result['reduction_pct'] > 0

    def test_no_dead_ends_high_threshold(self, api_with_dead_ends):
        """With threshold 50mm, no dead ends should be removed (smallest is 80mm)."""
        result = api_with_dead_ends.skeletonise(min_diameter_mm=50)
        assert len(result['dead_end_removals']) == 0

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.skeletonise()
        assert 'error' in result


class TestSensitivityAnalysis:

    @pytest.fixture
    def api_simple(self):
        api = HydraulicAPI()
        api.create_network(
            name='sens_test',
            junctions=[
                {'id': 'J1', 'elevation': 50, 'demand': 5.0, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 60, 'demand': 3.0, 'x': 200, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 100, 'x': -200, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
                 'diameter': 300, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 400,
                 'diameter': 250, 'roughness': 130},
            ],
        )
        return api

    def test_roughness_sensitivity_returns_results(self, api_simple):
        result = api_simple.sensitivity_analysis('roughness')
        assert isinstance(result, list)
        assert len(result) == 2  # 2 pipes

    def test_sensitivity_sorted_by_impact(self, api_simple):
        result = api_simple.sensitivity_analysis('roughness')
        for i in range(len(result) - 1):
            assert result[i]['pressure_change_m'] >= result[i + 1]['pressure_change_m']

    def test_sensitivity_has_rank(self, api_simple):
        result = api_simple.sensitivity_analysis('roughness')
        assert result[0]['sensitivity_rank'] == 1

    def test_demand_sensitivity(self, api_simple):
        result = api_simple.sensitivity_analysis('demand')
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.sensitivity_analysis()
        assert 'error' in result

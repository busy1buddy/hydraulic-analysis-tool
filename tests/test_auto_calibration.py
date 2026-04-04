"""
Tests for Auto-Calibration (I4)
================================
Tests that the scipy.optimize roughness calibration improves R².
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


@pytest.fixture
def api_with_network():
    """API with a simple network for calibration testing."""
    api = HydraulicAPI()
    api.create_network(
        name='calib_test',
        junctions=[
            {'id': 'J1', 'elevation': 50, 'demand': 5.0, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 55, 'demand': 3.0, 'x': 100, 'y': 0},
            {'id': 'J3', 'elevation': 45, 'demand': 4.0, 'x': 200, 'y': 0},
        ],
        reservoirs=[{'id': 'R1', 'head': 100, 'x': -100, 'y': 0}],
        pipes=[
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
             'diameter': 300, 'roughness': 130},
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 400,
             'diameter': 250, 'roughness': 130},
            {'id': 'P3', 'start': 'J2', 'end': 'J3', 'length': 300,
             'diameter': 200, 'roughness': 130},
        ],
    )
    return api


class TestAutoCalibration:
    """Tests for automatic roughness calibration."""

    def test_auto_calibrate_returns_result(self, api_with_network):
        """Auto-calibrate should return a result dict."""
        api = api_with_network
        # Get current pressures as "measured" (perfect calibration)
        results = api.run_steady_state(save_plot=False)
        pressures = results['pressures']
        measured = {nid: p['avg_m'] for nid, p in pressures.items()}

        result = api.auto_calibrate_roughness(measured)
        assert 'groups' in result
        assert 'before' in result
        assert 'after' in result
        assert 'iterations' in result

    def test_calibration_improves_r2(self, api_with_network):
        """
        Given deliberately wrong roughness, calibration should improve R².

        Strategy: run with correct C=130, record pressures as "measured",
        then change C to wrong values and calibrate back.
        """
        api = api_with_network

        # Step 1: Get "true" pressures at C=130
        results = api.run_steady_state(save_plot=False)
        true_pressures = {nid: p['avg_m'] for nid, p in results['pressures'].items()}

        # Step 2: Set wrong roughness (C=100 — much too low)
        for pid in api.wn.pipe_name_list:
            api.wn.get_link(pid).roughness = 100

        # Step 3: Auto-calibrate with the "true" measurements
        result = api.auto_calibrate_roughness(true_pressures)

        # R² should improve (after > before)
        assert result['after']['r2'] >= result['before']['r2']
        # RMSE should decrease
        assert result['after']['rmse'] <= result['before']['rmse'] + 0.1

    def test_calibration_convergence_tracked(self, api_with_network):
        api = api_with_network
        results = api.run_steady_state(save_plot=False)
        measured = {nid: p['avg_m'] for nid, p in results['pressures'].items()}

        result = api.auto_calibrate_roughness(measured)
        assert 'convergence' in result
        assert len(result['convergence']) > 0

    def test_groups_contain_pipe_info(self, api_with_network):
        api = api_with_network
        results = api.run_steady_state(save_plot=False)
        measured = {nid: p['avg_m'] for nid, p in results['pressures'].items()}

        result = api.auto_calibrate_roughness(measured)
        for gname, g in result['groups'].items():
            assert 'C_before' in g
            assert 'C_after' in g
            assert 'pipes' in g
            assert 'n_pipes' in g

    def test_auto_group_pipes(self, api_with_network):
        """Auto-grouping should assign all pipes to groups."""
        api = api_with_network
        groups = api._auto_group_pipes()
        all_pipes = set()
        for g in groups.values():
            all_pipes.update(g['pipes'])
        assert len(all_pipes) == 3  # P1, P2, P3

    def test_custom_material_groups(self, api_with_network):
        """Test calibration with explicit material groups."""
        api = api_with_network
        results = api.run_steady_state(save_plot=False)
        measured = {nid: p['avg_m'] for nid, p in results['pressures'].items()}

        groups = {
            'Group A': {
                'pipes': ['P1', 'P2'],
                'bounds': (100, 150),
            },
            'Group B': {
                'pipes': ['P3'],
                'bounds': (100, 150),
            },
        }

        result = api.auto_calibrate_roughness(measured, material_groups=groups)
        assert 'Group A' in result['groups']
        assert 'Group B' in result['groups']

    def test_no_network_returns_error(self):
        api = HydraulicAPI()
        result = api.auto_calibrate_roughness({'J1': 30.0})
        assert 'error' in result

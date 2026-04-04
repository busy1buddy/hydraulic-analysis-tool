"""
Tests for Pipe Profile (J1) and Pump Operating Point (J2)
==========================================================
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
        name='profile_test',
        junctions=[
            {'id': 'J1', 'elevation': 50, 'demand': 5.0, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 60, 'demand': 3.0, 'x': 200, 'y': 0},
            {'id': 'J3', 'elevation': 45, 'demand': 4.0, 'x': 400, 'y': 0},
        ],
        reservoirs=[{'id': 'R1', 'head': 100, 'x': -200, 'y': 0}],
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


class TestPipeProfile:

    def test_hgl_calculated(self, api_with_network):
        """HGL should equal elevation + pressure at each node."""
        api = api_with_network
        results = api.run_steady_state(save_plot=False)
        profile = api.compute_pipe_profile(['R1', 'J1', 'J2', 'J3'], results)
        assert 'error' not in profile
        for i, nid in enumerate(profile['node_ids']):
            expected_hgl = profile['ground'][i] + profile['pressure_head'][i]
            assert abs(profile['hgl'][i] - expected_hgl) < 0.1

    def test_distance_accumulates(self, api_with_network):
        """Stations should increase monotonically."""
        api = api_with_network
        profile = api.compute_pipe_profile(['R1', 'J1', 'J2', 'J3'])
        stations = profile['stations']
        for i in range(1, len(stations)):
            assert stations[i] > stations[i - 1]
        # Total should be 500 + 400 + 300 = 1200
        assert abs(profile['total_length_m'] - 1200) < 0.1

    def test_pipe_info_present(self, api_with_network):
        profile = api_with_network.compute_pipe_profile(['R1', 'J1', 'J2', 'J3'])
        assert len(profile['pipes']) == 3
        assert profile['pipes'][0]['id'] == 'P1'
        assert profile['pipes'][0]['diameter_mm'] == 300

    def test_short_path(self, api_with_network):
        """Two-node path should work."""
        profile = api_with_network.compute_pipe_profile(['R1', 'J1'])
        assert 'error' not in profile
        assert len(profile['stations']) == 2

    def test_invalid_path(self, api_with_network):
        """Non-adjacent nodes should return error."""
        profile = api_with_network.compute_pipe_profile(['R1', 'J3'])
        assert 'error' in profile

    def test_single_node_error(self, api_with_network):
        profile = api_with_network.compute_pipe_profile(['R1'])
        assert 'error' in profile

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.compute_pipe_profile(['J1', 'J2'])
        assert 'error' in result

    def test_hgl_decreases_along_flow(self, api_with_network):
        """HGL should generally decrease from reservoir downstream."""
        api = api_with_network
        profile = api.compute_pipe_profile(['R1', 'J1', 'J2', 'J3'])
        # Reservoir HGL = head = 100 m, should be highest
        assert profile['hgl'][0] >= max(profile['hgl'][1:])


class TestPumpOperatingPoint:

    @pytest.fixture
    def api_with_pump(self):
        """Network with a pump for operating point testing."""
        api = HydraulicAPI()
        api.load_network('Net1.inp')
        return api

    def test_pump_not_found(self, api_with_network):
        result = api_with_network.compute_pump_operating_point('NONEXISTENT')
        assert 'error' in result

    def test_no_network(self):
        api = HydraulicAPI()
        result = api.compute_pump_operating_point('P1')
        assert 'error' in result

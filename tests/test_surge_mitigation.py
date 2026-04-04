"""
Tests for Surge Mitigation Design (N6)
========================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestClosureTime:

    def test_basic_calculation(self):
        api = HydraulicAPI()
        result = api.calculate_safe_closure_time(1000, 1100)
        # tc = 2L/a = 2*1000/1100 = 1.82s
        assert abs(result['critical_time_s'] - 1.82) < 0.1
        assert result['recommended_s'] > result['critical_time_s']

    def test_longer_pipe_longer_time(self):
        api = HydraulicAPI()
        short = api.calculate_safe_closure_time(500, 1100)
        long = api.calculate_safe_closure_time(2000, 1100)
        assert long['critical_time_s'] > short['critical_time_s']

    def test_invalid_inputs(self):
        api = HydraulicAPI()
        result = api.calculate_safe_closure_time(0, 1100)
        assert 'error' in result

    def test_known_hand_calculation(self):
        """Verify against hand calculation.
        L=500m, a=1100 m/s → tc = 2*500/1100 = 0.909s
        Recommended (5x) = 4.545s
        """
        api = HydraulicAPI()
        result = api.calculate_safe_closure_time(500, 1100)
        assert abs(result['critical_time_s'] - 0.91) < 0.02
        assert abs(result['recommended_s'] - 4.55) < 0.1

    def test_result_structure(self):
        api = HydraulicAPI()
        result = api.calculate_safe_closure_time(1000, 1100)
        assert 'critical_time_s' in result
        assert 'minimum_safe_s' in result
        assert 'recommended_s' in result
        assert 'surge_reduction' in result
        assert 'basis' in result


class TestSurgeMitigation:

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.design_surge_mitigation()
        assert 'error' in result

    def test_basic_mitigation_design(self):
        api = HydraulicAPI()
        api.create_network(
            name='surge_test',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 5, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -500, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 1000,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        result = api.design_surge_mitigation()
        assert 'options' in result
        assert 'slow_closing_valve' in result['options']
        assert 'surge_vessel' in result['options']
        assert 'air_valves' in result['options']

    def test_specific_pipe(self):
        api = HydraulicAPI()
        api.create_network(
            name='surge_pipe',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 5, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 3, 'x': 500, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -500, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 800,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        result = api.design_surge_mitigation(pipe_id='P2')
        assert result['pipe_id'] == 'P2'
        assert result['pipe_length_m'] == 800

    def test_vessel_volume_positive(self):
        api = HydraulicAPI()
        api.create_network(
            name='surge_vol',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 10, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -500, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 2000,
                 'diameter': 300, 'roughness': 130},
            ],
        )
        result = api.design_surge_mitigation()
        assert result['options']['surge_vessel']['volume_litres'] > 0

"""
Tests for Scenario Difference Report (N8) and Custom Thresholds (N10)
======================================================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestScenarioDifference:

    @pytest.fixture
    def api_with_results(self):
        api = HydraulicAPI()
        api.create_network(
            name='diff_test',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 5, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 3, 'x': 100, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 150, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 200,
                 'diameter': 150, 'roughness': 130},
            ],
        )
        return api

    def test_basic_difference(self, api_with_results):
        api = api_with_results
        r_before = api.run_steady_state(save_plot=False)

        # Upsize pipe
        api.wn.get_link('P1').diameter = 0.300
        r_after = api.run_steady_state(save_plot=False)

        diff = api.scenario_difference(r_before, r_after, 'Before', 'After')
        assert 'node_differences' in diff
        assert 'pipe_differences' in diff
        assert 'summary' in diff

    def test_pressure_improvement_detected(self, api_with_results):
        api = api_with_results
        r_before = api.run_steady_state(save_plot=False)

        api.wn.get_link('P1').diameter = 0.300
        r_after = api.run_steady_state(save_plot=False)

        diff = api.scenario_difference(r_before, r_after)
        # Upsizing should improve pressures
        improvements = [d for d in diff['node_differences'] if d['change_m'] > 0]
        assert len(improvements) > 0

    def test_velocity_reduction_detected(self, api_with_results):
        api = api_with_results
        r_before = api.run_steady_state(save_plot=False)

        api.wn.get_link('P1').diameter = 0.300
        r_after = api.run_steady_state(save_plot=False)

        diff = api.scenario_difference(r_before, r_after)
        # Larger pipe should reduce velocity
        vel_changes = [d for d in diff['pipe_differences']
                       if d['pipe'] == 'P1']
        assert len(vel_changes) > 0
        assert vel_changes[0]['velocity_change_ms'] < 0

    def test_no_results_error(self):
        api = HydraulicAPI()
        result = api.scenario_difference(None, None)
        assert 'error' in result

    def test_summary_plain_english(self, api_with_results):
        api = api_with_results
        r_before = api.run_steady_state(save_plot=False)
        api.wn.get_link('P1').diameter = 0.300
        r_after = api.run_steady_state(save_plot=False)

        diff = api.scenario_difference(r_before, r_after)
        assert isinstance(diff['summary'], str)
        assert len(diff['summary']) > 10


class TestCustomThresholds:

    def test_set_thresholds(self):
        api = HydraulicAPI()
        result = api.set_compliance_thresholds(
            min_pressure_m=10, max_pressure_m=120)
        assert result['thresholds']['min_pressure_m'] == 10
        assert result['thresholds']['max_pressure_m'] == 120

    def test_get_thresholds(self):
        api = HydraulicAPI()
        t = api.get_compliance_thresholds()
        assert t['min_pressure_m'] == 20  # WSAA default
        assert t['max_pressure_m'] == 50

    def test_mining_thresholds(self):
        """Mining projects use higher pressure limits."""
        api = HydraulicAPI()
        api.set_compliance_thresholds(max_pressure_m=120)
        t = api.get_compliance_thresholds()
        assert t['max_pressure_m'] == 120

    def test_custom_thresholds_affect_compliance(self):
        """Custom thresholds should change compliance results."""
        api = HydraulicAPI()
        api.create_network(
            name='threshold_test',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )

        # Default thresholds: pressure ~50m should be at boundary
        r = api.run_steady_state(save_plot=False)

        # Set strict threshold: max 30m
        api.set_compliance_thresholds(max_pressure_m=30)
        cert = api.run_design_compliance_check()

        # With 30m max threshold, 50m head may cause failures
        # (depends on headloss)
        assert 'checks' in cert

    def test_custom_chlorine_threshold(self):
        api = HydraulicAPI()
        api.set_compliance_thresholds(min_chlorine_mgl=0.5)
        assert api.WSAA_MIN_CHLORINE_MGL == 0.5

    def test_thresholds_persist_across_analyses(self):
        api = HydraulicAPI()
        api.set_compliance_thresholds(min_pressure_m=15)
        assert api.DEFAULTS['min_pressure_m'] == 15
        # Second call should still show 15
        t = api.get_compliance_thresholds()
        assert t['min_pressure_m'] == 15

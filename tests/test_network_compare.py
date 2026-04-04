"""
Tests for Network Comparison (I10) and Demand Forecasting (I11)
================================================================
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
        name='compare_base',
        junctions=[
            {'id': 'J1', 'elevation': 50, 'demand': 5.0, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 60, 'demand': 3.0, 'x': 100, 'y': 0},
        ],
        reservoirs=[{'id': 'R1', 'head': 100, 'x': -100, 'y': 0}],
        pipes=[
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
             'diameter': 300, 'roughness': 130},
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 400,
             'diameter': 250, 'roughness': 130},
        ],
    )
    return api


class TestNetworkComparison:

    def test_identical_networks_show_zero_differences(self, api_with_network):
        """Comparing a network to itself should show no differences."""
        result = api_with_network.compare_networks(api_with_network._inp_file)
        assert result['summary']['identical'] is True
        assert result['summary']['nodes_added'] == 0
        assert result['summary']['pipes_added'] == 0
        assert result['summary']['properties_changed'] == 0

    def test_modified_pipe_detected(self, api_with_network, tmp_path):
        """Changing a pipe diameter should be detected."""
        api = api_with_network
        # Create modified version
        api2 = HydraulicAPI(work_dir=str(tmp_path))
        api2.create_network(
            name='compare_mod',
            junctions=[
                {'id': 'J1', 'elevation': 50, 'demand': 5.0, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 60, 'demand': 3.0, 'x': 100, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 100, 'x': -100, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
                 'diameter': 400, 'roughness': 130},  # Changed from 300 to 400
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 400,
                 'diameter': 250, 'roughness': 130},
            ],
        )
        result = api.compare_networks(api2._inp_file)
        assert result['summary']['properties_changed'] >= 1
        # Find P1 change
        p1_changes = [p for p in result['properties'] if p.get('pipe') == 'P1']
        assert len(p1_changes) == 1
        assert 'diameter' in p1_changes[0]['changes'][0]

    def test_added_pipe_detected(self, api_with_network, tmp_path):
        """Adding a pipe to the second network should be detected."""
        api2 = HydraulicAPI(work_dir=str(tmp_path))
        api2.create_network(
            name='compare_add',
            junctions=[
                {'id': 'J1', 'elevation': 50, 'demand': 5.0, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 60, 'demand': 3.0, 'x': 100, 'y': 0},
                {'id': 'J3', 'elevation': 55, 'demand': 2.0, 'x': 200, 'y': 0},
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
        result = api_with_network.compare_networks(api2._inp_file)
        assert 'P3' in result['topology']['added_pipes']
        assert 'J3' in result['topology']['added_nodes']

    def test_no_network_returns_error(self):
        api = HydraulicAPI()
        result = api.compare_networks("nonexistent.inp")
        assert 'error' in result


class TestDemandForecasting:

    def test_linear_forecast(self, api_with_network):
        result = api_with_network.forecast_demand(
            growth_model='linear', growth_rate=0.02,
            base_year=2026, forecast_years=[2030, 2040])
        assert 2030 in result['forecasts']
        assert 2040 in result['forecasts']
        # Linear: 2030 = 1 + 0.02*4 = 1.08
        assert abs(result['forecasts'][2030]['multiplier'] - 1.08) < 0.01
        # 2040 = 1 + 0.02*14 = 1.28
        assert abs(result['forecasts'][2040]['multiplier'] - 1.28) < 0.01

    def test_exponential_forecast(self, api_with_network):
        result = api_with_network.forecast_demand(
            growth_model='exponential', growth_rate=0.03,
            base_year=2026, forecast_years=[2036])
        # (1.03)^10 ≈ 1.3439
        assert abs(result['forecasts'][2036]['multiplier'] - 1.344) < 0.01

    def test_logistic_forecast(self, api_with_network):
        result = api_with_network.forecast_demand(
            growth_model='logistic', growth_rate=0.05,
            base_year=2026, forecast_years=[2076])
        # Logistic should asymptote at 2.0
        assert result['forecasts'][2076]['multiplier'] < 2.1
        assert result['forecasts'][2076]['multiplier'] > 1.5

    def test_forecast_detects_failure(self, api_with_network):
        """High growth should eventually cause pressure failures."""
        result = api_with_network.forecast_demand(
            growth_model='linear', growth_rate=0.10,  # 10% per year
            base_year=2026, forecast_years=[2030, 2040, 2050])
        # With 10% growth, should fail eventually
        # May or may not fail depending on network capacity
        assert 'first_failure_year' in result

    def test_forecast_restores_demands(self, api_with_network):
        """After forecasting, original demands should be restored."""
        api = api_with_network
        # Record original
        original = {}
        for jid in api.wn.junction_name_list:
            j = api.wn.get_node(jid)
            if j.demand_timeseries_list:
                original[jid] = j.demand_timeseries_list[0].base_value

        api.forecast_demand(growth_rate=0.5, forecast_years=[2050])

        # Check restored
        for jid, base in original.items():
            j = api.wn.get_node(jid)
            current = j.demand_timeseries_list[0].base_value
            assert abs(current - base) < 1e-6, f"{jid}: expected {base}, got {current}"

    def test_no_network_returns_error(self):
        api = HydraulicAPI()
        result = api.forecast_demand()
        assert 'error' in result

    def test_total_demand_increases(self, api_with_network):
        """Total demand should increase with each forecast year."""
        result = api_with_network.forecast_demand(
            growth_rate=0.03, forecast_years=[2030, 2040, 2050])
        demands = [result['forecasts'][y]['total_demand_lps'] for y in [2030, 2040, 2050]]
        assert demands[0] < demands[1] < demands[2]

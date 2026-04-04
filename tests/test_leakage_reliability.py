"""
Tests for Leakage Detection (J5) and Network Reliability (J13)
===============================================================
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
        name='leak_test',
        junctions=[
            {'id': 'J1', 'elevation': 50, 'demand': 5.0, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 55, 'demand': 3.0, 'x': 200, 'y': 0},
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


class TestLeakageDetection:

    def test_leakage_correct_for_known_inputs(self, api_with_network):
        """Total demand is 12 LPS. Inflow of 15 LPS means 3 LPS loss."""
        result = api_with_network.leakage_analysis(measured_inflow_lps=15.0)
        assert abs(result['total_demand_lps'] - 12.0) < 0.1
        assert abs(result['total_loss_lps'] - 3.0) < 0.1
        assert result['loss_pct'] == pytest.approx(20.0, abs=1)

    def test_no_loss_scenario(self, api_with_network):
        """Inflow = demand means zero real loss."""
        result = api_with_network.leakage_analysis(measured_inflow_lps=12.0)
        assert result['total_loss_lps'] == pytest.approx(0, abs=0.5)

    def test_ili_calculated(self, api_with_network):
        result = api_with_network.leakage_analysis(measured_inflow_lps=15.0)
        assert 'ili' in result
        assert result['ili'] >= 0

    def test_performance_category_assigned(self, api_with_network):
        result = api_with_network.leakage_analysis(measured_inflow_lps=15.0)
        assert result['performance_category'] is not None
        assert any(cat in result['performance_category']
                   for cat in ['A', 'B', 'C', 'D', 'E'])

    def test_network_stats_present(self, api_with_network):
        result = api_with_network.leakage_analysis(measured_inflow_lps=15.0)
        assert result['network_length_km'] > 0
        assert result['n_connections'] == 3

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.leakage_analysis(15.0)
        assert 'error' in result


class TestNetworkReliability:

    def test_reliability_returns_results(self, api_with_network):
        results = api_with_network.reliability_analysis()
        assert isinstance(results, list)
        assert len(results) == 3  # 3 pipes

    def test_most_critical_pipe_identified(self, api_with_network):
        """P1 (connecting reservoir) should be most critical."""
        results = api_with_network.reliability_analysis()
        # First result is most critical
        assert results[0]['criticality_index'] >= results[-1]['criticality_index']
        # P1 failure should affect most nodes (it's the only supply path)
        p1 = [r for r in results if r['pipe_id'] == 'P1']
        assert len(p1) == 1
        assert p1[0]['n_affected'] >= 1

    def test_criticality_range(self, api_with_network):
        results = api_with_network.reliability_analysis()
        for r in results:
            assert 0 <= r['criticality_index'] <= 1

    def test_result_fields(self, api_with_network):
        results = api_with_network.reliability_analysis()
        for r in results:
            assert 'pipe_id' in r
            assert 'diameter_mm' in r
            assert 'n_affected' in r
            assert 'criticality_index' in r

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.reliability_analysis()
        assert 'error' in result

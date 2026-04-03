"""Tests for fire flow analysis."""

import pytest


class TestFireFlowAnalysis:
    def test_returns_results(self, loaded_network):
        result = loaded_network.run_fire_flow('J3', flow_lps=25, save_plot=False)
        assert 'fire_node' in result
        assert 'residual_pressures' in result
        assert 'compliance' in result
        assert result['fire_node'] == 'J3'
        assert result['fire_flow_lps'] == 25

    def test_residual_pressures_for_all_junctions(self, loaded_network):
        result = loaded_network.run_fire_flow('J3', flow_lps=25, save_plot=False)
        assert len(result['residual_pressures']) == 7  # All 7 junctions

    def test_fire_flow_reduces_pressure(self, loaded_network):
        """Adding fire demand should reduce pressures compared to normal."""
        normal = loaded_network.run_steady_state(save_plot=False)
        fire = loaded_network.run_fire_flow('J5', flow_lps=25, save_plot=False)

        # Fire flow should reduce pressure at the fire node
        normal_p = normal['pressures']['J5']['min_m']
        fire_p = fire['residual_pressures']['J5']
        assert fire_p < normal_p

    def test_no_network_error(self, api_instance):
        result = api_instance.run_fire_flow('J1')
        assert 'error' in result

    def test_compliance_check(self, loaded_network):
        """Fire flow at high-demand node should trigger compliance warnings."""
        result = loaded_network.run_fire_flow('J5', flow_lps=50, save_plot=False)
        assert len(result['compliance']) > 0

    def test_restores_original_demand(self, loaded_network):
        """Original demand should be restored after fire flow analysis."""
        node = loaded_network.wn.get_node('J3')
        original = node.demand_timeseries_list[0].base_value
        loaded_network.run_fire_flow('J3', flow_lps=25, save_plot=False)
        assert node.demand_timeseries_list[0].base_value == original

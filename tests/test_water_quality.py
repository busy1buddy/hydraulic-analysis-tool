"""Tests for water quality (water age) analysis."""

import pytest


class TestWaterQualityAnalysis:
    def test_returns_results(self, loaded_network):
        result = loaded_network.run_water_quality(
            parameter='age', duration_hrs=24, save_plot=False)
        assert 'parameter' in result
        assert 'junction_quality' in result
        assert 'stagnation_risk' in result
        assert 'compliance' in result

    def test_quality_for_all_junctions(self, loaded_network):
        result = loaded_network.run_water_quality(
            parameter='age', duration_hrs=24, save_plot=False)
        assert len(result['junction_quality']) == 7

    def test_age_values_positive(self, loaded_network):
        result = loaded_network.run_water_quality(
            parameter='age', duration_hrs=48, save_plot=False)
        for junc, data in result['junction_quality'].items():
            assert data['max_age_hrs'] >= 0, f'{junc} has negative age'

    def test_no_network_error(self, api_instance):
        result = api_instance.run_water_quality()
        assert 'error' in result

    def test_restores_original_duration(self, loaded_network):
        original_dur = loaded_network.wn.options.time.duration
        loaded_network.run_water_quality(
            parameter='age', duration_hrs=48, save_plot=False)
        assert loaded_network.wn.options.time.duration == original_dur

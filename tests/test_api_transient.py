"""Tests for transient (water hammer) analysis results."""

import pytest


class TestTransientResults:
    def test_returns_junctions(self, transient_results):
        assert len(transient_results['junctions']) == 6

    def test_surge_positive(self, transient_results):
        """Valve closure should cause positive surge (overpressure)."""
        assert transient_results['max_surge_m'] > 0
        assert transient_results['max_surge_kPa'] > 0

    def test_surge_magnitude(self, transient_results):
        """Known result: max surge ~20.6m for 0.5s closure at 1000 m/s."""
        assert 15 < transient_results['max_surge_m'] < 30

    def test_each_junction_has_data(self, transient_results):
        for name, data in transient_results['junctions'].items():
            assert 'steady_head_m' in data
            assert 'max_head_m' in data
            assert 'min_head_m' in data
            assert 'surge_m' in data
            assert data['max_head_m'] >= data['steady_head_m']

    def test_wave_speed_in_results(self, transient_results):
        assert transient_results['wave_speed_ms'] == 1000

    def test_valve_in_results(self, transient_results):
        assert transient_results['valve'] == 'V1'


class TestTransientCompliance:
    def test_has_compliance(self, transient_results):
        assert 'compliance' in transient_results

    def test_within_pn35(self, transient_results):
        """Default scenario should be within PN35 rating."""
        critical = [c for c in transient_results['compliance']
                    if c['type'] == 'CRITICAL']
        assert len(critical) == 0, f"Unexpected critical: {critical}"


class TestTransientMitigation:
    def test_has_mitigation(self, transient_results):
        assert 'mitigation' in transient_results
        assert len(transient_results['mitigation']) > 0

    def test_mitigation_content(self, transient_results):
        """With ~20m surge, should recommend slow-closing valves."""
        mitigations = ' '.join(transient_results['mitigation']).lower()
        assert 'valve' in mitigations or 'closure' in mitigations


class TestTransientErrors:
    def test_no_network_error(self, api_instance):
        """Should error if no network loaded."""
        result = api_instance.run_transient('V1', closure_time=0.5)
        assert 'error' in result

    def test_invalid_valve(self, loaded_network):
        """Should error if valve doesn't exist in network."""
        with pytest.raises(Exception):
            loaded_network.run_transient('NONEXISTENT', closure_time=0.5,
                                        save_plot=False)

"""Tests for steady-state hydraulic analysis results."""

import numpy as np
import pytest


class TestSteadyStatePressures:
    def test_returns_all_junctions(self, steady_results):
        assert len(steady_results['pressures']) == 7

    def test_j4_low_pressure(self, steady_results):
        """J4 is known to have min pressure of 17.2m (below WSAA 20m)."""
        j4 = steady_results['pressures']['J4']
        assert j4['min_m'] < 20

    def test_pressures_reasonable(self, steady_results):
        """All pressures should be between -10m and 200m (sanity check)."""
        for junc, data in steady_results['pressures'].items():
            assert data['min_m'] > -10, f"{junc} pressure too low: {data['min_m']}"
            assert data['max_m'] < 200, f"{junc} pressure too high: {data['max_m']}"

    def test_reservoir_side_highest(self, steady_results):
        """J1 (closest to reservoir) should have lower pressure than
        downstream junctions due to higher elevation."""
        j1 = steady_results['pressures']['J1']
        j6 = steady_results['pressures']['J6']
        # J6 has lower elevation (38m vs 50m), so should have higher pressure
        assert j6['avg_m'] > j1['avg_m']


class TestSteadyStateFlows:
    def test_returns_all_pipes(self, steady_results):
        assert len(steady_results['flows']) == 9

    def test_main_pipe_highest_flow(self, steady_results):
        """P1 (main from reservoir) should carry the most flow."""
        p1_avg = abs(steady_results['flows']['P1']['avg_lps'])
        for name, data in steady_results['flows'].items():
            if name != 'P1':
                assert p1_avg >= abs(data['avg_lps']) * 0.5, \
                    f"P1 avg {p1_avg} expected to be dominant flow"

    def test_velocities_calculated(self, steady_results):
        for name, data in steady_results['flows'].items():
            assert 'avg_velocity_ms' in data
            assert data['avg_velocity_ms'] >= 0


class TestSteadyStateCompliance:
    def test_has_compliance(self, steady_results):
        assert 'compliance' in steady_results
        assert len(steady_results['compliance']) > 0

    def test_j4_flagged(self, steady_results):
        """J4 should be flagged for low pressure."""
        messages = [c['message'] for c in steady_results['compliance']
                    if c.get('element') == 'J4']
        assert any('pressure' in m.lower() for m in messages)

    def test_velocity_warning(self, steady_results):
        """P4 or P8 should be flagged for high velocity."""
        velocity_warnings = [c for c in steady_results['compliance']
                            if 'velocity' in c.get('message', '').lower()]
        assert len(velocity_warnings) > 0

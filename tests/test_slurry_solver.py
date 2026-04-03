"""Tests for non-Newtonian/slurry fluid solver."""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBinghamPlastic:
    def test_zero_flow(self):
        from slurry_solver import bingham_plastic_headloss
        result = bingham_plastic_headloss(0, 0.2, 100, 1300, 5.0, 0.015)
        assert result['headloss_m'] == 0
        assert result['regime'] == 'static'

    def test_positive_headloss(self):
        from slurry_solver import bingham_plastic_headloss
        result = bingham_plastic_headloss(0.01, 0.2, 100, 1300, 5.0, 0.015)
        assert result['headloss_m'] > 0
        assert result['velocity_ms'] > 0

    def test_higher_flow_more_headloss(self):
        from slurry_solver import bingham_plastic_headloss
        r1 = bingham_plastic_headloss(0.005, 0.2, 100, 1300, 5.0, 0.015)
        r2 = bingham_plastic_headloss(0.020, 0.2, 100, 1300, 5.0, 0.015)
        assert r2['headloss_m'] > r1['headloss_m']

    def test_higher_yield_stress_more_headloss(self):
        from slurry_solver import bingham_plastic_headloss
        r1 = bingham_plastic_headloss(0.01, 0.2, 100, 1300, 5.0, 0.015)
        r2 = bingham_plastic_headloss(0.01, 0.2, 100, 1300, 50.0, 0.015)
        assert r2['headloss_m'] >= r1['headloss_m']


class TestPowerLaw:
    def test_shear_thinning(self):
        from slurry_solver import power_law_headloss
        result = power_law_headloss(0.01, 0.2, 100, 1010, 0.5, 0.6)
        assert result['headloss_m'] > 0
        assert result['flow_index_n'] == 0.6

    def test_zero_flow(self):
        from slurry_solver import power_law_headloss
        result = power_law_headloss(0, 0.2, 100, 1010, 0.5, 0.6)
        assert result['headloss_m'] == 0


class TestHerschelBulkley:
    def test_general_model(self):
        from slurry_solver import herschel_bulkley_headloss
        result = herschel_bulkley_headloss(0.01, 0.2, 100, 1200, 10.0, 0.3, 0.7)
        assert result['headloss_m'] > 0


class TestSlurryDatabase:
    def test_list_fluids(self):
        from slurry_solver import list_fluids
        fluids = list_fluids()
        assert 'water' in fluids
        assert 'mine_tailings_30pct' in fluids
        assert 'paste_fill_70pct' in fluids
        assert len(fluids) >= 5

    def test_network_analysis(self, loaded_network):
        from slurry_solver import analyze_slurry_network
        result = analyze_slurry_network(loaded_network.wn, 'mine_tailings_30pct')
        assert 'pipe_results' in result
        assert 'total_headloss_m' in result
        assert result['total_headloss_m'] > 0
        assert len(result['pipe_results']) == 9  # 9 pipes in AU network

    def test_water_baseline(self, loaded_network):
        from slurry_solver import analyze_slurry_network
        result = analyze_slurry_network(loaded_network.wn, 'water')
        assert result['fluid_name'] == 'water'

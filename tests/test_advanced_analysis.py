"""
Tests for Water Hammer Sizing (J6) and Monte Carlo (J8)
========================================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


@pytest.fixture
def api():
    api = HydraulicAPI()
    api.create_network(
        name='advanced_test',
        junctions=[
            {'id': 'J1', 'elevation': 50, 'demand': 5.0, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 55, 'demand': 3.0, 'x': 200, 'y': 0},
        ],
        reservoirs=[{'id': 'R1', 'head': 100, 'x': -200, 'y': 0}],
        pipes=[
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
             'diameter': 300, 'roughness': 130},
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 400,
             'diameter': 250, 'roughness': 130},
        ],
    )
    return api


class TestBladderAccumulator:

    def test_basic_sizing(self, api):
        result = api.size_bladder_accumulator(
            max_surge_kPa=5000, operating_pressure_kPa=2000)
        assert result['total_volume_m3'] > 0
        assert result['precharge_kPa'] > 0
        assert 'Boyle' in result['basis']

    def test_precharge_fraction(self, api):
        result = api.size_bladder_accumulator(
            max_surge_kPa=4000, operating_pressure_kPa=2000, precharge_pct=0.9)
        assert result['precharge_kPa'] == pytest.approx(1800, abs=1)

    def test_invalid_pressures(self, api):
        result = api.size_bladder_accumulator(
            max_surge_kPa=1000, operating_pressure_kPa=0)
        assert 'error' in result


class TestFlywheelSizing:

    def test_basic_sizing(self, api):
        result = api.size_flywheel(pump_power_kW=75, required_rundown_s=5.0)
        assert result['moment_of_inertia_kgm2'] > 0
        assert result['flywheel_mass_kg'] > 0
        assert 'Thorley' in result['basis']

    def test_higher_power_larger_flywheel(self, api):
        r1 = api.size_flywheel(pump_power_kW=30)
        r2 = api.size_flywheel(pump_power_kW=75)
        assert r2['flywheel_mass_kg'] > r1['flywheel_mass_kg']

    def test_longer_rundown_larger_flywheel(self, api):
        r1 = api.size_flywheel(pump_power_kW=75, required_rundown_s=3)
        r2 = api.size_flywheel(pump_power_kW=75, required_rundown_s=10)
        assert r2['moment_of_inertia_kgm2'] > r1['moment_of_inertia_kgm2']


class TestMonteCarlo:

    def test_basic_run(self, api):
        result = api.monte_carlo_analysis(n_simulations=10, seed=42)
        assert result['n_simulations'] == 10
        assert result['n_successful'] > 0
        assert len(result['node_stats']) > 0

    def test_mean_converges(self, api):
        """Mean pressure should be close to deterministic value."""
        # Deterministic run
        det = api.run_steady_state(save_plot=False)
        det_p = det['pressures']['J1']['avg_m']

        # Monte Carlo with small variation
        mc = api.monte_carlo_analysis(n_simulations=20, roughness_cv=0.05,
                                       demand_cv=0.05, seed=42)
        mc_p = mc['node_stats']['J1']['mean_m']
        # Should be within 5 m of deterministic
        assert abs(mc_p - det_p) < 5.0

    def test_failure_probability_range(self, api):
        result = api.monte_carlo_analysis(n_simulations=10, seed=42)
        for jid, stats in result['node_stats'].items():
            assert 0 <= stats['failure_probability'] <= 1

    def test_std_positive(self, api):
        result = api.monte_carlo_analysis(n_simulations=20, seed=42)
        for jid, stats in result['node_stats'].items():
            assert stats['std_m'] >= 0

    def test_percentiles_ordered(self, api):
        result = api.monte_carlo_analysis(n_simulations=20, seed=42)
        for jid, stats in result['node_stats'].items():
            assert stats['p5_m'] <= stats['mean_m'] <= stats['p95_m']

    def test_demands_restored(self, api):
        """Original demands should be restored after MC."""
        original = {}
        for jid in api.wn.junction_name_list:
            j = api.wn.get_node(jid)
            if j.demand_timeseries_list:
                original[jid] = j.demand_timeseries_list[0].base_value

        api.monte_carlo_analysis(n_simulations=5, seed=42)

        for jid, d in original.items():
            current = api.wn.get_node(jid).demand_timeseries_list[0].base_value
            assert abs(current - d) < 1e-6

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.monte_carlo_analysis()
        assert 'error' in result

"""
Knowledge Base Fidelity Tests (v2.2.1 hardening)
=================================================
Verify O9 Knowledge Base formulas match the active solver outputs to within ±2%.
This prevents the KB from drifting away from the actual implementations.
"""

import math
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestHazenWilliamsFidelity:
    """KB HW formula must match WNTR solver ±2% for a known case."""

    def test_single_pipe_hw(self):
        # Known case: DN200 pipe, L=1000m, Q=25 LPS (0.025 m³/s), C=130
        # KB formula: hL = 10.67 × L × Q^1.852 / (C^1.852 × D^4.87)
        L = 1000.0
        Q = 0.025
        D = 0.200
        C = 130.0
        hl_kb = 10.67 * L * Q**1.852 / (C**1.852 * D**4.87)

        # Build network with only this pipe and solve
        api = HydraulicAPI()
        api.create_network(
            name='hw_fidelity',
            junctions=[{'id': 'J1', 'elevation': 0,
                        'demand': 25, 'x': 1000, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 100, 'x': 0, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1',
                     'length': L, 'diameter': 200, 'roughness': C}],
        )
        results = api.run_steady_state(save_plot=False)
        # Headloss = reservoir head - (junction pressure + elevation)
        # Reservoir head 100, J1 elevation 0, so hl = 100 - P_J1
        p_j1 = results['pressures']['J1']['avg_m']
        hl_solver = 100.0 - p_j1

        pct_diff = abs(hl_solver - hl_kb) / hl_kb * 100
        assert pct_diff < 2.0, (
            f'KB HW ({hl_kb:.2f}m) vs solver ({hl_solver:.2f}m): '
            f'{pct_diff:.2f}% diff exceeds 2%')


class TestJoukowskyFidelity:
    """KB Joukowsky formula must match api.joukowsky() method."""

    def test_joukowsky_point(self):
        api = HydraulicAPI()
        # KB: ΔP = ρ × a × ΔV
        a = 1100  # m/s
        dV = 1.0  # m/s
        rho = 1000
        dp_kb_pa = rho * a * dV
        dp_kb_m = dp_kb_pa / (rho * 9.81)  # convert to m head

        # api.joukowsky(wave_speed, velocity_change) returns dict
        result = api.joukowsky(a, dV)
        # Result may be in Pa, kPa or m head — compare by the 'surge_pressure_m' key
        surge_m = result.get('head_rise_m')
        assert surge_m is not None, f'joukowsky() returned: {result}'
        pct_diff = abs(surge_m - dp_kb_m) / dp_kb_m * 100
        assert pct_diff < 2.0


class TestWSAAThresholdFidelity:
    """KB WSAA thresholds must match HydraulicAPI.DEFAULTS."""

    def test_min_pressure_matches(self):
        api = HydraulicAPI()
        kb = api.knowledge_base('wsaa_min_pressure')
        # Extract '20' from e.g. '20 m head'
        kb_val = int(kb['value'].split()[0])
        assert kb_val == api.DEFAULTS['min_pressure_m']

    def test_max_pressure_matches(self):
        api = HydraulicAPI()
        kb = api.knowledge_base('wsaa_max_pressure')
        # First number in '50 m head (residential)...'
        kb_val = int(kb['value'].split()[0])
        assert kb_val == api.DEFAULTS['max_pressure_m']

    def test_max_velocity_matches(self):
        api = HydraulicAPI()
        kb = api.knowledge_base('wsaa_max_velocity')
        kb_val = float(kb['value'].split()[0])
        assert abs(kb_val - api.DEFAULTS['max_velocity_ms']) < 0.01


class TestBinghamPlasticFidelity:
    """KB slurry friction factor formula must be Darcy (64/Re_B), not Fanning."""

    def test_kb_states_darcy_not_fanning(self):
        api = HydraulicAPI()
        kb = api.knowledge_base('bingham_plastic')
        # Must explicitly warn against Fanning 16/Re_B
        assert '64/Re_B' in kb['laminar_friction']
        assert 'NEVER' in kb['laminar_friction'] or \
               'Fanning' in kb['laminar_friction']


class TestClimateScenarioMetadata:
    """O2 climate scenarios must cite CSIRO/IPCC sources."""

    def test_all_scenarios_have_metadata(self):
        api = HydraulicAPI()
        api.create_network(
            name='climate_meta',
            junctions=[{'id': 'J1', 'elevation': 10, 'demand': 1,
                        'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1',
                     'length': 100, 'diameter': 150, 'roughness': 130}],
        )
        for scenario in ('low', 'medium', 'high'):
            r = api.climate_demand_projection(
                target_years=[2050], climate_scenario=scenario)
            meta = r['scenario_metadata']
            assert 'rcp' in meta
            assert 'warming_2100_c' in meta
            assert 'doi' in meta
            assert meta['doi']  # non-empty

    def test_rcp_warming_ordered(self):
        api = HydraulicAPI()
        api.create_network(
            name='rcp_order',
            junctions=[{'id': 'J1', 'elevation': 10, 'demand': 1,
                        'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1',
                     'length': 100, 'diameter': 150, 'roughness': 130}],
        )
        r = api.climate_demand_projection(
            target_years=[2050], climate_scenario='low')
        all_meta = r['all_scenarios_metadata']
        low_w = all_meta['low']['warming_2100_c']
        med_w = all_meta['medium']['warming_2100_c']
        high_w = all_meta['high']['warming_2100_c']
        assert low_w < med_w < high_w


class TestLamontConfidenceIntervals:
    """O7 Lamont forecast must return 95% CI and caveats."""

    def test_forecast_has_confidence_intervals(self):
        api = HydraulicAPI()
        api.create_network(
            name='lamont_ci',
            junctions=[{'id': 'J1', 'elevation': 10, 'demand': 1,
                        'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1',
                     'length': 1000, 'diameter': 150, 'roughness': 90}],
        )
        r = api.lamont_break_forecast(forecast_years=[2050])
        # Must have caveats
        assert 'caveats' in r
        assert len(r['caveats']) >= 3
        assert 'confidence_interval_assumption' in r

        # Must have per-pipe CI
        pipe_forecast = r['pipe_forecasts'][0]['forecasts'][2050]
        assert 'break_rate_lower_95ci' in pipe_forecast
        assert 'break_rate_upper_95ci' in pipe_forecast
        # Bounds must bracket the point estimate
        point = pipe_forecast['break_rate_per_km_yr']
        lo = pipe_forecast['break_rate_lower_95ci']
        hi = pipe_forecast['break_rate_upper_95ci']
        assert lo <= point <= hi

    def test_caveats_mention_liability(self):
        api = HydraulicAPI()
        api.create_network(
            name='lamont_caveats',
            junctions=[{'id': 'J1', 'elevation': 10, 'demand': 1,
                        'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1',
                     'length': 100, 'diameter': 150, 'roughness': 130}],
        )
        r = api.lamont_break_forecast()
        caveat_text = ' '.join(r['caveats']).lower()
        assert ('not' in caveat_text and
                ('sole' in caveat_text or 'basis' in caveat_text))

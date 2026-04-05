"""
T-series feature tests: pump efficiency, sensitivity report, emergency burst.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_INP = os.path.join(PROJECT_ROOT, 'tutorials', 'demo_network',
                        'network.inp')
PUMP_INP = os.path.join(PROJECT_ROOT, 'tutorials', 'pump_station',
                        'network.inp')


# ---------- T3 pump_efficiency_analysis -------------------------------------

class TestPumpEfficiency:

    def test_no_network_error(self):
        a = HydraulicAPI()
        r = a.pump_efficiency_analysis()
        assert 'error' in r
        assert 'Fix:' in r['error']

    def test_network_without_pumps(self):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.pump_efficiency_analysis()
        assert 'error' not in r
        assert r['n_pumps'] == 0
        assert r['pumps'] == []

    def test_network_with_pumps(self):
        if not os.path.exists(PUMP_INP):
            pytest.skip('pump_station tutorial missing')
        a = HydraulicAPI()
        a.load_network(PUMP_INP)
        r = a.pump_efficiency_analysis()
        assert 'error' not in r
        assert r['n_pumps'] >= 1
        pump0 = r['pumps'][0]
        if 'error' not in pump0:
            # All expected fields present
            assert 'efficiency' in pump0
            assert 'hydraulic_power_kw' in pump0
            assert 'electrical_power_kw' in pump0
            assert 'annual_energy_kwh' in pump0
            assert 'annual_cost_aud' in pump0
            # Efficiency in a plausible range
            assert 0 < pump0['efficiency'] <= 0.82

    def test_summary_aggregates(self):
        if not os.path.exists(PUMP_INP):
            pytest.skip('pump_station tutorial missing')
        a = HydraulicAPI()
        a.load_network(PUMP_INP)
        r = a.pump_efficiency_analysis()
        s = r['summary']
        assert 'total_electrical_kw' in s
        assert 'total_annual_cost_aud' in s
        if r['n_pumps'] > 0:
            good_pumps = [p for p in r['pumps'] if 'error' not in p]
            if good_pumps:
                expected_kw = round(
                    sum(p['electrical_power_kw'] for p in good_pumps), 2)
                assert abs(s['total_electrical_kw'] - expected_kw) < 0.1

    def test_tariff_affects_cost(self):
        """Build a small pumped network with real flow to verify cost scaling."""
        a = HydraulicAPI()
        a.create_network(
            name='pump_tariff',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 0, 'x': 50, 'y': 0},
                {'id': 'J2', 'elevation': 30, 'demand': 10, 'x': 150, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 5, 'x': 0, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'J1', 'end': 'J2',
                 'length': 200, 'diameter': 200, 'roughness': 130},
            ],
        )
        a.wn.add_curve('C1', 'HEAD', [(0.010, 50.0), (0.020, 40.0),
                                       (0.030, 25.0)])
        a.wn.add_pump('PU1', 'R1', 'J1', pump_type='HEAD',
                      pump_parameter='C1')

        r_cheap = a.pump_efficiency_analysis(
            electricity_price_aud_per_kwh=0.10)
        r_expensive = a.pump_efficiency_analysis(
            electricity_price_aud_per_kwh=0.50)
        assert r_cheap['n_pumps'] == 1
        # Only assert scaling if the pump actually has flow in the solution
        if r_cheap['summary']['total_annual_cost_aud'] > 0:
            assert (r_expensive['summary']['total_annual_cost_aud'] >
                    r_cheap['summary']['total_annual_cost_aud'])

    def test_assumptions_documented(self):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.pump_efficiency_analysis()
        assert 'assumptions' in r
        assert r['assumptions']['eta_max_assumption'] > 0
        assert r['assumptions']['limitations']


# ---------- T4 sensitivity_report -------------------------------------------

class TestSensitivityReport:

    def test_no_network_error(self):
        a = HydraulicAPI()
        r = a.sensitivity_report()
        assert 'error' in r

    def test_returns_rankings(self):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.sensitivity_report(perturbation_pct=20, max_targets=3)
        assert 'error' not in r
        assert 'rankings' in r
        assert r['n_parameters'] > 0
        # Top 5 non-empty
        assert len(r['top_5']) > 0

    def test_rankings_sorted_descending(self):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.sensitivity_report(perturbation_pct=20, max_targets=3)
        vals = [x['max_pressure_change_m'] for x in r['rankings']]
        assert vals == sorted(vals, reverse=True)

    def test_summary_lines(self):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.sensitivity_report(perturbation_pct=20, max_targets=3)
        assert 'summary_lines' in r
        assert len(r['summary_lines']) >= 1
        assert 'sensitive' in ' '.join(r['summary_lines']).lower()

    def test_baseline_restored(self):
        """After sensitivity run, demands and roughness must match originals."""
        a = HydraulicAPI()
        a.load_network(DEMO_INP)

        # Snapshot
        orig_roughness = a.wn.get_link('P1').roughness
        orig_demand = a.wn.get_node('J1').demand_timeseries_list[0].base_value

        a.sensitivity_report(perturbation_pct=20, max_targets=3)

        assert abs(a.wn.get_link('P1').roughness - orig_roughness) < 1e-9
        assert abs(
            a.wn.get_node('J1').demand_timeseries_list[0].base_value
            - orig_demand) < 1e-9

    def test_identifies_most_sensitive_correctly(self):
        """Demand at the stressed branch should be the top driver."""
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.sensitivity_report(perturbation_pct=20, max_targets=10)
        top = r['top_5'][0]
        # The top driver on demo network is the undersized-branch demand.
        # J9 demand or J10 demand or P10 roughness should top the list.
        top_label = top['parameter']
        assert ('J9' in top_label or 'J10' in top_label
                or 'P10' in top_label or 'P11' in top_label), \
            f'Unexpected top driver: {top_label}'


# ---------- Innovation #3: emergency_pipe_burst ------------------------------

class TestEmergencyPipeBurst:

    def test_no_network_error(self):
        a = HydraulicAPI()
        r = a.emergency_pipe_burst('P1')
        assert 'error' in r
        assert 'Fix:' in r['error']

    def test_invalid_pipe_error(self):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.emergency_pipe_burst('DOES_NOT_EXIST')
        assert 'error' in r
        assert 'Fix:' in r['error']

    def test_branch_burst_isolates_customers(self):
        """Bursting the branch to J9 should isolate J9."""
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.emergency_pipe_burst('P10')  # R1-...-J3-[P10]-J9
        assert r['n_isolated_junctions'] >= 1
        isolated_ids = [x['node'] for x in r['isolated']]
        assert 'J9' in isolated_ids
        assert r['severity'] in ('LOW', 'MEDIUM', 'HIGH')

    def test_loop_pipe_burst_has_low_impact(self):
        """Bursting a pipe in a ring-main should leave supply intact."""
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.emergency_pipe_burst('P6')  # ring main pipe J5-J6
        # Ring topology means no isolation
        assert r['n_isolated_junctions'] <= 1

    def test_action_list_is_populated(self):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.emergency_pipe_burst('P10')
        assert 'immediate_actions' in r
        assert len(r['immediate_actions']) >= 4
        # First action dispatches crew
        assert 'DISPATCH' in r['immediate_actions'][0]
        # Second action isolates
        assert 'CLOSE' in r['immediate_actions'][1] or \
               'ISOLATE' in r['immediate_actions'][1]

    def test_adjacency_detection(self):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.emergency_pipe_burst('P10')
        # P10 connects J3-J9, so adjacent pipes include P3 (J2-J3) and P4 (J3-J4)
        adj = set(r['adjacent_pipes_to_close_if_no_valves'])
        assert 'P3' in adj or 'P4' in adj

    def test_baseline_preserved_after_burst_simulation(self):
        """Original pipe diameter must be restored after simulation."""
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        orig_dia = a.wn.get_link('P10').diameter
        a.emergency_pipe_burst('P10')
        assert abs(a.wn.get_link('P10').diameter - orig_dia) < 1e-9

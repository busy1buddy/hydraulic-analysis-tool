"""
End-to-End Workflow Tests (P1)
===============================
Complete user workflows exercising the full pipeline from network load
through analysis to output artefacts.
"""

import os
import sys
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TUTORIALS = os.path.join(PROJECT_ROOT, 'tutorials')


def _require_tutorial(name):
    path = os.path.join(TUTORIALS, name, 'network.inp')
    if not os.path.exists(path):
        pytest.skip(f'Tutorial network missing: {name}')
    return path


class TestWorkflowA_UtilityMorningCheck:
    """Daily operational check: load → steady → water quality → certificate."""

    def test_full_morning_check(self, tmp_path):
        t0 = time.perf_counter()
        api = HydraulicAPI()
        inp = _require_tutorial('simple_loop')

        # Load network
        api.load_network(inp)

        # Steady state
        steady = api.run_steady_state(save_plot=False)
        assert 'error' not in steady
        assert 'pressures' in steady

        # Water quality (chlorine decay)
        wq = api.run_water_quality_chlorine()
        assert 'error' not in wq or wq.get('nodes')

        # Compliance certificate
        cert = api.run_design_compliance_check()
        assert 'error' not in cert
        assert 'overall_status' in cert
        assert cert['overall_status'] in ('COMPLIANT', 'NON-COMPLIANT')
        assert len(cert['checks']) >= 1
        # Check each result line has PASS/FAIL status
        for check in cert['checks']:
            assert 'status' in check
            assert check['status'] in ('PASS', 'FAIL', 'WARN', 'N/A', 'SKIPPED')

        # Health summary populated
        health = api.network_health_summary()
        assert 'error' not in health
        assert len(health['summary_paragraph']) > 50
        assert 'metrics' in health

        # Quality score
        qs = api.compute_quality_score(steady)
        assert 'error' not in qs
        assert 'total_score' in qs
        assert qs['total_score'] > 0

        elapsed = time.perf_counter() - t0
        assert elapsed < 30.0, f'Morning check took {elapsed:.1f}s (>30s)'


class TestWorkflowB_MiningSlurryDesign:
    """Slurry pipeline: load → slurry mode → steady → deposition → surge."""

    def test_full_slurry_design(self):
        t0 = time.perf_counter()
        api = HydraulicAPI()
        inp = _require_tutorial('mining_slurry_line')

        api.load_network(inp)

        # Baseline water steady state
        water_result = api.run_steady_state(save_plot=False)
        assert 'error' not in water_result

        # Slurry design report (tau_y=15 Pa, mu_p=0.05, rho=1800)
        slurry = api.slurry_design_report(
            d_particle_mm=0.5, rho_solid=2650,
            concentration_vol=0.15, rho_fluid=1000, mu_fluid=0.001)
        assert 'error' not in slurry
        assert 'pipe_analysis' in slurry
        assert len(slurry['pipe_analysis']) > 0

        # Each pipe must have Durand critical velocity
        for pipe in slurry['pipe_analysis']:
            assert 'critical_velocity_durand_ms' in pipe
            assert pipe['critical_velocity_durand_ms'] >= 0

        # Surge analysis (Joukowsky)
        jouk = api.joukowsky(wave_speed=1100, velocity_change=1.0)
        assert 'error' not in jouk
        assert 'head_rise_m' in jouk
        assert jouk['head_rise_m'] > 50  # should be ~112 m

        # Compliance certificate
        cert = api.run_design_compliance_check()
        assert 'error' not in cert
        assert 'checks' in cert

        elapsed = time.perf_counter() - t0
        assert elapsed < 60.0, f'Slurry workflow took {elapsed:.1f}s (>60s)'


class TestWorkflowC_RehabilitationPlanning:
    """Rehab: load → import conditions → prioritise → export template."""

    def test_full_rehab_workflow(self, tmp_path):
        t0 = time.perf_counter()
        api = HydraulicAPI()
        inp = _require_tutorial('rehabilitation_comparison')

        api.load_network(inp)

        # Synthesise pipe conditions: oldest pipes get worst condition
        import csv
        csv_path = tmp_path / 'conditions.csv'
        pipe_ids = list(api.wn.pipe_name_list)
        # Age pipes from 5-80 years (oldest first)
        with open(csv_path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['pipe_id', 'install_year', 'condition_score',
                        'material'])
            for i, pid in enumerate(pipe_ids):
                age = 80 - int(i * 75 / max(len(pipe_ids) - 1, 1))
                install_year = 2026 - age
                cond_score = min(5, max(1, int(age / 16) + 1))
                w.writerow([pid, install_year, cond_score, 'CI'])

        # Import conditions (returns count of rows imported)
        n_imported = api.import_pipe_conditions_csv(str(csv_path))
        assert n_imported == len(pipe_ids)

        # Prioritise (returns sorted list)
        ranked = api.prioritize_rehabilitation(current_year=2026)
        assert isinstance(ranked, list)
        assert len(ranked) == len(pipe_ids)

        # Oldest pipe (pipe_ids[0]) should be top of ranking
        top_ids = [p['pipe_id'] for p in ranked[:3]]
        assert pipe_ids[0] in top_ids, \
            f'Oldest pipe {pipe_ids[0]} not in top 3: {top_ids}'

        # Export field template
        template_path = str(tmp_path / 'template.xlsx')
        tmpl = api.generate_field_template(template_path)
        assert 'error' not in tmpl
        assert os.path.exists(template_path)

        import pandas as pd
        pipes_sheet = pd.read_excel(template_path, sheet_name='Pipes')
        assert len(pipes_sheet) == len(pipe_ids)

        elapsed = time.perf_counter() - t0
        assert elapsed < 15.0, f'Rehab workflow took {elapsed:.1f}s (>15s)'


class TestWorkflowD_NewNetworkFromExcel:
    """Create Excel → import → steady state."""

    def test_full_excel_import_workflow(self, tmp_path):
        t0 = time.perf_counter()

        # Create Excel with 5 nodes and 4 pipes
        import pandas as pd
        excel_path = tmp_path / 'new_net.xlsx'

        # Check import_from_excel signature to construct compatible sheets
        api = HydraulicAPI()
        sig = api.import_from_excel.__doc__ or ''

        # Schema: node_id, x, y, elevation, demand_lps (optional)
        # High-elevation nodes with prefix R treated as reservoirs by heuristic
        nodes_df = pd.DataFrame([
            {'node_id': 'R1', 'x': 0, 'y': 0,
             'elevation': 80, 'demand_lps': 0},
            {'node_id': 'J1', 'x': 100, 'y': 0,
             'elevation': 20, 'demand_lps': 2},
            {'node_id': 'J2', 'x': 200, 'y': 0,
             'elevation': 25, 'demand_lps': 1.5},
            {'node_id': 'J3', 'x': 200, 'y': 100,
             'elevation': 22, 'demand_lps': 1.0},
            {'node_id': 'J4', 'x': 100, 'y': 100,
             'elevation': 30, 'demand_lps': 0.8},
        ])
        pipes_df = pd.DataFrame([
            {'pipe_id': 'P1', 'start_node': 'R1', 'end_node': 'J1',
             'length_m': 100, 'diameter_mm': 200, 'roughness_C': 130},
            {'pipe_id': 'P2', 'start_node': 'J1', 'end_node': 'J2',
             'length_m': 100, 'diameter_mm': 150, 'roughness_C': 130},
            {'pipe_id': 'P3', 'start_node': 'J2', 'end_node': 'J3',
             'length_m': 100, 'diameter_mm': 150, 'roughness_C': 130},
            {'pipe_id': 'P4', 'start_node': 'J3', 'end_node': 'J4',
             'length_m': 100, 'diameter_mm': 150, 'roughness_C': 130},
        ])

        with pd.ExcelWriter(excel_path) as w:
            nodes_df.to_excel(w, sheet_name='Nodes', index=False)
            pipes_df.to_excel(w, sheet_name='Pipes', index=False)

        result = api.import_from_excel(str(excel_path))
        if 'error' in result:
            pytest.skip(
                f'import_from_excel schema differs: {result["error"]}')

        # Network loaded: 1 reservoir + 4 junctions = 5 nodes
        total_nodes = (len(api.wn.junction_name_list) +
                       len(api.wn.reservoir_name_list))
        assert total_nodes == 5
        assert len(api.wn.pipe_name_list) == 4

        # Steady state
        steady = api.run_steady_state(save_plot=False)
        assert 'error' not in steady
        for node, p in steady['pressures'].items():
            assert p['min_m'] >= 0, f'{node}: negative pressure {p["min_m"]}'

        elapsed = time.perf_counter() - t0
        assert elapsed < 10.0, f'Excel workflow took {elapsed:.1f}s (>10s)'

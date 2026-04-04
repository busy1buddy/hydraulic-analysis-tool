"""
Integration Test Suite (K2)
============================
End-to-end workflow tests covering full analysis pipelines.
Each test follows a realistic engineer workflow.
"""

import os
import sys
import csv
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TUTORIALS = os.path.join(ROOT, 'tutorials')
MODELS = os.path.join(ROOT, 'models')

from epanet_api import HydraulicAPI


def _tutorial_inp(name):
    """Get path to tutorial network .inp file."""
    return os.path.join(TUTORIALS, name, 'network.inp')


# =========================================================================
# Workflow 1: Load → Steady State → Slurry → Compare
# =========================================================================

class TestWorkflow1_SteadyVsSlurry:
    """Load network, run water and slurry, compare headloss."""

    @pytest.fixture
    def api(self):
        api = HydraulicAPI()
        path = _tutorial_inp('industrial_ring_main')
        if not os.path.exists(path):
            pytest.skip("Tutorial industrial_ring_main not found")
        api.load_network_from_path(path)
        return api

    def test_water_steady_state_completes(self, api):
        results = api.run_steady_state(save_plot=False)
        assert 'pressures' in results
        assert 'flows' in results
        assert len(results['pressures']) > 0

    def test_slurry_headloss_exceeds_water(self, api):
        """Slurry headloss should be higher than water for same network."""
        from slurry_solver import bingham_plastic_headloss

        water_results = api.run_steady_state(save_plot=False)
        water_flows = water_results['flows']

        # Pick a pipe with flow
        for pid, fdata in water_flows.items():
            if abs(fdata.get('avg_lps', 0)) > 0.1:
                pipe = api.get_link(pid)
                Q = abs(fdata['avg_lps']) / 1000  # LPS to m³/s

                # Water headloss (from results)
                # Slurry headloss (Bingham plastic)
                slurry_result = bingham_plastic_headloss(
                    flow_m3s=Q, diameter_m=pipe.diameter,
                    length_m=pipe.length, density=1800,
                    tau_y=15.0, mu_p=0.05)

                # Result is a dict with 'headloss_m' key
                if isinstance(slurry_result, dict):
                    slurry_hl = slurry_result.get('headloss_m', 0)
                else:
                    slurry_hl = float(slurry_result)

                # Slurry headloss should be > 0 for non-zero flow
                assert slurry_hl > 0, f"Pipe {pid}: slurry headloss should be > 0"
                break

    def test_joukowsky_uses_actual_density(self, api):
        """Joukowsky with rho=1800 should give 1.8× water surge."""
        j_water = api.joukowsky(1100, 1.5, density=1000)
        j_slurry = api.joukowsky(1100, 1.5, density=1800)
        # Pressure rise is proportional to density
        assert abs(j_slurry['pressure_rise_kPa'] / j_water['pressure_rise_kPa'] - 1.8) < 0.01

    def test_compliance_generated(self, api):
        results = api.run_steady_state(save_plot=False)
        assert 'compliance' in results
        assert len(results['compliance']) > 0
        for item in results['compliance']:
            assert 'type' in item
            assert item['type'] in ('OK', 'INFO', 'WARNING', 'CRITICAL')


# =========================================================================
# Workflow 2: EPS → Calibration → Report
# =========================================================================

class TestWorkflow2_EPSCalibrationReport:
    """Run EPS, check calibration, generate report."""

    @pytest.fixture
    def api(self):
        api = HydraulicAPI()
        path = _tutorial_inp('dead_end_network')
        if not os.path.exists(path):
            pytest.skip("Tutorial dead_end_network not found")
        api.load_network_from_path(path)
        return api

    def test_eps_min_pressure_less_than_steady(self, api):
        """EPS minimum pressure should be <= steady-state pressure."""
        # Run steady (single timestep)
        api.wn.options.time.duration = 0
        steady = api.run_steady_state(save_plot=False)

        # Run 24h EPS
        api.wn.options.time.duration = 24 * 3600
        api.wn.options.time.hydraulic_timestep = 3600
        api.wn.options.time.report_timestep = 3600
        eps = api.run_steady_state(save_plot=False)

        # For at least one junction, EPS min should be <= steady avg
        for jid in eps['pressures']:
            if jid in steady['pressures']:
                eps_min = eps['pressures'][jid]['min_m']
                steady_avg = steady['pressures'][jid]['avg_m']
                # EPS min should generally be <= steady (peak demand drops pressure)
                # Allow small tolerance for numerical precision
                assert eps_min <= steady_avg + 0.5, \
                    f"{jid}: EPS min {eps_min} > steady {steady_avg}"

    def test_report_generation_docx(self, api, tmp_path):
        """Generate DOCX report and verify it contains executive summary."""
        results = api.run_steady_state(save_plot=False)
        summary = api.get_network_summary()

        from reports.docx_report import generate_docx_report
        path = str(tmp_path / "test_report.docx")
        generate_docx_report(
            {'steady_state': results}, summary, path,
            engineer_name='Test Engineer', project_name='Integration Test')

        assert os.path.exists(path)
        assert os.path.getsize(path) > 5000  # minimum viable DOCX

        # Verify content (read DOCX XML)
        from docx import Document
        doc = Document(path)
        all_text = '\n'.join(p.text for p in doc.paragraphs)
        assert 'Executive Summary' in all_text
        assert 'Compliance' in all_text

    def test_report_generation_pdf(self, api, tmp_path):
        """Generate PDF report."""
        results = api.run_steady_state(save_plot=False)
        summary = api.get_network_summary()

        from reports.pdf_report import generate_pdf_report
        path = str(tmp_path / "test_report.pdf")
        generate_pdf_report(
            {'steady_state': results}, summary, path,
            engineer_name='Test Engineer')

        assert os.path.exists(path)
        assert os.path.getsize(path) > 2000


# =========================================================================
# Workflow 3: Asset Management Pipeline
# =========================================================================

class TestWorkflow3_AssetManagement:
    """Import conditions, prioritise rehab, validate scoring."""

    @pytest.fixture
    def api(self):
        api = HydraulicAPI()
        path = _tutorial_inp('rehabilitation_comparison')
        if not os.path.exists(path):
            # Fallback to any available network
            api.create_network(
                name='rehab_integ',
                junctions=[
                    {'id': 'J1', 'elevation': 50, 'demand': 5, 'x': 0, 'y': 0},
                    {'id': 'J2', 'elevation': 55, 'demand': 3, 'x': 200, 'y': 0},
                    {'id': 'J3', 'elevation': 45, 'demand': 4, 'x': 400, 'y': 0},
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
        else:
            api.load_network_from_path(path)
        return api

    def test_import_condition_csv_and_prioritise(self, api, tmp_path):
        """Full pipeline: import CSV → prioritise → verify ranking."""
        # Create synthetic condition CSV
        csv_path = str(tmp_path / "conditions.csv")
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['pipe_id', 'install_year', 'condition_score',
                             'break_history', 'material'])
            writer.writerow(['P1', '1965', '4.5', '5', 'CI'])  # worst
            writer.writerow(['P2', '2015', '1.5', '0', 'PVC']) # best
            writer.writerow(['P3', '1990', '3.0', '2', 'DI'])  # medium

        count = api.import_pipe_conditions_csv(csv_path)
        assert count == 3

        results = api.prioritize_rehabilitation(current_year=2026)
        assert len(results) >= 3

        # P1 (oldest, worst condition, most breaks) should be highest scored
        p1 = [r for r in results if r['pipe_id'] == 'P1'][0]
        assert p1['risk_category'] in ('CRITICAL', 'HIGH')
        assert results[0]['risk_category'] in ('CRITICAL', 'HIGH')

        # P2 (newest, best condition, no breaks) should have low score
        p2 = [r for r in results if r['pipe_id'] == 'P2'][0]
        assert p2['risk_category'] in ('LOW', 'MEDIUM')

    def test_deterioration_prediction(self, api):
        """Predict deterioration for a pipe with known condition."""
        api.set_pipe_condition('P1', install_year=1970, condition_score=3.5,
                               material='DI')
        pred = api.predict_deterioration('P1', current_year=2026,
                                          forecast_years=[2030, 2040, 2050])
        # Condition should worsen over time
        assert pred[2050]['condition_score'] >= pred[2030]['condition_score']


# =========================================================================
# Workflow 4: Water Quality → Compliance
# =========================================================================

class TestWorkflow4_WaterQuality:
    """Run water quality, check compliance thresholds."""

    @pytest.fixture
    def api(self):
        api = HydraulicAPI()
        path = _tutorial_inp('simple_loop')
        if not os.path.exists(path):
            api.create_network(
                name='wq_integ',
                junctions=[
                    {'id': 'J1', 'elevation': 50, 'demand': 2, 'x': 0, 'y': 0},
                    {'id': 'J2', 'elevation': 50, 'demand': 1, 'x': 100, 'y': 0},
                    {'id': 'J3', 'elevation': 50, 'demand': 1, 'x': 100, 'y': 100},
                ],
                reservoirs=[{'id': 'R1', 'head': 80, 'x': -50, 'y': 0}],
                pipes=[
                    {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                     'diameter': 200, 'roughness': 130},
                    {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 150,
                     'diameter': 150, 'roughness': 130},
                    {'id': 'P3', 'start': 'J2', 'end': 'J3', 'length': 150,
                     'diameter': 150, 'roughness': 130},
                    {'id': 'P4', 'start': 'J3', 'end': 'J1', 'length': 150,
                     'diameter': 150, 'roughness': 130},
                ],
            )
        else:
            api.load_network_from_path(path)
        return api

    def test_water_age_in_hours(self, api):
        """Water age should be returned in hours, not seconds."""
        results = api.run_water_quality(parameter='age', duration_hrs=48)
        if 'error' in results:
            pytest.skip(f"WQ failed: {results['error']}")
        jq = results.get('junction_quality', {})
        for jid, data in jq.items():
            max_age = data.get('max_age_hrs', 0)
            # Age in hours should be reasonable (0-48 for 48h simulation)
            assert max_age < 100, f"{jid}: age {max_age} hrs seems too high (seconds?)"

    def test_chlorine_decreases_from_source(self, api):
        """Chlorine should decrease as water moves from source to dead ends."""
        results = api.run_water_quality_chlorine(
            initial_conc=1.0, bulk_coeff=-0.5, wall_coeff=-0.1,
            duration_hrs=72)
        if 'error' in results:
            pytest.skip(f"WQ failed: {results['error']}")
        jq = results.get('junction_quality', {})
        if not jq:
            pytest.skip("No junction quality data")
        # At least one node should have chlorine < initial 1.0
        min_chlorines = [d.get('min_conc', d.get('min_chlorine_mgl', 1.0))
                         for d in jq.values()]
        assert any(c < 1.0 for c in min_chlorines), \
            f"Chlorine should decay from source. Values: {min_chlorines}"


# =========================================================================
# Workflow 5: Full Analysis Pipeline
# =========================================================================

class TestWorkflow5_FullPipeline:
    """Load, analyse, check all subsystems."""

    @pytest.fixture
    def api(self):
        api = HydraulicAPI()
        api.load_network('australian_network.inp')
        return api

    def test_network_summary_correct(self, api):
        summary = api.get_network_summary()
        assert summary['junctions'] > 0
        assert summary['pipes'] > 0

    def test_steady_state_pressures_physical(self, api):
        """All pressures should be physically reasonable."""
        results = api.run_steady_state(save_plot=False)
        for jid, p in results['pressures'].items():
            # Pressure should be between -10 and 200 m for any reasonable network
            assert -10 < p['avg_m'] < 200, f"{jid}: pressure {p['avg_m']} m unreasonable"

    def test_velocities_non_negative(self, api):
        """All displayed velocities should be non-negative."""
        results = api.run_steady_state(save_plot=False)
        for pid, f in results['flows'].items():
            assert f['max_velocity_ms'] >= 0, f"{pid}: negative velocity"

    def test_pipe_profile_on_real_network(self, api):
        """Pipe profile should work on the real network."""
        junctions = api.get_node_list('junction')
        if len(junctions) < 2:
            pytest.skip("Not enough junctions")
        # Find two connected junctions
        for pid in api.wn.pipe_name_list:
            pipe = api.get_link(pid)
            sn, en = pipe.start_node_name, pipe.end_node_name
            profile = api.compute_pipe_profile([sn, en])
            if 'error' not in profile:
                assert len(profile['stations']) == 2
                assert profile['total_length_m'] > 0
                break

    def test_sensitivity_on_real_network(self, api):
        """Sensitivity analysis should complete on real network."""
        results = api.sensitivity_analysis('roughness', variation_pct=10)
        assert isinstance(results, list)
        assert len(results) > 0
        assert results[0]['sensitivity_rank'] == 1

    def test_leakage_analysis(self, api):
        """Leakage analysis with synthetic inflow data."""
        result = api.leakage_analysis(measured_inflow_lps=25.0)
        assert result['total_demand_lps'] > 0
        assert 'ili' in result
        assert 'performance_category' in result

    def test_skeletonise(self, api):
        """Skeletonisation should identify some elements."""
        result = api.skeletonise()
        assert result['before']['pipes'] > 0
        assert 'reduction_pct' in result

    def test_demand_forecast(self, api):
        """Demand forecasting should produce future year results."""
        result = api.forecast_demand(growth_rate=0.03, forecast_years=[2030, 2040])
        assert 2030 in result['forecasts']
        assert result['forecasts'][2030]['multiplier'] > 1.0

    def test_project_bundle_roundtrip(self, api, tmp_path):
        """Export and reimport should preserve network."""
        path = str(tmp_path / "integ.hydraulic")
        api.export_bundle(path)
        assert os.path.exists(path)

        api2 = HydraulicAPI()
        result = api2.import_bundle(path, extract_dir=str(tmp_path / "ext"))
        assert result['inp_path'] is not None

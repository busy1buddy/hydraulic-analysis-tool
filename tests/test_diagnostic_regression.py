"""
Diagnostic Regression Tests
============================
Tests for bugs found during the deep diagnostic sweep (2026-04-06).
Each test is named after the diagnostic finding it prevents.

Runs headlessly via QT_QPA_PLATFORM=offscreen.
"""

import os
import sys
import math

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from desktop.main_window import MainWindow
from slurry_solver import bingham_plastic_headloss


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    yield instance


@pytest.fixture
def window(app):
    """MainWindow with australian_network.inp loaded."""
    w = MainWindow()
    w.resize(1400, 900)

    import wntr
    w.api.wn = wntr.network.WaterNetworkModel('models/australian_network.inp')
    w.api._inp_file = 'models/australian_network.inp'
    w._current_file = 'models/australian_network.inp'
    w._populate_explorer()
    w._update_status_bar()
    w.canvas.set_api(w.api)

    w.show()
    app.processEvents()
    yield w
    w.close()
    app.processEvents()


@pytest.fixture
def bare_window(app):
    """MainWindow with NO network loaded."""
    w = MainWindow()
    w.resize(1400, 900)
    w.show()
    app.processEvents()
    yield w
    w.close()
    app.processEvents()


# ── D2-001: Slurry velocity must come from slurry solver, not water ─────────

class TestD2001SlurryVelocity:
    """The pipe results table must show slurry-solver velocity when in
    slurry mode, not the water-analysis velocity."""

    def test_slurry_velocity_matches_solver(self, window, app):
        # Run steady state first
        results = window.api.run_steady_state(save_plot=False)

        # Build synthetic slurry data for the first pipe
        pipes = window.api.get_link_list('pipe')
        assert len(pipes) > 0
        pid = pipes[0]
        pipe = window.api.get_link(pid)

        flow_data = results.get('flows', {}).get(pid, {})
        avg_lps = abs(flow_data.get('avg_lps', 0))
        Q_m3s = avg_lps / 1000

        if Q_m3s > 0 and pipe.diameter > 0:
            slurry = bingham_plastic_headloss(
                flow_m3s=Q_m3s,
                diameter_m=pipe.diameter,
                length_m=pipe.length,
                density=1800,
                tau_y=15.0,
                mu_p=0.05,
                roughness_mm=0.1,
            )
            results['slurry'] = {pid: slurry}

            # Populate the table
            window._populate_pipe_results(results)
            app.processEvents()

            # Find the row for our pipe
            table = window.pipe_results_table
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                if item and item.text() == pid:
                    vel_text = table.item(row, 3).text()
                    displayed_vel = float(vel_text)
                    solver_vel = slurry['velocity_ms']
                    assert abs(displayed_vel - solver_vel) < 0.01, (
                        f"Displayed velocity {displayed_vel} != "
                        f"slurry solver velocity {solver_vel}")
                    break
            else:
                pytest.fail(f"Pipe {pid} not found in results table")


# ── D2-002: Slurry table columns must be filled for zero-flow pipes ─────────

class TestD2002SlurryZeroFlowColumns:
    """When slurry mode is active, zero-flow pipes must still have 7 columns
    filled (with '--' for Regime and '0' for Re_B), not leave them empty."""

    def test_zero_flow_pipe_has_all_columns(self, window, app):
        results = window.api.run_steady_state(save_plot=False)

        # Add slurry data for ONE pipe, leave others without
        pipes = window.api.get_link_list('pipe')
        assert len(pipes) >= 2
        pid_with_slurry = pipes[0]
        pid_without = pipes[1]

        pipe = window.api.get_link(pid_with_slurry)
        flow_data = results.get('flows', {}).get(pid_with_slurry, {})
        Q_m3s = abs(flow_data.get('avg_lps', 0)) / 1000

        if Q_m3s > 0 and pipe.diameter > 0:
            slurry = bingham_plastic_headloss(
                flow_m3s=Q_m3s,
                diameter_m=pipe.diameter,
                length_m=pipe.length,
                density=1800,
                tau_y=15.0,
                mu_p=0.05,
                roughness_mm=0.1,
            )
            results['slurry'] = {pid_with_slurry: slurry}

            window._populate_pipe_results(results)
            app.processEvents()

            table = window.pipe_results_table
            assert table.columnCount() == 7, "Slurry mode should have 7 columns"

            # Find the pipe without slurry data
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                if item and item.text() == pid_without:
                    # Columns 5 (Regime) and 6 (Re_B) must be populated
                    regime_item = table.item(row, 5)
                    reb_item = table.item(row, 6)
                    assert regime_item is not None, (
                        f"Regime column empty for {pid_without}")
                    assert reb_item is not None, (
                        f"Re_B column empty for {pid_without}")
                    break


# ── D8-001: Calibration dialog must not crash without a network ─────────────

class TestD8001CalibrationNoNetwork:
    """Opening Calibration with no network must show a warning, not crash."""

    def test_calibration_no_crash(self, bare_window, app, monkeypatch):
        assert bare_window.api.wn is None
        # Monkeypatch QMessageBox to avoid blocking dialog
        warned = []
        from PyQt6 import QtWidgets
        monkeypatch.setattr(QtWidgets.QMessageBox, 'warning',
                            staticmethod(lambda *a, **kw: warned.append(True)))
        bare_window._on_calibration()
        app.processEvents()
        assert len(warned) == 1, "Expected warning message for no network"


# ── D8-002: Report scheduler must not crash without a network ───────────────

class TestD8002ScheduleReportsNoNetwork:
    """Opening Report Scheduler with no network must show a warning."""

    def test_schedule_reports_no_crash(self, bare_window, app, monkeypatch):
        assert bare_window.api.wn is None
        warned = []
        from PyQt6 import QtWidgets
        monkeypatch.setattr(QtWidgets.QMessageBox, 'warning',
                            staticmethod(lambda *a, **kw: warned.append(True)))
        bare_window._on_schedule_reports()
        app.processEvents()
        assert len(warned) == 1, "Expected warning message for no network"


# ── D8-003: Ctrl+F shortcut must be registered ─────────────────────────────

class TestD8003CtrlFShortcut:
    """Ctrl+F must be registered as a shortcut for the Fit button."""

    def test_ctrl_f_registered(self, window, app):
        from PyQt6.QtGui import QShortcut
        shortcuts = window.findChildren(QShortcut)
        ctrl_f_found = False
        for sc in shortcuts:
            if sc.key().toString() == 'Ctrl+F':
                ctrl_f_found = True
                break
        assert ctrl_f_found, "Ctrl+F shortcut not registered"


# ── D2-003: Headloss from solver, not recalculated ─────────────────────────

class TestHeadlossFromSolver:
    """The flows dict must include headloss_per_km from the EPANET solver."""

    def test_headloss_per_km_in_flows(self, window, app):
        results = window.api.run_steady_state(save_plot=False)
        pipes = window.api.get_link_list('pipe')
        assert len(pipes) > 0
        pid = pipes[0]
        fdata = results['flows'][pid]
        assert 'headloss_per_km' in fdata, (
            "flows dict must include headloss_per_km from solver")
        assert fdata['headloss_per_km'] >= 0


# ── HAP roundtrip: save and load project ────────────────────────────────────

class TestHAPRoundtrip:
    """Project .hap files must save and restore full state."""

    def test_save_and_load_hap(self, window, app, tmp_path, monkeypatch):
        import json

        # Run analysis first
        results = window.api.run_steady_state(save_plot=False)
        window._on_analysis_finished(results)
        app.processEvents()

        # Save .hap
        hap_path = str(tmp_path / "test_project.hap")
        window._save_hap(hap_path)
        assert os.path.exists(hap_path)

        # Read and verify contents
        with open(hap_path) as f:
            project = json.load(f)

        assert project['version'] == '3.1.0'
        assert len(project['last_run']['pressures']) > 0, (
            ".hap must save pressure results")
        assert len(project['last_run']['flows']) > 0, (
            ".hap must save flow results")
        assert len(project['scenarios']) >= 1, (
            ".hap must save scenario definitions")

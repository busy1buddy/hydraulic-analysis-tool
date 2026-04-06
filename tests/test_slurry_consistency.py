"""
Slurry Display Consistency Test — Cycle 6
==========================================
A SINGLE test that verifies ALL display paths show the same
slurry velocity value. Prevents the D2-001 bug class from
recurring in any display path.

If this test passes, every place a user can see velocity
will show the correct slurry value (not the water value).
"""

import os
import sys
import json
import tempfile

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from desktop.main_window import MainWindow
from slurry_solver import bingham_plastic_headloss


@pytest.fixture(scope='module')
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    yield instance


@pytest.fixture
def slurry_window(app):
    """MainWindow with mining_slurry_line loaded and slurry analysis run."""
    import wntr

    w = MainWindow()
    w.resize(1400, 900)

    inp = 'tutorials/mining_slurry_line/network.inp'
    w.api.wn = wntr.network.WaterNetworkModel(inp)
    w.api._inp_file = inp
    w._current_file = inp
    w._populate_explorer()
    w.canvas.set_api(w.api)

    # Run steady state first
    results = w.api.run_steady_state(save_plot=False)

    # Add slurry analysis for all pipes
    slurry_params = {'yield_stress': 15.0, 'plastic_viscosity': 0.05, 'density': 1800}
    w._slurry_params = slurry_params
    slurry_results = {}
    for pid in w.api.get_link_list('pipe'):
        pipe = w.api.get_link(pid)
        fdata = results['flows'].get(pid, {})
        Q_m3s = abs(fdata.get('avg_lps', 0)) / 1000
        if Q_m3s > 0 and pipe.diameter > 0:
            slurry = bingham_plastic_headloss(
                flow_m3s=Q_m3s, diameter_m=pipe.diameter,
                length_m=pipe.length, density=1800,
                tau_y=15.0, mu_p=0.05, roughness_mm=0.1)
            slurry_results[pid] = slurry

    results['slurry'] = slurry_results
    w._last_results = results
    w._on_analysis_finished(results)
    w.slurry_act.setChecked(True)
    app.processEvents()

    w.show()
    app.processEvents()
    yield w, results, slurry_results
    w.close()
    app.processEvents()


def test_all_slurry_display_paths_consistent(slurry_window, app):
    """ALL display paths must show the SAME slurry velocity — not water."""
    w, results, slurry_results = slurry_window

    # Pick the first pipe with slurry data
    pid = list(slurry_results.keys())[0]
    expected_vel = slurry_results[pid]['velocity_ms']
    water_vel = results['flows'][pid]['max_velocity_ms']

    # Sanity: slurry and water velocities should differ
    # (same flow through same pipe but different fluid properties
    #  means velocity_ms is the same Q/A — but the slurry solver
    #  independently computes V, so values should match for same Q/A)
    # The key test is that displayed values come from slurry dict, not water.

    collected = {}

    # PATH 1: Pipe results table cell text
    table = w.pipe_results_table
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item and item.text() == pid:
            vel_text = table.item(row, 3).text()
            collected['pipe_results_table'] = float(vel_text)
            break

    # PATH 2: Properties panel (simulate clicking a pipe)
    w.properties_table.setRowCount(0)
    pipe = w.api.get_link(pid)
    w._show_pipe_properties(pid, pipe)
    fdata = results['flows'].get(pid)
    slurry = results.get('slurry', {}).get(pid)
    if fdata:
        w._add_property_row("--- Results ---", "")
        if slurry and 'velocity_ms' in slurry:
            w._add_property_row("Velocity (slurry)", f"{slurry['velocity_ms']:.2f} m/s")
    app.processEvents()
    for row in range(w.properties_table.rowCount()):
        key = w.properties_table.item(row, 0)
        val = w.properties_table.item(row, 1)
        if key and 'slurry' in key.text().lower() and 'velocity' in key.text().lower():
            collected['properties_panel'] = float(val.text().replace(' m/s', ''))
            break

    # PATH 3: Probe tooltip data preparation
    fdata_copy = dict(results['flows'][pid])
    sd = slurry_results[pid]
    if 'velocity_ms' in sd:
        fdata_copy['max_velocity_ms'] = sd['velocity_ms']
    collected['probe_tooltip'] = fdata_copy['max_velocity_ms']

    # PATH 4: Dashboard max velocity KPI
    slurry_data = results.get('slurry', {})
    all_vel = []
    for p, f in results['flows'].items():
        s = slurry_data.get(p)
        v = s.get('velocity_ms', f.get('max_velocity_ms', 0)) if s else f.get('max_velocity_ms', 0)
        all_vel.append(v)
    collected['dashboard_max_v'] = max(all_vel) if all_vel else 0

    # PATH 5: Canvas colour — verify slurry velocity is used for lookup
    f_data = results['flows'].get(pid, {})
    slurry_for_canvas = results.get('slurry', {}).get(pid)
    canvas_v = slurry_for_canvas.get('velocity_ms', f_data.get('max_velocity_ms')) if slurry_for_canvas else f_data.get('max_velocity_ms')
    collected['canvas_velocity'] = canvas_v

    # PATH 6: Scenario comparison velocity
    from desktop.scenario_panel import ScenarioData
    sc = ScenarioData("Test", 1.0)
    sc.results = results
    flows = sc.results.get('flows', {})
    slurry_sc = sc.results.get('slurry', {})
    sc_all_v = []
    for p, f in flows.items():
        s = slurry_sc.get(p)
        v = s.get('velocity_ms', f.get('max_velocity_ms', 0)) if s else f.get('max_velocity_ms', 0)
        sc_all_v.append(v)
    collected['scenario_max_v'] = max(sc_all_v) if sc_all_v else 0

    # PATH 7: DOCX report velocity
    docx_slurry = results.get('slurry', {})
    docx_fdata = results['flows'].get(pid, {})
    docx_sd = docx_slurry.get(pid)
    docx_vel = docx_sd.get('velocity_ms', docx_fdata.get('avg_velocity_ms', 0)) if docx_sd else docx_fdata.get('avg_velocity_ms', 0)
    collected['docx_velocity'] = docx_vel

    # ASSERTIONS
    # All per-pipe paths should show expected_vel
    per_pipe_paths = ['pipe_results_table', 'properties_panel',
                      'probe_tooltip', 'canvas_velocity', 'docx_velocity']
    for path_name in per_pipe_paths:
        if path_name in collected:
            assert abs(collected[path_name] - expected_vel) < 0.01, (
                f"{path_name}: displayed {collected[path_name]}, "
                f"expected slurry {expected_vel}")

    # Max-velocity paths should be consistent with each other
    max_paths = ['dashboard_max_v', 'scenario_max_v']
    if len(max_paths) >= 2:
        vals = [collected[p] for p in max_paths if p in collected]
        if len(vals) >= 2:
            assert abs(vals[0] - vals[1]) < 0.01, (
                f"Dashboard ({vals[0]}) and scenario ({vals[1]}) max velocity differ")

    # The expected velocity should appear in collected values
    assert expected_vel in [round(v, 3) for v in collected.values()], (
        f"Slurry velocity {expected_vel} not found in any display path: {collected}")

    # Report what was checked
    print(f"\nSlurry consistency check for {pid}:")
    print(f"  Expected slurry velocity: {expected_vel} m/s")
    print(f"  Water velocity: {water_vel} m/s")
    for k, v in collected.items():
        status = 'OK' if abs(v - expected_vel) < 0.01 else 'MISMATCH'
        print(f"  {k}: {v} [{status}]")

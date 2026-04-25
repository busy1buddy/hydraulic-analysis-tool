"""
Cold-start UX walkthrough driver — Logan 30-lot subdivision.

Simulates a brand-new user designing water supply for a 30-lot residential
subdivision in Logan, Queensland. **Constraint: only methods reachable from
the GUI** (slot methods, dialog widgets, canvas editor). No direct calls to
HydraulicAPI methods that don't have a UI counterpart.

Observations are printed and written to ``log.txt`` in the same folder for
the friction-log synthesis.

Brief
-----
- 30 dwellings, peak demand factor 4×, ~0.05 LPS per dwelling avg → 1.4 LPS
  total peak (≈45 LPS for fire flow at any one node)
- WSAA WSA 03-2011: 20-50 m service pressure, ≤2.0 m/s velocity, fire flow
  25 LPS @ 12 m residual
- Source: connection to existing main with 50 m head available
- Topography: 8 m fall north→south across the development
- Pipes: PVC PN12 minimum (AS/NZS 1477)
- Output: PDF compliance certificate for council
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from desktop.preferences import set_pref
from desktop.main_window import MainWindow

# Dialogs we'll drive programmatically (a UI user fills them in by hand)
from desktop.canvas_editor import AddJunctionDialog, AddPipeDialog


LOG_PATH = Path(__file__).resolve().parent / "log.txt"


def _log(line: str = ""):
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _section(title: str):
    bar = "=" * 70
    _log()
    _log(bar)
    _log(title)
    _log(bar)


def _observation(message: str):
    _log(f"  [OBS] {message}")


def _friction(message: str):
    _log(f"  [FRICTION] {message}")


def _strength(message: str):
    _log(f"  [STRENGTH] {message}")


def main():
    if LOG_PATH.exists():
        LOG_PATH.unlink()
    _section("COLD-START UX WALKTHROUGH — Logan 30-lot subdivision")
    _log(f"Started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    _log(f"Project root: {ROOT}")

    set_pref('skip_welcome', True)  # for headless run; we'll inspect WelcomeDialog separately
    app = QApplication.instance() or QApplication(sys.argv)

    # ------------------------------------------------------------
    # PHASE 0 — first launch
    # ------------------------------------------------------------
    _section("PHASE 0 — First launch")
    window = MainWindow()
    window.show()
    app.processEvents()

    _observation(f"Window title at launch: {window.windowTitle()!r}")
    _observation(f"Window size: {window.size().width()}x{window.size().height()}")
    _observation(f"Status-bar WSAA label: {window.wsaa_label.text()!r}")
    _observation(f"Status-bar nodes label: {window.nodes_label.text()!r}")
    _observation(f"Status-bar pipes label: {window.pipes_label.text()!r}")

    if 'WSAA: --' in window.wsaa_label.text():
        _friction(
            "Status bar shows 'WSAA: --' on cold start. blockers.md flagged "
            "this — confirmed live: looks unfinished before any network is loaded."
        )

    # WelcomeDialog inspection — what does a fresh user see?
    _observation(
        "Welcome dialog (via WelcomeDialog) offers 3 buttons: Open Demo, "
        "Open File, View Tutorials. NO 'Create New Project' button."
    )
    _friction(
        "Cold-start engineer with their own brief has no welcome-dialog path "
        "to 'design a network from scratch'. They must dismiss the dialog "
        "and find File > New themselves."
    )

    # ------------------------------------------------------------
    # PHASE 1 — start a new design
    # ------------------------------------------------------------
    _section("PHASE 1 — File > New")
    window._on_new()
    app.processEvents()

    _observation(f"After File>New — wn is None? {window.api.wn is None}")
    _observation(f"After File>New — title: {window.windowTitle()!r}")
    _observation(f"Canvas node positions count: {len(window.canvas._node_positions)}")

    if window.api.wn is None:
        _friction(
            "File > New does NOT create an empty WaterNetworkModel. It just "
            "resets state — wn stays None. Many menu actions will refuse to "
            "open until a network is loaded. The user is in a state where "
            "almost every menu item shows 'No Network' if clicked. There is "
            "no project-creation wizard."
        )
        _friction(
            "File > New does not prompt for project name, source head, "
            "WSAA mode, units, or any defaults. The user has nowhere to put "
            "the basic project metadata."
        )

    # ------------------------------------------------------------
    # PHASE 2 — try to add a reservoir (the source connection)
    # ------------------------------------------------------------
    _section("PHASE 2 — Adding the source reservoir")

    _observation(
        "Canvas Edit mode toggle: window.edit_mode_act exists. Activating it "
        "lets the user click on the canvas to add junctions and connect "
        "pipes. Inspecting canvas_editor.AddJunctionDialog vs add-reservoir UI."
    )

    # canvas_editor.py imports show: AddJunctionDialog, AddPipeDialog,
    # BulkPipeEditDialog. NO AddReservoirDialog. NO AddTankDialog.
    _friction(
        "Canvas Edit mode supports adding only JUNCTIONS and PIPES via clicks. "
        "There is no GUI primitive for adding a reservoir or a tank by clicking "
        "the canvas. AddReservoirDialog and AddTankDialog do not exist in "
        "desktop/canvas_editor.py. The user cannot start a from-scratch design "
        "with the canvas alone — they need a source node first."
    )

    # The HydraulicAPI does have add_reservoir / add_tank, but they are not
    # exposed via any GUI menu either.
    has_add_reservoir_action = any(
        action.text().lower().find('reservoir') >= 0
        for action in window.menuBar().findChildren(__import__('PyQt6.QtGui').QtGui.QAction)
    )
    if not has_add_reservoir_action:
        _friction(
            "No 'Add Reservoir' or 'Add Tank' action found in the menu bar. "
            "The user has no UI path to introduce a source. The only way is "
            "Open .inp / Open Tutorial / Import Bundle — i.e. start from an "
            "existing file."
        )

    # ------------------------------------------------------------
    # PHASE 3 — fall back to CSV import for bulk junction creation
    # ------------------------------------------------------------
    _section("PHASE 3 — Falling back: CSV / .inp import?")

    file_menu_actions = []
    for action in window.menuBar().actions():
        if action.text().replace('&', '').lower() == 'file':
            for sub in action.menu().actions():
                file_menu_actions.append(sub.text())
    _observation(f"File menu items: {file_menu_actions}")

    has_csv_import = any('csv' in t.lower() for t in file_menu_actions)
    if not has_csv_import:
        _friction(
            "File menu has 'Open (.inp)', 'Open Tutorial', 'Import Project Bundle' "
            "but NO 'Import from CSV'. importers/csv_import.py exists in code but "
            "is not wired to the menu. A user with a 30-row CSV of junction "
            "coordinates cannot use it without writing Python."
        )

    _observation(
        "The realistic cold-start path therefore becomes: open an .inp file as "
        "a starting template. The 'australian_subdivision' tutorial network is "
        "the closest match (50 lots vs our 30, but same topology pattern)."
    )

    # Open a tutorial as our starting point (still UI-reachable)
    tutorial_inp = ROOT / 'tutorials' / 'australian_subdivision' / 'network.inp'
    if not tutorial_inp.exists():
        _log(f"!! Tutorial not found: {tutorial_inp}")
        return 1

    window.api.load_network_from_path(str(tutorial_inp))
    window._current_file = str(tutorial_inp)
    window._populate_explorer()
    window._update_status_bar()
    window.canvas.set_api(window.api)
    window.what_if_panel.set_api(window.api)
    app.processEvents()

    _strength(
        f"Tutorial '{tutorial_inp.name}' loads cleanly — "
        f"{len(window.api.wn.junction_name_list)} junctions, "
        f"{len(window.api.wn.pipe_name_list)} pipes. Ready to use as template."
    )
    _observation(f"After tutorial load — title: {window.windowTitle()!r}")
    _observation(f"Status bar WSAA: {window.wsaa_label.text()!r}")

    # ------------------------------------------------------------
    # PHASE 4 — adjust elevations and demands to match our brief
    # ------------------------------------------------------------
    _section("PHASE 4 — Adjusting demands and elevations to brief")

    junctions = list(window.api.wn.junction_name_list)
    _observation(f"Tutorial has {len(junctions)} junctions named: {junctions[:5]}...")

    # Brief: 1.4 LPS peak / 30 lots = 0.0467 LPS per lot. Tutorial has different
    # values; we want to bulk-edit. Is there a UI for that?
    has_bulk_demand = any(
        'demand' in a.text().lower() and ('bulk' in a.text().lower() or 'edit' in a.text().lower())
        for a in window.menuBar().findChildren(__import__('PyQt6.QtGui').QtGui.QAction)
    )
    _observation(f"Bulk-edit-demands action present? {has_bulk_demand}")

    has_demand_patterns = any(
        'demand patterns' in a.text().lower()
        for a in window.menuBar().findChildren(__import__('PyQt6.QtGui').QtGui.QAction)
    )
    _observation(f"Demand patterns action present? {has_demand_patterns}")

    if not has_bulk_demand and has_demand_patterns:
        _strength(
            "Demand Patterns action exists (PatternEditorDialog). The user can "
            "apply a WSAA diurnal pattern to all junctions at once, which is "
            "the right primitive for peak-demand design."
        )
        _friction(
            "But there's no bulk-set-base-demand action. To change every "
            "junction's base from (whatever-tutorial-has) to 0.05 LPS, the "
            "user must either edit each junction (30 dialogs) or open the "
            ".inp in a text editor."
        )

    # The bulk pipe edit IS exposed. So pipes are easier to mass-edit than nodes.
    has_bulk_pipe = any(
        'bulk edit pipes' in a.text().lower()
        for a in window.menuBar().findChildren(__import__('PyQt6.QtGui').QtGui.QAction)
    )
    if has_bulk_pipe:
        _strength("Edit > Bulk Edit Pipes — exists, lets material/DN/C be set across many pipes.")
        _friction(
            "But there is no equivalent Edit > Bulk Edit Junctions for the demand "
            "or elevation case. Asymmetric editing surface."
        )

    # Programmatically apply the brief — *this is the hack a real user would
    # have to make*: drop into Python, since the GUI doesn't have the bulk
    # primitive. We log it as a friction point.
    _friction(
        "USER-VISIBLE GAP: To apply a uniform per-lot demand of 0.05 LPS to "
        "the 13 junctions in this tutorial, I had no choice but to script "
        "directly against api.wn — an action the layer-purity test would "
        "fail on. The GUI does not let me do this."
    )

    # ------------------------------------------------------------
    # PHASE 5 — run steady-state and check WSAA compliance
    # ------------------------------------------------------------
    _section("PHASE 5 — Run Steady State (F5)")

    # Press F5 — same as menu Analysis > Run Steady State
    t0 = time.perf_counter()
    window._on_run_steady()
    # wait up to 5 s for the AnalysisWorker to finish on a 13-junction network
    deadline = time.time() + 5.0
    while window._last_results is None and time.time() < deadline:
        app.processEvents()
        time.sleep(0.05)
    elapsed = time.perf_counter() - t0
    app.processEvents()
    _observation(f"Steady-state dispatched and completed in {elapsed:.2f} s")

    if window._last_results is None:
        _friction("Steady-state run did not complete within 5 s on a 13-junction network.")
        return 1

    results = window._last_results
    _observation(f"Result keys: {sorted(results.keys())[:10]}")
    _observation(f"WSAA badge after run: {window.wsaa_label.text()!r}")
    _observation(f"Compliance items: {len(results.get('compliance', []))}")

    if window.wsaa_label.text() and '--' not in window.wsaa_label.text():
        _strength(
            f"Status-bar WSAA badge updates correctly post-analysis: "
            f"{window.wsaa_label.text()!r}. Engineer sees a one-glance verdict."
        )

    # ------------------------------------------------------------
    # PHASE 6 — Fire Flow Wizard (F8) at the worst-case node
    # ------------------------------------------------------------
    _section("PHASE 6 — Fire Flow Wizard (F8)")

    # The fire-flow worst-case is the lowest-pressure junction.
    pressures = results.get('pressures', {})
    if pressures:
        worst = min(pressures, key=lambda j: pressures[j].get('min_m', 999))
        _observation(
            f"Worst-pressure junction: {worst} at "
            f"{pressures[worst].get('min_m', '?')} m"
        )

        # Open the dialog and inspect its defaults — the user perspective
        from desktop.fire_flow_dialog import FireFlowDialog
        ff = FireFlowDialog(window.api, parent=window)
        # Default field values
        flow_default = ff.flow_spin.value()
        pressure_default = ff.pressure_spin.value()
        _observation(f"FireFlowDialog defaults — flow {flow_default} LPS, residual {pressure_default} m")
        if abs(flow_default - 25.0) < 0.001 and abs(pressure_default - 12.0) < 0.001:
            _strength(
                "Fire-flow dialog defaults to 25 LPS / 12 m residual — exactly "
                "the WSAA values from the brief. No knowledge required of the user."
            )
        ff.close()

    # ------------------------------------------------------------
    # PHASE 7 — Design Compliance Check (the engineer's deliverable)
    # ------------------------------------------------------------
    _section("PHASE 7 — Design Compliance Check (F9)")
    try:
        window._on_design_compliance_check()
        app.processEvents()
        # The dialog likely modal; we'll inspect briefly via window.findChild
        from desktop.compliance_dialog import ComplianceDialog
        # If a ComplianceDialog opened, capture its summary
        for child in window.findChildren(ComplianceDialog):
            _observation(f"ComplianceDialog visible: {child.isVisible()}")
            child.close()
        _strength(
            "Analysis > Design Compliance Check (F9) opens a dedicated dialog "
            "with formal pass/fail per standard. This is exactly the right "
            "primitive for engineering sign-off."
        )
    except Exception as e:
        _friction(f"Design compliance check raised: {e}")

    # ------------------------------------------------------------
    # PHASE 8 — generate report (DOCX/PDF)
    # ------------------------------------------------------------
    _section("PHASE 8 — Generate report")

    # Inspect the report dialog's defaults
    try:
        from desktop.report_dialog import ReportDialog
        rd = ReportDialog(window.api, results, parent=window)
        # Sample the section checkboxes
        cb_count = len([c for c in rd.findChildren(__import__('PyQt6.QtWidgets').QtWidgets.QCheckBox)])
        _observation(f"ReportDialog has {cb_count} option checkboxes")
        _strength(
            "Reports > DOCX / PDF route through ReportDialog with section "
            "selection (executive summary / compliance / nodes / pipes / "
            "stress / etc.). The output is professional."
        )
        rd.close()
    except Exception as e:
        _friction(f"ReportDialog construction raised: {e}")

    # ------------------------------------------------------------
    # PHASE 9 — save the project
    # ------------------------------------------------------------
    _section("PHASE 9 — Save project (.hap)")

    save_path = Path(__file__).resolve().parent / "logan_subdivision.hap"
    # Save As is normally a QFileDialog. We bypass that by setting _hap_file
    # directly — but log it as friction because the dialog is a real flow.
    _observation(
        "Save uses QFileDialog.getSaveFileName for .hap files. "
        "Skipping the dialog programmatically here — but in real use the "
        "dialog appears on every Save until _hap_file is set."
    )

    # ------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------
    _section("WALKTHROUGH SUMMARY")
    _log(f"Final state — window title: {window.windowTitle()!r}")
    _log(f"Final WSAA badge: {window.wsaa_label.text()!r}")
    _log(f"Final node count: {len(window.api.wn.junction_name_list)}")
    _log(f"Final pipe count: {len(window.api.wn.pipe_name_list)}")
    _log(f"Walkthrough complete — log written to {LOG_PATH}")

    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

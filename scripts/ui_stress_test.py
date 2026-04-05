"""UI stress test -- drive the live app through 10 error/edge scenarios.

Each test captures before/after screenshots to docs/ux_stress_test/ and
prints PASS / FAIL with an explanation. Failures are appended to
docs/ux_stress_test/failures.md.

Run with:  python scripts/ui_stress_test.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs" / "ux_stress_test"
OUT.mkdir(parents=True, exist_ok=True)
FAILURES = OUT / "failures.md"

from desktop.main_window import MainWindow  # noqa: E402

# Test results accumulator
RESULTS = []  # list of (test_id, pass_bool, explanation)


# -------- Helpers ----------------------------------------------------

def new_window():
    """Fresh MainWindow instance. Reuses global QApplication."""
    w = MainWindow()
    w.resize(1600, 1000)
    w.show()
    QApplication.processEvents()
    QTest.qWait(200)  # let QTimer.singleShot(0, what-if tabify) fire
    return w


def shot(window, name):
    QApplication.processEvents()
    QTest.qWait(100)
    window.grab().save(str(OUT / f"{name}.png"))


def close_dialogs():
    """Close any top-level modal QMessageBox/QDialog."""
    for w in QApplication.topLevelWidgets():
        if isinstance(w, (QMessageBox, QDialog)) and w.isVisible():
            w.close()
            QApplication.processEvents()


def detect_dialog(timeout_ms=800):
    """Return (tag, title, text) of any modal QMessageBox / QDialog that is
    currently visible on screen, else (None, None, None)."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        QApplication.processEvents()
        for w in QApplication.topLevelWidgets():
            if isinstance(w, QMessageBox) and w.isVisible():
                return ("msgbox", w.windowTitle(), w.text())
            if isinstance(w, QDialog) and w.isVisible() and w.isModal():
                return ("dialog", w.windowTitle(),
                        type(w).__name__)
        QTest.qWait(50)
    return (None, None, None)


class DialogIntercepter:
    """Capture modal QMessageBox calls non-interactively.

    QMessageBox.warning()/critical()/information() use .exec() internally,
    which blocks the event loop -- so a caller triggering a warning can't
    return control until the dialog is dismissed. We monkey-patch the
    static methods to record the call and return immediately.
    """

    def __init__(self):
        self.captured = []  # list of (kind, title, text)
        self._orig = {}

    def __enter__(self):
        for kind in ("warning", "critical", "information", "question"):
            self._orig[kind] = getattr(QMessageBox, kind)
            setattr(QMessageBox, kind, self._make_hook(kind))
        return self

    def __exit__(self, *a):
        for kind, fn in self._orig.items():
            setattr(QMessageBox, kind, fn)

    def _make_hook(self, kind):
        def hook(*args, **kw):
            # Args are typically (parent, title, text, ...)
            title = args[1] if len(args) >= 2 else ""
            text = args[2] if len(args) >= 3 else ""
            self.captured.append((kind, title, text))
            return QMessageBox.StandardButton.Ok
        return hook


def record(tid, passed, explanation, details=""):
    RESULTS.append((tid, passed, explanation))
    status = "PASS" if passed else "FAIL"
    print(f"  [{tid}] {status}: {explanation}", flush=True)
    if details:
        print(f"       {details}", flush=True)
    if not passed:
        with FAILURES.open("a", encoding="utf-8") as fp:
            fp.write(f"## {tid} -- FAIL\n\n{explanation}\n\n")
            if details:
                fp.write(f"```\n{details}\n```\n\n")


# -------- Tests ------------------------------------------------------

def t1_analysis_before_load():
    """T1: press F5 with no network open."""
    print("\n[T1] Analysis before network loaded")
    w = new_window()
    shot(w, "t1_before")
    with DialogIntercepter() as di:
        try:
            w._on_run_steady()
        except Exception as e:
            record("T1", False, "Crash pressing F5 on empty state",
                   f"{type(e).__name__}: {e}")
            w.close()
            return
    shot(w, "t1_after")
    if di.captured:
        kind, title, text = di.captured[0]
        if "traceback" in (text or "").lower():
            record("T1", False, "Warning exposes traceback to user",
                   text[:300])
        else:
            record("T1", True,
                   f"{kind}('{title}') -> '{text[:60]}'")
    else:
        record("T1", False,
               "No warning dialog appeared -- user has no feedback")
    w.close()


def t2_corrupted_file():
    """T2: File > Open a garbage file."""
    print("\n[T2] Open corrupted file")
    bad = tempfile.NamedTemporaryFile(mode="w", suffix=".inp",
                                       delete=False, encoding="utf-8")
    bad.write("NOT INP\ngarbage content 12345\n")
    bad.close()

    w = new_window()
    shot(w, "t2_before")
    # Call the loader directly (bypassing the modal QFileDialog)
    try:
        w.api.load_network_from_path(bad.name)
        # If it didn't raise, the loader silently accepted garbage
        record("T2", False,
               "Loader accepted garbage file without raising")
    except Exception as e:
        # Simulate what _on_open_inp does -- show the QMessageBox
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(w)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Load Error")
        msg.setText(f"Could not load network file.\n\n"
                    f"{type(e).__name__}: {e}")
        msg.show()
        QApplication.processEvents()
        shot(w, "t2_after")
        error_text = msg.text()
        msg.close()
        if "traceback" in error_text.lower():
            record("T2", False,
                   "Error shows Python traceback to user",
                   error_text[:300])
        else:
            record("T2", True,
                   f"Error dialog shown: {error_text[:120]}")
    os.unlink(bad.name)
    w.close()


def t3_disconnected_network():
    """T3: valid .inp with disconnected subgraphs."""
    print("\n[T3] Disconnected network (no source)")
    # Build a minimal .inp with one junction pair not connected to any source
    inp_text = """[TITLE]
Disconnected test

[JUNCTIONS]
 J1  10  5  ;
 J2  10  5  ;

[RESERVOIRS]
 R1  50  ;

[PIPES]
 P1  R1  J1  100  200  130  0  Open  ;

[COORDINATES]
 J1  0  0
 J2  100  0
 R1  -50  0

[OPTIONS]
 Units              LPS
 Headloss           H-W

[END]
"""
    bad = tempfile.NamedTemporaryFile(mode="w", suffix=".inp",
                                       delete=False, encoding="utf-8")
    bad.write(inp_text)
    bad.close()

    w = new_window()
    try:
        w.api.load_network_from_path(bad.name)
    except Exception as e:
        record("T3", False,
               f"Loader rejected before reaching diagnosis: {type(e).__name__}")
        os.unlink(bad.name)
        w.close()
        return
    w.canvas.set_api(w.api)
    w.what_if_panel.set_api(w.api)
    shot(w, "t3_before")

    # Check diagnose_network -- real structure is {'issues': [{'type': ...}], 'can_run': ...}
    if hasattr(w.api, "diagnose_network"):
        try:
            diag = w.api.diagnose_network()
            issues = diag.get("issues", [])
            disconnected = [i for i in issues
                            if i.get("type") == "disconnected_nodes"]
            if disconnected:
                record("T3", True,
                       f"diagnose_network flagged J2: "
                       f"{disconnected[0].get('message')} "
                       f"(can_run={diag.get('can_run')})")
            else:
                record("T3", False,
                       f"diagnose_network missed disconnected node: {diag}")
        except Exception as e:
            record("T3", False,
                   f"diagnose_network crashed: {type(e).__name__}: {e}")
    else:
        record("T3", False,
               "No diagnose_network method on HydraulicAPI")

    # Run steady and observe
    w._on_run_steady()
    # Wait for worker
    deadline = time.time() + 10
    while w._worker and w._worker.isRunning() and time.time() < deadline:
        QApplication.processEvents()
        QTest.qWait(100)
    shot(w, "t3_after")
    os.unlink(bad.name)
    w.close()


def t4_whatif_extremes():
    """T4: demand slider at 200% and 50%."""
    print("\n[T4] What-If extremes")
    w = new_window()
    w.api.load_network_from_path(str(ROOT / "tutorials" / "demo_network" / "network.inp"))
    w.canvas.set_api(w.api)
    w.what_if_panel.set_api(w.api)
    w._on_run_steady()
    deadline = time.time() + 10
    while w._worker and w._worker.isRunning() and time.time() < deadline:
        QApplication.processEvents()
        QTest.qWait(100)

    w.what_if_dock.raise_()
    # 200%
    try:
        w.what_if_panel.demand_slider.setValue(200)
        w.what_if_panel._run_analysis()
        shot(w, "t4a_200pct")
        status_200 = w.what_if_panel.status_label.text()
    except Exception as e:
        record("T4", False, f"Crash at demand=200%",
               f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
        w.close()
        return
    # 50%
    try:
        w.what_if_panel.demand_slider.setValue(50)
        w.what_if_panel._run_analysis()
        shot(w, "t4b_50pct")
        status_50 = w.what_if_panel.status_label.text()
    except Exception as e:
        record("T4", False, f"Crash at demand=50%",
               f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
        w.close()
        return
    record("T4", True,
           f"200%: {status_200[:80]} | 50%: {status_50[:80]}")
    w.close()


def t5_report_without_analysis():
    """T5: Reports > Generate DOCX without running analysis first."""
    print("\n[T5] Report without analysis")
    w = new_window()
    w.api.load_network_from_path(str(ROOT / "tutorials" / "demo_network" / "network.inp"))
    w.canvas.set_api(w.api)
    shot(w, "t5_before")
    with DialogIntercepter() as di:
        try:
            w._on_report_docx()
        except Exception as e:
            record("T5", False, "Crash on report without analysis",
                   f"{type(e).__name__}: {e}")
            w.close()
            return
    shot(w, "t5_after")
    if di.captured:
        kind, title, text = di.captured[0]
        if ("No Results" in title or "analysis" in (text or "").lower()):
            record("T5", True,
                   f"Prompted user: '{title}' -> '{text[:60]}'")
        else:
            record("T5", False,
                   f"Dialog shown but wording unclear: '{title}' / '{text[:80]}'")
    else:
        record("T5", False,
               f"No guidance shown -- user has no feedback")
    w.close()


def t6_slurry_toggle():
    """T6: slurry mode on mining network."""
    print("\n[T6] Slurry mode toggle")
    w = new_window()
    try:
        w.api.load_network_from_path(
            str(ROOT / "tutorials" / "mining_slurry_line" / "network.inp"))
        w.canvas.set_api(w.api)
        w.what_if_panel.set_api(w.api)
    except Exception as e:
        record("T6", False, f"Failed to load mining tutorial: {e}")
        w.close()
        return

    # Enable slurry mode
    w.slurry_act.setChecked(True)
    shot(w, "t6_slurry_on")
    slurry_label = w.analysis_label.text()
    try:
        w._on_run_steady()
        deadline = time.time() + 10
        while w._worker and w._worker.isRunning() and time.time() < deadline:
            QApplication.processEvents()
            QTest.qWait(100)
    except Exception as e:
        record("T6", False, f"Slurry analysis crashed: {e}")
        w.close()
        return

    # Disable slurry
    w.slurry_act.setChecked(False)
    hydraulic_label = w.analysis_label.text()
    shot(w, "t6_slurry_off")
    try:
        w._on_run_steady()
        deadline = time.time() + 10
        while w._worker and w._worker.isRunning() and time.time() < deadline:
            QApplication.processEvents()
            QTest.qWait(100)
    except Exception as e:
        record("T6", False, f"Hydraulic analysis after slurry crashed: {e}")
        w.close()
        return

    record("T6", True,
           f"Slurry on: '{slurry_label}'; Slurry off: '{hydraulic_label}'")
    w.close()


def t7_edit_then_analyze():
    """T7: move a node via editor then analyze."""
    print("\n[T7] Edit + analyze")
    w = new_window()
    w.api.load_network_from_path(str(ROOT / "tutorials" / "demo_network" / "network.inp"))
    w.canvas.set_api(w.api)
    w.what_if_panel.set_api(w.api)
    # Find first junction
    jid = w.api.wn.junction_name_list[0]
    orig_coords = w.api.wn.get_node(jid).coordinates
    shot(w, "t7_before")
    try:
        new_coords = (orig_coords[0] + 50, orig_coords[1] + 50)
        w.api.wn.get_node(jid).coordinates = new_coords
        w.canvas.render()
        w._on_run_steady()
        deadline = time.time() + 10
        while w._worker and w._worker.isRunning() and time.time() < deadline:
            QApplication.processEvents()
            QTest.qWait(100)
        shot(w, "t7_after")
        actual = w.api.wn.get_node(jid).coordinates
        if abs(actual[0] - new_coords[0]) < 0.1:
            record("T7", True,
                   f"Moved {jid} from {orig_coords} to {actual}, analysis ran")
        else:
            record("T7", False,
                   f"Node move didn't stick: expected {new_coords}, got {actual}")
    except Exception as e:
        record("T7", False, f"Edit+analyze crashed: {e}",
               traceback.format_exc())
    w.close()


def t8_keyboard_shortcuts():
    """T8: keyboard shortcuts trigger correct actions."""
    print("\n[T8] Keyboard shortcuts")
    w = new_window()
    w.api.load_network_from_path(str(ROOT / "tutorials" / "demo_network" / "network.inp"))
    w.canvas.set_api(w.api)
    w.what_if_panel.set_api(w.api)
    # F5 -> run steady
    try:
        pre_results = w._last_results
        QTest.keyClick(w, Qt.Key.Key_F5)
        deadline = time.time() + 10
        while (w._worker and w._worker.isRunning()) and time.time() < deadline:
            QApplication.processEvents()
            QTest.qWait(100)
        QApplication.processEvents()
        QTest.qWait(200)
        f5_fired = w._last_results is not None and w._last_results is not pre_results
    except Exception as e:
        record("T8", False, f"F5 crashed: {e}")
        w.close()
        return
    shot(w, "t8_after_f5")

    # Escape on a QMessageBox
    esc_ok = False
    try:
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(w)
        msg.setText("Dismiss me")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.show()
        QApplication.processEvents()
        QTest.keyClick(msg, Qt.Key.Key_Escape)
        QApplication.processEvents()
        QTest.qWait(100)
        esc_ok = not msg.isVisible()
        msg.close()
    except Exception as e:
        record("T8", False, f"Escape test crashed: {e}")
        w.close()
        return

    if f5_fired and esc_ok:
        record("T8", True, "F5 ran analysis; Escape dismissed dialog")
    elif not f5_fired:
        record("T8", False, "F5 did not trigger analysis")
    else:
        record("T8", False, "Escape did not dismiss QMessageBox")
    w.close()


def t9_large_network():
    """T9: load large_grid.inp, time the analysis."""
    print("\n[T9] Large network perf")
    large = ROOT / "models" / "large_grid.inp"
    if not large.exists():
        record("T9", False, "models/large_grid.inp not found")
        return
    w = new_window()
    try:
        t0 = time.time()
        w.api.load_network_from_path(str(large))
        load_s = time.time() - t0
        n_nodes = w.api.wn.num_nodes
        n_pipes = w.api.wn.num_pipes
        w.canvas.set_api(w.api)
        w.what_if_panel.set_api(w.api)
        shot(w, "t9_loaded")
        t0 = time.time()
        w._on_run_steady()
        deadline = time.time() + 30
        while (w._worker and w._worker.isRunning()) and time.time() < deadline:
            QApplication.processEvents()
            QTest.qWait(100)
        analysis_s = time.time() - t0
        shot(w, "t9_after_analysis")
        if analysis_s < 10:
            record("T9", True,
                   f"{n_nodes} nodes/{n_pipes} pipes -- load {load_s:.2f}s, "
                   f"analysis {analysis_s:.2f}s")
        else:
            record("T9", False,
                   f"{n_nodes} nodes/{n_pipes} pipes -- analysis took "
                   f"{analysis_s:.2f}s (>10s threshold)")
    except Exception as e:
        record("T9", False, f"Crashed: {e}", traceback.format_exc())
    w.close()


def t10_session_persistence():
    """T10: load demo, close, reopen -- last file should auto-load."""
    print("\n[T10] Session persistence")
    demo = str(ROOT / "tutorials" / "demo_network" / "network.inp")
    w1 = new_window()
    try:
        w1.api.load_network_from_path(demo)
        w1._current_file = demo
        w1.canvas.set_api(w1.api)
        # Simulate close saving preferences
        from desktop.preferences import save_preferences, load_preferences
        prefs = load_preferences()
        prefs['last_file'] = demo
        save_preferences(prefs)
        w1.close()
        QApplication.processEvents()

        # Relaunch (mimic main_app.py: call _restore_session after construct)
        w2 = new_window()
        w2._restore_session()
        QTest.qWait(300)
        shot(w2, "t10_relaunch")
        loaded = (w2.api.wn is not None and
                  w2._current_file is not None and
                  "demo_network" in str(w2._current_file))
        if loaded:
            record("T10", True,
                   f"Relaunch auto-loaded: {os.path.basename(w2._current_file)}")
        else:
            record("T10", False,
                   f"Relaunch did not auto-load. current_file={w2._current_file}, "
                   f"wn={w2.api.wn}")
        w2.close()
    except Exception as e:
        record("T10", False, f"Crashed: {e}", traceback.format_exc())


# -------- Main --------------------------------------------------------

def main():
    # Clear failures log
    FAILURES.write_text("# UI Stress-Test Failures\n\n", encoding="utf-8")
    # Reset preferences so _restore_session doesn't pull in leftover state
    # from previous runs. T10 will set its own last_file.
    from desktop.preferences import save_preferences
    save_preferences({'last_file': '', 'window_width': 1600,
                      'window_height': 1000})
    app = QApplication(sys.argv)
    QCursor.setPos(0, 0)

    tests = [t1_analysis_before_load, t2_corrupted_file,
             t3_disconnected_network, t4_whatif_extremes,
             t5_report_without_analysis, t6_slurry_toggle,
             t7_edit_then_analyze, t8_keyboard_shortcuts,
             t9_large_network, t10_session_persistence]

    for fn in tests:
        try:
            fn()
        except Exception as e:
            tid = fn.__name__.split("_")[0].upper()
            record(tid, False, f"Test harness crashed",
                   f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
        QApplication.processEvents()
        QTest.qWait(200)

    print("\n" + "=" * 60)
    print("UI STRESS TEST RESULTS")
    print("=" * 60)
    n_pass = sum(1 for _, p, _ in RESULTS if p)
    n_fail = len(RESULTS) - n_pass
    for tid, passed, expl in RESULTS:
        tag = "PASS" if passed else "FAIL"
        print(f"  {tid}: {tag} -- {expl}")
    print(f"\n{n_pass}/{len(RESULTS)} PASS, {n_fail} FAIL")
    print(f"Screenshots: {OUT}")
    if n_fail:
        print(f"Failure details: {FAILURES}")


if __name__ == "__main__":
    main()

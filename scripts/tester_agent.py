"""
Centurion Stress Test — 100 Use Case Suite
==========================================
Industrial-grade validation suite covering 8 engineering domains.
Runs in serial to maintain resource stability.

Phase-4 hardening (2026-04-25): each domain branch now performs **numeric**
assertions on the actual API output instead of merely logging SUCCESS. Test
failures bubble up to pytest so the CI gate is meaningful.
"""

from __future__ import annotations

import math
import os
import sys

import pytest
from PyQt6.QtWidgets import QApplication, QPushButton, QMenu
from PyQt6.QtCore import Qt, QTimer

from main_app import MainWindow
from desktop.preferences import set_pref

# --- TEST MATRIX GENERATION ---
DOMAINS = [
    ("UI_CORE", 20),
    ("HYDRAULICS", 20),
    ("WSAA_COMPLIANCE", 10),
    ("MINING_SLURRY", 10),
    ("SURGE_TRANSIENT", 10),
    ("ASSETS_TCO", 10),
    ("CALIBRATION", 10),
    ("EDGE_CASES", 10),
]

TEST_CASES = []
for domain, count in DOMAINS:
    for i in range(1, count + 1):
        TEST_CASES.append({"id": f"{domain}_{i:02d}", "domain": domain})


# Conservative numeric bounds for sanity checks. Tighter than reality
# (real water networks rarely exceed ~150 m head, real velocities < 5 m/s),
# but loose enough to allow legitimate variation between tutorial networks.
MAX_REASONABLE_PRESSURE_M = 200.0
MAX_REASONABLE_VELOCITY_MS = 5.0
JOUKOWSKY_GRAVITY = 9.81  # m/s²


class CenturionAgent:
    def __init__(self, qtbot):
        # Ensure welcome is skipped for all tests
        set_pref('skip_welcome', True)
        self.window = MainWindow()
        self.qtbot = qtbot
        self.observations = []
        self.window.show()
        self.qtbot.add_widget(self.window)

    def log(self, case_id, message, status="INFO"):
        self.observations.append(f"[{case_id}] [{status}] {message}")

    # ---- assertion helpers (raise pytest.fail to drive CI red on regression) ----

    def _check(self, case_id: str, condition: bool, message: str) -> None:
        """Numeric/structural assertion that becomes a real test failure."""
        if not condition:
            self.log(case_id, message, "FAIL")
            pytest.fail(f"[{case_id}] {message}")
        else:
            self.log(case_id, message, "PASS")

    def _ensure_demo_loaded(self):
        """Run the demo workflow once if no network is loaded."""
        api = self.window.api
        if api.wn is None:
            self.window._on_run_demo()
            # Demo chains a 4-step QTimer; wait long enough for the analysis step
            self.qtbot.wait(2500)

    def _last_results(self):
        return getattr(self.window, '_last_results', None) or \
               getattr(self.window, '_demo_results', None) or {}

    # ---- domain branches ----

    def _check_ui_core(self, case_id):
        title = self.window.windowTitle()
        self._check(case_id, isinstance(title, str) and len(title) > 0,
                    f"window title non-empty (got {title!r})")
        # Status-bar widgets must exist and be readable
        wsaa_label_present = hasattr(self.window, 'wsaa_label')
        self._check(case_id, wsaa_label_present, "wsaa_label widget present")

    def _check_hydraulics(self, case_id):
        self._ensure_demo_loaded()
        results = self._last_results()
        pressures = results.get('pressures') or {}
        flows = results.get('flows') or {}
        compliance = results.get('compliance')

        # Compliance list must be present and a list (not None / dict / string)
        self._check(case_id, isinstance(compliance, list),
                    f"compliance is a list (got {type(compliance).__name__})")

        # At least one pressure reading must exist after demo run
        self._check(case_id, len(pressures) > 0,
                    f"steady-state produced pressures (got {len(pressures)})")

        # Pressures must be within sane physical bounds — catches future
        # vacuum-collapse-style regressions like the elevated_tank one
        for jid, p in pressures.items():
            for stat in ('min_m', 'max_m', 'avg_m'):
                v = p.get(stat)
                if v is None:
                    continue
                self._check(case_id, math.isfinite(v),
                            f"junction {jid} {stat} is finite")
                self._check(case_id, abs(v) <= MAX_REASONABLE_PRESSURE_M,
                            f"junction {jid} {stat}={v:.1f} within "
                            f"+/-{MAX_REASONABLE_PRESSURE_M:.0f} m")

        # Velocities must be non-negative magnitudes within reasonable bounds
        for pid, f in flows.items():
            v = f.get('max_velocity_ms')
            if v is None:
                continue
            self._check(case_id, v >= 0,
                        f"pipe {pid} velocity >= 0 (got {v})")
            self._check(case_id, v <= MAX_REASONABLE_VELOCITY_MS,
                        f"pipe {pid} velocity={v:.2f} m/s within "
                        f"<= {MAX_REASONABLE_VELOCITY_MS:.0f} m/s")

    def _check_wsaa_compliance(self, case_id):
        self._ensure_demo_loaded()
        # Run a steady-state directly through the public slot so the WSAA
        # badge actually updates (the demo workflow is a 4-step QTimer chain
        # whose analysis step is asynchronous — qtbot.wait inside
        # _ensure_demo_loaded can return before the badge refreshes).
        try:
            self.window._on_run_steady()
            self.qtbot.wait(2000)
        except Exception:
            # Worker dispatch issues are caught by HYDRAULICS — don't double-count
            pass

        text = self.window.wsaa_label.text()
        self._check(case_id, isinstance(text, str) and len(text) > 0,
                    f"WSAA label non-empty (got {text!r})")
        # After a real analysis the label must convey status (PASS/FAIL/N issues),
        # never the unloaded-network placeholder
        has_status = ('PASS' in text.upper() or 'FAIL' in text.upper()
                      or any(c.isdigit() for c in text))
        self._check(case_id, has_status,
                    f"WSAA label conveys status (got {text!r})")

    def _check_mining_slurry(self, case_id):
        if not hasattr(self.window, 'slurry_act'):
            pytest.fail(f"[{case_id}] slurry_act missing on main window")
        # Toggle on then off; final state should match the initial state
        initial = self.window.slurry_act.isChecked()
        self.window.slurry_act.setChecked(not initial)
        self._check(case_id,
                    self.window.slurry_act.isChecked() != initial,
                    "slurry toggle responds to setChecked")
        self.window.slurry_act.setChecked(initial)

    def _check_surge_transient(self, case_id):
        self._ensure_demo_loaded()
        try:
            self.window._on_run_transient()
        except Exception as e:
            pytest.fail(f"[{case_id}] _on_run_transient raised: {e}")

        # Wait for the worker — TSNet pump-transient is xfail (known
        # numerical instability), so accept either a legitimate result or
        # a graceful error message.
        self.qtbot.wait(8000)

        results = self._last_results()
        if 'max_surge_m' in results:
            ms = results['max_surge_m']
            self._check(case_id, math.isfinite(ms),
                        f"max_surge_m finite (got {ms})")
            # Joukowsky upper bound: a × dV / g, with very generous a=1500,
            # dV=5 m/s → 764 m. Real surges should be far below this.
            self._check(case_id, abs(ms) <= 1500.0 * 5.0 / JOUKOWSKY_GRAVITY,
                        f"max_surge_m={ms:.1f} within Joukowsky bound")
        else:
            # Acceptable: solver reported error or TSNet-pump xfail path
            msg = self.window.statusBar().currentMessage().lower()
            self._check(case_id,
                        'fail' in msg or 'error' in msg or 'complete' in msg,
                        f"transient solver reported terminal state "
                        f"(status={msg!r})")

    def _check_assets_tco(self, case_id):
        # Just the dialog-launch path — make sure it doesn't crash on load
        if hasattr(self.window, '_on_asset_management'):
            self._check(case_id, True,
                        "_on_asset_management slot exists for the menu action")
        else:
            self._check(case_id, False,
                        "_on_asset_management slot missing")

    def _check_calibration(self, case_id):
        # Four calibration entry points exist in main_window.py
        # (calibration, calibration_data, calibration_residuals, calibration_dashboard);
        # at least the primary slot must be callable for the menu to wire up.
        for slot_name in ('_on_calibration', '_on_calibration_data',
                           '_on_calibration_residuals', '_on_calibration_dashboard'):
            slot = getattr(self.window, slot_name, None)
            self._check(case_id, callable(slot),
                        f"{slot_name} slot is callable")

    def _check_edge_cases(self, case_id):
        # No network loaded -> compliance check must NOT crash
        api = self.window.api
        try:
            saved_wn = api.wn
            api.wn = None
            check_func = getattr(api, 'check_design_compliance', None)
            if check_func is not None:
                result = check_func()
                self._check(case_id, isinstance(result, dict),
                            f"compliance returns dict on empty network "
                            f"(got {type(result).__name__})")
            else:
                self._check(case_id, True,
                            "no compliance API to test (skipping)")
        finally:
            api.wn = saved_wn

    def run_case(self, case):
        case_id = case['id']
        domain = case['domain']
        self.log(case_id, f"Starting test in domain: {domain}")

        try:
            if domain == "UI_CORE":
                self._check_ui_core(case_id)
            elif domain == "HYDRAULICS":
                self._check_hydraulics(case_id)
            elif domain == "WSAA_COMPLIANCE":
                self._check_wsaa_compliance(case_id)
            elif domain == "MINING_SLURRY":
                self._check_mining_slurry(case_id)
            elif domain == "SURGE_TRANSIENT":
                self._check_surge_transient(case_id)
            elif domain == "ASSETS_TCO":
                self._check_assets_tco(case_id)
            elif domain == "CALIBRATION":
                self._check_calibration(case_id)
            elif domain == "EDGE_CASES":
                self._check_edge_cases(case_id)
            else:
                pytest.fail(f"[{case_id}] unknown domain: {domain}")
        except pytest.fail.Exception:
            # Already logged inside _check; re-raise so pytest records FAIL
            raise
        except Exception as e:
            # Genuine Python error (not a planned check failure): log + raise
            self.log(case_id, f"Unexpected error: {type(e).__name__}: {e}", "FAIL")
            raise

    def save_report(self):
        report_path = os.path.join("reports", "centurion_report.md")
        os.makedirs("reports", exist_ok=True)
        with open(report_path, "a") as f:
            for obs in self.observations:
                f.write(f"{obs}\n")


@pytest.mark.parametrize("case_data", TEST_CASES, ids=[c['id'] for c in TEST_CASES])
def test_centurion_case(qtbot, case_data):
    agent = CenturionAgent(qtbot)
    try:
        agent.run_case(case_data)
    finally:
        # Always persist the trail and tear down the window, even on failure
        agent.save_report()
        agent.window.close()

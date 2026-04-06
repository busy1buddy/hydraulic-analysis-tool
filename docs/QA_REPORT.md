# QA Report -- Cycle 1, Role 3
**Date:** 2026-04-06
**Test baseline:** 1076 tests passing
**Test count after QA:** 1109 tests passing (+33 new)

## Summary

| Category | Findings | Critical | High | Fixed |
|---|---|---|---|---|
| Boundary Testing | 7 crash risks | 4 | 2 | Yes |
| State Machine | 3 vulnerabilities | 1 | 2 | Yes |
| Data Integrity | 3 architecture gaps | 0 | 2 | Documented |
| Concurrency | 1 race condition | 0 | 1 | Yes |
| Cross-Tutorial | 0 issues | 0 | 0 | -- |

## Boundary Testing Findings

### B-001: Zero mu_p crashes bingham_plastic_headloss (CRITICAL -- FIXED)
**File:** slurry_solver.py:125
**Problem:** `Re_B = density * V * diameter_m / mu_p` divides by zero when mu_p=0
**Fix:** Added guard: `if mu_p <= 0: return error dict`
**Test:** test_boundary.py::TestBinghamBoundary::test_zero_mu_p_no_crash

### B-002: Zero density crashes bingham_plastic_headloss (CRITICAL -- FIXED)
**File:** slurry_solver.py:144
**Problem:** `64 / Re_B` divides by zero when Re_B=0 (density=0 makes Re_B=0)
**Fix:** Added guard: `if density <= 0: return error dict`
**Test:** test_boundary.py::TestBinghamBoundary::test_zero_density_no_crash

### B-003: Zero K crashes power_law_headloss (CRITICAL -- FIXED)
**File:** slurry_solver.py:186
**Problem:** Metzner-Reed calculation divides by K, crashes when K=0
**Fix:** Added guard: `if K <= 0 or n <= 0: return error dict`
**Test:** test_boundary.py::TestPowerLawBoundary::test_zero_K_no_crash

### B-004: Zero mu_fluid crashes settling_velocity (CRITICAL -- FIXED)
**File:** slurry_solver.py:499
**Problem:** Stokes formula `(d^2 * delta_rho * g) / (18 * mu_fluid)` divides by zero
**Fix:** Added guard: `if mu_fluid <= 0: return error dict`
**Test:** test_boundary.py::TestSettlingBoundary::test_zero_mu_fluid_no_crash

### B-005: Zero n crashes power_law_headloss (HIGH -- FIXED)
**File:** slurry_solver.py:186-188
**Problem:** n=0 in exponent calculations causes divide-by-zero in `(3*n+1)/(4*n)`
**Fix:** Covered by B-003 guard
**Test:** test_boundary.py::TestPowerLawBoundary::test_zero_n_no_crash

### B-006: Negative inputs accepted without error (HIGH -- FIXED)
**Problem:** Negative mu_p, K, mu_fluid are physically invalid but were silently accepted
**Fix:** All guards check `<= 0` not just `== 0`
**Tests:** test_negative_mu_p_no_crash, test_negative_K_no_crash, test_negative_mu_fluid_no_crash

### B-007: Extreme flow produces finite results (PASS)
**Test:** test_boundary.py::TestBinghamBoundary::test_extreme_flow_finite
100 m3/s through DN200 produces very high but finite headloss.

## State Machine Findings

### SM-001: Stale results after loading new file (CRITICAL -- FIXED)
**File:** desktop/main_window.py:718-737
**Problem:** Loading a new .inp file did not clear `_last_results`. Results from File A displayed for File B.
**Fix:** Added `self._last_results = None` and table row clearing after `load_network_from_path()`
**Test:** test_state_machine.py::TestAnalysedToLoaded::test_load_new_file_clears_results

### SM-002: Concurrent analysis runs not blocked (HIGH -- FIXED)
**File:** desktop/main_window.py:969
**Problem:** User could start a second analysis while one was running, causing data corruption.
**Fix:** Added `if self._worker.isRunning(): return` guard with status message.
**Test:** test_state_machine.py::TestConcurrentAnalysis::test_concurrent_guard_message

### SM-003: Dangling worker on app close (HIGH -- FIXED)
**File:** desktop/main_window.py:2083
**Problem:** Closing the app while analysis was running left worker thread dangling.
**Fix:** Added `self._worker.quit(); self._worker.wait(1000)` in closeEvent.

## Data Integrity Findings (Documented, Not Fixed)

### DI-001: .hap project format incomplete (HIGH -- DEFERRED)
**Problem:** .hap saves only metadata pointers (inp_path, empty scenarios, empty last_run). No actual results or scenario data persisted.
**Impact:** Users cannot save and reload analysis results between sessions.
**Status:** Architecture limitation -- needs design decision on format.

### DI-002: No .hap loader (HIGH -- DEFERRED)
**Problem:** `_save_hap()` exists but no corresponding `_load_hap()` to restore project state.
**Status:** Requires design for result serialization format.

### DI-003: GeoJSON omits pumps and valves (MEDIUM -- DEFERRED)
**Problem:** `export_geojson()` exports junctions and pipes but skips pumps, valves.
**Status:** Low risk for typical use cases (pipe network analysis).

## State Transition Coverage

| From | Action | To | Guard | Test |
|---|---|---|---|---|
| EMPTY | F5 | EMPTY | Warning dialog | test_run_steady_from_empty |
| EMPTY | F6 | EMPTY | Warning dialog | test_run_transient_from_empty |
| EMPTY | Slurry toggle | EMPTY | Status message | test_slurry_toggle_from_empty |
| LOADED | F5 | ANALYSED | Runs analysis | test_run_steady_populates_results |
| ANALYSED | Load file | LOADED | Clears results | test_load_new_file_clears_results |
| ANY | Analysis running | Blocked | Status message | test_concurrent_guard_message |
| LOADED | Slurry on | SLURRY_ON | Status update | test_slurry_on_updates_status |
| SLURRY_ON | Slurry off | LOADED | Reverts | test_slurry_off_reverts |
| ANY | Ctrl+Z | Same | No-op if empty | test_undo_from_no_edits |
| ANY | Ctrl+Y | Same | No-op if empty | test_redo_from_no_edits |

## New Test Files

| File | Tests | Coverage |
|---|---|---|
| tests/test_boundary.py | 23 | Slurry solver, pipe stress, API boundary conditions |
| tests/test_state_machine.py | 11 | Application state transitions and guards |

## Highest-Risk Untested Code Paths

1. **Transient analysis with invalid valve parameters** (closure_time=0, negative start_time) -- TSNet may crash
2. **Live analysis racing with manual analysis** in edit mode -- potential result contamination
3. **NaN/inf propagation** through report generation -- untested edge case
4. **Multiple rapid file loads** -- could the UI get confused if loading files faster than WNTR can parse?

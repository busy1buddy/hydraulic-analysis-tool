# Architecture Review -- Cycle 1, Role 6
**Date:** 2026-04-06

## Summary

| Category | Finding | Severity | Count |
|----------|---------|----------|-------|
| Exception Handling | Bare `except Exception:` in desktop/ | HIGH | 47 |
| Function Size | Functions > 80 lines | MEDIUM | 11 |
| Testing | Placeholder `assert True` tests | MEDIUM | 2 |
| Dependencies | fpdf2 missing from desktop requirements | MEDIUM | 1 |
| Dependencies | EPyT unused | LOW | 1 |
| API Contract | wn=None handling | GOOD | 14/19 guarded |
| Return Consistency | All run_*() return dicts | GOOD | -- |

## Dependency Audit

### requirements.txt
- wntr: Active, core solver
- tsnet: Active, transient analysis
- epyt: **UNUSED** -- never imported anywhere (CLAUDE.md notes this as known)
- fpdf2: Active, PDF report generation
- python-docx: Active, DOCX report generation

### requirements_desktop.txt
- **Missing:** fpdf2 -- causes ImportError for PDF reports when installed standalone
- reportlab listed but may be redundant if fpdf2 is the actual PDF library

## Code Quality -- Top Issues

### 1. Bare Exception Handlers (47 instances in desktop/)
Most are in main_window.py (11), network_canvas.py (11), canvas_editor.py (7).
These silently swallow errors making field debugging impossible.
**Status:** Deferred to next cycle -- widespread change, needs systematic approach.

### 2. Oversized Functions
- `_setup_menus()`: 265 lines -- creates 50+ menu items
- `_setup_dock_panels()`: 175 lines
- `run_design_compliance_check()`: 177 lines
- `compute_quality_score()`: 153 lines
**Status:** CLAUDE.md notes epanet_api.py size as accepted tradeoff. UI setup
functions are initialization-only and rarely change.

### 3. Placeholder Tests
- test_eps.py:202 -- `assert True`
- test_ui_smoke.py:114 -- `assert True`
**Status:** Low risk -- these are smoke tests, not calculation verification.

## API Contract Verification

All public HydraulicAPI methods:
- Return dicts (never None or bare values) -- PASS
- 14/19 check self.wn is None -- PASS (5 are helpers called after public methods)
- Unit information in return keys (pressure_m, velocity_ms, flow_lps) -- PASS
- Error handling returns `{'error': 'message'}` -- PASS

## Test Architecture

- 84 test files, ~1109 tests
- External ground truth: test_epanet_verification.py validates against EPA reference networks
- Hand calculation verification: test_hydraulic_benchmarks.py, D7 diagnostic
- 33 new boundary/state machine tests added this cycle
- No circular self-verification in core calculation tests

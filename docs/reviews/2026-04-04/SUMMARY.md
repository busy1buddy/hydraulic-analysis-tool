# Review Cycle Summary — 2026-04-04 (v1.3.0)

## Findings by Severity

| Severity | Count | Source |
|----------|-------|--------|
| BLOCKER | 7 | Code Review (2), UI Review (5) |
| HIGH | 11 | Architect (1), Code Review (3), UI Review (7) |
| MEDIUM | 14 | Architect (1), Code Review (0*), UI Review (12), Hydraulic (1) |
| LOW | 11 | Code Review (3), UI Review (5), Hydraulic (3) |
| **Total** | **43** | |

*Code review MEDIUM findings all resolved on inspection.

## BLOCKER Items (must fix before release)

### B1 — CLI wave speed default 1000 m/s (Code Review)
- epanet_api.py:1830 — `--wave-speed default=1000` should be 1100
- AS 2280 violation: underestimates transient surge by ~10%

### B2 — run_pump_trip() wave speed=1000 (Code Review)
- epanet_api.py:1108 — default param shadows DEFAULTS dict
- Same issue in run_pump_startup():1155

### B3-B7 — Bare floats without units in UI tables (UI Review)
- Error messages expose Python exception types (6 files)
- Fire flow, scenario, calibration, rehab tables show numbers without units
- analysis_worker error includes type(e).__name__

## HIGH Items (fix before professional release)

### H1 — Desktop imports reports/ directly (Architect)
- desktop/report_dialog.py:91,113 violates layer architecture

### H2 — Age score magic number (Code Review)
- epanet_api.py:1733 — needs DESIGN_LIFE_YEARS constant

### H3 — MGA coordinate bounds not named constants (Code Review)
- gis_basemap.py:54-56

### H4-H10 — Missing units in multiple UI panels (UI Review)
- Rehab dialog, water quality, pressure zones, pipe stress, properties panel

## Top 3 Recommended Actions

1. **Fix wave speed defaults** (B1, B2) — Safety-critical. Change CLI default to 1100, change method signatures to `wave_speed=None` so DEFAULTS dict is used.

2. **Add units to all displayed values** (B3-B7, H4-H10) — Professional quality. Every number in every table needs its unit suffix ("m", "LPS", "m/s", etc).

3. **Sanitize error messages** (B3) — Replace `type(e).__name__: {e}` with engineer-friendly messages in all 6 dialog files and analysis_worker.

## Data Validation: PASS
- 58/58 pipe database checks pass
- All AS/NZS standards verified

## Hydraulic Benchmarks: PASS
- 74/74 benchmark tests verified correct
- EPA Net1/Net2/Net3 zero-difference match
- Bingham/Joukowsky/stress formulas correct

## Architecture: MOSTLY CLEAN
- 21/22 desktop files comply with layer rules
- 1 violation: report_dialog.py imports reports/ directly

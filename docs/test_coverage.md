# Test Coverage Summary

**Total: 280 tests passing, 12 xfail (TSNet pump stability)**

## Test Files

### tests/test_ui_interactive.py — 78 tests
Full headless UI interaction tests (QT_QPA_PLATFORM=offscreen).

| Class | Tests | Coverage |
|-------|-------|---------|
| TestMenuCompleteness | 12 | All 6 menus, every action exists, slurry toggle, File>New clears state, View toggles, Reset Layout |
| TestProjectExplorer | 9 | Root node, Junctions(7), Pipes(9), Reservoirs(1), Tanks(1), click junction/pipe/reservoir populates Properties |
| TestResultsTableCompleteness | 16 | 7 junction rows, 9 pipe rows, all IDs present, P4/P8 velocity red, P1/P5 not red, unit headers, pipe stress 9 rows, SF range 1.5-20, WSAA status |
| TestScenarioPanel | 8 | Base exists, add/duplicate/delete/cannot-delete-base, tree display, run-all, comparison table |
| TestCanvasInteractions | 11 | Click J1/J7/R1/T1, all 9 pipes, 5 color modes, fit padding >10%, labels on/off, node/pipe counts |
| TestSlurryParameterValidation | 6 | Zero yield, small yield, density/Reynolds, slurry>water for all pipes, zero flow, toggle label |
| TestReportGeneration | 4 | DOCX >10KB, PDF >1KB, report contains node/pipe counts, no bare floats |
| TestErrorHandling | 5 | Steady/transient/report without network (warnings), save without file, error handler |
| TestWindowState | 7 | Docks not closable, properties/results visible after restore, scene click connected, pipe click works, min size, HAP save/load |
| TestFullWorkflow | 1 | Load -> steady -> click P4 -> report -> slurry comparison -> WSAA label (end-to-end) |

### tests/test_hydraulic_benchmarks.py — 17 tests
Hydraulic calculation benchmarks from review cycle.

| Benchmark | Tests | Tolerance |
|-----------|-------|-----------|
| Joukowsky | 2 | Head ±0.5 m, pressure ±10 kPa |
| Hoop stress | 1 | ±0.01 MPa |
| Von Mises | 1 | ±0.5 MPa |
| Barlow wall | 2 | ±0.1 mm |
| Mass balance | 1 | ±0.01 LPS per junction |
| Bingham baseline | 2 | ±5% of Hagen-Poiseuille, Darcy >0.020 m |
| Hazen-Williams | 1 | ±5% of hand calc |
| Pump affinity | 2 | ±1% ratio, ±0.5 m head |
| V=Q/A | 1 | ±0.01 m/s all pipes |
| WSAA thresholds | 4 | Exact match |

### tests/test_api_core.py — 15 tests
API init, network load/create, Joukowsky, JSON export.

### tests/test_api_steady.py — 10 tests
Steady-state pressures, flows, velocities, compliance.

### tests/test_api_transient.py — 12 tests
Transient surge, compliance, mitigation, error handling.

### tests/test_compliance.py — 6 tests
WSAA pressure/velocity thresholds, PN35 rating.

### tests/test_fire_flow.py — 6 tests
Fire flow analysis, residual pressures, demand restore.

### tests/test_slurry_solver.py — 12 tests
Bingham plastic, power law, Herschel-Bulkley, network analysis.

### tests/test_pipe_stress.py — 8 tests
Hoop, von Mises, Barlow, full analysis, transient factor.

### tests/test_pipe_database.py — 12 tests
Material lookup, sizes, roughness aging, wave speed.

### tests/test_pump_curves.py — 14 tests
Pump head/efficiency, speed reduction, system curve, operating point, recommendation.

### tests/test_pump_transient.py — 15 tests (12 xfail)
Pump trip/startup (xfail: TSNet numerical stability), error handling.

### tests/test_scenarios.py — 7 tests
Scenario creation, pipe upsize, demand growth, comparison.

### tests/test_reports.py — 9 tests
DOCX/PDF generation, sections, tables, cover page, transient reports.

### tests/test_importers.py — 5 tests
CSV import, shapefile/DXF dependency checks.

### tests/test_nicegui_app.py — 7 tests
Legacy NiceGUI app structure, theme, network plot.

### tests/test_3d_scene.py — 33 tests
3D scene color interpolation, material detection, EPS animator, measurement.

### tests/test_server.py — 8 tests
Legacy FastAPI endpoints.

### tests/test_usability.py — 7 tests
End-to-end workflows, network discovery, Joukowsky scenarios.

### tests/test_water_quality.py — 5 tests
Water age analysis, stagnation risk, duration restore.

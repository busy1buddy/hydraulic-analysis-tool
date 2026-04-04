# Build Progress

## Phase -1 — Expanded CLAUDE.md (2026-04-04)
- Rewrote CLAUDE.md with all 8 sections: Project Identity, Architecture Layers, Unit Conventions, Hydraulic Domain Rules, GodMode Orchestration, Code Conventions, Known Deferred Items, File/Path Conventions
- Established PyQt6 as target UI framework (replacing NiceGUI)
- Encoded all 7 blocker constraints as permanent domain rules
- Defined agent routing, parallel dispatch, and self-review gate

## Phase 0 — Fix all 7 blockers (2026-04-04)
- B1: Fixed slurry friction factor from Fanning (16/Re) to Darcy (64/Re) in slurry_solver.py
- B2: Fixed transient compliance to use gauge pressure (total_head - elevation) in both valve and pump paths
- B3: Fixed water age units — WNTR returns seconds, now divides by 3600 before comparing to 24-hour threshold
- B4: Fixed PVC OD per AS/NZS 1477 series (DN100->110, DN200->225, DN250->280, DN300->315, DN375->400), concrete HW-C by size (DN375/450->110, DN600/750->100, DN900->90), DI wave speeds >= 1100, added DN500 DI, fixed DI internal diameters
- B5: Fixed slurry pump motor ratings (SLP-200-30: 45->22 kW, SLP-400-50: 110->75 kW) for realistic shaft/motor ratios
- B6: Removed direct wntr import from network_editor.py and scenario_manager.py, added CRUD methods to HydraulicAPI, routed all mutations through API
- B7: Fixed velocity to use abs(flow).max() for reversing pipes, added zero-area guard
- PE100 yield fixed from 10 to 20 MPa in pipe_stress.py
- Created scripts/validate_pipe_db.py — 58/58 checks pass
- All 185 tests pass, 12 xfail (known TSNet pump stability)

## Phase 1 — PyQt6 Walking Skeleton (2026-04-04)
- Created desktop/main_window.py: QMainWindow with 6 menus (File, Analysis, Tools, Reports, View, Help)
- Three dock panels: Project Explorer (tree), Properties (table), Results (node/pipe tables)
- Status bar: Analysis Type | Nodes: N | Pipes: N | WSAA: --
- File > Open loads .inp via HydraulicAPI, populates explorer tree
- File > Save/Save As supports .hap JSON project format
- Dark theme (Catppuccin Mocha) via stylesheet
- Entry point: main_app.py (accepts .inp as CLI argument)
- Created requirements_desktop.txt
- All 185 tests pass

## Phase 2 — Interactive Network Canvas (2026-04-04)
- Created desktop/network_canvas.py: PyQtGraph-based 2D network view
- Nodes as circles (junctions), squares (reservoirs/tanks), with click selection
- Pipes as lines with color overlays
- 5 color modes: WSAA Compliance, Pressure, Velocity, Headloss, Status
- WSAA compliance overlay: green/orange/red based on pressure and velocity thresholds
- Color legend widget, zoom/pan/fit, labels toggle
- Canvas element selection updates Properties panel
- All 185 tests pass

## Phase 6 — Packaging and Installer (2026-04-04)
- Created hydraulic_tool.spec: PyInstaller spec with --onedir mode
- Hidden imports for WNTR, TSNet, PyQt6, scipy, all domain modules
- Data files bundled: au_pipes.py, pump_curves.py, models/*.inp, reports/
- Created build.bat: one-command build script
- Created installer/setup.iss: Inno Setup with .hap and .inp file associations
- Desktop shortcut, Start Menu entry, uninstaller
- All 185 tests pass, 12 xfail (known TSNet pump stability)

## Track 2.5 — Fire Flow Wizard UI (2026-04-04)
- Created desktop/fire_flow_dialog.py: WSAA fire flow analysis wizard
- Single-node mode: select junction, specify flow (25 LPS) and min residual (12 m), run
- Sweep mode: test all junctions, build fire flow availability map
- Results table: junction, residual pressure, required, PASS/FAIL with colour coding
- Canvas integration: sweep results update canvas colour variable
- Menu: Analysis > Fire Flow Wizard (F8)
- Tested on fire_flow_demand tutorial: 9/10 nodes pass at 25 LPS / 12 m

## Track 1.3 — Error Handling Sweep (2026-04-04)
- Tested 15 crash paths: malformed .inp, binary garbage, non-existent file, no-network steady/transient/EPS/report/patterns, negative elevation, zero-length pipe, zero-diameter pipe, save with no file, error handler, editor with no network, undo empty stack
- 15/15 PASS — no crashes on any boundary condition
- All error paths show QMessageBox warnings or handle gracefully

## Track 1.1 — Visualisation Audit (2026-04-04)
- Ran all 10 tutorials through full UI pipeline: load, analyse, colourmap, value overlay, scaling, labels, fit, all colour modes
- 0 issues found across all 10 tutorials
- All tutorials: canvas nodes/pipes match expected, results tables populated, stress table correct, WSAA label set
- ColourMapWidget (Viridis/Plasma/RdBu/RdBu/Jet) renders without crash on all networks
- Value overlay, pipe DN scaling, node demand scaling all functional
- Fit view produces finite ranges on all coordinate layouts

## Phase 5 — Reports, Audit Trail, Quality Review, Pipe Stress (2026-04-04)
- Created desktop/report_dialog.py: report builder with section checklist, DOCX/PDF generation
- Created desktop/audit_trail.py: auto-logs every analysis run with .inp snapshot, parameters, results, compliance summary
- Created desktop/pipe_stress_panel.py: hoop/von Mises/safety factor per pipe, red highlights for SF < 1.5
- Report dialog with 7 section checkboxes, project info, one-click generate
- Audit trail stores to docs/audit/{YYYY-MM-DD}/{HHMMSS}/
- Pipe stress panel integrated into Results dock with material detection from roughness
- PE100 yield corrected to 20 MPa (AS/NZS 4130)
- All 185 tests pass

## Phase 4 — Scenario Comparison (2026-04-04)
- Created desktop/scenario_panel.py: scenario management with create/edit/duplicate/delete
- ScenarioData: stores demand multiplier, modifications, results
- ScenarioDialog: form for name and demand multiplier
- ScenarioComparisonTable: side-by-side min/max pressure, max velocity, WSAA issues
- Run All: executes all scenarios sequentially, updates comparison table
- Scenario dock tabified with Project Explorer on left
- Base scenario results shown on canvas after run-all
- All 185 tests pass

## Phase 3 — Analysis Integration (2026-04-04)
- Created desktop/analysis_worker.py: QThread worker for background analysis
- Supports steady-state, transient, and slurry analysis modes
- Progress bar in status bar during solve
- On finish: canvas colors update, results tables populate, WSAA status updates
- On error: QMessageBox with human-readable message
- Node results table: ID, Elevation, Pressure, Head, WSAA Status (PASS/FAIL with standard ref)
- Pipe results table: ID, Diameter (DN), Length, Velocity, Headloss (m/km)
- Slurry mode toggle integrates slurry_solver.py for Bingham plastic headloss
- WSAA compliance summary in status bar with pass/fail coloring
- All 185 tests pass

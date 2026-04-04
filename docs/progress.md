# Build Progress

## v1.3.0 Release (2026-04-04)
- C2: Pressure zone management — zone CRUD API, auto-detect by elevation, zone balance analysis, PRV recommendations, canvas overlay, full dialog UI
- C3: GIS background map — OpenStreetMap tile layer, MGA2020 + lat/lon coordinate detection, tile caching, basemap toggle in View menu
- C4: Rehabilitation prioritisation — pipe condition CSV import, weighted scoring (age/condition/breaks/hydraulics), CRITICAL/HIGH/MEDIUM/LOW risk ranking
- C5: Report improvements — executive summary with compliance overview, key metrics table, recommended actions, PDF colour-coded cells, alternating rows
- Self-directed: requirements.txt updated with all missing deps (PyQt6, pyqtgraph, python-docx, fpdf2, anthropic)
- Self-directed: ROADMAP.md updated to reflect all resolved limitations
- Self-directed: docs/USER_TESTING.md — comprehensive first-time engineer testing guide (8 scenarios)
- 540 tests passing (+36 new), 12 xfailed (TSNet pump stability)

## v1.2.0 Release (2026-04-04)
- C1: Calibration tools — import CSV measurements, R²/RMSE/NSE statistics, scatter plot, canvas highlighting
- C6: Session persistence — save/restore last file, window size, slurry mode, colour mode
- C7: Network statistics panel — pipe length, demand, material summary, WSAA compliance counts
- C8: Keyboard shortcuts dialog (already built in A6)
- Review bridge rewritten: Anthropic API direct (1.5s vs 45-120s subprocess)
- 504 tests passing

## Continuous Improvement (2026-04-04)
- Fixed Joukowsky pressure rise: now uses actual fluid density (was hardcoded rho=1000). Slurry pressure rise is proportionally higher. Added density parameter + slurry benchmark test.
- Added minimum velocity compliance check: 0.6 m/s per WSAA, flags sediment deposition risk as INFO
- Fixed Herschel-Bulkley + Power Law laminar friction: Fanning (16/Re) → Darcy (64/Re), Dodge-Metzner turbulent × 4
- Default wave speed: 1000 → 1100 m/s (AS 2280 minimum for DI)
- Canvas render performance: 8236ms → 68ms (121x speedup via batched pipe rendering)
- Enriched reviewer prompt with all domain knowledge from validation work
- Formula audit: 21 items verified against published standards (docs/validation/formula_audit.md)
- 468 tests passing

## A5 — Probe Tool (2026-04-04)
- Created desktop/probe_tooltip.py: ProbeTooltip(QWidget) with dark semi-transparent background (#1e1e2e, 0.9 opacity) and rounded corners
- Shows all result variables: junction (Type, ID, Elevation, Demand, Pressure min/avg/max, Head, WSAA Status) and pipe (Type, ID, DN, Length, Velocity, Flow, Headloss, Roughness)
- Fixed-width Consolas font, white/coloured text; value colours reflect WSAA compliance (green/amber/red)
- Disappears on Escape or next probe click; positions near click point avoiding screen edges
- Added "Probe" checkable button to canvas toolbar with tooltip
- Wired probe_requested signal in NetworkCanvas; canvas.set_probe_mode() routes clicks to ProbeTooltip instead of Properties panel
- ProbeTooltip lazy-created in MainWindow._probe_tooltip

## A6 — UX Polish (2026-04-04)
- Added tooltips to all canvas toolbar buttons: Fit, Labels, Edit, Values, Probe
- Added File > Open Tutorial... (opens QFileDialog starting in tutorials/ directory)
- Added Help > Keyboard Shortcuts (F1) showing all shortcuts in a QMessageBox
- All "Load a network first" error messages updated to actionable form: "No network loaded. Use File > Open (Ctrl+O) to load an .inp file."
- Added setToolTip to WSAA status label explaining PASS/FAIL and how to compute it
- Added drag-and-drop .inp file support: dragEnterEvent/dropEvent on MainWindow

## A7 — Escape / Probe Dismiss (2026-04-04)
- keyPressEvent updated: Escape hides probe tooltip (if visible) before cancelling pipe creation
- Probe mode toggle button deactivation also hides tooltip

## A8 — Docs Update (2026-04-04)
- Updated docs/progress.md with A5–A8 entries

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

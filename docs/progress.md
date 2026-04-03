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

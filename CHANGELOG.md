# Changelog

All notable changes to the Hydraulic Analysis Tool.

## [v2.0.0] — 2026-04-04

### Added
- **Pump failure impact analysis**: simulate power loss at any pump station, report affected customers and pressure drops
- **Quick network assessment**: comprehensive evaluation of unknown networks in seconds (topology, resilience, quality score, diagnostics, recommendations)
- **Mining slurry design workflow**: complete step-by-step guide for slurry pipeline design

### Changed
- REST API now includes `/api/assessment` endpoint
- Tools menu: added Quick Assessment (F10)

## [v1.9.0] — 2026-04-04

### Added
- **Todini resilience index** as first-class metric: status bar display, dashboard KPI card, compliance certificate inclusion, benchmarked across all 10 tutorials
- **Quality score system**: 0-100 scoring across 6 categories (pressure, velocity, resilience, stress, data, connectivity) with A-F grades
- **Demand pattern library**: 8 built-in patterns (WSAA residential/commercial, industrial, irrigation, hospital, school term/holiday, mining process) with apply/save/custom
- **Advanced slurry design**: Wasp critical velocity model, pump derating (Wilson et al. 2006), per-pipe settling risk analysis report
- **Enhanced network comparison**: categorised changelog (added/removed/resized/demand changed) with colour codes
- **Auto tutorial generator**: generates README.md with topology, results, and suggested workflow from any .inp file
- **Dashboard enhancements**: resilience KPI, dead ends, loops, bridges cards

## [v1.8.0] — 2026-04-04

### Added
- **Design compliance certificate**: formal WSAA compliance check with PDF export (Analysis > Design Compliance Check, F9)
- **Network topology analysis**: dead ends, bridges (Tarjan's algorithm), loops (cyclomatic complexity), connectivity ratio
- **Hydraulic fingerprint**: pressure/velocity statistics, energy dissipation index, Todini resilience index
- **Smart error recovery**: `diagnose_network()` with actionable suggestions for common problems
- **REST API**: lightweight HTTP server with 11 endpoints for remote/programmatic access
- **Batch analysis**: run configurable analyses across multiple .inp files

## [v1.7.0] — 2026-04-04

### Added
- K1: Coverage audit (epanet_api.py 78%, slurry_solver.py 93%, pipe_stress.py 97%)
- K2: Integration test suite — 20 end-to-end workflow tests across 5 engineer workflows

## [v1.6.0] — 2026-04-04

### Added
- Network Health Dashboard: at-a-glance KPI cards (pressure, velocity, compliance traffic lights)
- 3D network visualisation: PyQtGraph OpenGL with elevation Z-axis and WSAA colours
- Advanced slurry: settling velocity (Stokes/Schiller-Naumann/Newton), Durand deposition velocity, Rouse profiles
- Report template system: 3 defaults (Standard/Executive/Technical), custom save/load
- Report scheduler: Windows Task Scheduler integration

## [v1.5.0] — 2026-04-04

### Added
- Water hammer protection sizing: bladder accumulator (Boyle's law), flywheel inertia, Thorley references
- Monte Carlo uncertainty: N simulations, roughness/demand CV, per-node failure probability
- Asset deterioration modelling: Gompertz curves by material, failure year prediction
- SCADA replay: import CSV demands, run EPS with actual measured patterns
- Pipe cost database editor: custom costs, CSV import
- Chlorine booster station design: deficiency detection, dosing, WSAA 0.2 mg/L threshold

## [v1.4.0] — 2026-04-04

### Added
- Pipe profile longitudinal section: HGL, invert, pressure chart with path selection
- Pump operating point: pump curve + system curve intersection, BEP warnings
- Network skeletonisation: dead-end removal, series pipe merging, equivalent pipes
- Leakage detection: ILI index, WSAA performance category, MNF method
- Sensitivity analysis: one-at-a-time roughness/demand variation, impact ranking
- Network reliability: single-pipe failure simulation, criticality index

## [v1.3.0] — 2026-04-04

### Added
- Split-screen scenario comparison with linked viewports and difference mode
- GIF/MP4 animation export with progress dialog
- Auto-calibration: scipy.optimize roughness optimisation by material group
- Surge protection wizard: vessel sizing, air valve placement, slow-closing valve
- Percentile clip on colourbar
- Fire flow sweep QThread (replaced processEvents)
- Project bundle: .hydraulic ZIP export/import
- Network comparison: topology diff, property changes
- Demand forecasting: linear/exponential/logistic growth, WSAA failure year
- Pipe sizing optimisation: Rawlinsons cost database, iterative upsizing

### Fixed
- Review cycle: 43 findings, 7 blockers fixed (wave speed, UI units, error messages)
- PyInstaller rebuilt (94 MB exe)

## [v1.2.0] — 2026-04-04

### Added
- Calibration tools: CSV import, R²/RMSE/NSE statistics, scatter plot, canvas highlighting
- Session persistence: save/restore last file, window size, slurry mode, colour mode
- Network statistics panel: pipe length, demand, material summary, WSAA compliance counts

### Changed
- Review bridge rewritten: Anthropic API direct (1.5s vs 45-120s subprocess)

## [v1.1.0] — 2026-04-04

### Fixed
- Joukowsky pressure rise uses actual fluid density (was hardcoded 1000 kg/m³)
- Minimum velocity compliance: 0.6 m/s per WSAA, flags sediment deposition risk
- Herschel-Bulkley + Power Law: Fanning (16/Re) corrected to Darcy (64/Re)
- Default wave speed: 1000 → 1100 m/s (AS 2280 minimum for DI)
- Canvas render: 8236ms → 68ms (121x speedup via batched pipe rendering)

### Added
- Formula audit: 21 items verified against published standards

## [v1.0.0] — 2026-04-04

### Added
- PyQt6 desktop application with dark theme (Catppuccin Mocha)
- Interactive network canvas: PyQtGraph 2D with 5 colour modes
- Steady-state, transient, and EPS analysis via WNTR/TSNet
- Slurry mode: Bingham plastic headloss, non-Newtonian rheology
- Scenario management: create, compare, run-all
- Report generation: DOCX and PDF with compliance tables
- Pipe stress panel: hoop/von Mises/safety factor
- Audit trail: automatic logging of all analysis runs
- Fire flow wizard: single-node and sweep modes
- Canvas editor: add/delete nodes and pipes
- Probe tooltip: detailed element inspection
- 185 tests passing

## Known Limitations

- TSNet transient analysis may crash on some pump configurations (known solver instability, marked xfail in tests)
- GIS basemap requires internet for OpenStreetMap tile download
- 3D view requires OpenGL support (may not work in remote desktop)
- Elevated tank and pump-only networks show Todini Ir=0.0 (mathematically correct but not meaningful for tank-dominant systems)
- REST API is single-threaded — not suitable for high-concurrency production use
- Pump derating for slurry is simplified — use manufacturer data for final design

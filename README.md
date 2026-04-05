# Hydraulic Analysis Tool v2.6.1

Professional hydraulic analysis desktop application for Australian water supply and mining engineers. Combines EPANET steady-state, TSNet transient, and non-Newtonian slurry solvers with WSAA compliance checking, network visualisation, and automated reporting.

Built to rival PumpSim ($15K), AFT Fathom ($10K), and WaterGEMS ($15K) — at zero cost.

**1012 automated tests | 11 tutorial networks | Australian standards built-in**

## What's New in v2.5-v2.6

- **Safety Case Report** — formal regulatory output with Joukowsky
  surge, water hammer 2L/a, optional slurry settling, SHA-256 audit
  hash, signature block disclaimer. `Analysis > Safety Case Report...`
- **Root Cause Analysis** — traces WSAA violations to limiting pipes,
  ranks fixes (upsize vs parallel main) with AUD unit costs
- **Live Sensitivity Panel** — sliders for demand, roughness, source
  head with 150 ms debounced re-analysis
- **Network Validator** — pre-analysis integrity check for isolated
  nodes, disconnected subgraphs, missing sources
- **GIS Export** — GeoJSON with WSAA status properties
- **Demand Pattern Wizard** — WSAA diurnal curves
- **Help > Run Demo** — one-click guided tour
- **Pump Efficiency Analysis** — annual energy cost estimates
- **Automated Sensitivity Report** — ranked parameter drivers
- **Emergency Pipe Burst** — rapid 2am ops assessment with actions

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch desktop application
python main_app.py

# 3. Open a network: File > Open (Ctrl+O)
#    Or try a tutorial: File > Open Tutorial

# 4. Run analysis: press F5 (Steady State)

# 5. Check results in status bar:
#    WSAA: PASS/FAIL | Ir: 0.346 (B) | Score: 85/100 (B)
```

## Features

### Hydraulic Analysis
- **Steady-state**: Hazen-Williams via WNTR/EPANET, WSAA compliance
- **Extended Period Simulation**: 24-hour demand patterns with animation
- **Transient / Water Hammer**: Method of Characteristics via TSNet
- **Fire flow**: WSAA 25 LPS @ 12 m residual, sweep all nodes
- **Water quality**: age, chlorine decay, source tracing
- **Sensitivity analysis**: roughness/demand variation, impact ranking
- **Monte Carlo**: uncertainty quantification with N simulations

### Mining & Slurry (First-Class)
- **Non-Newtonian models**: Bingham Plastic, Power Law, Herschel-Bulkley
- **Critical deposition velocity**: Durand (1952) and Wasp (1977) models
- **Settling velocity**: Stokes/Schiller-Naumann/Newton regimes
- **Pump derating**: head and efficiency correction for slurry service (Wilson et al. 2006)
- **Slurry design report**: per-pipe settling risk analysis with safety margins
- **Concentration profiles**: Rouse equation for cross-section distribution

### Network Intelligence
- **Todini resilience index**: 0.0 (no redundancy) to 1.0 (full redundancy), target > 0.3
- **Quality score**: 0-100 across 6 categories, A-F grades
- **Topology analysis**: dead ends, bridges (Tarjan's), loops, connectivity
- **Quick assessment**: comprehensive evaluation of unknown networks in seconds
- **Pump failure impact**: simulate power loss, report affected customers
- **Network diagnostics**: detect problems and suggest fixes
- **Reliability analysis**: single-pipe failure criticality ranking

### Asset Management
- **Rehabilitation prioritisation**: condition scoring with CSV import
- **Deterioration modelling**: Gompertz curves by material, failure year prediction
- **Pipe stress**: hoop/von Mises/safety factor per AS 2280
- **Leakage detection**: ILI index, WSAA performance category
- **Demand forecasting**: linear/exponential/logistic growth to failure year

### Visualisation & Reporting
- **Interactive canvas**: PyQtGraph 2D with 5 colour modes (WSAA, pressure, velocity, headloss, status)
- **3D network view**: PyQtGraph OpenGL with elevation exaggeration
- **Split-screen comparison**: dual canvas with linked viewports
- **Animation**: EPS and transient playback with GIF/MP4 export
- **Reports**: DOCX and PDF with executive summary, compliance tables, colour-coded cells
- **Compliance certificate**: formal design check with PDF export
- **Dashboard**: at-a-glance KPI cards (pressure, velocity, resilience, connectivity)

### Data & Integration
- **REST API**: 11 HTTP endpoints for remote access (`python rest_api.py`)
- **Batch analysis**: run multiple .inp files through configurable pipeline
- **Demand patterns**: 8 built-in (WSAA, commercial, industrial, mining), custom save
- **Project bundles**: .hydraulic ZIP export/import
- **Importers**: CSV, DXF, Shapefile
- **Scenario management**: create, compare, run-all

## Tutorial Networks

| Tutorial | Description | Quality Score |
|----------|-------------|--------------|
| simple_loop | Basic 3-junction loop | 95 (A) |
| dead_end_network | Network with dead-end branches | 92 (A) |
| fire_flow_demand | Residential fire flow design | 90 (A) |
| mining_slurry_line | Slurry pipeline system | 90 (A) |
| rehabilitation_comparison | Before/after pipe replacement | 90 (A) |
| pressure_zone_boundary | Multi-zone with PRVs | 86 (B) |
| industrial_ring_main | Industrial ring main | 80 (B) |
| pump_station | Boosted supply system | 80 (B) |
| elevated_tank | Tank-fed distribution | 61 (C) |
| multistage_pump | Pump test circuit | 56 (D) |

## Project Structure

```
desktop/           PyQt6 application (main UI layer)
epanet_api.py      Core API — single orchestration point
slurry_solver.py   Non-Newtonian rheology solver
pipe_stress.py     Pipe stress calculations (AS 2280)
data/              Australian pipe DB, pump curves, demand patterns
reports/           DOCX and PDF report generators
importers/         CSV, DXF, Shapefile importers
models/            Example .inp network files
tutorials/         10 tutorial networks with documentation
tests/             833 automated tests
rest_api.py        HTTP API server
docs/              Validation, progress, user testing
```

## Testing

```bash
python -m pytest tests/ -v                     # Full suite (833 tests)
python -m pytest tests/ -k "not transient"     # Exclude TSNet (794 tests)
python -m pytest tests/test_slurry_solver.py   # Slurry tests only
python scripts/validate_pipe_db.py             # Pipe database validation
```

## Standards

All compliance checks reference specific Australian standards:

| Standard | Coverage |
|----------|----------|
| WSAA WSA 03-2011 | Pressure (20-50 m), velocity (<2.0 m/s), fire flow (25 LPS @ 12 m) |
| AS 2280 | Ductile iron pipes, PN25/PN35 |
| AS/NZS 1477 | PVC pipes, PN12/PN18 |
| AS/NZS 4130 | PE/HDPE pipes, SDR11 PN16 |
| AS 4058 | Concrete pipes |

## Keyboard Shortcuts

| Key | Action | Key | Action |
|-----|--------|-----|--------|
| Ctrl+O | Open file | F5 | Steady State |
| Ctrl+S | Save | F7 | Extended Period |
| F1 | Help | F8 | Fire Flow |
| F9 | Compliance Check | F10 | Quick Assessment |

## Known Limitations

- TSNet transient analysis may crash on some pump configurations (known solver instability)
- GIS basemap requires internet for OpenStreetMap tiles
- 3D view requires OpenGL (may not work in remote desktop sessions)
- Todini index returns 0.0 for tank-only networks (mathematically correct, not meaningful)
- REST API is single-threaded, not for high-concurrency production use
- Pump derating for slurry is simplified — use manufacturer data for final design
- Water quality analysis requires sufficient simulation duration for convergence

## Citation

When referencing this tool in engineering reports:

> Hydraulic Analysis Tool v2.0.0 (2026). Open-source hydraulic, transient, and slurry analysis platform. Analysis performed using WNTR (Klise et al. 2018) and TSNet (Shi & O'Callaghan 2020) solvers with WSAA WSA 03-2011 compliance checking.

## vs Commercial Software

| Feature | This Tool | PumpSim ($15K) | AFT Fathom ($10K) | WaterGEMS ($15K) |
|---------|-----------|----------------|-------------------|-----------------|
| Steady-state | Yes | Yes | Yes | Yes |
| Water hammer | Yes | No | Separate ($15K) | Add-on |
| Water quality | Yes | No | No | Yes |
| Non-Newtonian slurry | Yes | Yes | Limited | No |
| Compliance certificates | Yes | No | No | Limited |
| Network intelligence | Yes | No | No | Limited |
| REST API | Yes | No | No | No |
| Python scripting | Yes | No | No | No |
| Automated tests | 833 | 0 | 0 | 0 |
| Cost | **Free** | $5-15K/yr | $5-15K/yr | $5-15K/yr |

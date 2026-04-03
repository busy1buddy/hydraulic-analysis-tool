# Changelog

## v1.1.0 - 3D Visualization Enhancement (2026-04-03)

### Phase 1.1: Professional 3D Visualization

All 7 items from the Phase 1.1 roadmap completed:

- **1. Animated Flow Particles**
  - Moving dot particles along pipes showing fluid direction and velocity
  - Particle speed proportional to flow velocity, color intensity shows speed
  - Configurable particles-per-pipe count and animation speed slider
  - Start/Stop toggle with smooth animation via ui.timer

- **2. Pipe Material Textures**
  - Auto-detection of pipe material from roughness (C-factor) or name
  - 8 material types: PVC, PE/HDPE, Ductile Iron, Steel, Concrete, Copper, Cast Iron
  - Color-coded material rendering with accent stripe rings
  - "Material" option added to Color By selector
  - Material legend panel in sidebar

- **3. EPS Result Animation**
  - Play/Pause/Step Forward/Step Back/Reset controls
  - Slider scrubbing through all EPS timesteps
  - Real-time color updates (pressure or velocity) as time progresses
  - Time display (hours) and step counter
  - EPSAnimator class extracts per-timestep data from WNTR results

- **4. Selection Highlighting**
  - Yellow semi-transparent glow overlay on clicked elements
  - Shape-matched highlights (sphere for junctions, box for reservoirs/valves, cylinder for pipes/tanks)
  - Auto-clears previous highlight on new selection
  - Enhanced info panel shows analysis results for selected elements

- **5. Measurement Tool**
  - Toggle measurement mode via toolbar button
  - Click two points to measure 3D, horizontal, and vertical distances
  - Visual markers (magenta spheres) and connecting line drawn in scene
  - Distance label rendered at midpoint in 3D
  - Results displayed in sidebar panel
  - Clear measurements button

- **6. Labels Toggle**
  - Four independent toggle checkboxes: Names, Diameters, Flows, Pressures
  - Names visible by default; others hidden until toggled
  - Labels created during render for all elements with available data
  - Instant show/hide without re-rendering

- **7. Screenshot Export**
  - Camera icon button captures the Three.js canvas
  - Downloads as `epanet_3d_view.png`
  - Works by finding the largest canvas element and calling toDataURL

### UI Enhancements
- Reorganized 3D View toolbar into logical rows (Render, Views+Tools, Labels, Flow Animation, Time Animation)
- Added velocity scale legend and material color legend to sidebar
- Enhanced element info panel with analysis results (pressure, flow, velocity)
- Added tank and valve detail display in info panel

### Test Suite
- **185 tests passing** (28 new), 12 xfailed (TSNet pump stability)
- New test classes: MaterialDetection, EPSAnimator, MeasurementLogic, MaterialStyles, ColorScales

---

## v1.0.0 - PumpSim-Rival Release (2026-04-03)

### Mining & Industrial Capabilities

- **Non-Newtonian / Slurry Solver** (`slurry_solver.py`)
  - Three rheological models: Bingham Plastic, Power Law, Herschel-Bulkley
  - Slurry fluid database with 7 pre-configured fluids (mine tailings 30%/50%, paste fill 70%, cement slurry, polymer solution, drilling mud, water baseline)
  - Settling velocity compliance checks and pipe wear warnings
  - Full network analysis with per-pipe headloss, velocity, flow regime detection
  - Buckingham-Reiner laminar, Wilson-Thomas turbulent, Dodge-Metzner correlations

- **Pump Curve Database & Recommendation Engine** (`data/pump_curves.py`)
  - 7 pump models: 3 water supply, 2 mining dewatering, 2 slurry
  - Full curve data: head-flow, efficiency-flow, power, NPSHr
  - Speed adjustment via affinity laws (RPM percentage)
  - System curve generation (Hazen-Williams + static head)
  - Operating point finder (pump vs system curve intersection)
  - Pump recommendation engine with suitability scoring
  - Filter by application: water, mining, slurry

- **Pipe Stress Calculator** (`pipe_stress.py`)
  - Hoop stress (thin-wall theory), radial stress, axial stress
  - Von Mises equivalent stress for combined loading
  - Barlow's formula for minimum wall thickness design
  - 7 material yield strengths (ductile iron, steel grades, PVC, PE, concrete)
  - Transient surge factor support
  - Safety factor calculations with OK/WARNING/CRITICAL status

### 3D Visualization

- **3D Network Visualization Engine** (`app/components/scene_3d.py`)
  - Three.js rendering via NiceGUI `ui.scene()`
  - Pipes as cylinders with diameter-proportional thickness
  - Color-coded results overlay (pressure, velocity)
  - Node markers: spheres (junctions), cubes (reservoirs), cylinders (tanks), cones (pumps), boxes (valves)
  - Elevation-based 3D layout with configurable vertical exaggeration
  - Orbit camera controls with view presets (Plan, Isometric, Side, Front)
  - Click-to-select element info panel
  - Pressure and velocity color scales with legend

- **3D View Dashboard Tab** (`app/pages/view_3d.py`)
  - Network selector with Load & Render
  - Run Analysis + Color mode (pressure/velocity/default)
  - Element info panel showing properties on click

### Dashboard
- Now **7 tabs**: Steady-State, Transient, Joukowsky, **3D View**, Scenarios, Network Editor, Feedback

### Test Suite
- **157 tests passing**, 12 xfailed (TSNet pump stability)
- New tests: 3D scene, slurry solver, pump curves, pipe stress (40+ new tests)

### Project Metrics
- 71 total files, 53 Python files, 18 test files
- ~9,100 lines of Python code

---

## v0.5.0 - All 7 Features Complete (2026-04-03)

### Release 2: Scenario Comparison & Import System
- **Scenario Manager** (`scenario_manager.py`)
  - Create named scenarios with pipe, roughness, and demand modifications
  - Run and compare scenarios side-by-side
  - Pressure and flow difference calculations
  - Compliance comparison between scenarios
  - NiceGUI page with interactive comparison charts

- **CSV Network Importer** (`importers/csv_import.py`)
  - Import networks from nodes.csv + pipes.csv
  - Supports junctions, reservoirs, tanks, pipes, valves
  - Sample CSV generator for testing
  - Imported networks run correctly in EPANET

- **GIS Shapefile Importer** (`importers/shapefile_import.py`)
  - Import from GIS shapefiles with Australian CRS support (GDA2020/MGA)
  - Auto-maps common attribute name variations
  - Finds nearest nodes for pipe connectivity
  - Requires geopandas (optional dependency)

- **DXF/CAD Importer** (`importers/dxf_import.py`)
  - Import from AutoCAD DXF files
  - Layer-based element detection (PIPES, JUNCTIONS, RESERVOIRS)
  - Snap tolerance for node matching
  - Requires ezdxf (optional dependency)

### Release 3: Pump Transients & Report Generation
- **Pump Transient Analysis** (`run_pump_trip`, `run_pump_startup` in epanet_api.py)
  - Pump station network model (`models/pump_station.inp`)
  - Pump trip (sudden shutdown) and startup analysis
  - Uses TSNet valve closure as proxy for pump events
  - Note: TSNet pump solver has known numerical stability issues (marked xfail in tests)

- **Word Document Reports** (`reports/docx_report.py`)
  - Professional engineering report generation
  - Cover page, network description, results tables, compliance, conclusions
  - Includes steady-state, transient, fire flow, and water quality sections
  - Requires python-docx

- **PDF/HTML Reports** (`reports/pdf_report.py`)
  - HTML-based report that can be printed to PDF
  - Same content structure as DOCX reports
  - Falls back to HTML if fpdf2 not installed

- **Report API** (`generate_report` method + `/api/report` endpoint)

### Release 4: Network Editor
- **Interactive Network Editor** (`app/pages/network_editor.py`)
  - Load, view, and edit network elements in the dashboard
  - Element selector: browse junctions, pipes, reservoirs, tanks, valves
  - Edit properties: elevation, demand, diameter, roughness, length, head
  - Add new junctions and pipes via dialog forms
  - Delete selected elements
  - Save modified network back to .inp file
  - Mode toggle: Select/Edit, Add Junction, Add Pipe

### Dashboard Updates
- **6 tabs** in NiceGUI app: Steady-State, Transient, Joukowsky, Scenarios, Network Editor, Feedback
- Scenario comparison page with side-by-side charts

### Test Suite
- **119 total tests**: 107 passed, 12 xfailed (pump transients - TSNet limitation)
- New test files: test_scenarios.py, test_importers.py, test_pump_transient.py, test_reports.py

---

## v0.3.0 - Phase 1 & 2 Complete (2026-04-03)

### Development Infrastructure
- **6 Claude Code skills** created in `.claude/skills/`:
  - `run-analysis` - Guides steady-state and transient analysis workflow
  - `create-network` - Australian defaults, unit conventions, templates
  - `test-project` - pytest workflow, health checks
  - `dashboard-server` - Preview MCP launch, debugging
  - `add-feature` - Three-layer pattern (API -> endpoint -> UI)
  - `au-engineering` - WSAA standards, pipe properties, AS/NZS references

### Testing Framework
- **89 automated tests** across 9 test files
- Test categories: API core, steady-state, transient, compliance, fire flow, water quality, pipe database, NiceGUI app, server endpoints, usability workflows
- pytest with coverage reporting
- `pyproject.toml` with test configuration

### NiceGUI Dashboard (Phase 2)
- Full migration from HTML/JS to Python-native NiceGUI
- 4 tabs: Steady-State, Transient/Water Hammer, Joukowsky Calculator, **Feedback**
- Dark theme with Plotly.js charts
- Runs on port 8766 (`python -m app.main`)
- All UI code in Python (no inline JavaScript)
- Works offline (no CDN dependencies)
- Legacy FastAPI dashboard preserved on port 8765

### User Feedback Channel
- Built-in Feedback tab in dashboard
- Submit bugs, feature requests, usability issues
- Severity levels and role-based categorization
- Feedback history with status tracking
- Data stored in `output/feedback.json`

### Australian Pipe Database (Release 1)
- `data/au_pipes.py` with properties for 4 materials:
  - Ductile Iron (AS 2280): DN100-DN600
  - PVC (AS/NZS 1477): DN100-DN375
  - PE/HDPE (AS/NZS 4130): DN63-DN630
  - Concrete (AS 4058): DN300-DN900
- Functions: `get_pipe_properties()`, `list_materials()`, `list_sizes()`, `lookup_roughness()`, `lookup_wave_speed()`
- Age-dependent roughness lookup

### New Analysis Types (Release 1)
- **Fire Flow Analysis** (`run_fire_flow()`)
  - Applies fire demand at specified junction
  - Checks WSAA 12m residual pressure requirement
  - Residual pressure bar chart output
  - Restores original demands after analysis

- **Water Quality (Age) Analysis** (`run_water_quality()`)
  - Simulates water age throughout network
  - Flags stagnation risk (>24hr age)
  - Configurable simulation duration
  - Restores original settings after analysis

- New REST endpoints: `/api/fireflow/{file}`, `/api/waterquality/{file}`

### Bug Fixes
- Fixed `sys.stdout` UTF-8 wrapper breaking pytest on Windows
- Fixed WNTR 1.4.0 `base_demand` read-only property (use `demand_timeseries_list[0].base_value`)

---

## v0.2.0 - Documentation & Organization (2026-04-03)

### Project Organization
- Files organized into `models/`, `output/`, `docs/` directories
- All path references updated in Python scripts
- EPANET temp files cleaned up

### Documentation
- `README.md` - Complete project overview
- `docs/USER_GUIDE.md` - 326-line usage guide covering all features
- `docs/MAINTENANCE.md` - 236-line maintenance and troubleshooting guide
- `requirements.txt` - Full dependency list

---

## v0.1.0 - Initial Release (2026-04-03)

### Core Features
- EPANET hydraulic analysis via WNTR 1.4.0
- Transient/water hammer analysis via TSNet 0.3.1 (MOC solver)
- `epanet_api.py` - Unified Python API (HydraulicAPI class)
- `server.py` - FastAPI REST API on port 8765
- `dashboard.html` - Interactive Plotly.js web dashboard
- Australian WSAA compliance checking
- Joukowsky pressure rise calculator
- Standalone analysis scripts

### Network Models
- `australian_network.inp` - 7-junction suburban network
- `transient_network.inp` - 6-junction network with valve V1
- `api_test_network.inp` - Simple 3-node test network

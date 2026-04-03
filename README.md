# EPANET Hydraulic & Slurry Analysis Toolkit

Open-source hydraulic, transient, and slurry analysis platform for water supply and mining engineering. Combines EPANET steady-state and TSNet transient solvers with non-Newtonian rheological models, 3D visualization, and Australian WSAA compliance.

Built to rival commercial tools like PumpSim, AFT Fathom, and WaterGEMS -- at zero cost.

## Quick Start

```bash
pip install -r requirements.txt
python -m app.main
# Dashboard at http://localhost:8766
```

## What This Does

### Hydraulic Analysis
- **Steady-state simulation** - 24hr extended period via EPANET/WNTR
- **Water hammer / transient** - Method of Characteristics via TSNet
- **Fire flow analysis** - WSAA 12m residual pressure compliance
- **Water quality (age)** - stagnation risk detection
- **Pump trip/startup transients** - sudden shutdown and controlled startup

### Mining & Industrial
- **Non-Newtonian fluids** - Bingham Plastic, Power Law, Herschel-Bulkley models
- **Slurry database** - mine tailings, paste fill, cement, drilling mud
- **Settling velocity checks** - minimum velocity compliance for slurry lines
- **Pipe wear assessment** - velocity-based wear risk for abrasive slurries

### Pump Engineering
- **Pump curve database** - 7 pumps (water supply, mining dewatering, slurry)
- **Pump recommendation** - auto-select best pump for required duty point
- **System curve generation** - static head + friction losses
- **Operating point analysis** - pump vs system curve intersection

### Pipe Engineering
- **Australian pipe database** - ductile iron, PVC, PE, concrete (32 sizes per AS/NZS)
- **Stress calculations** - hoop, radial, axial, von Mises, Barlow's formula
- **Material strength database** - 7 materials with yield/tensile strengths
- **Transient surge factor** - combined steady + surge stress analysis

### Visualization
- **3D network rendering** - Three.js with orbit camera, elevation layout
- **Color-coded results** - pressure and velocity overlays
- **Interactive Plotly charts** - 24hr time-series, pressure envelopes
- **Network topology** - 2D and 3D views with element info on click

### Data & Reporting
- **Import** - CSV, GIS Shapefile, DXF/CAD
- **Export** - Word DOCX, PDF/HTML reports with compliance sections
- **Scenario comparison** - side-by-side what-if analysis
- **JSON API** - full REST API for automation

## Project Structure

```
EPANET_CLAUDE/
|-- app/                          # NiceGUI dashboard (7 tabs)
|   |-- main.py                   # Entry point (port 8766)
|   |-- pages/                    # Steady-state, transient, 3D view, scenarios,
|   |                             # network editor, Joukowsky, feedback
|   `-- components/               # 3D scene, compliance, metrics, network plot
|-- data/
|   |-- au_pipes.py               # Australian pipe database (AS/NZS)
|   `-- pump_curves.py            # Pump curve database + recommendation engine
|-- importers/                    # CSV, GIS shapefile, DXF importers
|-- reports/                      # Word DOCX + PDF report generators
|-- models/                       # EPANET .inp network files
|-- tests/                        # 157 automated tests (18 files)
|-- docs/
|   |-- USER_GUIDE.md             # Feature documentation
|   |-- MAINTENANCE.md            # Troubleshooting + extending
|   |-- CHANGELOG.md              # Version history
|   `-- ROADMAP.md                # Future development plan
|-- .claude/skills/               # 6 Claude Code development skills
|-- epanet_api.py                 # Core API (HydraulicAPI class)
|-- slurry_solver.py              # Non-Newtonian rheological solver
|-- pipe_stress.py                # Pipe stress calculator
|-- scenario_manager.py           # Scenario comparison engine
|-- server.py                     # FastAPI REST API (legacy)
`-- dashboard.html                # Legacy HTML dashboard
```

## Technology Stack

| Component | Package | Purpose |
|-----------|---------|---------|
| Hydraulic solver | WNTR 1.4.0 | EPANET steady-state simulation |
| Transient solver | TSNet 0.3.1 | Water hammer (MOC method) |
| EPANET toolkit | EPyT 2.3.5 | Direct EPANET C library access |
| Dashboard | NiceGUI 3.9 | Python-native interactive UI |
| 3D rendering | Three.js | 3D network visualization (via NiceGUI) |
| Charts | Plotly | Interactive 2D charts |
| REST API | FastAPI | Legacy API backend |
| Reports | python-docx, fpdf2 | Word and PDF generation |
| Testing | pytest | 157 tests, 18 test files |

## Testing

```bash
python -m pytest tests/ -v                    # All 157 tests
python -m pytest tests/ --cov=epanet_api      # With coverage
python -m pytest tests/test_slurry_solver.py   # Just slurry tests
```

## Units (Australian / SI)

| Parameter | Unit |
|-----------|------|
| Flow | LPS (litres per second) |
| Pressure | m (metres of head) |
| Pipe diameter | mm |
| Pipe length | m |
| Velocity | m/s |
| Stress | MPa |
| Headloss | Hazen-Williams C-factor |

## Documentation

- **[User Guide](docs/USER_GUIDE.md)** - Full feature documentation
- **[Maintenance Guide](docs/MAINTENANCE.md)** - Troubleshooting + extending
- **[Changelog](docs/CHANGELOG.md)** - Version history
- **[Roadmap](docs/ROADMAP.md)** - Future plans to exceed $15K/yr commercial tools

## vs Commercial Software

| Feature | This Toolkit | PumpSim ($15K) | AFT Fathom ($10K) |
|---------|-------------|----------------|-------------------|
| Steady-state | Yes | Yes | Yes |
| Water hammer | Yes | No | Separate ($15K) |
| Water quality | Yes | No | No |
| Non-Newtonian | Yes | Yes | Limited |
| 3D visualization | Yes | Yes | No |
| Pump selection | Yes | Yes | Yes |
| Python API | Yes | No | No |
| Report generation | Yes | Limited | Yes |
| Automated tests | 157 | None | None |
| Cost | **Free** | $5-15K/yr | $5-15K/yr |

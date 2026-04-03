# Future Roadmap

How to take this from a strong open-source toolkit to something that exceeds $15K/year commercial software like PumpSim, AFT Fathom, and WaterGEMS.

---

## What We Have Today (v1.0)

| Category | Capabilities |
|----------|-------------|
| **Hydraulic Analysis** | Steady-state (24hr EPS), water hammer (MOC), fire flow, water quality (age), pump trip/startup |
| **Slurry / Mining** | Bingham Plastic, Power Law, Herschel-Bulkley solvers; 7 pre-configured fluids; settling/wear checks |
| **Pump Engineering** | 7-pump database with curves, recommendation engine, system curves, operating point analysis |
| **Pipe Engineering** | Australian pipe database (4 materials, 32 sizes), stress calculator (hoop/von Mises/Barlow) |
| **Visualization** | 2D Plotly charts, 3D Three.js scene with color-coded results |
| **Data Import** | CSV, GIS Shapefile, DXF/CAD |
| **Scenario Analysis** | Side-by-side what-if comparison with modification tracking |
| **Reporting** | Word DOCX and PDF report generation |
| **Network Editing** | View, edit, add, delete elements; save to .inp |
| **Compliance** | WSAA Australian standards (pressure, velocity, pipe rating, fire flow) |
| **Testing** | 157 automated tests, 18 test files |
| **UI** | NiceGUI dashboard (7 tabs), legacy FastAPI REST API |
| **Feedback** | Built-in user feedback channel |

---

## Phase 1: Polish & Professional Quality (Near-term)

These items transform the current build into a tool professional engineers would trust daily.

### 1.1 3D Visualization Enhancement -- COMPLETED (v1.1.0)
- ~~**Animated flow particles** - show fluid direction and velocity as moving dots along pipes~~
- ~~**Pipe textures** - material-based textures (steel, PVC, concrete) on 3D pipes~~
- ~~**Result animation** - step through 24hr simulation in 3D, watching pressures change~~
- ~~**Selection highlighting** - glow/outline effect on selected elements~~
- ~~**Measurement tool** - click two points to measure distance~~
- ~~**Labels toggle** - show/hide node labels, pipe diameters, flow values in 3D~~
- ~~**Screenshot/video export** - capture 3D views for reports~~

### 1.2 Pump Curve Digitizer
- Upload a pump curve image (from manufacturer PDF)
- Click points on the image to digitize the curve
- Auto-fit polynomial to digitized points
- Save to pump database
- Could use OpenCV for image processing or a simpler click-coordinate approach

### 1.3 Dynamic Operational Simulation
- **Control logic engine** - IF/THEN rules for pump/valve control
- **Tank level triggers** - start/stop pumps based on tank levels
- **Time-based scheduling** - pump schedules over 24hr/weekly cycles
- **Energy cost optimization** - time-of-use tariffs, minimize pumping cost
- WNTR already supports controls and rules - this is an exposure/UI task

### 1.4 Terrain Mapping
- Import DEM (Digital Elevation Model) files
- Map pipeline routes onto 3D terrain surface
- Auto-set junction elevations from DEM
- Render terrain mesh in 3D scene
- Australian DEM data from ELVIS (elevation.fsdf.org.au)

### 1.5 Input Validation & Error Recovery
- Validate network connectivity before simulation
- Check for disconnected nodes, dead-end pipes
- Graceful handling of solver convergence failures
- User-friendly error messages (not Python tracebacks)

---

## Phase 2: Feature Parity with Commercial Tools (Mid-term)

These close the remaining gaps with PumpSim, AFT Fathom, and WaterGEMS.

### 2.1 Comprehensive Pump Curve System
- **Manufacturer database** - import from Grundfos, Flygt, Xylem, KSB, Sulzer product selectors
- **Multi-pump analysis** - series and parallel pump combinations
- **VFD/variable speed** - affinity law curves at different RPM percentages
- **NPSHa vs NPSHr** - cavitation analysis with inlet pipe losses
- **Pump wear curves** - degraded performance over time
- **Positive displacement pumps** - flow-per-RPM, pressure-per-RPM models

### 2.2 Advanced Slurry Modelling
- **Particle settling velocity** - Stokes, intermediate, Newton's law regimes
- **Critical deposition velocity** - minimum velocity to prevent settling
- **Slurry concentration effects** - viscosity vs concentration curves
- **Wear rate estimation** - pipe wall erosion from abrasive slurry
- **Thickener/cyclone integration** - model concentration changes through process equipment
- **Paste fill design** - underground backfill pipeline design per mining standards

### 2.3 Water Quality Modelling (Extended)
- **Chlorine decay** - first-order bulk and wall decay
- **Contamination tracking** - source tracing for backflow events
- **DBP formation** - disinfection byproduct prediction
- **Temperature modelling** - heat transfer in exposed pipelines
- **Multi-species reactions** - complex water chemistry

### 2.4 GIS Integration
- **Live GIS overlay** - OpenStreetMap/satellite imagery under 3D network
- **Spatial queries** - find pipes within X metres of a location
- **Asset register integration** - link pipes to asset management databases
- **Coordinate reference systems** - full GDA2020/WGS84/MGA support with on-the-fly reprojection
- **Shapefile/GeoPackage export** - export results back to GIS

### 2.5 SCADA / Real-Time Integration
- **OPC UA client** - read live SCADA data (pressures, flows, pump status)
- **Digital twin mode** - compare live vs model in real time
- **Alarm generation** - flag when live data deviates from model predictions
- **Historian integration** - store time-series in InfluxDB/TimescaleDB
- **Dashboard live mode** - auto-updating charts from SCADA feeds

---

## Phase 3: Competitive Advantage (Long-term)

These go beyond what any single commercial tool offers today.

### 3.1 AI-Powered Analysis
- **Automated network optimization** - genetic algorithm for pipe sizing, pump selection
- **Leak detection** - ML model trained on pressure/flow patterns
- **Demand forecasting** - predict future demands from historical data
- **Energy optimization** - RL-based pump scheduling for lowest cost
- **Anomaly detection** - flag unusual hydraulic behaviour automatically

### 3.2 Collaboration Features
- **Multi-user editing** - concurrent network modification (WebSocket)
- **Version control** - track changes to network models over time
- **Review & approval workflow** - engineering review before finalizing designs
- **Commenting** - attach notes to specific elements
- **Role-based access** - viewer, editor, approver roles

### 3.3 Cloud Deployment
- **Web-accessible** - NiceGUI already supports multi-user web deployment
- **Simulation queue** - background processing for large networks
- **Results caching** - don't re-run unchanged analyses
- **User management** - authentication, project workspaces
- **API for integrations** - REST API already exists, add OAuth tokens

### 3.4 Regulatory Compliance Engine
- **Australian standards** (current): WSAA, AS/NZS 2566, AS 2419.1
- **Mining regulations**: state-specific requirements (NSW, QLD, WA, VIC)
- **Environmental compliance**: discharge limits, EPA requirements
- **International standards**: ISO, EN, AWWA for export markets
- **Automated compliance reports** - generate submission-ready documents

### 3.5 Extended Simulation Capabilities
- **Multiphase flow** - gas-liquid mixtures in pipelines
- **Thermal hydraulics** - temperature-dependent fluid properties
- **Compressible gas flow** - compressed air reticulation (like PumpSim Premium)
- **Coupled hydraulic-structural** - pipe movement under pressure loading
- **Seismic analysis** - earthquake resilience assessment (WNTR already has this foundation)

### 3.6 Professional Distribution
- **Windows installer** - Tauri-based native app with auto-update
- **Offline-first** - works without internet (NiceGUI already does this)
- **Licensing system** - trial, professional, enterprise tiers
- **Training materials** - built-in tutorials, example projects
- **Certification program** - for consulting engineers

---

## Competitive Comparison

| Feature | Our Toolkit | PumpSim ($15K) | AFT Fathom ($10K) | WaterGEMS ($15K) |
|---------|------------|----------------|-------------------|------------------|
| Steady-state hydraulics | Yes | Yes | Yes | Yes |
| Water hammer / transient | Yes | No | Separate ($15K AFT Impulse) | Separate (HAMMER) |
| Water quality | Yes | No | No | Yes |
| Non-Newtonian fluids | Yes | Yes | Yes (limited) | No |
| 3D visualization | Yes | Yes (better) | No | No |
| Pump recommendation | Yes | Yes (better) | Yes (best) | Limited |
| GIS integration | Yes | No | No | Yes (best) |
| Fire flow analysis | Yes | No | No | Yes |
| Scenario comparison | Yes | Limited | Yes | Yes |
| Python API | Yes | No | No | Limited |
| Report generation | Yes | Limited | Yes | Yes |
| Network editor | Yes | Yes (better) | Yes | Yes (best) |
| SCADA integration | Planned | No | No | Yes |
| AI optimization | Planned | No | No | No |
| Automated testing | 157 tests | No | No | No |
| Cost | Free | $5-15K/yr | $5-15K/yr | $5-15K/yr |

### Where we already win
- **Transient analysis included** (competitors charge separately)
- **Water quality + hydraulics in one tool**
- **Python API for automation** (none of the competitors offer this)
- **Open source + free** (vs $5-15K/year)
- **Automated testing** (157 tests - commercial tools have none exposed)
- **Both mining AND water supply** in one tool

### Where we need to improve
- **3D visualization quality** - PumpSim's is more polished (textures, animation)
- **Pump curve database size** - AFT Fathom has thousands of real manufacturer pumps
- **Network editor UX** - WaterGEMS has the best drag-and-drop editor
- **Validation/certification** - commercial tools have decades of engineering validation
- **Documentation depth** - commercial tools have video tutorials, training courses

---

## Priority Ranking

If building towards commercial-competitive quality, this is the recommended priority order:

| Priority | Item | Impact | Effort |
|----------|------|--------|--------|
| ~~1~~ | ~~3D flow animation + textures~~ | ~~DONE (v1.1.0)~~ | ~~Medium~~ |
| 2 | Dynamic simulation control logic | Core engineering feature | Medium |
| 3 | Pump curve digitizer | Practical daily-use feature | Low |
| 4 | Terrain mapping (DEM) | Visual + engineering impact | Medium |
| 5 | Manufacturer pump database expansion | Practical impact | Low-Medium |
| 6 | Input validation + error UX | Trust + usability | Medium |
| 7 | SCADA/OPC integration | Enterprise differentiator | High |
| 8 | AI-powered optimization | Unique competitive advantage | High |
| 9 | Multi-user collaboration | Enterprise feature | High |
| 10 | Cloud deployment | Scale + accessibility | Medium |
| 11 | Tauri desktop installer | Distribution | Medium |
| 12 | Regulatory compliance engine | Market requirement | Medium |

---

## Technical Debt

Items to address for long-term maintainability:

- Replace `print()` statements with Python `logging` module
- Add structured logging (JSON format) for production deployment
- Add input validation at API boundaries (Pydantic models for all methods)
- Add rate limiting and authentication to REST API
- Add database (SQLite) for results persistence instead of JSON files
- Improve TSNet pump transient stability (or evaluate alternative solvers)
- Add concurrent analysis support (async/queue for long-running simulations)
- Add configuration file (YAML/TOML) instead of hardcoded defaults
- Set up CI/CD pipeline (GitHub Actions) for automated testing on push

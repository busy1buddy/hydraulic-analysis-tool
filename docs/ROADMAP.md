# Product Roadmap — Hydraulic Analysis Tool

**Version:** v1.0.0-release (2026-04-04)
**Test suite:** 363 tests passing, 12 xfail (TSNet pump stability)
**Architecture:** PyQt6 desktop app + WNTR/TSNet solvers + Australian pipe/pump databases

This roadmap covers three parallel tracks: production hardening (depth), feature gaps (breadth), and validation (prove the numbers). Items are prioritised by impact on professional engineering credibility.

---

## Track 1 — Production Hardening (depth)

### 1.1 Visualisation completeness audit
**Priority:** CRITICAL | **Effort:** 2-3 days | **Depends on:** nothing

Run the app against all 10 tutorial networks and document every visual issue.

Checklist:
- [ ] ColourBar renders correctly for each variable type (pressure, velocity, headloss)
- [ ] ColourBar ticks are readable at extreme ranges (0.01 to 10000)
- [ ] Value overlays do not overlap on dense networks (fire_flow_demand has 10 nodes)
- [ ] Value overlays scale font with zoom level
- [ ] Animation player works on transient_network.inp (the only transient-capable network)
- [ ] Animation player gracefully handles networks with no transient data
- [ ] Pipe DN scaling works at extreme sizes: DN63 (PE) to DN900 (Concrete)
- [ ] Pipe DN scaling is visually distinct: DN150 vs DN600 must be obviously different
- [ ] Node demand scaling differentiates 0 LPS from 50 LPS
- [ ] Probe tool (not yet built) returns correct values for junctions, reservoirs, tanks, pipes, pumps, valves
- [ ] Split-screen comparison (not yet built) works with two scenarios
- [ ] GIF export (not yet built) produces a valid animated file
- [ ] All 5 colourmap options produce visually distinct gradients
- [ ] Log scale checkbox works correctly for values spanning 3+ orders of magnitude
- [ ] Percentile clip (not yet built) handles outlier values without distorting the scale

Current status: ColourMapWidget, ColourBar, AnimationPanel, pipe/node scaling, and value overlay are built. Probe tool, split-screen, and GIF export are designed but not yet implemented.

### 1.2 Performance profiling
**Priority:** HIGH | **Effort:** 3-5 days | **Depends on:** 1.1

Profile the app on a large network (1000+ nodes). Use EPANET's BWSN-1 or generate a synthetic grid network.

Targets:
- [ ] Canvas redraw < 100ms at 1000 nodes (currently untested)
- [ ] Animation player maintains 30fps at 1000 nodes x 200 timesteps
- [ ] Results table scrolls smoothly at 1000 rows (QTableWidget may need virtualisation)
- [ ] Memory usage < 500 MB for 1000-node steady-state analysis
- [ ] Memory usage < 2 GB for 1000-node transient (200 steps x 1000 nodes x 8 bytes = 1.6 MB — should be fine)
- [ ] No memory leaks over a 1-hour session (open/close/analyse cycle 50 times)
- [ ] Startup time < 3 seconds on a modern Windows machine
- [ ] PyInstaller exe startup < 10 seconds

Profiling tools: cProfile for Python, QElapsedTimer for Qt, tracemalloc for memory.

### 1.3 Error handling completeness
**Priority:** HIGH | **Effort:** 2-3 days | **Depends on:** nothing

Document every crash path and add defensive handling.

Known crash scenarios to test:
- [ ] Malformed .inp files (missing [JUNCTIONS] section, truncated file, binary garbage)
- [ ] .inp files with unsupported EPANET features (rules, controls, emitters, sources)
- [ ] Networks with isolated nodes (no connected pipes)
- [ ] Networks with negative elevations (valid but unusual)
- [ ] Networks with zero-length pipes (WNTR rejects these)
- [ ] Networks with zero-diameter pipes (causes division by zero in velocity calc)
- [ ] Transient analysis on a network with no valves or pumps
- [ ] Pump trip on a pump with >3 curve points (TSNet limitation)
- [ ] Report generation when analysis produced warnings/errors
- [ ] Opening a .hap file that references a missing .inp file
- [ ] Disk full during report generation or audit trail write
- [ ] Network modification (canvas editor) then analyse without saving

Current status: basic error handling exists (QMessageBox for missing network, try/except around analysis). Need systematic coverage of every boundary condition.

### 1.4 UI/UX review
**Priority:** MEDIUM | **Effort:** 1-2 days | **Depends on:** 1.1

Act as a first-time hydraulic engineer and document friction points.

Checklist:
- [ ] Is the File > Open workflow obvious? (currently no drag-and-drop)
- [ ] Can a user find the tutorial examples from inside the app?
- [ ] Is the Analysis > Run Steady State shortcut (F5) documented in the menu?
- [ ] Are error messages actionable? ("Load a network first" vs "Click File > Open to load an .inp file")
- [ ] Is the slurry mode workflow clear? (toggle → set parameters → run)
- [ ] Is it obvious that you need to run analysis before generating a report?
- [ ] Can a user understand the WSAA compliance results without prior knowledge?
- [ ] Are keyboard shortcuts documented? (F5, F6, Ctrl+Z, Ctrl+Y, Ctrl+O, Ctrl+S, Ctrl+Q)
- [ ] Is the Properties panel obviously interactive? (currently just shows data, no edit)
- [ ] Is the colour bar unit label always visible and correct?

---

## Track 2 — Feature Gaps (breadth)

### 2.1 Water quality modelling
**Priority:** HIGH | **Effort:** 5-8 days | **Depends on:** nothing

EPANET's core differentiator. WNTR already supports water quality simulation — this is primarily a UI exposure task.

What to build:
- Analysis > Water Quality submenu (Age, Chlorine, Trace)
- Chlorine decay parameters dialog (bulk coefficient, wall coefficient, initial concentration)
- Canvas colour mode: Chlorine Concentration (mg/L)
- Canvas colour mode: Water Age (hours) — partially exists, needs integration with new colourmap
- Compliance check: minimum residual chlorine 0.2 mg/L per WSAA
- Report section: water quality summary table (max age, min chlorine per junction)
- Tutorial: add water quality analysis to dead_end_network example

WNTR API: `sim = wntr.sim.EpanetSimulator(wn); results = sim.run_sim()` with `wn.options.quality.parameter = 'CHEMICAL'`.

### 2.2 Demand patterns and extended period simulation (EPS)
**Priority:** HIGH | **Effort:** 5-8 days | **Depends on:** nothing

Currently all analyses use base demand with a scalar multiplier. Real networks have diurnal patterns.

What to build:
- Demand Pattern Editor dialog (table: 24 rows x 2 columns: hour, multiplier)
- Pattern library presets: Residential (WSAA typical), Commercial, Industrial, Irrigation
- Apply pattern to individual junctions or all junctions
- Extended period simulation: run over 24h, 48h, or 168h (1 week)
- Results: pressure/velocity envelope (min/max band) over simulation period
- Canvas: animate EPS results using existing AnimationPanel
- Compliance: check WSAA min pressure across ALL timesteps, not just average

The EPS infrastructure already exists (WNTR runs 24h by default) — the gap is UI exposure and envelope reporting.

### 2.3 Calibration tools
**Priority:** MEDIUM | **Effort:** 8-12 days | **Depends on:** 2.2

Engineers use field data to calibrate models. This is what separates a design tool from a verified operational model.

What to build:
- Import field measurements (CSV: node_id, timestamp, pressure_m)
- Import flow measurements (CSV: pipe_id, timestamp, flow_lps)
- Roughness calibration wizard: iteratively adjust C-factors to match measured pressures
- Demand calibration: scale demands to match measured flows at metering points
- Goodness of fit report: predicted vs measured scatter plot, R^2, RMSE, Nash-Sutcliffe
- Calibration report section in DOCX/PDF

Calibration algorithms: start with manual roughness grouping (DI, PVC, PE, Concrete), then genetic algorithm for automated calibration.

### 2.4 Pressure zone management
**Priority:** MEDIUM | **Effort:** 3-5 days | **Depends on:** nothing

Multi-zone systems are standard in Australian water networks.

What to build:
- Zone assignment: right-click node > Assign to Zone (dropdown)
- Zone colour-coding on canvas (distinct colour per zone)
- PRV/PSV valve analysis with zone boundary identification
- Zone balance report: supply vs demand per zone per timestep
- Zone pressure envelope: min/max/avg pressure per zone
- Canvas: zone boundary lines drawn automatically

### 2.5 Fire flow analysis wizard
**Priority:** MEDIUM | **Effort:** 3-5 days | **Depends on:** nothing

Already implemented in epanet_api.py (`run_fire_flow()`) but not exposed as a proper feature.

What to build:
- Analysis > Fire Flow Wizard dialog
- Specify: target node, required flow (default 25 LPS per WSAA), minimum residual pressure (12 m per WSAA)
- Automated: sweep all nodes, find max available flow at each
- Results: fire flow availability map on canvas (green = adequate, red = inadequate)
- Compliance report: which nodes fail fire flow requirements
- Tutorial: add fire flow analysis to fire_flow_demand example

### 2.6 GIS integration
**Priority:** LOW (but critical for professional adoption) | **Effort:** 10-15 days | **Depends on:** nothing

Engineers work with GIS data.

What to build:
- Shapefile import: import pipes and nodes from GIS layers (partially exists in importers/)
- Coordinate system: support MGA2020/GDA2020 via pyproj
- Background map: OpenStreetMap tile layer behind the network canvas (via requests + tile caching)
- Export: save results as shapefile with result attributes per element
- DEM import: set junction elevations from Digital Elevation Model

Libraries: geopandas, pyproj, contextily (for basemaps).

### 2.7 Asset management integration
**Priority:** LOW | **Effort:** 5-8 days | **Depends on:** 2.3

Australian utilities use asset management systems.

What to build:
- Import pipe age/condition from CSV
- Pipe condition scoring: function of age, material, break history
- Rehabilitation prioritisation: rank pipes by (headloss x age x condition score)
- Capital works report: recommended replacements with estimated cost
- Export: pipe condition scores to CSV for asset register

---

## Track 3 — Validation (prove the numbers)

### 3.1 EPANET verification test suite
**Priority:** CRITICAL | **Effort:** 3-5 days | **Depends on:** nothing

EPA publishes official test networks with reference results. Run all of them and compare.

Networks to verify:
- [ ] Net1.inp — 9 junctions, 12 pipes, 1 pump, 1 tank. Pressures must match EPANET 2.2 within 0.1%
- [ ] Net2.inp — 35 junctions, 40 pipes, 1 pump, 1 tank. Extended period with tank filling/draining
- [ ] Net3.inp — 92 junctions, 117 pipes, 2 pumps, 3 tanks. Largest standard test network
- [ ] BWSN-1 — 126 junctions. Water security benchmark
- [ ] BWSN-2 — 12,523 junctions. Large-scale performance test

Verification method: run each network through WNTR, compare node pressures and link flows against EPANET 2.2 reference outputs at every timestep. Tolerance: < 0.1% for pressures, < 0.5% for flows.

### 3.2 Slurry solver validation
**Priority:** HIGH | **Effort:** 3-5 days | **Depends on:** nothing

The slurry solver is unique to this tool — it needs independent validation against published literature.

Benchmarks:
- [ ] Buckingham-Reiner: benchmark against Darby (Chemical Engineering Fluid Mechanics, 3rd ed.) Table 7-1
- [ ] Herschel-Bulkley: benchmark against Chhabra & Richardson (Non-Newtonian Flow, 2nd ed.)
- [ ] Wilson-Thomas turbulent friction: benchmark against Wilson, Addie & Clift (Slurry Transport Using Centrifugal Pumps, 3rd ed.)
- [ ] Newtonian limit: already benchmarked (Benchmark #6, passes at < 5%)
- [ ] Document valid flow regime range: Re_B from 1 to 10^6, He from 0 to 10^8
- [ ] Document accuracy at transition regime (Re near Re_crit): this is the weakest area

### 3.3 Transient solver validation
**Priority:** MEDIUM | **Effort:** 2-3 days | **Depends on:** nothing

TSNet has known limitations. Document them precisely rather than hiding them.

Items:
- [ ] Joukowsky benchmark: current result matches within 0.5 m (already verified in Benchmark #1)
- [ ] Valve closure wave shape: compare TSNet waveform against analytical solution for simple pipe
- [ ] Pump trip: document the 12 xfail cases with root cause (sqrt of negative head, >3 curve points, zero roughness)
- [ ] Network configuration limits: which topologies work? (linear, branched, looped, multi-pump)
- [ ] Comparison with commercial MOC solver if reference data available (AFT Impulse, Bentley HAMMER)

### 3.4 Pipe stress validation
**Priority:** MEDIUM | **Effort:** 1-2 days | **Depends on:** nothing

The pipe stress calculations need engineering review.

Benchmarks:
- [ ] Hoop stress: already benchmarked (Benchmark #2, exact match)
- [ ] Von Mises: already benchmarked (Benchmark #3, within 0.5 MPa)
- [ ] Barlow wall thickness: already benchmarked (Benchmark #4, exact match)
- [ ] PN safety factor methodology: document that this is rated_pressure / operating_pressure, not a code check
- [ ] Compare against AS 2280 worked examples for ductile iron
- [ ] Compare against AS/NZS 4130 for PE100 SDR11
- [ ] Document limitations: thin-wall theory only (not valid for wall_thickness/diameter > 0.1)

### 3.5 Competitive benchmarking
**Priority:** LOW | **Effort:** 2-3 days | **Depends on:** 3.1

Run the same network through this tool AND EPANET 2.2 (free from EPA).

Items:
- [ ] Use Net1.inp as the standard comparison
- [ ] Table: node pressures from both tools, difference column
- [ ] Table: link flows from both tools, difference column
- [ ] Screenshot comparison: our FEA visualisation vs EPANET 2.2 2D map
- [ ] Performance: time to load, solve, and render (our tool vs EPANET 2.2)
- [ ] Feature comparison table: what we do that EPANET doesn't (slurry, 3D, scenarios, reports)

---

## Known Limitations (honest assessment as of v1.0.0-release)

### Cannot do today
| Limitation | Impact | Workaround |
|------------|--------|------------|
| No water quality UI | Cannot visualise chlorine/age on canvas | Use WNTR Python API directly |
| No demand pattern editor | All analysis uses flat or multiplied demand | Edit pattern in .inp file manually |
| No calibration tools | Cannot match model to field measurements | Manual roughness adjustment |
| No GIS basemap | Network floats in abstract coordinate space | Use shapefile import for real coordinates |
| TSNet pump transient unstable | 12 tests xfail, some networks crash | Use valve closure proxy for pump trip analysis |
| TSNet requires 1 or 3 curve points | Most real pump curves have 7+ points | Simplify curve to 3 points before transient |
| No SCADA/real-time integration | Desktop tool only, no live data | Export results to CSV for comparison |
| Single-threaded analysis | Large networks block the UI | QThread worker handles this, but no parallel solves |
| No multi-user collaboration | Single user, local files only | Share .inp/.hap files via file sharing |
| Probe tool not yet built | Cannot click-inspect all variables at once | Use Properties panel (shows one element at a time) |
| Split-screen comparison not yet built | Cannot visually compare two scenarios side by side | Use scenario comparison table |
| GIF export not yet built | Cannot export transient animation | Use screen recording software |

### Works but with caveats
| Feature | Caveat |
|---------|--------|
| Transient analysis | Only works on networks with valves; pump trip requires simple pump curves |
| Slurry solver | Validated for Bingham plastic laminar/turbulent; transition regime accuracy uncertain |
| Pipe stress | Thin-wall theory only; PN safety factor is pressure-class ratio, not a code-compliance check |
| Report generation | DOCX is full-featured; PDF uses fpdf2 which produces basic formatting |
| Canvas editor | Add/delete/move works; no drag-to-move (must use editor.move_node() programmatically) |
| PyInstaller exe | 918 MB distribution size; 10-second startup time; requires Windows x64 |

### Known bugs
| Bug | Severity | Status |
|-----|----------|--------|
| TSNet sqrt(negative) on some pump networks | LOW (xfail) | TSNet library issue, not fixable without upstream patch |
| Canvas nodes not visible until Fit button clicked on some screen DPIs | LOW | Workaround: click Fit after loading |
| Colourbar tick labels show scientific notation at extreme ranges | LOW | Cosmetic; values are correct |

---

## Immediate Next Actions (priority order)

| # | Action | Track | Effort | Why first |
|---|--------|-------|--------|-----------|
| 1 | Visualisation audit on all 10 tutorials | 1.1 | 2-3 days | Find real issues before anyone else uses the tool |
| 2 | EPANET verification suite (Net1, Net2, Net3) | 3.1 | 3-5 days | Prove the numbers before distributing to engineers |
| 3 | Water quality modelling UI | 2.1 | 5-8 days | Biggest feature gap vs EPANET's core value proposition |
| 4 | Demand patterns + EPS | 2.2 | 5-8 days | Required for any real professional analysis |
| 5 | Performance profiling on 1000+ node network | 1.2 | 3-5 days | Must know scaling limits before marketing to real projects |
| 6 | Error handling sweep | 1.3 | 2-3 days | First-time users will find every crash path |
| 7 | Fire flow wizard UI | 2.5 | 3-5 days | Already implemented in API, just needs UI exposure |
| 8 | Slurry solver validation against published data | 3.2 | 3-5 days | Mining clients will demand validation documentation |

---

## Project Statistics (v1.0.0-release)

| Metric | Value |
|--------|-------|
| Python source files | 70 |
| Lines of code (approx) | ~12,000 |
| Test files | 22 |
| Tests passing | 363 |
| Tests xfail | 12 |
| Tutorial examples | 10 |
| Pipe materials in database | 4 (DI, PVC, PE, Concrete) |
| Pipe sizes in database | 35 |
| Pump curves in database | 7 |
| Git commits | 21 |
| PyInstaller exe size | 94 MB |
| Distribution size | 918 MB |

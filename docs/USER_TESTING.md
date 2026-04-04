# User Testing Guide — First-Time Engineer

This guide walks a water/mining engineer through their first session with the Hydraulic Analysis Tool. Follow these steps to validate that the application works correctly and produces reliable results.

## Prerequisites

- Windows 10/11 (64-bit)
- An EPANET `.inp` file (or use a built-in tutorial)
- Basic understanding of WSAA WSA 03-2011 guidelines

## Quick Start (5 minutes)

1. **Launch** the application: `python main_app.py`
2. **Open a network**: File > Open Tutorial, or File > Open (.inp) for your own file
3. **Run analysis**: Press `F5` (Steady State)
4. **Check results**: Look at the bottom panel for node pressures and pipe velocities
5. **Check WSAA**: Status bar shows PASS/FAIL with issue count

## Test Scenarios

### Test 1: WSAA Compliance Check

**What to verify:** Pressures are within 20-50 m and velocities below 2.0 m/s.

1. Open `models/Net1.inp` (File > Open)
2. Press `F5` to run steady-state analysis
3. Check the **Node Results** table — every node should show PASS or FAIL
4. Check the **status bar** at bottom — should show "WSAA: PASS" or issue count
5. Switch colour mode to "WSAA Compliance" — green = pass, red = fail, orange = warning
6. Click any node to see its pressure in the Properties panel
7. Click any pipe to see its velocity

**Expected:** Net1 is a well-designed EPA example network and should pass all WSAA checks.

### Test 2: Extended Period Simulation (EPS)

**What to verify:** Pressures stay compliant across a full 24-hour demand cycle.

1. Open a network with demand patterns
2. Press `F7` (EPS) — set 24-hour duration, 1-hour timestep
3. After completion, switch colour mode to "Pressure Min (EPS)"
4. Red nodes indicate minimum pressure dropped below 15 m during the day
5. Check the **Animation** panel tab — use Play button to watch pressure changes over time

**Expected:** Peak demand (typically 7-9am) may cause pressure drops at high-elevation nodes.

### Test 3: Fire Flow Analysis

**What to verify:** Network can deliver 25 LPS at 12 m residual pressure (WSAA).

1. Open a network
2. Press `F8` (Fire Flow Wizard)
3. Select a junction node and click "Run Single Node"
4. Check residual pressures — all should be above 12 m for PASS
5. Click "Run Sweep" to test every node (may take a minute on large networks)

**Expected:** Well-designed networks pass at most nodes. Nodes at network extremities or high elevations may fail.

### Test 4: Pressure Zone Management

**What to verify:** Zones can be defined and analysed for balance.

1. Open a network and run steady-state (F5)
2. Go to Tools > Pressure Zones
3. Click "Auto-Detect Zones by Elevation" — creates Low/Mid/High zones
4. Click "Run Zone Analysis" — check the report table
5. Look for: WSAA compliance per zone, PRV recommendations, demand balance
6. Click "Apply Zone Colours to Canvas" to see zones visually

**Expected:** High-elevation zones may have low pressures. Low-elevation zones may exceed 50 m and recommend PRVs.

### Test 5: Report Generation

**What to verify:** Reports include executive summary and correct data.

1. Run a steady-state analysis (F5)
2. Go to Reports > Generate Report (DOCX) or (PDF)
3. Choose a save location and fill in engineer name
4. Open the generated report and check:
   - Executive summary with compliance overview (PASS/FAIL)
   - Key hydraulic metrics table
   - Recommended actions list
   - Pressure and velocity tables match the UI values
   - All values include units (m, LPS, m/s)

**Expected:** Report should match what you see in the application. PDF now includes colour-coded compliance cells.

### Test 6: Rehabilitation Prioritisation

**What to verify:** Pipes are scored and ranked by condition.

1. Open a network
2. Go to Tools > Rehabilitation Prioritisation
3. (Optional) Import a CSV with pipe condition data: columns `pipe_id, install_year, condition_score, break_history, material`
4. Click "Run Prioritisation"
5. Check that pipes are sorted by priority score (highest = most urgent)
6. Filter by risk category (CRITICAL, HIGH, MEDIUM, LOW)

**Expected:** Without condition data, all pipes get medium risk scores (50%). With data, old pipes in poor condition with break history rank highest.

### Test 7: Canvas Interactions

**What to verify:** All canvas tools work correctly.

1. Open a network
2. **Zoom**: Mouse wheel
3. **Pan**: Click and drag on empty space
4. **Select node**: Click a node — properties appear on the right
5. **Select pipe**: Click a pipe — properties appear on the right
6. **Labels**: Click "Labels" button to show/hide IDs
7. **Values**: Click "Values" button to show pressure/velocity numbers
8. **Probe**: Click "Probe" button, then click any element for detailed tooltip
9. **Fit**: Click "Fit" button to zoom to show entire network
10. **Edit Mode**: Click "Edit" to enter edit mode — left-click to add nodes, right-click to delete

### Test 8: Unit Verification

**What to verify:** All displayed values use correct Australian units.

| Quantity | Expected Unit | Where to Check |
|----------|---------------|----------------|
| Pressure | m head | Node Results table, Properties panel |
| Flow | LPS | Pipe Results table |
| Velocity | m/s | Pipe Results table, Properties panel |
| Diameter | DN mm (integer) | Properties panel, Pipe Results table |
| Elevation | m AHD | Properties panel |
| Headloss | m/km | Pipe Results table |

**Critical check:** Pipe diameters should display as integer mm (e.g., "300 mm", NOT "0.3 m"). WNTR stores diameters in metres internally.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+N | New project |
| Ctrl+O | Open .inp file |
| Ctrl+S | Save |
| F5 | Run Steady State |
| F6 | Run Transient |
| F7 | Run Extended Period (EPS) |
| F8 | Fire Flow Wizard |
| F1 | Keyboard Shortcuts help |
| Ctrl+Z | Undo (in Edit Mode) |
| Ctrl+Y | Redo (in Edit Mode) |
| Escape | Cancel operation / hide probe |

## Reporting Issues

If you find any issues:
1. Note the exact steps to reproduce
2. Record what you expected vs what happened
3. Check the terminal/console for any error messages
4. File an issue on the project repository

## v2.0.0 Tutorial Smoke Test Results (2026-04-04)

All 10 tutorial networks tested: load, steady-state, quality score, resilience, diagnostics.

| Tutorial | Status | Quality Score | Resilience | Issues |
|----------|--------|--------------|------------|--------|
| dead_end_network | PASS | 92/100 (A) | 0.324 (B) | 0 |
| elevated_tank | PASS | 61/100 (C) | 0.000 (F) | 0 |
| fire_flow_demand | PASS | 90/100 (A) | 0.334 (B) | 0 |
| industrial_ring_main | PASS | 80/100 (B) | 0.712 (A) | 0 |
| mining_slurry_line | PASS | 90/100 (A) | 0.540 (A) | 0 |
| multistage_pump | PASS | 56/100 (D) | 0.000 (F) | 1 |
| pressure_zone_boundary | PASS | 86/100 (B) | 0.523 (A) | 0 |
| pump_station | PASS | 80/100 (B) | 1.000 (A) | 1 |
| rehabilitation_comparison | PASS | 90/100 (A) | 0.300 (B) | 0 |
| simple_loop | PASS | 95/100 (A) | 0.346 (B) | 0 |

**Result: 10/10 PASS** — no crashes, no Python tracebacks, all analyses complete.

Notes:
- elevated_tank and multistage_pump have Ir=0 because they have no junction demands (tank/pump test circuits)
- multistage_pump and pump_station show 1 diagnostic issue each (high demand or roughness warnings)

## Standards Reference

This tool checks against:
- **WSAA WSA 03-2011** — Water supply code of Australia
- **AS/NZS 1477** — PVC pipes and fittings
- **AS 2280** — Ductile iron pipes
- **AS/NZS 4130** — Polyethylene pipes
- **AS 4058** — Precast concrete pipes

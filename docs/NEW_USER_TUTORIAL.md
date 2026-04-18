# New User Tutorial — From Installation to Compliance Report

**Target audience:** Graduate hydraulic engineer familiar with EPANET 2.2 but
new to this tool.

**What you will do:** Load a real Australian subdivision network, run hydraulic
analysis, interpret results, fix a WSAA violation, and generate a professional
compliance report. Approximately 30 minutes.

---

## Step 1: Installation

1. Install Python 3.10+ from [python.org](https://python.org) (check "Add to PATH").
2. Open a terminal and run:
   ```
   pip install wntr tsnet pyqt6 pyqtgraph python-docx fpdf2 matplotlib
   ```
3. Download or clone the project, then from the project root:
   ```
   python main_app.py
   ```

The application window should appear with a dark theme, menu bar, and empty
canvas. If you see a Welcome dialog, click **Open File** and proceed to Step 3.

---

## Step 2: What You See

The main window has five areas:

| Area | Location | Purpose |
|------|----------|---------|
| **Canvas** | Centre | Network map — nodes as circles, pipes as lines |
| **Project Explorer** | Left panel | Tree showing network components (junctions, pipes, etc.) |
| **Properties** | Right panel | Details of the currently selected element |
| **Results Tables** | Bottom tabs | Node and Pipe results after analysis |
| **Status Bar** | Bottom | WSAA compliance status, file path, coordinates |

**Menu bar:** File, Edit, View, Analysis, Tools, Help.

**Key shortcuts you will use:**
- `Ctrl+O` — Open file
- `F5` — Run steady-state analysis
- `F8` — Run fire flow analysis
- `Ctrl+F` — Fit network to view
- `Ctrl+S` — Save project

---

## Step 3: Opening the Australian Subdivision Network

1. Click **File > Open** (or press `Ctrl+O`).
2. Navigate to `tutorials/australian_subdivision/network.inp`.
3. Click **Open**.

**What you should see:**
- The canvas shows 13 junction nodes and 1 reservoir (R1) connected by 17 pipes.
- The Project Explorer populates with "Junctions (13)", "Pipes (17)", "Reservoirs (1)".
- The status bar shows the file path.
- Reservoir R1 appears at the top of the network (head = 100 m AHD).
- Junctions are numbered J1-J13, with J13 at the bottom-right (lowest elevation, 55 m).

**If something goes wrong:**
- "File not found" — check that you are running from the project root directory.
- Network appears tiny — press `Ctrl+F` to fit the view, or scroll to zoom.

---

## Step 4: Running Steady-State Analysis

1. Press **F5** (or click **Analysis > Steady State**).
2. Wait for the progress bar to complete (< 2 seconds for this network).

**What you should see:**
- The status bar shows "WSAA: PASS 3i" (0 warnings, 3 informational items).
- The Results tab at the bottom fills with two tables: **Node Results** and **Pipe Results**.
- The canvas pipes may change colour depending on your colour mode setting.

**Expected values in the Node Results table:**

| Junction | Elevation (m) | Min P (m) | Status |
|----------|--------------|-----------|--------|
| J1       | 65.0         | 35.0 m    | PASS   |
| J13      | 55.0         | 45.0 m    | PASS   |

All 13 junctions should show pressures between 35.0 and 45.0 m.

**Expected values in the Pipe Results table:**

| Pipe | Velocity (m/s) | Headloss (m/km) |
|------|---------------|----------------|
| P1   | 0.03          | 0.0            |

All velocities are very low (< 0.1 m/s) because this is average-day demand.

---

## Step 5: Reading the Results

### Node Results Table (bottom-left tab)

| Column | Meaning | Unit |
|--------|---------|------|
| ID | Junction identifier | — |
| Elevation | Height above datum | m AHD |
| Min Pressure | Lowest gauge pressure across all timesteps | m head |
| Head | Hydraulic grade line (elevation + pressure) | m |
| Status | WSAA compliance: PASS, FAIL (<20 m), or FAIL (>50 m) | — |

### Pipe Results Table (bottom-right tab)

| Column | Meaning | Unit |
|--------|---------|------|
| ID | Pipe identifier | — |
| Diameter | Nominal diameter | DN mm |
| Length | Pipe length | m |
| Velocity | Maximum flow velocity | m/s |
| Headloss | Friction loss per kilometre | m/km |

**Tip:** Click any column header to sort. Right-click the table for
"Show only violations" to filter to problem areas.

---

## Step 6: Identifying WSAA Violations

After analysis, check the WSAA status in the bottom-right of the status bar:
- **"WSAA: PASS"** (green) — all checks pass
- **"WSAA: 3!"** (red) — 3 warning/critical issues found

For this network on average-day demand, you should see **"WSAA: PASS 3i"** —
no failures, but 3 informational items about low velocity (sediment risk).

To see violations in the table:
1. Right-click the Pipe Results table.
2. Click **"Show only violations"**.
3. Red-highlighted rows appear (if any). Currently there are none.
4. Click **"Show all"** to reset the filter.

The canvas also colours pipes by velocity: blue = low, red = high.
To change colour mode: **View > Colour Mode > Pressure** or **Velocity**.

---

## Step 7: Fixing a Violation

Let's create a violation, then fix it. We will simulate a fire flow scenario
where P17 (the DN100 cul-de-sac to J13) carries 25 LPS and exceeds the
2.0 m/s velocity limit.

### Create the problem (for learning purposes):

In a real design, you would run fire flow analysis (Step 9). For now,
understand that P17 at DN100 carrying 25 LPS gives:
```
V = Q / A = 0.025 / (pi/4 x 0.110^2) = 2.64 m/s  >  2.0 m/s  FAIL
```

### Fix it in Edit Mode:

1. Click **Edit > Edit Mode** (or the Edit button in the toolbar).
2. Click on pipe **P17** in the canvas. Its properties appear in the right panel.
3. Find the **Diameter** row. It shows "110 mm" (DN100).
4. Double-click the diameter value and change it to **160** (DN150).
5. Press **Enter** to confirm.
6. The pipe width on the canvas may update to reflect the larger diameter.

### Verify the fix:

1. Press **F5** to re-run analysis.
2. Check P17 velocity in the Pipe Results table.
3. Expected new velocity: 0.025 / (pi/4 x 0.160^2) = **1.25 m/s** (PASS).

**Note:** After editing, use `Ctrl+Z` to undo if needed.

---

## Step 8: Re-Running and Verifying

After making the pipe diameter change:

1. Press **F5** to run steady-state analysis.
2. Check the status bar — should still show "WSAA: PASS".
3. Look at the Pipe Results table for P17:
   - Velocity should now be ~1.25 m/s (if fire flow demand is applied).
   - Under normal demand, velocity will be near 0.

4. Check that pressures haven't changed significantly — a diameter increase
   reduces headloss, so downstream pressures may increase slightly.

---

## Step 9: Running Fire Flow Analysis

1. Click **Analysis > Fire Flow** (or press **F8**).
2. In the Fire Flow dialog:
   - **Fire Node:** Select J13 (the furthest, lowest-elevation node).
   - **Fire Flow:** 25 LPS (WSAA Table 3.3 residential requirement).
   - Click **Run**.
3. The analysis runs steady-state with the fire flow demand added at J13.

**What you should see:**
- Residual pressure at J13 during fire flow: ~37 m (well above 12 m minimum).
- Velocities in the ring main: 0.3-0.7 m/s.
- P17 velocity depends on whether you upsized it in Step 7.

**WSAA fire flow criteria:**
- Residual pressure at fire node >= 12 m head
- Fire flow delivery >= 25 LPS for 2 hours
- All pipe velocities <= 2.0 m/s

---

## Step 10: Generating a Compliance Report

1. Click **File > Report > DOCX** (or **Analysis > Report**).
2. In the Report Builder dialog:
   - **Project Name:** "Brisbane 50-Lot Subdivision"
   - **Engineer:** Your name
   - Check all sections (Executive Summary, Network Summary, etc.)
   - Click **Generate DOCX**.
3. Choose a save location (e.g., `report.docx`).

**What the report contains:**
- Cover page with project name, engineer, date
- Executive summary with compliance overview
- Network description with junction and pipe tables
- Steady-state results: all pressures and flows
- Compliance summary: colour-coded PASS/WARNING/CRITICAL
- Conclusions and recommended actions

The report is ready for peer review or submission to the water authority.

---

## Step 11: Saving the Project

1. Press **Ctrl+S** (or **File > Save Project**).
2. Save as a `.hap` file (e.g., `subdivision.hap`).

The `.hap` file stores:
- Path to the .inp network file
- All analysis results (pressures, flows, compliance)
- Slurry parameters (if configured)
- Colour mode and view settings

This means you can close the application and reopen with all results preserved.

---

## Step 12: Closing and Reopening

1. Close the application (File > Exit or click X).
2. Relaunch: `python main_app.py`
3. Open the `.hap` file: **File > Open** and select your `.hap` file.

**What you should see:**
- Network loads with all junctions, pipes, and reservoir.
- Results tables are populated (analysis results restored from .hap).
- WSAA status bar shows the same compliance status as before.
- If the .inp file has been modified since saving, you will see a
  warning about file modification time.

**Congratulations!** You have completed a full hydraulic design workflow:
load network, run analysis, identify issues, fix a violation, verify,
run fire flow, generate a compliance report, and save the project.

---

## Quick Reference

| Action | Shortcut | Menu |
|--------|----------|------|
| Open file | Ctrl+O | File > Open |
| Save project | Ctrl+S | File > Save Project |
| Steady-state | F5 | Analysis > Steady State |
| Fire flow | F8 | Analysis > Fire Flow |
| Fit view | Ctrl+F | — |
| Undo | Ctrl+Z | Edit > Undo |
| Compliance check | F9 | Analysis > Design Compliance |
| Generate report | — | File > Report > DOCX |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No network loaded" | Open an .inp file first (Ctrl+O) |
| Network too small/large | Press Ctrl+F to fit view |
| Results tables empty | Run analysis first (F5) |
| WSAA shows warnings | Check Node/Pipe Results for red cells |
| Report generation fails | Ensure python-docx is installed |
| .hap file won't load | Check that the .inp file path still exists |
| Analysis hangs | The network may be disconnected — check topology |

## CLI Alternative

For batch processing or CI integration, use the command-line interface:
```
python -m hydraulic_tool analyse network.inp --format json
python -m hydraulic_tool validate network.inp
python -m hydraulic_tool report network.inp --output report.docx
```

## Next Steps for Mechanical/Industrial Engineers
If you are designing mechanical pump systems, tailings lines, or industrial process piping (rather than municipal grids), it is highly recommended that you load and run the following tutorials next to understand the advanced physics solvers:

1. **`tutorials/multistage_pump/network.inp`** — Demonstrates configuring series pumps for high-head applications.
2. **`tutorials/mining_slurry_line/network.inp`** — Demonstrates configuring Non-Newtonian (Bingham Plastic) slurry parameters using the **Analysis > Slurry Mode** toggle.
3. **Transient Surge Analysis** — Open the multistage pump tutorial and press **F6** to see how the TSNet solver models the water hammer envelope after a pump trip.

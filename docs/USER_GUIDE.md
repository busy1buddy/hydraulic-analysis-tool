# User Guide — EPANET Hydraulic Analysis Toolkit

**Version:** v1.0.0-release | **Target audience:** Australian water supply and mining engineers

This guide covers everything you need to perform professional hydraulic analysis from first launch to printed report. No Python knowledge required.

---

## 1. Installation

### Option A — Windows Installer (recommended)

1. Run **HydraulicAnalysisTool-Setup.exe** from the `installer/` folder or the provided USB drive.
2. Follow the on-screen prompts. Default install location: `C:\Program Files\HydraulicAnalysisTool\`
3. A desktop shortcut **Hydraulic Analysis Tool** is created automatically.
4. Double-click the shortcut to launch. First startup may take 5–10 seconds while the solver initialises.

### Option B — Python source (developers)

Requires Python 3.10 or higher and pip.

```
pip install -r requirements.txt
python main_app.py
```

### Verify it works

The main window should appear with a blank canvas and the menu bar showing **File / Edit / Analysis / Water Quality / View / Tools / Help**. The status bar at the bottom shows **No network loaded**.

If the window does not open, check that your antivirus is not blocking the executable, or contact your IT department for the signed installer.

---

## 2. Opening a Network

### File > Open (.inp)

1. Click **File > Open (.inp)...** or press **Ctrl+O**.
2. Browse to your EPANET `.inp` file and click Open.
3. The network appears on the canvas. Node and pipe counts are shown in the status bar.

### Drag and drop

Drag an `.inp` file from Windows Explorer directly onto the application window. The network loads immediately.

### Open Tutorial

1. Click **File > Open Tutorial...**
2. A dialog lists all 10 built-in tutorial networks (see Section 10 for descriptions).
3. Select a tutorial and click Open. The network and all pre-configured scenarios load.

### What you see after loading

- **Canvas (centre):** nodes shown as circles, pipes as lines. Use scroll wheel to zoom, drag to pan, and click **Fit** in the canvas toolbar to zoom to fit.
- **Properties panel (right):** click any node or pipe to see its ID, elevation, demand, diameter, and roughness.
- **Scenarios panel (far right):** lists any scenarios saved with the project.

---

## 3. Running Analysis

All analysis commands are in the **Analysis** menu or available via keyboard shortcut. You must load a network first.

### Steady State (F5)

Solves the network at a single instant in time using base demands.

1. Press **F5** or click **Analysis > Run Steady State**.
2. Results appear immediately in the Results panel below the canvas:
   - **Node table:** junction ID, pressure (m), elevation (m AHD), demand (LPS).
   - **Pipe table:** pipe ID, flow (LPS), velocity (m/s), headloss (m/km).
   - **WSAA Compliance:** pass/fail summary (see Section 4).
3. The canvas colours pipes and nodes by pressure (default). Use the ColourMap controls top-right to change variable.

### Transient / Water Hammer (F6)

Simulates a rapid valve closure or pump trip and calculates the resulting pressure surge.

1. Press **F6** or click **Analysis > Run Transient**.
2. A dialog asks for:
   - **Valve ID** — the valve element to close (e.g., V1).
   - **Closure time (s)** — time to fully close. Values under 2 s produce significant water hammer.
   - **Wave speed (m/s)** — depends on pipe material: PE 300, PVC 400, Ductile Iron 1100, Steel 1100.
   - **Duration (s)** — total simulation length. Allow at least 5× the pipe travel time.
3. Results show maximum surge pressure (m and kPa), surge wave envelope, and whether the pressure exceeds the pipe pressure rating.

### Extended Period Simulation / EPS (F7)

Runs the network over 24 hours (or longer) using an hourly demand pattern.

1. Press **F7** or click **Analysis > Run Extended Period (EPS)**.
2. Optionally set the pattern duration (24 h, 48 h, or 168 h) in the dialog.
3. Results show pressure and velocity envelopes (min/max band) across all timesteps.
4. Use the AnimationPanel (bottom of canvas) to step through each hour.
5. WSAA compliance is checked at **every timestep** — a network that passes at average demand may fail at peak hour.

### Fire Flow Wizard (F8)

Tests whether each node can sustain a 25 LPS fire demand while maintaining 12 m residual pressure (WSAA requirement).

1. Press **F8** or click **Analysis > Fire Flow Wizard...**
2. Set the required flow (default 25 LPS) and residual pressure (default 12 m).
3. Click **Run**. The wizard sweeps all nodes automatically.
4. The canvas shows a colour-coded fire flow map: green = adequate, red = inadequate.
5. The Results panel lists every node with its available fire flow and pass/fail status.

---

## 4. Understanding Results

### Node pressure table

| Column | Units | WSAA Requirement |
|--------|-------|-----------------|
| Pressure | m head | 20–50 m |
| Elevation | m AHD | — |
| Demand | LPS | — |

Cells highlighted in **red** are outside the WSAA range. A pressure below 20 m means the service connection may not function. A pressure above 50 m means pipes are overpressured and PRVs may be required.

### Pipe flow and velocity table

| Column | Units | WSAA Requirement |
|--------|-------|-----------------|
| Flow | LPS | — |
| Velocity | m/s | < 2.0 m/s |
| Headloss | m/km | — (informational) |

Velocity above 2.0 m/s is flagged in red. High velocity causes noise, erosion, and water hammer risk. Consider upsizing the pipe diameter.

### WSAA Compliance summary

The compliance panel appears after any analysis run. It shows:

- **PASS** (green) — all nodes within 20–50 m pressure and all pipes below 2.0 m/s.
- **FAIL** (red) — one or more violations, listed by element ID with the measured value.

The compliance check references WSAA *Water Supply Code of Australia* (WSA 03) and the specific threshold is noted alongside each result (e.g., "WSAA minimum 20 m — Junction J4: 17.3 m").

### Pressure display

Pressures are shown to one decimal place (e.g., 23.4 m). This is the precision appropriate for engineering assessment — the solver produces more decimal places but the last digit has no physical significance at pipe network scale.

### Velocity display

Velocities are shown to two decimal places (e.g., 1.87 m/s), matching the precision needed to assess compliance with the 2.00 m/s WSAA limit.

---

## 5. Canvas Features

### Colour modes

Use the **ColourMap** widget in the top-right panel to change what the colours represent:

| Mode | What it shows |
|------|--------------|
| Pressure | Node pressure in m head (blue = low, red = high) |
| Velocity | Pipe velocity in m/s |
| Headloss | Pipe headloss gradient in m/km |
| Flow | Pipe flow rate in LPS |
| Water Age | Hours since water entered the network (requires water quality run) |
| Chlorine | Chlorine residual in mg/L (requires chlorine decay run) |

The ColourBar on the right side of the panel shows the scale. Units are always labelled.

### Value overlay

Click the **Values** button in the canvas toolbar to show numeric values on every element. The display shows the currently active colour mode variable. For large networks (200+ elements), values may overlap — zoom in to read individual elements.

### Labels

Click the **Labels** button to toggle node and pipe ID labels on the canvas.

### Pipe DN scaling

Click **View > Scale Pipes by DN** to draw pipe widths proportional to their nominal diameter. DN63 (PE service pipe) appears thin; DN900 (concrete trunk main) appears thick. This helps quickly identify the network hierarchy.

### Node demand scaling

Click **View > Scale Nodes by Demand** to size junction circles proportional to their base demand. Zero-demand nodes (e.g., intermediate connections) appear as small dots; high-demand nodes appear larger.

### Probe tool

Click the **Probe** button in the canvas toolbar to enter probe mode. Click any node or pipe on the canvas to see a floating tooltip showing all hydraulic result variables for that element at the current timestep. Press **Escape** to dismiss the tooltip and exit probe mode.

### Fit to window

Click the **Fit** button in the canvas toolbar (or use the keyboard shortcut **Ctrl+F**) to zoom and pan the canvas so the entire network is visible.

### Edit mode

Click the **Edit** button to enter edit mode. In edit mode you can:
- Left-click an empty area to add a junction.
- Right-click a node or pipe to delete it.
- Use the editor programmatically via **Edit > Undo** (Ctrl+Z) and **Edit > Redo** (Ctrl+Y).

---

## 6. Slurry Mode

Slurry mode applies a non-Newtonian rheology model to replace the standard Hazen-Williams friction formula. Use this for mining tailings lines, paste fill pipelines, and cement or polymer slurries.

### Enabling slurry mode

1. Load your network as normal.
2. Click **Analysis > Slurry Mode** (checkable menu item). A slurry parameters panel appears below the ColourMap.

### Setting slurry parameters

| Parameter | Description | Typical range |
|-----------|-------------|--------------|
| Fluid type | Preset or custom | See list below |
| Density (kg/m³) | Slurry bulk density | 1100–1800 |
| Yield stress (Pa) | Minimum shear stress to initiate flow (Bingham/H-B) | 5–100 Pa |
| Plastic viscosity (Pa·s) | Post-yield viscosity (Bingham) | 0.01–0.2 |
| Consistency index K | Power-law coefficient | 0.01–10 |
| Flow index n | Power-law exponent (< 1 = shear thinning) | 0.2–1.0 |

**Built-in fluid presets:**

| Preset | Model | Typical use |
|--------|-------|-------------|
| mine_tailings_30pct | Bingham plastic | 30% solids copper or gold tailings |
| mine_tailings_50pct | Bingham plastic | 50% solids high-density tailings |
| paste_fill_70pct | Bingham plastic | Paste fill for underground voids |
| cement_slurry | Bingham plastic | Cement grouting and backfill |
| polymer_solution | Power law | Drag-reducing polymer injection |
| drilling_mud | Herschel-Bulkley | Directional drilling |

### Running slurry analysis

Press **F5** (Steady State) with slurry mode enabled. The solver applies the selected rheology model to every pipe and reports:

- Headloss per pipe using the Buckingham-Reiner (Bingham laminar), Wilson-Thomas (turbulent), or power-law formulation.
- Flow regime (laminar / turbulent / transition) per pipe.
- A comparison table showing slurry headloss vs the equivalent water headloss.

### Interpretation

Slurry headloss is almost always higher than water headloss for the same flow rate. If the slurry velocity is below the deposition velocity, the pipe may settle and block. The results panel flags any pipe at risk.

### Disabling slurry mode

Click **Analysis > Slurry Mode** again to uncheck it. The next analysis run uses standard Hazen-Williams.

---

## 7. Scenarios

Scenarios allow you to compare a base network against alternatives — for example, a pipe upsizing, a demand growth projection, or a roughness deterioration study.

### Creating a scenario

1. In the **Scenarios** panel (right side of window), click **New Scenario**.
2. Enter a name (e.g., "Upsize P6 to DN250") and an optional description.
3. Define modifications:
   - **Pipe diameter** — select a pipe ID and enter the new diameter in mm.
   - **Pipe roughness** — select a pipe ID and enter the new Hazen-Williams C-factor.
   - **Demand factor** — apply a multiplier to all junction demands (e.g., 1.3 for 30% growth).
   - **Demand set** — set a specific junction to a fixed demand in LPS.
4. Click **Save**. The scenario appears in the scenarios list.

### Running all scenarios

Click **Run All** in the Scenarios panel to solve every scenario in sequence. Progress is shown in the status bar.

### Comparison table

After running all scenarios, click **Compare** to open the scenario comparison table. Columns show each scenario; rows show key metrics:

- Minimum network pressure (m)
- Maximum pipe velocity (m/s)
- WSAA compliance (pass/fail)
- Pump operating point (if applicable)
- Total network headloss (m)

Cells that differ significantly from the base case are highlighted.

### Saving and loading

Scenarios are saved in the `.hap` project file (File > Save As). To reload a project with all its scenarios, use File > Open and select the `.hap` file.

---

## 8. Water Quality

Water quality analysis tracks how a substance (or water age) changes as water travels through the network. Requires a network loaded and at least one reservoir source defined.

### Water Age

Estimates how long water has been in the network at each node. Old water (high age) indicates dead ends, poor circulation, or oversized storage.

1. Click **Water Quality > Water Age...**
2. Set the simulation duration (default 72 hours — long enough for the network to reach a repeating pattern).
3. Click **Run**. Results show water age in hours at each junction.
4. Change the canvas colour mode to **Water Age** to see the spatial distribution.

WSAA guideline: water age should not exceed 3 days (72 hours) at any service connection.

### Chlorine Decay

Models the decay of chlorine residual as water travels through the network.

1. Click **Water Quality > Chlorine Decay...**
2. Set parameters:
   - **Initial concentration (mg/L)** — chlorine at the reservoir/source (typically 0.5–1.0 mg/L for treated water).
   - **Bulk decay coefficient (1/day)** — rate of decay in the bulk water volume (typical: 0.5–2.0).
   - **Wall decay coefficient (m/day)** — rate of decay at the pipe wall (typical: 0.01–0.1 for lined pipes).
3. Click **Run**. Results show chlorine concentration in mg/L at each junction.
4. Change the canvas colour mode to **Chlorine** to see the spatial distribution.

WSAA requirement: minimum residual chlorine of 0.2 mg/L at all service connections.

### Trace

Tracks the proportion of water originating from a selected source node. Useful for blending analysis in multi-source systems.

1. Click **Water Quality > Trace...**
2. Select the source node to trace from.
3. Click **Run**. Results show percentage (0–100%) from the selected source at each junction.

---

## 9. Reports

Reports compile analysis results into a professional engineering document suitable for client delivery or design documentation.

### Generating a report

1. Run at least one analysis (Steady State, Transient, or Fire Flow) so results are available.
2. Click **File > Generate Report...** or use the Reports button in the Results panel.
3. In the report dialog:
   - **Title** — project title (e.g., "Drummoyne WA — Reticulation Upgrade")
   - **Engineer name** — displayed on the cover page
   - **Project number** — for filing reference
   - **Format** — DOCX (full formatting) or PDF (basic formatting)
   - **Include sections** — check/uncheck to include Steady State, Transient, Fire Flow, Water Quality as applicable
4. Click **Generate**. The report is saved to the `output/` folder and the path is shown in the status bar.

### Report sections

A full report includes:

1. Cover page — project title, engineer, date, project number
2. Network description — element counts, source heads, total demand
3. Node table — all junctions with elevation, pressure, demand
4. Pipe table — all pipes with diameter, length, roughness, flow, velocity
5. WSAA compliance summary — pass/fail for pressure and velocity
6. Transient results — surge pressures and envelope (if run)
7. Fire flow results — availability map and node compliance (if run)
8. Water quality results — age or chlorine summary (if run)
9. Conclusions — auto-generated summary of compliance status

### DOCX vs PDF

DOCX format produces the best output: formatted tables, bold headings, compliance colour coding, and editable text for the engineer to annotate. PDF is available for quick sharing but uses basic formatting without colour.

---

## 10. Tutorials

Open any tutorial via **File > Open Tutorial...**. Each tutorial includes a pre-built network, scenarios, and engineering notes in the `README.md` file inside the tutorial folder.

| # | Tutorial | Description |
|---|----------|-------------|
| 1 | **Simple Loop** | 6-node looped residential network. Learn how loops balance flow and pressure, and verify WSAA pressure compliance. |
| 2 | **Dead End Network** | Branching tree with an 800 m dead-end branch. See how water age stagnates and plan a flushing program. |
| 3 | **Pump Station** | Single pump lifting water to an elevated distribution zone. Find the pump operating point on the system curve. |
| 4 | **Pressure Zone Boundary** | Two pressure zones separated by a PRV. Select the correct PRV set-point to protect the low-pressure zone. |
| 5 | **Fire Flow Demand** | Residential network under 25 LPS fire demand. Check WSAA fire flow residual (12 m at 25 LPS) at every node. |
| 6 | **Mining Slurry Line** | Straight pipeline comparing water vs Bingham plastic slurry. Quantify the headloss penalty for high-density tailings. |
| 7 | **Multistage Pump** | Two pumps in series for a high-elevation supply. Assess head addition, single-pump failure, and transient starting point. |
| 8 | **Elevated Tank** | Gravity-fed distribution from a steel tank. Observe how tank drawdown affects pressure at the furthest junction. |
| 9 | **Industrial Ring Main** | Large DN400–DN600 ring main for a mining estate. Apply the 120 m HGL threshold and assess N-1 pipe security. |
| 10 | **Rehabilitation Comparison** | Old cast-iron main (C=80) vs cement-lined pipe (C=130). Quantify the headloss reduction and compliance recovery. |

---

## 11. Keyboard Shortcuts

### File

| Shortcut | Action |
|----------|--------|
| Ctrl+N | New project |
| Ctrl+O | Open .inp file |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save As (.hap project file) |
| Ctrl+Q | Exit |

### Edit

| Shortcut | Action |
|----------|--------|
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Escape | Cancel pipe creation / hide probe tooltip |

### Analysis

| Shortcut | Action |
|----------|--------|
| F5 | Run Steady State |
| F6 | Run Transient |
| F7 | Run Extended Period (EPS) |
| F8 | Fire Flow Wizard |

### Canvas

| Shortcut | Action |
|----------|--------|
| Ctrl+F | Fit network to window |
| Scroll wheel | Zoom in / out |
| Middle-click drag | Pan |

### Help

| Shortcut | Action |
|----------|--------|
| F1 | Show keyboard shortcuts dialog |

---

## Quick Reference — Australian Standards

| Standard | Requirement | Value |
|----------|-------------|-------|
| WSAA WSA 03 | Minimum service pressure | 20 m head |
| WSAA WSA 03 | Maximum service pressure | 50 m head |
| WSAA WSA 03 | Maximum pipe velocity | 2.0 m/s |
| WSAA WSA 03 | Fire flow residual pressure | 12 m at 25 LPS |
| WSAA WSA 03 | Maximum water age | 72 hours |
| WSAA WSA 03 | Minimum chlorine residual | 0.2 mg/L |
| AS 2280 | Ductile iron pressure class | PN25 / PN35 |
| AS/NZS 1477 | PVC pressure class | PN12 / PN18 |
| AS/NZS 4130 | PE/HDPE pressure class | SDR11 PN16 |

---

*For technical support, see `docs/` for the API reference, validation reports, and roadmap. For Python API usage, see the legacy `docs/USER_GUIDE.md` (the version in the project root covers the Python API and web dashboard).*

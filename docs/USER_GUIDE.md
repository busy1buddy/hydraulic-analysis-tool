# User Guide — Hydraulic Analysis Toolkit

## Installation

**Requirements:** Python 3.11+, PyQt6

```bash
pip install -r requirements_desktop.txt
python main_app.py
```

## Quick Start: Your First Analysis in 5 Minutes

1. **File > Open** (Ctrl+O) -- select an `.inp` file
2. Press **F5** to run steady-state analysis
3. Results appear in the bottom panel
4. Change colour mode to **Pressure** or **WSAA Compliance**
5. Red nodes = WSAA violations, green = compliant

## Opening Networks

- **`.inp` files** -- EPANET format (from WaterGEMS, InfoWater, etc.)
- **`.hap` files** -- Project files with saved results and scenarios
- **File > Load Tutorial** for example networks

## Running Analysis

### Steady-State (F5)

- Runs EPANET hydraulic simulation
- Results: pressures (m), velocities (m/s), headloss (m/km)
- Compliance checked automatically against WSAA WSA 03-2011

### Transient / Water Hammer (F6)

- Simulates pressure surge from valve closure or pump trip
- Results: maximum surge pressure, time history
- Recommendations for surge protection sizing

### Extended Period Simulation (F7)

- 24-hour simulation with demand patterns
- Shows pressure variation over time
- Identifies peak/off-peak conditions

### Fire Flow (F8)

- Tests WSAA fire flow requirement: 25 LPS at 12 m residual
- Sweeps all hydrant nodes to find weakest point

### Design Compliance Check (F9)

- Formal 6-check WSAA compliance certificate
- Checks: pressure, velocity, fire flow, water age, pipe stress, resilience

## Understanding Results

### Pressure (m)

- WSAA minimum: 20 m (service pressure)
- WSAA maximum: 50 m (residential)
- Red highlighting = violation
- Mining/industrial: up to 120 m acceptable

### Velocity (m/s)

- WSAA maximum: 2.0 m/s
- Below 0.6 m/s: sediment risk
- Red highlighting = exceeds limit

### Headloss (m/km)

- Read directly from EPANET solver
- High headloss = undersized pipe or high roughness

## Colour Modes

| Mode | What it shows |
|---|---|
| **WSAA Compliance** | Green/amber/red per node against WSAA thresholds |
| **Pressure** | Continuous colourmap across all nodes |
| **Velocity** | Pipe velocity colourmap |
| **Headloss** | Pipe headloss colourmap |
| **Status** | Element status (open/closed/active) |

## Slurry Mode

For mining concentrate lines, tailings, and other non-Newtonian fluids:

1. **Analysis > Slurry Parameters** -- set yield stress, plastic viscosity, and density
2. **Analysis > Slurry Mode** -- enable slurry calculations
3. Press **F5** -- headloss now shows slurry values
4. The **Regime** column shows laminar or turbulent flow
5. Use for mining concentrate lines, tailings

## Network Editing

- Click the **Edit** button in the toolbar to enter edit mode
- Click on the canvas to add junctions, drag to move them
- Right-click for context menu (add pipe, delete element)
- **Ctrl+Z** to undo, **Ctrl+Y** to redo
- Live analysis updates results as you edit

## Scenarios

- Add scenarios with different demand multipliers
- Compare side-by-side in the Scenario panel
- Difference reports show impact of changes

## What-If Analysis

1. **View > Toggle What-If Panel**
2. Slide the demand multiplier (50-200%)
3. Pressure changes update in real-time on the canvas

## Generating Reports

- **Reports > Generate DOCX** or **Reports > Generate PDF**
- Includes: network summary, results tables, compliance status
- Suitable for regulatory submission

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+N | New network |
| Ctrl+O | Open file |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save As (.hap) |
| Ctrl+Q | Exit |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Ctrl+F | Fit view |
| F5 | Run steady-state |
| F6 | Run transient |
| F7 | Run EPS |
| F8 | Fire flow |
| F9 | Design compliance |
| F10 | Quick assessment |
| F1 | Keyboard shortcuts |

## Troubleshooting

| Problem | Solution |
|---|---|
| "No network loaded" | Use File > Open first |
| Negative pressure | Check reservoir head and elevation |
| Solver won't converge | Check for disconnected nodes (Tools > Diagnose) |
| Slurry headloss very high | Normal -- slurry has much higher friction than water |

## Australian Pipe Database

The tool includes pipe data for:

| Material | Standard | Sizes | C-factor (new) |
|---|---|---|---|
| Ductile Iron | AS 2280 | DN100 - DN600 | C = 140 |
| PVC | AS/NZS 1477 | DN100 - DN375 | C = 150 |
| PE/HDPE | AS/NZS 4130 | DN63 - DN630 | C = 150 |
| Concrete | AS 4058 | DN300 - DN900 | C = 90-120 |

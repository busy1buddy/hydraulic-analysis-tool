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

- Calculated from pipe properties using the Hazen-Williams formula. Matches EPANET solver output for H-W networks.
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

## Guide for Mechanical & Industrial Engineers

If you are coming from a mechanical engineering, mining, or industrial piping background (e.g., using AFT Fathom or Pipe-Flo), please note the following differences in this software:

### 1. WSAA Compliance Warnings (Velocities)
This tool automatically flags pipes that exceed **2.0 m/s** in red as a "FAIL". This is based on the WSAA (Water Services Association of Australia) municipal code for plastic/AC pipes. If you are designing heavy-duty industrial steel pipelines where 3.0 - 4.5 m/s is acceptable, you can safely ignore these red WSAA warnings. Your design is mathematically sound; it just violates a municipal standard.

### 2. Civil vs. Mechanical Terminology
Because the underlying engine (EPANET) was built for city grids, the terminology differs from mechanical CAD:
- **Reservoir**: Represents an infinite source of water at a fixed pressure or head (e.g., a pressurized feed tank, or a large suction header). 
- **Junction**: Represents a standard node where pipes meet, or where flow is extracted/injected into the system.
- **Tank**: Represents a finite storage vessel whose water level changes over time based on flow.

### 3. 1D Node-Link Abstraction
Unlike SolidWorks or Inventor, this is a **1D hydraulic solver**. It does not import 3D STEP/IGES geometry. You must mentally abstract your 3D pipe routing into a simplified 2D "Node and Link" schematic. 
- You must manually calculate and input "Minor Loss Coefficients" (K-factors) for all elbows, tees, and valves into the pipe properties, as the software will not automatically detect them from geometry.

### 4. Transient (Water Hammer) Complexity
The **Transient Analysis (F6)** tool is powerful but requires precise physics inputs. If you do not specify the correct **Wave Speed (Celerity)** for your specific pipe material (e.g., ~1200 m/s for Steel vs. ~300 m/s for PVC), the surge pressure results will be wildly inaccurate. Ensure your valve closure times and wave speeds are correct before relying on the surge envelope results.

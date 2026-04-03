# User Guide

Complete guide to using the EPANET Hydraulic Analysis Toolkit.

---

## 1. Installation

### Prerequisites
- Python 3.10 or higher
- pip package manager

### Install Dependencies
```bash
cd EPANET_CLAUDE
pip install -r requirements.txt
```

This installs: WNTR, EPyT, TSNet, FastAPI, uvicorn, matplotlib, numpy, pandas, scipy, networkx, plotly.

### Verify Installation
```bash
python -c "import wntr; import tsnet; import epyt; print('All packages OK')"
```

---

## 2. Web Dashboard

### Starting the Dashboard
```bash
python server.py
```
The dashboard launches at **http://localhost:8765** (port 8765).

### From Claude Code
The dashboard is pre-configured in `.claude/launch.json`. Claude Code can launch it via Preview MCP and interact with all controls programmatically.

### Dashboard Tabs

#### Steady-State Analysis Tab
1. **Select a network** from the dropdown (loads .inp files from `models/`)
2. Click **Run Steady-State Analysis**
3. View results:
   - **Network Topology** - interactive Plotly map of nodes and pipes
   - **WSAA Compliance** - automatic check against Australian standards
   - **Junction Pressures** - 24hr pressure profiles with WSAA 20m minimum line
   - **Pipe Flows** - 24hr flow profiles in LPS
   - **Metrics** - min pressure, max velocity, total demand

#### Transient / Water Hammer Tab
1. **Select the network** containing a valve (e.g., `transient_network.inp`)
2. **Set parameters**:
   - **Valve ID**: name of the valve element (e.g., `V1`)
   - **Closure Time**: how fast the valve closes (seconds). Shorter = more severe hammer
   - **Start Time**: when closure begins in the simulation
   - **Wave Speed**: pressure wave velocity in pipes (m/s). Depends on pipe material
   - **Duration**: total simulation time (seconds)
3. Click **Run Water Hammer Analysis**
4. View results:
   - **Transient Head** - pressure oscillations over time at each junction
   - **Pressure Envelope** - max/min transient vs steady-state
   - **Compliance** - check against PN35 pipe rating (3500 kPa)
   - **Mitigation** - recommended surge protection measures

#### Joukowsky Calculator Tab
Quick calculation of instantaneous pressure rise from velocity change:
- **Formula**: dH = (a x dV) / g
- Select pipe material to auto-set wave speed, or enter custom value
- Enter velocity change (m/s) - typically the flow velocity before valve closure
- Results shown in metres of head and kPa

---

## 3. Python API

### Basic Usage

```python
from epanet_api import HydraulicAPI

api = HydraulicAPI()
```

### Loading an Existing Network

```python
summary = api.load_network('australian_network.inp')
print(summary)
# {'junctions': 7, 'reservoirs': 1, 'tanks': 1, 'pipes': 9, ...}
```

Network files are loaded from the `models/` directory.

### Running Steady-State Analysis

```python
results = api.run_steady_state()

# Access pressures
for junction, data in results['pressures'].items():
    print(f"{junction}: min={data['min_m']}m, max={data['max_m']}m")

# Access flows
for pipe, data in results['flows'].items():
    print(f"{pipe}: avg={data['avg_lps']} LPS, velocity={data['avg_velocity_ms']} m/s")

# Check compliance
for item in results['compliance']:
    print(f"{item['type']}: {item['message']}")

# Plot saved to output/api_steady_results.png
print(results['plot'])
```

### Running Transient Analysis

```python
api.load_network('transient_network.inp')

result = api.run_transient(
    valve_name='V1',        # Valve to close
    closure_time=0.5,       # Seconds (rapid = water hammer)
    start_time=2.0,         # Start closure at t=2s
    wave_speed=1000,        # m/s (ductile iron)
    sim_duration=20,        # Total simulation seconds
)

print(f"Max surge: {result['max_surge_m']}m ({result['max_surge_kPa']} kPa)")

for junction, data in result['junctions'].items():
    print(f"{junction}: surge={data['surge_m']}m, max={data['max_head_m']}m")

for rec in result['mitigation']:
    print(f"  - {rec}")
```

### Creating a Network from Scratch

```python
summary = api.create_network(
    name='my_suburb',
    reservoirs=[
        {'id': 'R1', 'head': 80, 'x': 0, 'y': 50},
    ],
    junctions=[
        {'id': 'J1', 'elevation': 50, 'demand': 0, 'x': 15, 'y': 50},
        {'id': 'J2', 'elevation': 45, 'demand': 10, 'x': 30, 'y': 45},
        {'id': 'J3', 'elevation': 42, 'demand': 15, 'x': 45, 'y': 40},
    ],
    pipes=[
        {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
         'diameter': 300, 'roughness': 130},
        {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 400,
         'diameter': 250, 'roughness': 130},
        {'id': 'P3', 'start': 'J2', 'end': 'J3', 'length': 350,
         'diameter': 200, 'roughness': 120},
    ],
    valves=[
        {'id': 'V1', 'start': 'J2', 'end': 'J3', 'diameter': 200,
         'type': 'TCV', 'setting': 1},
    ],
    tanks=[
        {'id': 'T1', 'elevation': 55, 'init_level': 3, 'min_level': 0.5,
         'max_level': 5, 'diameter': 12, 'x': 30, 'y': 70},
    ],
    duration_hrs=24,
    pattern=[0.5, 0.4, 0.3, 0.3, 0.5, 0.8,
             1.2, 1.5, 1.3, 1.0, 0.9, 0.8,
             0.7, 0.6, 0.7, 0.9, 1.3, 1.5,
             1.4, 1.2, 1.0, 0.8, 0.7, 0.6],
)

# Saved to models/my_suburb.inp automatically
```

**Parameter notes:**
- `demand` is in **LPS** (litres per second)
- `diameter` is in **mm** (converted to metres internally)
- `elevation` and `head` are in **metres**
- `roughness` is Hazen-Williams C-factor (typical: 110-140)
- `pattern` is a 24-element demand multiplier list (one per hour)

### Joukowsky Quick Calculator

```python
result = api.joukowsky(wave_speed=1000, velocity_change=1.5)
print(f"Pressure rise: {result['head_rise_m']}m = {result['pressure_rise_kPa']} kPa")
```

### Exporting Results

```python
api.export_results_json(results, 'my_analysis.json')
# Saved to output/my_analysis.json
```

---

## 4. Standalone Scripts

### Steady-State Analysis
```bash
python run_hydraulic_analysis.py
```
Runs a 24-hour extended period simulation on `models/australian_network.inp` and:
- Prints junction pressures, pipe flows, velocities
- Checks WSAA compliance
- Saves plot to `output/hydraulic_results.png`

### Transient Analysis
```bash
python run_transient_analysis.py
```
Runs water hammer analysis on `models/transient_network.inp` with 0.5s valve closure:
- Prints Joukowsky surge calculations
- Checks against PN35 pipe rating
- Provides mitigation recommendations
- Saves plot to `output/transient_results.png`

---

## 5. Network Model Files (.inp)

### Format
EPANET `.inp` files are plain text. Key sections:

| Section | Content |
|---------|---------|
| `[JUNCTIONS]` | Node ID, elevation (m), base demand (LPS) |
| `[RESERVOIRS]` | Source ID, head (m) |
| `[TANKS]` | Tank ID, elevation, levels, diameter |
| `[PIPES]` | Pipe ID, start/end nodes, length (m), diameter (mm), roughness |
| `[VALVES]` | Valve ID, nodes, diameter, type, setting |
| `[OPTIONS]` | Units (LPS), headloss method (H-W) |
| `[TIMES]` | Duration, timestep |
| `[COORDINATES]` | Node positions for visualization |

### Included Models

**`australian_network.inp`** - 7-junction suburban distribution network
- 1 reservoir (R1, 80m head)
- 1 elevated tank (T1)
- 9 pipes (150-300mm diameter)
- 24-hour demand pattern
- Total base demand: 38 LPS

**`transient_network.inp`** - 6-junction network with valve for water hammer
- 1 reservoir (R1, 80m head)
- 6 pipes + 1 TCV valve (V1)
- Designed for transient analysis scenarios

### Adding Your Own Network
1. Create an `.inp` file (use EPANET GUI or the Python API)
2. Save it to the `models/` directory
3. It will appear in the dashboard dropdown automatically

---

## 6. Australian Standards Reference

### WSAA Pressure Requirements
| Condition | Minimum Pressure |
|-----------|-----------------|
| Peak demand | 20m head (200 kPa) |
| Fire flow | 12m head (120 kPa) |
| Maximum static | 50m head (500 kPa) |

### Pipe Velocity Limits
| Pipe Type | Max Velocity |
|-----------|-------------|
| Distribution mains | 2.0 m/s |
| Trunk mains | 1.5 m/s |
| Service connections | 2.5 m/s |

### Pipe Pressure Ratings
| Class | Rating |
|-------|--------|
| PN16 | 1600 kPa |
| PN20 | 2000 kPa |
| PN25 | 2500 kPa |
| PN35 | 3500 kPa |

### Wave Speeds by Material
| Material | Wave Speed (m/s) |
|----------|-----------------|
| PE / HDPE | 250-350 |
| PVC | 350-500 |
| Ductile Iron | 1000-1200 |
| Steel | 900-1200 |
| Concrete | 1100-1300 |

---

## 7. API Endpoints (Dashboard Server)

When running `python server.py`, the following REST endpoints are available:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard HTML page |
| GET | `/api/networks` | List available .inp files |
| GET | `/api/network/{file}` | Network topology and details |
| GET | `/api/steady/{file}` | Run steady-state analysis |
| POST | `/api/transient` | Run transient analysis |
| POST | `/api/joukowsky` | Calculate Joukowsky pressure rise |

### Example: Calling via curl
```bash
# List networks
curl http://localhost:8765/api/networks

# Run steady-state
curl http://localhost:8765/api/steady/australian_network.inp

# Run transient
curl -X POST http://localhost:8765/api/transient \
  -H "Content-Type: application/json" \
  -d '{"inp_file":"transient_network.inp","valve":"V1","closure_time":0.5}'

# Joukowsky
curl -X POST http://localhost:8765/api/joukowsky \
  -H "Content-Type: application/json" \
  -d '{"wave_speed":1000,"velocity_change":2.0}'

# Fire flow
curl "http://localhost:8765/api/fireflow/australian_network.inp?node=J3&flow=25"

# Water quality
curl "http://localhost:8765/api/waterquality/australian_network.inp?parameter=age&duration=72"
```

---

## 8. Non-Newtonian / Slurry Analysis

For mining applications involving tailings, paste fill, or other non-Newtonian fluids.

### Available Fluids
```python
from slurry_solver import list_fluids, analyze_slurry_network
print(list_fluids())
# water, mine_tailings_30pct, mine_tailings_50pct, paste_fill_70pct,
# cement_slurry, polymer_solution, drilling_mud
```

### Running Slurry Analysis
```python
from epanet_api import HydraulicAPI
from slurry_solver import analyze_slurry_network
import wntr

api = HydraulicAPI()
api.load_network('australian_network.inp')

result = analyze_slurry_network(api.wn, 'mine_tailings_30pct')
for pipe, data in result['pipe_results'].items():
    print(f"{pipe}: headloss={data['headloss_m']}m, "
          f"velocity={data['velocity_ms']} m/s, regime={data['regime']}")
```

### Custom Fluid Properties
```python
custom = {
    'type': 'bingham_plastic',
    'density_kg_m3': 1400,
    'yield_stress_Pa': 12.0,
    'plastic_viscosity_Pa_s': 0.03,
    'description': 'Custom tailings',
}
result = analyze_slurry_network(api.wn, custom_fluid=custom)
```

### Rheological Models
| Model | Parameters | Use Case |
|-------|-----------|----------|
| Bingham Plastic | yield stress, plastic viscosity | Tailings, cement, paste fill |
| Power Law | consistency index K, flow index n | Polymer solutions, some muds |
| Herschel-Bulkley | yield stress, K, n | General non-Newtonian (most flexible) |

---

## 9. Pump Curve System

### Listing Available Pumps
```python
from data.pump_curves import list_pumps, recommend_pump

# All pumps
for p in list_pumps():
    print(f"{p['pump_id']}: {p['max_head_m']}m, {p['max_flow_lps']} LPS")

# Filter by application
water_pumps = list_pumps(application='water')
slurry_pumps = list_pumps(application='slurry')
```

### Pump Recommendation
```python
# Find best pump for 30 LPS at 40m head
recs = recommend_pump(required_flow_lps=30, required_head_m=40)
for r in recs:
    print(f"{r['model']}: {r['efficiency_pct']}% eff, "
          f"{r['head_margin_m']}m margin, score={r['suitability_score']}")
```

### System Curve & Operating Point
```python
from data.pump_curves import generate_system_curve, find_operating_point

sys_curve = generate_system_curve(
    static_head_m=25,       # Elevation difference
    pipe_length_m=1000,     # Total pipe length
    pipe_diameter_mm=200,   # Pipe diameter
    roughness=130,          # Hazen-Williams C
)

op = find_operating_point('WSP-200-40', sys_curve)
print(f"Operating at {op['flow_lps']} LPS, {op['head_m']}m, "
      f"{op['efficiency_pct']}% efficiency")
```

---

## 10. Pipe Stress Analysis

### Quick Stress Check
```python
from pipe_stress import analyze_pipe_stress

result = analyze_pipe_stress(
    pressure_kPa=1500,
    diameter_mm=200,
    wall_thickness_mm=7.0,
    material='ductile_iron',
    transient_factor=1.5,   # 50% surge on top of steady pressure
)
print(f"Hoop stress: {result['hoop_stress_MPa']} MPa")
print(f"Safety factor: {result['safety_factor_hoop']}")
print(f"Status: {result['status']}")
```

### Wall Thickness Design
```python
from pipe_stress import barlow_wall_thickness

design = barlow_wall_thickness(
    pressure_kPa=2500,
    diameter_mm=300,
    allowable_stress_MPa=300,  # Ductile iron yield
    safety_factor=2.5,
    corrosion_allowance_mm=1.5,
)
print(f"Minimum wall: {design['min_thickness_mm']}mm")
print(f"Design wall: {design['design_thickness_mm']}mm")
```

---

## 11. Scenario Comparison

### Creating and Comparing Scenarios
```python
from scenario_manager import ScenarioManager

mgr = ScenarioManager()

# Base case
mgr.create_scenario('base', 'australian_network.inp', description='Current network')

# Pipe upsizing scenario
mgr.create_scenario('upsize_p6', 'australian_network.inp',
    modifications=[{'type': 'pipe_diameter', 'target': 'P6', 'value': 250}],
    description='Upsize P6 from 150mm to 250mm',
)

# Demand growth scenario
mgr.create_scenario('growth_30pct', 'australian_network.inp',
    modifications=[{'type': 'demand_factor', 'value': 1.3}],
    description='30% demand growth projection',
)

# Run all and compare
mgr.run_all()
comparison = mgr.compare('base', 'growth_30pct')
for s in comparison['summary']:
    print(s)
```

### Available Modifications
| Type | Target | Value | Example |
|------|--------|-------|---------|
| `pipe_diameter` | Pipe ID | mm | Upsize P6 to 250mm |
| `pipe_roughness` | Pipe ID | C-factor | Age pipe to C=100 |
| `demand_factor` | (all) | multiplier | 1.3 = 30% growth |
| `demand_set` | Junction ID | LPS | Set J3 to 20 LPS |

---

## 12. Network Import

### From CSV
```python
from importers.csv_import import import_from_csv

result = import_from_csv('nodes.csv', 'pipes.csv', output_name='my_network')
print(f"Imported {result['total_nodes']} nodes, {result['total_links']} links")
```

**nodes.csv format:** `id, type, x, y, elevation, demand, head`
**pipes.csv format:** `id, start, end, length, diameter, roughness, type`

### From GIS Shapefile
```python
from importers.shapefile_import import import_from_shapefile

result = import_from_shapefile(
    'pipes.shp', 'nodes.shp',
    source_crs='EPSG:28355',  # MGA Zone 55
    output_name='gis_network',
)
```

### From DXF/CAD
```python
from importers.dxf_import import import_from_dxf

result = import_from_dxf(
    'drawing.dxf',
    pipe_layers=['WATER_MAINS'],
    junction_layers=['NODES'],
    default_diameter=200,
)
```

---

## 13. 3D Visualization

The 3D View tab in the NiceGUI dashboard renders the network in Three.js:

- **Load & Render** - displays the network in 3D with elevation
- **Run Analysis + Color** - runs steady-state and colors pipes by pressure or velocity
- **View presets** - Plan, Isometric, Side, Front views
- **Click elements** - shows properties in the info panel
- **Vertical Scale** - adjust elevation exaggeration (0.1 to 5.0)
- **Orbit controls** - drag to rotate, scroll to zoom, right-click to pan

---

## 14. Report Generation

### From Python API
```python
api.load_network('australian_network.inp')
steady = api.run_steady_state(save_plot=False)
path = api.generate_report(
    format='docx',
    steady_results=steady,
    title='Network Assessment',
    engineer_name='Jane Smith',
    project_name='Suburban Water Supply Upgrade',
)
print(f"Report saved: {path}")
```

### Report Sections
1. Cover page with project details and date
2. Network description with node and pipe tables
3. Steady-state results (pressures, flows, velocities)
4. Compliance summary (WSAA)
5. Transient results (if included)
6. Fire flow results (if included)
7. Water quality results (if included)
8. Auto-generated conclusions

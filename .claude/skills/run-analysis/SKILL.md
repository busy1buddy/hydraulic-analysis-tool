---
name: Run Hydraulic Analysis
description: Use when the user asks to run, simulate, or analyse a water network model. Covers steady-state hydraulic simulation, transient/water hammer analysis, and results interpretation with Australian WSAA compliance checking.
---

# Running Hydraulic Analysis

Always use the `HydraulicAPI` class from `epanet_api.py` - never the standalone scripts directly.

## Workflow

```python
from epanet_api import HydraulicAPI
api = HydraulicAPI()

# Step 1: Load the network
api.load_network('network_name.inp')  # from models/ directory

# Step 2: Run analysis
results = api.run_steady_state()      # 24hr extended period
# OR
results = api.run_transient('V1', closure_time=0.5)  # water hammer
```

## Steady-State Analysis
- Runs 24-hour extended period simulation via EPANET/WNTR
- Always report compliance results prominently (pressures, velocities)
- Key thresholds: minimum 20m pressure (WSAA), maximum 2.0 m/s velocity
- Plot saved to `output/` directory

## Transient Analysis
- Before running, verify the network has valves: check `api.wn.valve_name_list`
- TSNet MOC solver requires valve elements in the .inp file
- Key parameters: closure_time (seconds), wave_speed (m/s), sim_duration (seconds)
- Check results against PN35 pipe rating (3500 kPa)

## Presenting Results
- Always show compliance warnings first (they're what engineers care about)
- Report pressures in metres of head, flows in LPS, velocities in m/s
- For transient results, report surge in both metres and kPa
- Export results: `api.export_results_json(results, 'filename.json')` to output/
- Show generated plots using the Read tool on the PNG path in results['plot']

## Common Issues
- "V1 not found": selected network has no valve - use transient_network.inp
- Unicode errors on Windows: scripts handle this automatically via UTF-8 wrapper
- TSNet "initial condition discrepancy": normal for TCV valves, results are still valid

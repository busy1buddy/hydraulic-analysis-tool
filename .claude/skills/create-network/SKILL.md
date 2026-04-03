---
name: Create Water Network
description: Use when the user asks to create, build, design, or set up a new water distribution network model. Provides Australian engineering defaults and proper unit conventions.
---

# Creating Water Network Models

Use `HydraulicAPI.create_network()` to build networks programmatically. All networks are saved to `models/` as EPANET .inp files.

## Units Convention (Australian Practice)
- **Demand**: LPS (litres per second)
- **Diameter**: mm (millimetres) - API converts to metres internally
- **Elevation/Head**: metres
- **Length**: metres
- **Roughness**: Hazen-Williams C-factor

## Standard Australian Defaults

### Roughness (Hazen-Williams C)
- New ductile iron: 130-140
- Aged ductile iron: 100-110
- PVC: 140-150
- Concrete: 110-120

### Common Pipe Sizes
DN100, DN150, DN200, DN250, DN300, DN375, DN450, DN600

### Typical Parameters
- Reservoir head: 60-100m
- Junction elevations: 20-60m (follow terrain)
- Distribution pipe diameters: 100-300mm
- Trunk main diameters: 300-600mm
- Residential demand: 0.5-2.0 LPS per junction
- Commercial demand: 2.0-10.0 LPS per junction

### Standard Residential Demand Pattern (24-hour)
```python
pattern = [0.5, 0.4, 0.3, 0.3, 0.5, 0.8,   # 12am-6am
           1.2, 1.5, 1.3, 1.0, 0.9, 0.8,   # 6am-12pm
           0.7, 0.6, 0.7, 0.9, 1.3, 1.5,   # 12pm-6pm
           1.4, 1.2, 1.0, 0.8, 0.7, 0.6]   # 6pm-12am
```

## Example

```python
from epanet_api import HydraulicAPI
api = HydraulicAPI()

summary = api.create_network(
    name='my_network',
    reservoirs=[{'id': 'R1', 'head': 80, 'x': 0, 'y': 50}],
    junctions=[
        {'id': 'J1', 'elevation': 50, 'demand': 0, 'x': 15, 'y': 50},
        {'id': 'J2', 'elevation': 45, 'demand': 10, 'x': 30, 'y': 45},
    ],
    pipes=[
        {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
         'diameter': 300, 'roughness': 130},
        {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 400,
         'diameter': 250, 'roughness': 130},
    ],
    valves=[  # Only needed if doing transient analysis
        {'id': 'V1', 'start': 'J1', 'end': 'J2', 'diameter': 200,
         'type': 'TCV', 'setting': 1},
    ],
    duration_hrs=24,
    pattern=pattern,
)
```

## Validation Checklist
- All pipe start/end nodes must exist as junctions, reservoirs, or tanks
- At least one reservoir or tank is required as a source
- Spread coordinates for readable visualization
- Include demand pattern for realistic 24hr simulation
- For transient analysis, include at least one TCV valve

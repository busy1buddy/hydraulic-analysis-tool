# Mining Slurry Pipeline Design Workflow

Complete step-by-step guide for a mining engineer using the Hydraulic Analysis Tool
to design and verify a slurry pipeline system.

## Prerequisites

- Hydraulic Analysis Tool installed
- Slurry pipeline network model (.inp file)
- Slurry properties: particle size (d50), solid density, concentration

## Step 1: Load Network

1. Launch the application: `python main_app.py`
2. File > Open (Ctrl+O) → select `network.inp`
3. Verify in status bar: Nodes and Pipes count matches design
4. Use Tools > Quick Assessment (F10) to get an instant overview

## Step 2: Set Slurry Parameters

1. Analysis > Slurry Mode (toggle ON)
2. This activates Bingham plastic headloss calculations
3. Default parameters: density 1800 kg/m³, yield stress 15 Pa, plastic viscosity 0.05 Pa·s
4. Adjust in the API if needed:
   ```python
   api.run_steady_state(slurry=True, density=1800, tau_y=15.0, mu_p=0.05)
   ```

## Step 3: Run Steady-State Analysis

1. Analysis > Steady State (F5)
2. Check status bar:
   - WSAA status (pressure/velocity compliance)
   - Resilience index (Ir > 0.3 is good)
   - Quality score (aim for 75+)
3. Review results tables:
   - Node pressures in m head
   - Pipe velocities in m/s
4. Switch colour modes: Pressure, Velocity, Headloss

## Step 4: Check Critical Velocity

Use the API to generate a slurry design report:

```python
report = api.slurry_design_report(
    d_particle_mm=1.0,      # median particle size
    rho_solid=2650,          # solid density (kg/m³)
    concentration_vol=0.20,  # 20% solids by volume
    rho_fluid=1000,          # carrier fluid density
)
```

Review the report:
- **BELOW CRITICAL**: Pipe velocity is below critical deposition velocity — **solids will settle**
- **AT RISK**: Within 20% of critical velocity — marginal safety margin
- **OK**: Adequate velocity for slurry transport

Both Durand (1952) and Wasp (1977) models are calculated. The higher value is used as the design critical velocity.

## Step 5: Check Pump Operating Point

1. Select a pump in the Properties panel
2. View pump curve vs system curve intersection
3. Verify operating point is within 0.7-1.2 × BEP flow
4. For slurry service, apply pump derating:

```python
from slurry_solver import derate_pump_for_slurry
derated = derate_pump_for_slurry(
    head_water_m=50,
    efficiency_water=0.75,
    concentration_vol=0.20,
    rho_solid=2650,
)
# derated['head_slurry_m'], derated['efficiency_slurry']
```

Key outputs:
- **Head correction (C_H)**: multiply water head by this factor
- **Efficiency correction (C_η)**: multiply water efficiency by this
- **Power increase factor**: motor sizing multiplier

## Step 6: Run Surge Analysis

1. Analysis > Transient (Ctrl+T) — for water hammer analysis
2. If max surge > 30 m, the Surge Wizard appears automatically
3. Review surge protection recommendations:
   - **Bladder accumulator**: Boyle's law sizing
   - **Air valve**: placement at high points
   - **Slow-closing valve**: Thorley 3-5 second closure

For slurry, use actual density in Joukowsky calculation:
```python
j = api.joukowsky(wave_speed=1100, velocity=1.5, density=1800)
# Pressure rise proportional to density
```

## Step 7: Generate Compliance Certificate

1. Analysis > Design Compliance Check (F9)
2. Certificate checks:
   - Pressure (WSAA 20-50 m)
   - Velocity (< 2.0 m/s)
   - Fire flow (25 LPS @ 12 m)
   - Pipe stress (PN rating)
   - Resilience (Todini > 0.15)
3. Export as PDF for project records

## Step 8: Export Report

1. Reports > Generate Report (DOCX)
2. Select sections: Executive Summary, Compliance, Pipe Stress, Hydraulic Results
3. Enter engineer name and project name
4. Generate and review
5. For PDF: Reports > Generate Report (PDF)

## Key Slurry Design Checks

| Check | Target | Reference |
|-------|--------|-----------|
| Velocity > Critical deposition | V > V_c (Durand/Wasp) | Wilson et al. (2006) |
| Velocity < Erosion limit | V < 4-5 m/s | Site-specific |
| Pump head derated for SG | H_slurry = H_water × C_H | Wilson Ch.7 |
| Surge pressure within PN | P_surge < PN rating | AS 2280 |
| Minimum transport velocity | V > 1.5× V_c recommended | Industry practice |
| Pipe wall thickness | SF > 1.5 for hoop stress | AS 2280 |

## Troubleshooting

- **"Below critical velocity" warnings**: Increase pipe diameter or reduce concentration
- **High headloss**: Check roughness values — slurry increases friction
- **Solver convergence failure**: Check for disconnected nodes (Tools > Diagnostics)
- **Pump operating outside BEP**: Consider variable speed drive or impeller trim

## References

- Durand R. (1952) "The Hydraulic Transport of Coal and Solid Materials in Pipes", BHRA
- Wasp E.J., Kenny J.P., Gandhi R.L. (1977) "Solid-Liquid Flow", Trans Tech
- Wilson K.C., Addie G.R., Clift R. (2006) "Slurry Transport Using Centrifugal Pumps", 3rd ed.
- Thorley A.R.D. (2004) "Fluid Transients in Pipeline Systems"
- WSAA WSA 03-2011 "Water Supply Code of Australia"
- AS 2280 "Ductile Iron Pipes and Fittings"

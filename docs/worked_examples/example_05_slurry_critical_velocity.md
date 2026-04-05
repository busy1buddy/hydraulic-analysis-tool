# Example 5 — Critical Deposition Velocity for Coal Slurry

**Given:** A DN200 slurry pipeline carries fine coal particles.
- Particle d50 = 0.3 mm
- Solid density ρ_s = 1400 kg/m³ (bituminous coal)
- Concentration by volume C_v = 0.20
- Carrier fluid: water, ρ_f = 1000 kg/m³
- Pipe ID D = 0.200 m

**Required:** Calculate the critical deposition velocity (Durand,
1952) and verify the current operating velocity is above it.

## Durand (1952) correlation

```
v_crit = F_L × sqrt(2 × g × D × (s - 1))
```

where:
- F_L is Durand's factor (function of particle size and concentration)
- s = ρ_s / ρ_f (specific gravity of solid)
- g = 9.81 m/s²

For d50 = 0.3 mm, C_v = 0.20, F_L ≈ 1.34 (from Durand chart).

```
s = 1400 / 1000 = 1.4
v_crit = 1.34 × sqrt(2 × 9.81 × 0.200 × (1.4 - 1))
       = 1.34 × sqrt(1.5696)
       = 1.34 × 1.253
       = 1.679 m/s
```

The operating velocity must exceed **1.68 m/s** to prevent bed
formation.

## Why this matters

Below v_crit, solids drop out of suspension and settle in the pipe
invert, forming a moving bed. Consequences:
- Reduced cross-section → rising headloss
- Pump flow drops as system curve shifts
- Eventually: plugged pipeline, emergency shutdown

At coal mines, this has caused multi-million-dollar production losses.

## Tool verification

```python
from epanet_api import HydraulicAPI

api = HydraulicAPI()
api.load_network('tutorials/mining_slurry_line/network.inp')

report = api.slurry_design_report(
    d_particle_mm=0.3,
    rho_solid=1400,
    concentration_vol=0.20,
    rho_fluid=1000,
    mu_fluid=0.001,
)

for pipe in report['pipe_analysis']:
    vc_durand = pipe['critical_velocity_durand_ms']
    v_actual = pipe['velocity_ms']
    status = 'OK' if v_actual > vc_durand else 'AT RISK'
    print(f"{pipe['pipe_id']}: v={v_actual:.2f} m/s, "
          f"v_crit={vc_durand:.2f} m/s [{status}]")
```

## Comparison: Durand vs Wasp

For the same pipe and particle:
- **Durand (1952)**: simpler correlation, widely used in industry
- **Wasp et al. (1977)**: considers carrier fluid viscosity and
  heterogeneous flow regime — often gives a lower critical velocity
  for fine particles

Both models are computed by `slurry_design_report()`. Use the
**higher** of the two for conservative design.

## References

- Durand R. (1952) *Basic relationships of the transportation of
  solids in pipes - experimental research*, Proc. 5th Minnesota
  Intl. Hydraulics Conference
- Wasp E.J., Kenny J.P., Gandhi R.L. (1977) *Solid-liquid flow
  slurry pipeline transportation*
- Wilson K.C., Addie G.R., Sellgren A., Clift R. (2006) *Slurry
  transport using centrifugal pumps* 3rd ed.
- `api.knowledge_base('bingham_plastic')` — also covers rheology

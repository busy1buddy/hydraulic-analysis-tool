# Tutorial 6: Mining Slurry Pipeline

## What This Network Models

A 2000 m straight pipeline carrying mineral slurry from a headworks tank (R1, 80 m head) to a process plant discharge point (J4). The geometry is intentionally simple to isolate the effect of non-Newtonian rheology on head loss.

Network topology:
- **R1** (feed tank, 80 m head) — slurry supply
- **P1–P4**: four 500 m segments of DN200 steel pipe (C=100, lower than water pipe due to slurry abrasion and deposits)
- **J1–J3**: intermediate nodes at 35, 30, 25 m elevation (slight downhill grade)
- **J4**: discharge point at 20 m elevation, 20 LPS process demand

The flat demand pattern (all multipliers = 1.0) models steady 24/7 operation typical of mining process plants.

## Slurry vs Water Comparison

This tutorial is the primary use case for the slurry analysis tab. Compare:

| Scenario        | Fluid          | Expected headloss per 500m |
|----------------|----------------|---------------------------|
| WaterBase       | Water (SG=1.0) | ~5–8 m                    |
| SlurryBingham   | Bingham plastic (τ₀=15 Pa, μp=0.05 Pa·s) | ~12–20 m |
| SlurryPowerLaw  | Power Law (k=0.08, n=0.75)               | ~10–16 m |

The slurry solver applies the Darcy-Weisbach equation with modified friction factor using the Hedstrom number (Bingham) or Metzner-Reed (Power Law) approach.

## Key Things to Observe

1. **Pressure gradient along the pipeline**: Under water flow, plot pressure at R1→J1→J2→J3→J4. The slope should be linear for a constant-diameter pipe.

2. **Slurry headloss multiplier**: With slurry mode enabled and Bingham parameters set, the head loss increases significantly. Check whether J4 still has sufficient head to maintain flow (minimum operating pressure typically 10–20 m in mining applications).

3. **Critical deposition velocity**: For slurry pipelines, a minimum flow velocity must be maintained to prevent solids settling. For typical mineral slurries in DN200 pipe, minimum velocity is ~1.2–1.8 m/s. Check the velocity at design flow.

4. **Available driving head**: R1 head = 80 m, J4 elevation = 20 m. Available head = 60 m. Under slurry conditions, verify the 60 m driving head is sufficient against total friction losses.

5. **HighFlow scenario**: At 1.5× demand (30 LPS), check velocities remain below pipe erosion limit (~3.5 m/s for steel in slurry service).

## Expected Results (WaterBase scenario)

| Segment | Pipe | Flow (LPS) | Velocity (m/s) | Head loss (m) |
|---------|------|-----------|---------------|---------------|
| R1–J1   | P1   | ~20        | ~0.64         | ~5–7          |
| J1–J2   | P2   | ~20        | ~0.64         | ~5–7          |
| J2–J3   | P3   | ~20        | ~0.64         | ~5–7          |
| J3–J4   | P4   | ~20        | ~0.64         | ~5–7          |

Total head available: 60 m (80 − 20). Total friction loss: ~20–28 m. Remaining pressure at J4: ~32–40 m. For slurry, head loss doubles or more — J4 may approach minimum pressure.

## Australian Standards References

- Steel pipeline for slurry service follows **AS 1579** (arc-welded steel pipes) with internal wear lining or increased wall thickness
- Hazen-Williams C=100 approximates a worn steel pipe or ceramic-lined steel — appropriate for moderate-abrasion slurry
- Mining pipeline design velocities: minimum 1.2 m/s to prevent settlement, maximum 3.5 m/s for erosion control (industry standard, not codified in AS)
- Pipeline surge/water hammer analysis mandatory per duty-of-care for mining slurry pipelines — use the transient analysis tab

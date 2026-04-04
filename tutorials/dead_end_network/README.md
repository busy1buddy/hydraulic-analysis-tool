# Tutorial 2: Dead-End Branching Network

## What This Network Models

A tree-topology network branching from a single reservoir (R1, 80 m head). Unlike a looped network, dead-end branches have no alternative feed path. The long dead-end branch J4–J6–J7–J8 stretches 900 m from the reservoir with minimal demand at the terminus.

Network topology:
- **R1** (reservoir, 80 m head) feeds **J1** via DN250 main
- **J1** splits to branch A (J2–J3) and main spine (J4)
- **J4** continues to branch B (J5) and the dead-end branch (J6–J7–J8)
- Dead-end J8 is approximately 800 m from R1 along the branch path

## Key Things to Observe

1. **Pressure at dead-end terminus (J8)**: With elevation 36 m and 80 m reservoir head, the available pressure minus friction losses should still exceed 20 m WSAA minimum. Check that J8 stays above 20 m even at peak demand.

2. **Water age / stagnation**: Switch the Quality analysis to AGE mode. Run the 24-hour simulation. The dead-end branch (J6, J7, J8) will accumulate significantly older water than the main network nodes — this represents a real health and taste/odour risk.

3. **Low velocity in dead-end pipes**: Pipes P7, P8, P9 carry only the small demands at J6, J7, J8. Velocities will be very low (<0.1 m/s), which is why flushing programs are required for dead-end branches.

4. **Compare LowDemand scenario**: At 40% demand multiplier, J7 and J8 may have near-zero flow velocity — modelling night-time conditions when stagnation is worst.

5. **Pressure gradient along dead-end branch**: Plot pressure at J4, J6, J7, J8 — head loss is small due to low flow, so pressures are relatively uniform along the dead-end despite the length.

## Expected Results

| Junction | Elevation (m) | Expected Pressure Base (m) | Notes          |
|----------|--------------|---------------------------|----------------|
| J1       | 48           | ~30–33                    | Main junction  |
| J4       | 42           | ~34–37                    | Spine node     |
| J6       | 38           | ~38–41                    | Dead-end start |
| J7       | 37           | ~39–42                    | Dead-end mid   |
| J8       | 36           | ~39–43                    | Dead-end end   |

Dead-end terminus (J8) has HIGHER pressure than main nodes because it has lower elevation and minimal friction loss — this is characteristic of dead-end branches.

## Australian Standards References

- **WSAA**: Minimum service pressure 20 m head — check J8 under peak demand
- **WSAA**: Maximum pipe velocity 2.0 m/s — dead-end pipes will be well under this
- **AS 2280**: Ductile iron DN150–DN250 pipes, C=120–130
- Dead-end flushing frequency is typically specified in utility Operating Procedures based on water age modelling results such as this tutorial

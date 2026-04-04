# Tutorial 5: Fire Flow Demand Analysis

## What This Network Models

A 10-junction residential distribution network designed to test fire flow compliance at a hydrant location (J5). Fire flow analysis is a standard part of Australian subdivision design and development assessment.

Network topology:
- **R1** (reservoir, 80 m head) feeds the network via DN300 trunk
- **J1–J10** cover a typical residential subdivision at 35–48 m elevation
- **J5** is the designated fire hydrant node (elevation 42 m)
- Cross-connection P11 (J5–J9) provides alternate flow path during fire event
- Total base demand: ~51 LPS across 10 junctions

## Fire Flow Analysis Method

To model the FireFlow scenario manually in EPANET:
1. Open the .inp file
2. Add 25.0 LPS additional demand at J5 (total J5 demand = 7.0 + 25.0 = 32.0 LPS)
3. Run simulation and check pressure at J5 against WSAA 12 m minimum

The project.hap FireFlow scenario captures this configuration.

## Key Things to Observe

1. **Base pressure at J5**: With reservoir at 80 m and J5 at 42 m elevation, base pressure ~34–38 m. Well within WSAA 20–50 m range.

2. **Fire flow residual pressure at J5**: When 25 LPS fire demand is added, total network demand increases from ~51 to ~76 LPS. This draws down the HGL significantly. Check that J5 pressure remains above the WSAA fire flow residual of 12 m head.

3. **Pressure drop at nearby nodes**: J4, J9 feed pipes P5, P11 to J5. These pipes carry high velocity under fire flow — check against 2.0 m/s WSAA maximum.

4. **Which pipes go red (high velocity)**: Under fire flow, P4 (J3–J4), P5 (J4–J5), and P11 (J5–J9) will carry the bulk of the additional 25 LPS. These DN200 pipes are most likely to exceed velocity limits.

5. **Pipe sizing adequacy**: If J5 fire flow residual drops below 12 m, the network needs either larger diameter mains (upgrade P5 to DN250), higher reservoir head, or additional cross-connections.

## Expected Results

| Condition       | J5 Pressure (m) | WSAA Compliant? |
|----------------|-----------------|-----------------|
| Base demand     | ~35–38          | Yes (min 20 m)  |
| Peak demand 1.5×| ~28–32          | Yes (min 20 m)  |
| Fire flow +25LPS| ~14–18          | Marginal (min 12 m) |

Pipes most likely to exceed 2.0 m/s velocity during fire flow: P5 (J4–J5), P11 (J5–J9), P3 (J2–J3).

## Australian Standards References

- **WSAA**: Fire flow residual pressure minimum 12 m head at 25 LPS — the core compliance test in this tutorial
- **WSAA**: Normal service minimum 20 m head — must also be met at all other junctions during fire flow
- **WSAA**: Maximum velocity 2.0 m/s — check high-velocity pipes during fire event
- **AS 2419.1**: Fire hydrant installations — hydrant spacing and design
- Australian subdivision design codes typically require DN200 minimum in residential streets to meet fire flow requirements

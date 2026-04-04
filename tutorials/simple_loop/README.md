# Tutorial 1: Simple Looped Network

## What This Network Models

A 6-node looped residential distribution network fed from a single service reservoir (R1) at 80 m head. The loop provides redundancy — if any single pipe is isolated, all junctions remain supplied. This is the standard topology for Australian suburban water distribution.

Network topology:
- **R1** (reservoir, 80 m head) feeds **J1** via a DN300 main
- **J1–J2–J3–J4–J5–J6** form the distribution loop
- Two cross-connections (P7, P8) create multiple flow paths
- Elevations range from 35 m (J6) to 50 m (J1)

## Key Things to Observe

1. **Pressure distribution**: With a 80 m reservoir head and junction elevations of 35–50 m, expected pressures are 30–45 m. Run the Base scenario and check each junction pressure against WSAA limits (20–50 m).

2. **Flow splitting in the loop**: EPANET solves the Hardy-Cross equations so that head loss is equal on all paths between any two nodes. Observe how flow divides at J1 and recombines at J4/J5.

3. **Peak demand impact**: Switch to the PeakDemand scenario (1.5× multiplier). Watch which junctions approach the 20 m WSAA minimum.

4. **Pipe velocities**: All pipes should remain below 2.0 m/s (WSAA). Under peak demand the DN200 pipes (P3–P7) may approach this limit.

5. **Redundancy test**: In EPANET, close pipe P8 (the west cross-connection) and observe how flow reroutes and pressures change.

## Expected Results

| Junction | Elevation (m) | Expected Pressure Base (m) |
|----------|--------------|---------------------------|
| J1       | 50           | ~29–31                    |
| J2       | 45           | ~32–35                    |
| J3       | 42           | ~34–37                    |
| J4       | 40           | ~35–38                    |
| J5       | 38           | ~36–39                    |
| J6       | 35           | ~37–41                    |

Lowest pressure at J1 (highest elevation, closest to reservoir — most head consumed in P1). All junctions should comply with WSAA 20 m minimum at base demand.

## Australian Standards References

- **WSAA**: Minimum service pressure 20 m head, maximum 50 m head
- **WSAA**: Maximum pipe velocity 2.0 m/s
- **AS 2280**: Ductile iron pipes, C=130 (DN200–DN300), PN25 rated
- Pipe sizing follows AS/NZS 2280 for ductile iron, nominal diameters DN200 and DN250 and DN300

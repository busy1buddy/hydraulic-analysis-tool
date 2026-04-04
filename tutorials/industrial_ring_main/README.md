# Tutorial 9: Industrial Ring Main (Mining/Industrial)

## What This Network Models

A large-diameter ring main serving a mining or heavy industrial estate. Total demand is 235 LPS base — approximately 20,000 m³/day, typical of a mid-size copper or gold processing plant. The reservoir (R1) at 150 m head provides high driving pressure to overcome the large friction losses in the high-demand network.

Network topology:
- **R1** (headworks reservoir, 150 m head) — main supply
- **J1–J8** form a ring main at 42–55 m elevation, representing individual process areas
- **J5** (flotation circuit, 50 LPS) is the largest single consumer
- DN400–DN600 ductile iron mains throughout
- Two cross-mains (P10, P11) provide redundancy and flow balancing
- Total base demand: 235 LPS

The industrial demand pattern is near-constant (0.6–1.0 multiplier) unlike residential networks — mining plants operate 24 hours.

## Key Things to Observe

1. **High-pressure operation**: With R1 at 150 m and junctions at 42–55 m, available head = 95–108 m. After friction losses, junction pressures should be in the range of 80–110 m. This is well above WSAA residential limits but appropriate for industrial service (typical mining utility requirement: minimum 120 m HGL = 65–80 m pressure at these elevations).

2. **Mining pressure threshold (120 m HGL)**: In mining applications, the minimum HGL is often specified at 120 m (process equipment requirements) rather than the WSAA 20 m pressure. Check whether any junction HGL drops below 120 m under peak shift.

3. **Velocity in DN600 trunk (P1)**: R1 to J1 carries the full 235 LPS at base. In DN600, velocity = Q/(π×D²/4) = 0.235/(π×0.36/4) = 0.83 m/s — well within WSAA 2.0 m/s. This confirms DN600 is appropriate for the trunk.

4. **MaintenanceIsolation scenario**: Close the P10 cross-main (J1–J4). This forces all flow to travel the long way around the ring. J4 and J5 (furthest from R1 via the alternative path) will show the largest pressure drop. Check which junctions drop below the 120 m HGL mining threshold.

5. **Flow distribution in the ring**: With multiple cross-connections, EPANET solves for the flow split that minimises head loss. Observe which ring segments carry the most flow.

## Expected Results

| Junction | Elevation (m) | Demand (LPS) | Expected Pressure (m) | Expected HGL (m) |
|----------|--------------|-------------|----------------------|------------------|
| J1       | 55           | 25          | ~77–85               | ~132–140         |
| J2       | 52           | 30          | ~79–87               | ~131–139         |
| J4       | 45           | 35          | ~83–91               | ~128–136         |
| J5       | 42           | 50 (highest)| ~82–90               | ~124–132         |

J5 (highest demand, farthest around part of the ring) will have the lowest HGL — check against 120 m mining threshold.

## Australian Standards References

- **AS 2280**: Ductile iron DN400–DN600 pipes — applicable for large-diameter mains
- **WSAA**: Maximum velocity 2.0 m/s — check smaller DN400 pipes under peak flow
- Industrial water supply pressure typically specified in project design brief: 120 m HGL minimum for process plant reliability (not a published AS standard but common Australian mining practice)
- Ring mains in critical industrial applications require N-1 security: any single pipe segment failure must not reduce supply below minimum — test with MaintenanceIsolation scenario

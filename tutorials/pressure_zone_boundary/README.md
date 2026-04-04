# Tutorial 4: Pressure Zone Boundary with PRV

## What This Network Models

A two-zone pressure system where a high-level reservoir (R1, 120 m head) serves a high-elevation zone and, through a Pressure Reducing Valve (PRV, V1), a lower elevation zone. PRVs are essential in Australian networks with significant topographic relief.

Network topology:
- **R1** (reservoir, 120 m head) — high-zone source
- **High zone**: J1 (75 m), J2 (78 m), J3 (72 m) — fed directly from R1
- **V1** — PRV set to 65 m downstream HGL — separates the two zones
- **Low zone**: J4 (45 m), J5 (42 m), J6 (40 m) — controlled by PRV

Without the PRV, low-zone pressures would be up to 80 m (120 − 40), far exceeding the WSAA 50 m maximum and risking pipe bursts.

## Key Things to Observe

1. **High-zone pressures**: J1–J3 are at 72–78 m elevation with R1 at 120 m head. Expected pressures: 120 − 78 to 120 − 72 = 42–48 m. All within WSAA 20–50 m range.

2. **PRV action (V1)**: The PRV V1 is set to 65 m HGL downstream. This means J4 will have pressure = 65 − 45 = 20 m — exactly at the WSAA minimum. Check that the PRV is actually active (throttling) by inspecting valve status.

3. **Low-zone pressures**: J4 gets 20 m, J5 gets 23 m, J6 gets 25 m — all just within WSAA limits. Under peak demand with high headloss, J4 could drop below 20 m — check this.

4. **PRVFullOpen scenario**: At 2.5× demand, the downstream demand is so high that the PRV opens fully (insufficient upstream pressure to maintain 65 m set point). Watch the low-zone pressures crash.

5. **High-zone compliance**: Even though the reservoir is at 120 m, high-zone pressures are acceptable because the junctions are also at high elevation (72–78 m).

## Expected Results

| Zone | Junction | Elevation (m) | Expected Pressure (m) | WSAA Compliant? |
|------|----------|--------------|----------------------|-----------------|
| High | J1       | 75           | ~40–44               | Yes             |
| High | J2       | 78           | ~37–41               | Yes             |
| High | J3       | 72           | ~42–46               | Yes             |
| Low  | J4       | 45           | ~20–22               | Marginal        |
| Low  | J5       | 42           | ~22–25               | Yes             |
| Low  | J6       | 40           | ~24–27               | Yes             |

## Australian Standards References

- **WSAA**: Minimum service pressure 20 m — J4 is right at the limit, demonstrating why PRV set-point selection is critical
- **WSAA**: Maximum service pressure 50 m — without the PRV, low-zone pressures of 75–80 m would destroy pipes
- **AS/NZS 4058**: Concrete pipes used in trunk mains, PN25 rated — important for the high-zone trunk
- PRV installations typically include a bypass with isolation valves per WSAA Water Supply Code of Australia

# Tutorial 3: Pump Station Network

## What This Network Models

A pump station lifting water from a low-level wet well (R1, 20 m head) to an elevated distribution zone (J1–J5 at 50–60 m elevation). This is a common configuration in hilly Australian suburbs where gravity feed is insufficient.

Network topology:
- **R1** (wet well / sump, 20 m head) — low-level source
- **PU1** — centrifugal pump with defined pump curve (55 kW rated)
- **J1** (60 m elevation) — pump discharge header, zero demand
- **J2–J5** — distribution zone (50–58 m elevation), total demand ~23 LPS base

The pump curve (Curve ID 1) defines the head-flow relationship:
- Shutoff head: 65 m at 0 LPS
- Rated point: ~50 m at 30 LPS
- Run-out: 20 m at 50 LPS

## Key Things to Observe

1. **Pump operating point**: EPANET finds the intersection of the pump curve and the system curve. At base demand (~23 LPS total), the pump should operate near 55–58 m head. Check the pump flow in results.

2. **Pressure at J1 (discharge header)**: J1 is at 60 m elevation. The pump adds head from the 20 m wet well. If pump delivers 55 m head: HGL at J1 = 20 + 55 = 75 m. Pressure at J1 = 75 − 60 = 15 m. This is BELOW the WSAA 20 m minimum — the pump curve or layout would need adjustment.

3. **Peak demand shift**: Under PeakDemand (1.5×, ~34 LPS), the pump moves to a lower point on the curve (less head). Watch pressures fall at J4 and J5 which are lower elevation but further from the pump.

4. **Night minimum operation**: At 0.3× demand (~7 LPS), the pump operates near shutoff head (~63 m), pushing pressures potentially above 50 m WSAA maximum at lower junctions.

5. **Energy cost**: Enable energy reporting to see pump energy consumption across the 24-hour simulation pattern.

## Expected Results

| Junction | Elevation (m) | Expected Pressure Base (m) |
|----------|--------------|---------------------------|
| J1       | 60           | ~13–17 (near minimum)     |
| J2       | 58           | ~14–18                    |
| J3       | 55           | ~16–21                    |
| J4       | 52           | ~19–24                    |
| J5       | 50           | ~21–26                    |

J1 and J2 will be at or below WSAA minimum — a real design would either raise the reservoir, increase pump size, or lower the distribution zone elevation.

## Australian Standards References

- **WSAA**: Minimum service pressure 20 m head — J1 and J2 likely fail, demonstrating need for pump re-sizing
- **WSAA**: Maximum service pressure 50 m head — check J5 under NightMinimum scenario
- **AS 2941**: Pumping station design standard — pump curve must be provided for all permanent pump stations
- Pump efficiency target: minimum 70% at rated operating point per Australian water utility procurement specifications

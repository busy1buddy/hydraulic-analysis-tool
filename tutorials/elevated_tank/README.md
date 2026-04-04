# Tutorial 8: Elevated Tank Gravity Feed

## What This Network Models

A gravity-fed distribution system supplied entirely from an elevated steel tank (T1) at 80 m elevation with no pumps. Elevated tanks are common in Australian country towns and industrial estates — the tank is filled during off-peak hours (via a separate fill main not modelled here) and discharges through demand.

Network topology:
- **T1** (elevated tank, base elevation 80 m, initial water level 4 m above base = HGL 84 m)
- Tank volume: diameter 15 m, max level 6 m = approximately 1060 m³ usable storage
- **J1–J6** distribution zone at 28–38 m elevation
- Looped network with cross-connections P7 (J1–J4) and P8 (J2–J5)
- Total base demand: 31 LPS — about 112 m³/hr

At 31 LPS base demand and a pattern with peak reaching 1.5× (46 LPS), the 1060 m³ tank provides approximately 6–8 hours of supply at average demand.

## Key Things to Observe

1. **Tank level over 24 hours**: Watch T1's water level in the time-series results. Starting at 4 m (HGL = 84 m), during peak morning demand (hours 6–9 am pattern) the level drops rapidly. If there is no fill pump in the model, the tank will drain completely — EPANET will report MinLevel reached.

2. **Pressure variation with tank level**: Unlike a reservoir (fixed head), a tank's HGL drops as it empties. When T1 drops from level 4 m (HGL 84 m) to level 0.5 m (HGL 80.5 m), all junction pressures decrease by 3.5 m. Check J1 pressure at start vs end of simulation.

3. **Morning peak pressure crash**: At pattern multiplier 1.5 (about hours 7–8 am), tank outflow is highest. Combined with tank level drop, pressures at J3, J5, J6 may approach WSAA minimum 20 m.

4. **HighDemand scenario (1.8×)**: Tank level drops very quickly. At 1.8× demand (~56 LPS), EPANET will show the tank hitting MinLevel within ~5–6 hours, after which the system hydraulically stalls.

5. **TankEmpty scenario**: Set T1 InitLevel = 0.5 m (minimum level). Pressures are at their lowest — check which junctions drop below 20 m WSAA minimum.

## Expected Results

| Scenario    | T1 Final Level (m) | J6 Pressure at Hour 8 (m) | WSAA Compliant? |
|-------------|-------------------|--------------------------|-----------------|
| Base        | ~2.5–3.5          | ~45–49                   | Yes             |
| HighDemand  | Hits min (~0)     | ~35–42 (then stalls)     | Borderline      |
| LowDemand   | ~4.5–5.0          | ~48–52 (check max)       | Watch max 50 m  |

J6 is lowest elevation (28 m) so has highest pressures. Under LowDemand with full tank, J6 may reach 52–54 m — above WSAA 50 m maximum. Consider a PRV on the low-zone branches.

## Australian Standards References

- **WSAA**: Minimum service pressure 20 m — monitor during tank drawdown
- **WSAA**: Maximum service pressure 50 m — lower elevation junctions at risk when tank is full
- Storage tank sizing: WSAA recommends minimum 6-hour supply at average day demand for reliability
- Elevated steel tanks: structural design per **AS 1210** (Pressure vessels) and **AS 1170** (Structural loads)
- Tank minimum level: typically 0.5 m retained for fire reserve per local authority requirements

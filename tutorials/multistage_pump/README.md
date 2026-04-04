# Tutorial 7: Multistage Pump (Two Pumps in Series)

## What This Network Models

Two centrifugal pumps in series (PU1 then PU2) lifting water from a low-level wet well (R1, 20 m head) to a high-elevation distribution zone (J3–J5 at 82–90 m elevation). Series pump arrangements are used when the total head requirement exceeds what a single pump can efficiently deliver.

Network topology:
- **R1** (wet well, 20 m head) — low-level source
- **PU1** — first stage pump (37 kW, shutoff head 55 m)
- **J1** (45 m elevation) — interstage node, connects PU1 discharge to PU2 suction
- **PU2** — second stage pump (identical 37 kW)
- **J2** (80 m elevation) — second stage discharge header
- **J3–J5** — high-zone distribution at 82–90 m elevation, total demand ~19 LPS base

Combined pump head at operating point (~19 LPS): approximately 2 × 49 m = ~98 m total head. Net HGL at J2 = 20 + 98 = 118 m. J4 pressure = 118 − 90 = 28 m — within WSAA limits.

## Key Things to Observe

1. **Combined pump operating point**: Each pump adds head independently. At 19 LPS, each pump delivers ~49 m head. Combined = 98 m. Check this matches EPANET's calculated pump flows.

2. **Interstage pressure (J1)**: J1 is at 45 m elevation. After PU1 adds ~49 m to the 20 m source: HGL at J1 = 69 m. Pressure at J1 = 69 − 45 = 24 m. This is the suction pressure for PU2.

3. **SinglePump scenario**: Disable PU2 (set status Closed in EPANET). Single pump can only deliver ~55 m head max — total HGL = 75 m. Pressure at J4 (90 m elevation) = 75 − 90 = −15 m. NEGATIVE PRESSURE — the pump cannot reach J4. This is why redundancy is required.

4. **Pump trip transient**: The BothPumpsTrip scenario sets the initial steady-state for transient (water hammer) analysis. When both pumps trip simultaneously, a low-pressure wave propagates up the rising main — potentially causing column separation (cavitation) at J2, J3, J4.

5. **Peak demand at J3–J5**: At 1.5× demand (~29 LPS), the pumps move to a lower point on the curve. Check pressures remain above 20 m at J4 (the highest elevation node).

## Expected Results

| Scenario    | Pump Flow (LPS) | Each Pump Head (m) | J4 Pressure (m) |
|-------------|----------------|-------------------|-----------------|
| Base        | ~19            | ~49               | ~26–30          |
| Peak 1.5×   | ~29            | ~38               | ~15–20 (marginal)|
| SinglePump  | ~12            | ~51               | Negative (fails) |

## Australian Standards References

- **WSAA**: Minimum service pressure 20 m — J4 marginal under peak, fails under single pump
- **AS 2941**: Pump station design — requires duty/standby pump configuration, meaning a third pump or alternative supply should be provided
- Pump trip transient analysis is mandatory for high-head pump stations — transient pressures can reach 2–3× steady-state head
- Water hammer wave speed in DN300 DI pipe: approximately 1000–1200 m/s (WNTR uses this in TSNet transient solver)

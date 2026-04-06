# Fire Flow Demand — Walkthrough

## Engineering Context

A 10-node residential network designed to supply 25 LPS fire flow at node J5, with a total system demand of 51 LPS. WSAA WSA 03-2011 requires a minimum residual pressure of 12 m at the fire hydrant while delivering fire flow. This network tests whether the pipe sizing can handle the combined domestic and fire demand.

## Step-by-Step Instructions

1. **Open the network:** File > Open, select `network.inp` from this folder.
2. **Run steady-state analysis:** Press **F5** to verify normal operating conditions.
3. **Run fire flow analysis:** Press **F8** or Analysis > Fire Flow.
4. **Select node J5** as the fire flow test point.
5. **Compare normal vs fire flow pressures** in the results.

## Expected Results (Normal Conditions)

| Node | Pressure (m) |
|------|-------------|
| J2   | 29.4 (lowest) |
| J10  | 37.8        |

- **Maximum velocity:** P2 = 1.47 m/s
- **Compliance score:** 90.5 / 100
- **WSAA warnings:** 0

## What to Look For

- Under normal conditions, all pressures are within the 20-50 m WSAA range.
- P2 velocity at 1.47 m/s is approaching but still below the 2.0 m/s limit.
- J2 is the critical node — lowest pressure in the network.
- During fire flow, pressures will drop further due to the additional 25 LPS demand.

## Key Learning Points

- Fire flow analysis tests the network under extreme but realistic demand.
- WSAA requires 12 m residual pressure at the hydrant during fire flow, not the usual 20 m minimum.
- Pipe sizing must accommodate fire demand even though it occurs infrequently.
- High velocities during fire flow events are acceptable short-term.

## Exercise

Run **F8 fire flow** at node J2 (the weakest point). Does the residual pressure stay above 12 m? If not, which pipes need upsizing to maintain fire flow compliance?

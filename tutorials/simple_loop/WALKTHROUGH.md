# Simple Loop Network — Walkthrough

## Engineering Context

A 6-node looped residential water distribution network with DN200-300 pipes and Hazen-Williams C=130. Total demand is approximately 23 LPS. Looped networks provide redundancy — if one pipe is isolated, water can reach customers via alternate paths.

## Step-by-Step Instructions

1. **Open the network:** File > Open, select `network.inp` from this folder.
2. **Run steady-state analysis:** Press **F5** or Analysis > Steady State.
3. **Observe the network map:** Nodes colour by pressure, pipes by velocity.
4. **Check the compliance panel:** Score and any WSAA warnings appear in the results pane.

## Expected Results

| Node | Pressure (m) |
|------|-------------|
| J1   | 29.6        |
| J2   | 34.4        |
| J3   | 37.2        |
| J4   | 39.2        |
| J5   | 41.3        |
| J6   | 44.2        |

- **Maximum velocity:** P1 = 0.57 m/s
- **Compliance score:** 95.4 / 100
- **WSAA warnings:** 0

## What to Look For

- All pressures fall within the WSAA 20-50 m acceptable range.
- Velocities are well below the 2.0 m/s WSAA maximum.
- Pressure decreases from the reservoir toward the furthest demand nodes, as expected.
- The loop topology balances flow — no single pipe carries all demand.

## Key Learning Points

- Looped networks distribute pressure more evenly than branched networks.
- A compliance score above 90 indicates a well-designed system.
- Low velocities mean low headloss, but very low velocities can cause water quality issues.

## Exercise

Change pipe P4 diameter from DN150 to DN100 (select P4, edit diameter to 100 mm). Re-run F5. What happens to J3 pressure? The restriction should increase headloss and reduce downstream pressure, potentially triggering a WSAA warning.

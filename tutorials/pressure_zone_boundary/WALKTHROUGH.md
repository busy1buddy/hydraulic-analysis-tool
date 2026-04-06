# Pressure Zone Boundary — Walkthrough

## Engineering Context

Two pressure zones separated by a Pressure Reducing Valve (PRV). The high zone (J4-J6) receives water from a high-elevation source, resulting in pressures exceeding the WSAA 50 m residential maximum. PRVs are essential infrastructure for managing pressure in hilly terrain — common across Australian cities like Sydney, Melbourne, and mining town sites.

## Step-by-Step Instructions

1. **Open the network:** File > Open, select `network.inp` from this folder.
2. **Run steady-state analysis:** Press **F5**.
3. **Observe the pressure colouring** — the high zone nodes will show red/orange.
4. **Check the compliance panel** for WSAA maximum pressure warnings.

## Expected Results

| Node | Pressure (m) |
|------|-------------|
| J2   | 41.3        |
| J4   | > 50 (high zone) |
| J5   | > 50 (high zone) |
| J6   | 79.1        |

- **Compliance score:** 86.4 / 100
- **WSAA warnings:** 3 (J4, J5, J6 exceed 50 m maximum pressure)

## What to Look For

- J2 at 41.3 m is within the acceptable 20-50 m range (low zone is fine).
- J6 at 79.1 m is nearly 30 m over the WSAA residential limit.
- High pressures cause pipe fatigue, increase leak rates, and waste water through fixtures.
- The PRV on pipe P4 needs adjustment to reduce downstream pressure.

## Key Learning Points

- Pressure zones are defined by elevation bands — each zone has its own acceptable range.
- PRVs reduce pressure but cannot increase it (for that, use booster pumps).
- WSAA WSA 03-2011 sets 50 m as the residential maximum — higher pressures require pressure management.
- Every 10 m of excess pressure roughly doubles the leak rate from fittings.

## Exercise

What PRV setting on pipe P4 would bring J4-J6 below 50 m? Try reducing the PRV setting in steps of 5 m and re-running F5 until all high-zone nodes comply.

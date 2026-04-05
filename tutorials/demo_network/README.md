# Demo Network — Guided Tour

**Purpose:** The canonical showcase network used by `Help > Run Demo`
and `docs/DEMO_SCRIPT.md`. Ten junctions, eleven pipes, one reservoir,
with **two deliberate violations** planted for demonstration.

## Layout

```
          R1 (source, 100 m head)
           |
           P1 (DN300, 200 m)
           |
          J1 ── P9 ── J8      # Ring main
           |          |
          P2         P8
           |          |
          J2         J7
           |          |
          P3         P7
           |          |
          J3 ── P4 ── J4
           |          |
          P10        P5
          (DN80)     (DN150)
           |          |
          J9         J5 ── P11 ── J10
        (55 m AHD) (55 m)  (DN100)  (85 m AHD)
                         J6
                      (ring completes via P6,P7)
```

- **Reservoir:** R1 at 100 m head
- **Ring main:** J1→J2→J3→J4→J5→J6→J7→J8→J1 (DN150–250)
- **Deliberate violations:**
  - `P10` (DN80, J3→J9) — carries 12 LPS, velocity **2.39 m/s > 2.0 WSAA**
  - `J9` pressure **12.1 m < 20 m WSAA** (starved by undersized P10)
  - `J10` pressure **13.2 m < 20 m WSAA** (high-elevation branch at 85 m AHD)

## Suggested Analysis Steps

1. **Validate:** `api.validate_network()` — confirms connectivity.
2. **Steady-state:** `api.run_steady_state()` — identifies violations.
3. **Root cause:** `api.root_cause_analysis()` — traces violations to P10 and P11.
4. **What-if:** open `WhatIfPanel`, slide demand to 120% — see failures spread.
5. **Safety case:** `Analysis > Safety Case Report...` for formal output.

## Expected Results (Baseline)

| Metric | Expected |
|---|---|
| Quality score | ~65/100 (Grade C) |
| Resilience index (Todini) | ~0.35 |
| Minimum pressure | 12.1 m at J9 |
| Maximum velocity | 2.39 m/s on P10 |
| WSAA violations | 3 |

## What to Look For

- **Root cause analysis** correctly names P10 as the limiting segment
  for J9's pressure deficit.
- **Ranked fix options**: upsizing P10 DN80→DN100 (~$56K AUD) vs a
  parallel main (~similar cost).
- **`Help > Run Demo`** walks through the entire flow in under 10 seconds.

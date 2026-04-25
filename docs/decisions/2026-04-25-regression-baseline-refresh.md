# Regression Baseline Refresh — `elevated_tank`, `multistage_pump`

**Date:** 2026-04-25
**Decision owner:** Brian (project lead) — authorised in chat 2026-04-25
**Affected file:** `tests/regression_baselines.json`

## What was decided

Two rows of `tests/regression_baselines.json` are refreshed in-place:

- `elevated_tank`
- `multistage_pump`

All other baseline rows are left untouched.

## Why (alternatives considered)

Both rows were captured **before commit `b01eb80`** (2026-04-18) which physically corrected the two tutorial networks:

- *elevated_tank*: tank diameter increased to 30 m to prevent the catastrophic
  −50 million m vacuum during the 24 h simulation. The stale baseline literally
  encodes the bug-state value:
  ```json
  "min_pressure_m": -50051864.0
  ```
  The new metrics for the corrected tutorial drifted >5 % from this stale
  baseline, tripping `tests/test_regression.py::test_regression_baseline[elevated_tank]`.

- *multistage_pump*: short-circuit bypass pipe removed; high-lift zone is now
  fed correctly. The stale baseline carried `min_pressure_m: -32.8`, which is
  the broken-state value from before the fix.

Three alternatives were considered:

1. **Refresh just these two rows** ← chosen.
2. **Refresh all 11 rows via `--update`** — rejected; could mask genuine drift
   in the other nine tutorials whose baselines were not affected by `b01eb80`.
3. **Leave the failures and document a deferral** — rejected; the regression
   test would block every future PR until the baselines are fixed, with no
   benefit (the failure is not detecting a real regression).

## Standard / reference that supports it

- `tests/test_regression.py` documents `--update` as the supported mechanism
  for refreshing baselines after intentional calculation changes (lines
  121-131). The two tutorials' physics changed in `b01eb80`; this is the
  documented case.
- The new metrics are produced by the same `HydraulicAPI.run_steady_state`
  pipeline that the SME ledger validated immediately before the refresh
  (`hand calcs`, `hydraulic benchmarks`, `KB fidelity`, `EPANET verification`,
  `pipe DB` all PASS).

## What would need to change if this decision is reversed

If a future review finds the post-`b01eb80` tutorial state is wrong (e.g. tank
diameter at 30 m is unrealistic), reverse this decision by:

1. Restoring the pre-`b01eb80` `elevated_tank` and `multistage_pump`
   `network.inp` files (or the next correct state).
2. Re-running `_collect_metrics` on each and writing the result to
   `tests/regression_baselines.json`.
3. Updating `tutorials/elevated_tank/README.md` and
   `tutorials/multistage_pump/README.md` quality-score columns to match.

## Linked context

- Plan: `C:\Users\brian\.claude\plans\asyou-can-see-this-fizzy-tarjan.md`
  (Track 5 / Phase 2 verify gate)
- Originating fix: commit `b01eb80` "Fix UI crashes, physics anomalies, and
  update mechanical engineering docs" (2026-04-18)
- Permission denial that prompted the human-in-the-loop check: 2026-04-25
  during Phase 2/3 verify gate; the qa-engineer skill rule
  *"do not 'fix' the test when regression tiers fail; surface to human first"*
  fired exactly as designed.

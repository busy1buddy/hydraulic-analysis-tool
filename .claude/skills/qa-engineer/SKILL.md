---
name: qa-engineer
description: Use before any commit, at the end of every phase, and as Step 0 of /review-cycle. Provides the canonical command set for the project's test pyramid — full pytest suite, ground-truth tier, Centurion stress test, performance gates, and quality-gate aggregator. Trigger words: "run tests", "regression", "gate", "did this break anything", "before commit", "QA", "test count", "Centurion", "benchmark", "coverage".
---

# QA Engineer

## Overview

This skill carries the **definitive test commands** for the project. Use it whenever the question is "did anything break?" or "is this ready to merge?" The project has 1,222+ tests, a 38-formula audit, EPANET reference-network verification, a 100-case Centurion stress harness, and a steady-state performance benchmark. This skill keeps them straight.

## Quick Start

Before any commit:

```bash
python scripts/quality_gate.py
```

That command (added in plan Phase 5) chains the ground-truth tier + Centurion + performance gate and exits non-zero on any failure.

If `quality_gate.py` does not yet exist (pre-Phase-5), run the tasks below manually in order.

## Tasks

### Task 1 — Full pytest suite

```bash
python -m pytest tests/ -v
```

- Expected pass count: **≥ 1,222** (excluding 2 known TSNet pump-transient xfail classes)
- Expected duration: 5-10 minutes on a workstation
- The two xfail classes are intentional — see `tests/test_pump_transient.py:60, 100` (`@pump_xfail`)

To exclude TSNet (faster):

```bash
python -m pytest tests/ -k "not transient" -v
```

To get a clean count:

```bash
python -m pytest tests/ --collect-only -q | tail -1
# or
grep -c '^def test_' tests/*.py | awk -F: '{s+=$2} END {print s}'
```

### Task 2 — Ground-truth tier (immutable benchmarks)

These fixtures define correctness. They cannot be modified without sign-off.

```bash
python -m pytest tests/test_epanet_verification.py tests/test_hand_calculations.py tests/test_hydraulic_benchmarks.py tests/test_kb_fidelity.py tests/test_regression.py -v
python scripts/validate_pipe_db.py    # 58/58 PASS expected
```

Or use the SME ledger (same set, condensed output):

```bash
python .claude/skills/hydraulic-sme/scripts/run_sme_checks.py
```

If any tier fails, **do not "fix" the test**. Investigate the regression first.

### Task 3 — Centurion stress test (100 cases)

```bash
python -m pytest scripts/tester_agent.py -v
```

Covers 8 domains × 10-20 cases each: UI core, hydraulics, WSAA compliance, mining slurry, surge transient, assets/TCO, calibration, edge cases. Output appended to `reports/centurion_report.md`.

After plan Phase 4, assertions are numeric (not status-bar text).

### Task 4 — Performance gates

```bash
python scripts/benchmark_steady_state.py
```

Budget: 1000-node grid steady-state under **250 ms** total. Above 350 ms is a CI fail.

After plan Phase 5, `tests/test_performance.py` wraps this with `@pytest.mark.slow` and adds 24 h EPS (≤ 10 s) and 48 h water-quality (≤ 30 s) budgets using `tutorials/australian_subdivision`.

### Task 5 — Review cycle

```
/review-cycle
```

Triggers the full agent pipeline: architect → (code-reviewer ∥ data-validator) → (ui-reviewer ∥ hydraulic-tester) → feedback-synthesizer. Output to `docs/reviews/{YYYY-MM-DD}/`. **0 BLOCKER and 0 HIGH** is required to merge.

## How to Interpret Results

| Outcome | Meaning | Action |
|---|---|---|
| All tasks PASS | Safe to merge | Commit and proceed |
| 1 unit test fails (not in ground-truth) | Probable regression in changed code | Fix the implementation, never the test |
| Ground-truth tier fails | Formula or threshold broke | Stop. Open `docs/decisions/{date}.md`. Surface to human if standard cited. |
| Centurion fails | UI or workflow regression | Read the case ID in `reports/centurion_report.md` |
| Perf gate fails | Solver or render slowdown | Profile with `cProfile`; do not raise the budget |
| Review cycle BLOCKER | Layer/formula violation | Fix before merging |

## Test Count Truth

The README has historically claimed 833, 1012, and 1219. The actual count comes from:

```bash
grep -c '^def test_' tests/*.py | awk -F: '{s+=$2} END {print s}'
```

Currently: **1,222**. After plan Phase 3 (forecasting/terrain unit tests) it will be ≥ 1,250.

When updating README/HANDOVER, use the live count, not a memory of the previous one.

## Common Pitfalls

- Do not run `pytest tests/` from inside `dist/` or any subdirectory — must be from project root
- TSNet xfails are not regressions — `@pump_xfail` is set with `strict=False`
- `models/large_grid.inp` (500 nodes) is for performance, not unit tests
- The `.coverage` file at root is a binary pytest-cov artefact; not human-readable
- `scripts/run_agent_loop.py` is a 24-line stub — do not rely on it for orchestration

## When NOT to use this skill

- A specific failure is being investigated — use the `simplify` skill or read the test directly
- The change is documentation-only and does not run tests — skip QA
- Pure UI/visual question — use `pyqt-architect`
- Formula correctness debate — use `hydraulic-sme`

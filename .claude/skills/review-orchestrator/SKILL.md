---
name: review-orchestrator
description: Use to run a review pass at one of three depths — quick (code-reviewer only, on save), standard (the full /review-cycle pipeline), or deep (standard plus the Centurion stress harness and the perf gate). Procedural router on top of the existing `/review-cycle` slash command — does not duplicate any agent. Trigger words: "quick review", "standard review", "deep review", "before merge", "release gate", "before push".
---

# Review Orchestrator

## Overview

`/review-cycle` runs a fixed pipeline (architect → code-reviewer ∥ data-validator → ui-reviewer ∥ hydraulic-tester → feedback-synthesizer). That is the right shape for end-of-feature reviews, but it is too heavy for every save and too light for a release gate. This skill defines three explicit modes and the situations that call each one.

## Modes

### `quick` — single agent, on save / pre-commit

Runs only `code-reviewer` (sonnet) over the current diff. Catches unit drift, formula citation gaps, magic numbers, and bare excepts. ~30 s.

When: every save, pre-commit hook, "did I break the formula" check.

How:
```
# Manual:
@code-reviewer please review the diff against master:HEAD
# Hook (if configured): runs automatically on commit
```

### `standard` — full review-cycle, end-of-feature

Runs the existing `/review-cycle` command in full. ~2-3 min.

When: end of a feature/refactor, before merging a PR, after a phase completes.

How:
```
/review-cycle
```

Output to `docs/reviews/{YYYY-MM-DD}/`. Synthesizer SUMMARY must show **0 BLOCKER and 0 HIGH** to merge.

### `deep` — release gate

Runs `standard` plus:
1. `python scripts/quality_gate.py` (when present — Phase 5 deliverable; chains ground-truth + Centurion + perf)
2. `python -m pytest tests/test_layer_purity.py tests/test_ui_freeze.py -v`
3. `python .claude/skills/hydraulic-sme/scripts/run_sme_checks.py`
4. `python scripts/tester_agent.py -v` (Centurion 100-case)
5. `python scripts/benchmark_steady_state.py`

~10-15 min.

When: cutting a release, after a major refactor, before tagging a version.

## Mode Selection Decision Tree

```
Is this a save / commit, or smaller than ~50 LOC changed?
  yes -> quick
  no  -> Is this an end-of-phase or merge-ready PR?
            yes -> standard
            no  -> Is this a release / tag / large refactor?
                     yes -> deep
                     no  -> default to standard
```

## Bundled Agents and Skills

This skill loads the following automatically through agent invocation:

- `hydraulic-sme` — invariants and formula audit (loaded by code-reviewer + hydraulic-tester)
- `pyqt-architect` — layer purity and threading rules (loaded by ui-reviewer + code-reviewer)
- `qa-engineer` — canonical command set for tests (loaded by hydraulic-tester)

Each completed skill is referenced; do not re-implement their bodies here.

## Outputs

- `docs/reviews/{YYYY-MM-DD}/architect.md`
- `docs/reviews/{YYYY-MM-DD}/code-review.md`
- `docs/reviews/{YYYY-MM-DD}/ui-review.md`
- `docs/reviews/{YYYY-MM-DD}/hydraulic-benchmarks.md`
- `docs/reviews/{YYYY-MM-DD}/data-validation.md`
- `docs/reviews/{YYYY-MM-DD}/SUMMARY.md` ← consult this first

For `deep`, additionally:
- `reports/centurion_report.md` (appended)
- pytest output (stdout)

## Failure Handling

| Finding type | Action |
|---|---|
| BLOCKER | Stop. Fix before any further work. Surface to human if a standard value is questioned. |
| HIGH | Fix before merging, or open `docs/decisions/{YYYY-MM-DD}.md` documenting the deferral. |
| MEDIUM | Fix in this PR or open a follow-up ticket — do not ship silently. |
| LOW | Note in PR description; can ship. |

## When NOT to use this skill

- Pure documentation or comment changes — `quick` adds nothing
- Editing files only inside `tutorials/` — no code change to review
- Updating `data/au_pipes.py` — `data-validator` agent alone is sufficient (run it standalone)

## Caveat — current state of `scripts/quality_gate.py`

`scripts/quality_gate.py` is a Phase-5 deliverable in the active plan (see `C:\Users\brian\.claude\plans\asyou-can-see-this-fizzy-tarjan.md`). Until it lands, `deep` mode runs the underlying tasks individually. This skill will be updated when `quality_gate.py` is added.

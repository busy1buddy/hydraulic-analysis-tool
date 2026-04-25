---
name: hydraulic-sme
description: Use when the user asks domain questions or makes code changes that touch a hydraulic formula, a compliance threshold, a unit conversion, or an Australian standard reference. The skill carries the project's 15 hydraulic invariants, the 38-formula audit, and the encoded constraints from CLAUDE.md so reviewers do not have to re-read those documents in every session. Trigger words: "is this physically sensible", "cite the standard", "hand calc", "WSAA", "AS/NZS", "PVC OD", "PE100", "Joukowsky", "Buckingham-Reiner", "Hazen-Williams", "Darcy", "water age", "fire flow".
---

# Hydraulic Subject-Matter Expert

## Overview

This skill encodes the **non-obvious correctness rules** that have already cost real bugs in this codebase. Use it whenever a code change or design question touches:

- A hydraulic formula
- A WSAA or AS/NZS threshold
- A unit conversion crossing the WNTR boundary
- A pipe-database value (`data/au_pipes.py`)
- A pump-curve value (`data/pump_curves.py`)
- A solver's output that flows into a compliance check or report

The skill bundles the 15 hydraulic invariants from `tests/test_hydraulic_benchmarks.py`, the 38-formula audit at `docs/validation/formula_audit.md`, and the 13 encoded constraints from `CLAUDE.md` §4.

## Quick Start

Before changing any formula or threshold:

1. Run the SME ledger: `python .claude/skills/hydraulic-sme/scripts/run_sme_checks.py`
2. Make the change
3. Re-run the ledger
4. Confirm no PASS flipped to FAIL — if any did, see §"What to do when a benchmark fails" below

For domain questions (e.g. "is 2.6 m/s velocity acceptable in a fire-flow scenario?"), check the relevant section below before answering.

## The 13 Permanent Encoded Constraints

These are derived from resolved bugs and **must not regress**.

| # | Constraint | Verified at |
|---|---|---|
| 1 | Steady-state pressure compliance uses gauge pressure (never total head) | `epanet_api/analysis.py:39-62` |
| 2 | Transient compliance subtracts junction elevation before comparing to PN | `epanet_api/analysis.py:758-759, 1002-1003` |
| 3 | Slurry laminar friction = Darcy `64/Re_B`, never Fanning `16/Re_B` | `epanet_api/slurry_solver.py:164-167` |
| 4 | Buckingham-Reiner guard: `max(f_BP, 64/Re_B)` is the floor | `epanet_api/slurry_solver.py:164-167` |
| 5 | PVC OD per AS/NZS 1477 (DN100→110, …, DN300→315, DN375→400) | `data/au_pipes.py:142-192` |
| 6 | PE100 short-term yield = 20–22 MPa per AS/NZS 4130 (NOT 10) | `epanet_api/pipe_stress.py:116` |
| 7 | Concrete HW-C tiered by DN (DN375/450→110, DN600/750→100, DN900→90) | `data/au_pipes.py:301-346` |
| 8 | DI wave speed ≥ 1100 m/s minimum | `data/au_pipes.py:109-127` |
| 9 | Velocity uses `flows.abs().max()` for reversing pipes (never signed `flow.max()`) | `epanet_api/analysis.py:67, 153` |
| 10 | Zero-area / zero-diameter guard before computing velocity | `epanet_api/analysis.py:75, 150` |
| 11 | Joukowsky uses actual fluid `density`, never hardcoded 1000 | `epanet_api/surge.py:407-420` |
| 12 | Water age: WNTR returns seconds → divide by 3600 before 24 h compare | `epanet_api/analysis.py:408-419` |
| 13 | Slurry settling check flags velocity == 0 as highest risk (not just v > 0) | `epanet_api/slurry.py:88-93` |

## Australian Standards (always enforce)

| Standard | What | Threshold |
|---|---|---|
| WSAA WSA 03-2011 | Min service pressure | 20 m head |
| WSAA WSA 03-2011 | Max service pressure | 50 m head (residential) |
| WSAA WSA 03-2011 | Max pipe velocity | 2.0 m/s |
| WSAA WSA 03-2011 | Min pipe velocity | 0.6 m/s (sediment deposition) |
| WSAA WSA 03-2011 | Fire flow residual | 12 m head at 25 LPS |
| Mining/industrial | Max pressure override | 120 m — document each use |
| AS 2280 | Ductile iron pipe | PN25 / PN35, C = 120-140 |
| AS/NZS 1477 | PVC pipe | PN12 / PN18, C = 145-150 |
| AS/NZS 4130 | PE/HDPE pipe | SDR11 PN16, C = 140-150 |
| AS 4058 | Concrete pipe | PN25-PN35, C = 90-120 |

Defaults live at `epanet_api/__init__.py:54-56`. Detailed pipe specs live at `references/au_pipe_specs.md` (loaded into context when this skill activates).

## Formula audit reference

The full 38-formula audit is at `docs/validation/formula_audit.md`. Always cite a specific row when justifying a value. Common ones:

| Formula | Citation |
|---|---|
| Hazen-Williams | `hf = 10.67 × L × Q^1.852 / (C^1.852 × D^4.87)` (SI) — White, *Fluid Mechanics* 8th ed. |
| Darcy-Weisbach | `hL = f × (L/D) × (V²/2g)` |
| Joukowsky | `dH = a × dV / g` (use `dP = ρ × a × dV` when density ≠ 1000) |
| Buckingham-Reiner | `f_BP = (64/Re_B) × (1 + He/(6·Re_B) - He⁴/(3·f³·Re_B⁸))`, with floor `max(f_BP, 64/Re_B)` |
| Bingham Reynolds | `Re_B = ρVD / μ_p` (plastic viscosity, not apparent) |
| Hedstrom | `He = ρ × τ_y × D² / μ_p²` |
| Hoop stress (Barlow) | `σ_h = P × D / (2 × t)` — verify P/D/t units consistent |
| Von Mises | `σ_vm = √(0.5 × ((σ1-σ2)² + (σ2-σ3)² + (σ3-σ1)²))` |
| Durand critical velocity | `v_D = F_L × √(2g × D × (s-1))` for slurry deposition |
| Pump affinity | `Q ∝ N`, `H ∝ N²`, `P ∝ N³` |

## Unit conventions (enforce in every diff)

| Quantity | Internal | Display | Conversion |
|---|---|---|---|
| Pressure | m head | m head (hydraulic), kPa (stress) | 1 m head = 9.81 kPa |
| Flow | m³/s (WNTR) | LPS | × 1000 |
| Velocity | m/s | m/s (always abs) | none |
| Pipe diameter | m (WNTR) | DN mm (integer) | × 1000 |
| Stress | MPa | MPa | none |
| Water age | seconds (WNTR) | hours | ÷ 3600 |

Display rules: pressure 1 dp, velocity 2 dp, DN integer mm. **No bare floats** in `desktop/` or `reports/`.

## What to do when a benchmark fails

1. **Do not "fix" the test.** Find the regression — usually a unit conversion or a constraint above.
2. Identify the row in `docs/validation/formula_audit.md` that the change touches.
3. If a published reference disagrees with the code, surface to the human — do not edit the test.
4. If the test is genuinely outdated (e.g. a new standard supersedes), open a `docs/decisions/{date}.md` entry with the alternative considered, the standard cited, and the reversal trigger.

## Discovering Australian-specific values

When a question turns into "what does AS/NZS say about X?", consult in this order:

1. `references/au_pipe_specs.md` (in this skill)
2. `data/au_pipes.py` (the catalogue)
3. `docs/validation/formula_audit.md` (cross-references published sources)
4. The `au-engineering` sibling skill for general Australian engineering practice

Never invent a value. If sources disagree, surface to the human.

## Resources bundled with this skill

- `scripts/run_sme_checks.py` — chains hand-calcs + benchmarks + KB fidelity into one PASS/FAIL ledger
- `references/au_pipe_specs.md` — the AS/NZS pipe table extracted from `data-validator` agent for in-context use

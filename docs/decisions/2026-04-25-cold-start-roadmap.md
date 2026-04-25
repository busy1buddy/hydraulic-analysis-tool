# Cold-Start UX Roadmap — remaining work

**Date:** 2026-04-25
**Origin:** Friction log at `docs/walkthroughs/2026-04-25-cold-start/REPORT.md` §"Tactical recommendations".
**Why this exists:** Five tactical fixes were identified in the walkthrough. The top one (CSV import) shipped in commit `8757042`. The remaining four need ordering and rough scoping before execution. This document is the order of attack and the scope contract for each.

## Status of the five recommendations

| # | Recommendation | Status | Commit |
|---|---|---|---|
| 1 | `File > Import from CSV...` | **DONE** | `8757042` |
| 2 | New Project wizard | **DONE** | `beac5b1` |
| 3 | `Edit > Bulk Edit Junctions...` | **DONE** | `655da09` |
| 4 | `AddReservoirDialog` / `AddTankDialog` in canvas editor | **DONE** | `dc70c52` |
| 5 | Menu cleanup (deduplicate Settings + Pipe Profile, regroup Analysis) | **DONE** | (this commit) |

**All 5 cold-start roadmap items shipped.** Friction lines #1, #3, #4, and #6 in `docs/walkthroughs/2026-04-25-cold-start/REPORT.md` are RESOLVED. Friction #5 (`WSAA: --` placeholder on cold start) remains open as a visual-design concern in `docs/blockers.md`. The walkthrough's Gap "no AddReservoir/AddTank dialog" closed in PR #4.

The order is **not** the original priority order from the walkthrough — it's been resequenced so each PR builds on the previous, and so the lowest-risk mechanical work lands last (when the cognitive load of reviewing it is highest).

## Sequencing rationale

- **#2 (Wizard) before #3 (Bulk Edit) before #4 (Add Source dialogs).** Once the wizard exists, the canvas already has a reservoir, so #4 becomes "let the user add *more* sources later" rather than "let the user add the *first* source", which is a smaller scope and a better UX framing. #3 (Bulk Edit) only matters once a network has many junctions, which the wizard plus #4 makes easier to reach.
- **#5 (Menu cleanup) last.** It touches every UI test, doesn't change behaviour, and is best done when the surface is otherwise stable. Doing it after #2-#4 also lets us *delete* Help-menu items the wizard now obviates and *add* the new dialogs to a coherent menu shape in one pass.

---

## #2 — New Project wizard (next)

**Problem.** `File > New` clears state but leaves `api.wn = None`, and the canvas Edit mode adds only junctions and pipes. There is no path through the GUI to start a from-scratch design with a source node.

**Deliverable.** `desktop/new_project_wizard.py` — a `QWizard` (or 3-step `QDialog`) that collects:

1. **Project metadata** — name, engineer, date, target standard (WSAA / mining / custom).
2. **Source** — type (Reservoir / Tank / Connection-junction-with-fixed-head), head in m, optional name (default `R1` / `T1`).
3. **Defaults** — pipe material (PVC PN12 / DI / PE100), default roughness, default DN. These pre-populate AddPipeDialog from then on.

On accept, calls a new `api.bootstrap_project(...)` method (CoreMixin) that:
- Creates a fresh `WaterNetworkModel`
- Adds the source node at `(0, 0)`
- Stores the defaults on the API for future dialogs to read
- Returns the network summary

`File > New` and the Welcome dialog's third button (replacing "View Tutorials" or alongside it) launch this wizard. Dismissing the wizard returns to the prior state — does not destroy an existing network.

**Scope estimate.** ~250 LOC (wizard ~150 + `api.bootstrap_project` ~30 + WelcomeDialog change ~10 + tests ~60). Touches:
- `desktop/new_project_wizard.py` (new)
- `desktop/welcome_dialog.py` (add fourth button)
- `desktop/main_window.py` (`_on_new` becomes wizard launcher)
- `epanet_api/core.py` (`bootstrap_project`)
- `tests/test_new_project_wizard.py` (new)

**Gate.** Layer-purity test must stay green. New tests assert: wizard collects the right fields, `bootstrap_project` produces a network with exactly one source and zero junctions, dismissing the wizard preserves any existing network.

**Out of scope.** Topology generation (the wizard does *not* create junctions or pipes — that's still the canvas editor's job, or a future template-pattern library).

---

## #3 — `Edit > Bulk Edit Junctions...`

**Problem.** `Bulk Edit Pipes` exists; the symmetric junction editor doesn't. To set a uniform demand on 30 junctions (the Logan brief), the user must open 30 dialogs.

**Deliverable.** `desktop/canvas_editor.py:BulkJunctionEditDialog` mirroring `BulkPipeEditDialog`:
- Multi-select on canvas (already supported for highlights), confirm count in the dialog title
- Set elevation (with "leave unchanged" option), set base demand, set pattern (dropdown of patterns already in the network)
- Optional: percentage adjustment ("multiply demand by X") for global growth scenarios
- `Edit > Bulk Edit Junctions...` menu action and slot

**Scope estimate.** ~150 LOC (dialog ~80 + slot ~30 + tests ~40). Touches:
- `desktop/canvas_editor.py` (new dialog class)
- `desktop/main_window.py` (menu action + slot)
- `tests/test_canvas_editing.py` (new test cases)

**Gate.** Existing canvas-state tests stay green. New test asserts that bulk-set on a 5-junction selection writes the same demand to all five and leaves untouched junctions alone.

**Out of scope.** Bulk reservoir/tank editing (negligible value), bulk pipe-and-junction simultaneous editing (separate dialogs are clearer).

---

## #4 — `AddReservoirDialog` / `AddTankDialog` in canvas editor

**Problem.** Canvas Edit mode adds only junctions and pipes via clicks. Adding a second source (e.g. a tank to the design after the wizard placed a reservoir) requires Python.

**Deliverable.** Two new dialogs in `desktop/canvas_editor.py`:
- `AddReservoirDialog` — ID, head (m), coordinates (with the same MGA94/GDA2020 ranges as `AddJunctionDialog`)
- `AddTankDialog` — ID, elevation, init/min/max levels, diameter, coordinates

Plus a small mode-switch in canvas Edit toolbar: a dropdown or three buttons selecting "Add Junction / Add Reservoir / Add Tank" mode. The next click on the canvas opens the corresponding dialog.

**Scope estimate.** ~200 LOC (two dialogs ~100, edit-mode mode-switch ~50, tests ~50). Touches:
- `desktop/canvas_editor.py` (two new dialog classes + mode handling)
- `desktop/network_canvas.py` (toolbar additions)
- `tests/test_canvas_editing.py` (new test cases)

**Gate.** Layer-purity test stays green (no new wntr imports). New test asserts the dialog produces correct values, and that Edit-mode mode switching routes clicks to the right dialog.

**Out of scope.** Pumps and valves via clicks — those are link-type primitives that already need both endpoints, and the existing AddPipe-style flow handles them; lifting that to canvas-clicks is a separate effort.

---

## #5 — Menu cleanup (last)

**Problem.** Audit findings:
- `Settings` appears in both File and Tools menus (same action wired twice)
- `Pipe Profile` appears in both Analysis and View menus
- Analysis menu has 19 items mixing run-now actions, configurators, and one-shot reports
- Tools menu mixes Auto-place BPTs (design helper), Settings (config), Network Validator (diagnostic) — no theme

**Deliverable.**
1. Remove the duplicate Settings (keep in File only).
2. Remove the duplicate Pipe Profile (keep in Analysis only — that's where the dialog lives).
3. Split Analysis into three submenus:
   - **Analysis > Run** — Steady, EPS, Transient, Quality, Fire Flow Wizard
   - **Analysis > Configure** — Slurry Mode, Slurry Parameters, Demand Patterns, Water Quality Config
   - **Analysis > Reports** — Design Compliance Check, Safety Case Report, Pump Energy, Pipe Profile, LCC, Sensitivity, Calibration suite
4. Move `Tools > Settings` out (already removed via #1).
5. Add `Help > User Guide` and `Help > Theory Manual` (both files exist on disk; not currently linked).

**Scope estimate.** ~50 LOC. Pure UI rearrangement — no behaviour change. Touches `desktop/main_window.py` only, plus a tiny test that asserts the new shape.

**Gate.** Existing Centurion UI_CORE cases must still pass (they don't depend on menu structure). Add a new test in `tests/test_canvas_state.py` (or a new `tests/test_menu_shape.py`) asserting the four invariants:
- No action labelled "Settings" in the Tools menu
- No action labelled "Pipe Profile" in the View menu
- Analysis submenu contains exactly 3 children with the expected names
- Help menu links to USER_GUIDE.md and THEORY_MANUAL.md

**Out of scope.** Fundamentally redesigning the menu — this is a cleanup of obvious duplication and clearly mis-grouped items, not a redesign.

---

## Total roadmap scope

| PR | LOC (est) | Risk | Sequence |
|---|---|---|---|
| #2 New Project wizard | ~250 | Medium (new dialog flow) | next |
| #3 Bulk Edit Junctions | ~150 | Low | after #2 |
| #4 Add Source dialogs | ~200 | Low-medium | after #3 |
| #5 Menu cleanup | ~50 | Very low | last |

≈650 LOC across four PRs. Each is independently shippable; each closes one cold-start friction point with a verifiable test. Ground-truth tier (SME ledger, layer purity, regression) must stay green at each step — this is the unconditional gate.

## What this roadmap does *not* include

The walkthrough also surfaced two items that are **not** in this roadmap because they are out of UX scope:

- **Visual / DPI / 4K issues** — need a sighted human session, listed in `docs/blockers.md`.
- **Long-running iterative refinement UX** — only meaningfully testable with a real engineering project; would be the subject of a *second* walkthrough in 2-3 months once the four PRs above have landed.

## How this decision can be reversed

If after #2 the wizard turns out to be more friction than help (e.g. engineers prefer to start from a tutorial and adapt), revert by:

1. Removing the wizard launch from `File > New` (back to the bare reset behaviour).
2. Hiding the wizard's button in the Welcome dialog rather than removing the file (so the file stays available for future re-introduction).
3. Note the reversal in `docs/decisions/{date}-wizard-reversal.md` with the engineer feedback that drove it.

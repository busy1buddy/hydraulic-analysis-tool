# Cold-start UX walkthrough — Logan 30-lot subdivision

**Date:** 2026-04-25
**Persona:** A new engineer with their own brief, no prior knowledge of the toolkit, no tutorial as a starting template (used only as a fallback when the cold-start path was blocked).
**Constraint:** Only methods reachable from the GUI — slot methods, dialog widgets, menu actions, canvas editor. No direct `HydraulicAPI` calls that the GUI doesn't expose.
**Brief:** Design water supply for a 30-lot residential subdivision in Logan, QLD. WSAA WSA 03-2011: 20-50 m service pressure, ≤2.0 m/s, fire flow 25 LPS @ 12 m residual. Source: existing main with 50 m head. 8 m fall N→S. PVC PN12 minimum. Output: PDF compliance certificate.

**Driver:** `driver.py` in this folder.
**Raw log:** `log.txt` (printed by the driver).

## TL;DR

The toolkit's **analysis engine and reporting deliverables are professional**. The **cold-start design path is broken**: a new user with their own brief cannot start a from-scratch design through the GUI alone. There is no project-creation wizard, no way to add a reservoir or tank without opening an existing file, no GUI-reachable CSV import, and no bulk-edit-junctions primitive (despite Bulk Edit Pipes existing). The realistic path forces every cold-start user to grab the closest tutorial and edit it — which is also how I had to do it.

A real bug was found by attempting the report flow: `ReportDialog` crashed at construction with `AttributeError: 'ReportDialog' object has no attribute 'checkboxes'`. Fixed in this walkthrough (`desktop/report_dialog.py`).

## Top friction points (priority order)

1. **No project-creation path.** `File > New` clears state but leaves `api.wn = None`. Canvas Edit mode adds only junctions and pipes — no reservoir or tank. No menu action introduces a source. The user is left with a blank canvas and most menu items refusing to open. *Fix:* Welcome dialog needs a "Create New Project" button that opens a small wizard collecting project name, source type (reservoir/tank/connection), source head, target standard (WSAA / mining / custom), and bootstraps `api.wn` with that single source node. Opening the canvas in Edit mode after this should let the user click to add junctions and pipes anchored to the source. **STATUS: RESOLVED** in PR #2 of the cold-start roadmap. `api.bootstrap_project()` added to `epanet_api/core.py` with reservoir/tank/junction-with-head support; `desktop/new_project_wizard.py:NewProjectWizard` collects metadata + source + pipe defaults; `File > New` and `WelcomeDialog`'s new "Create New Project..." button both launch it; cancel preserves the existing network. 13 tests in `tests/test_new_project_wizard.py`.

2. **`ReportDialog` crash** (real bug, fixed in this walkthrough). `_detect_conditional_sections()` was called before `self.checkboxes = {}` was initialised in `__init__`; it referenced the missing attribute on every construction with non-empty results. The crash was silent in `_on_report_docx` because the surrounding try/except in some call sites swallowed it, but `Reports > Generate Report (DOCX/PDF)` would fail for any user who actually used it after a successful steady-state run.

3. **No CSV import in the menu.** `importers/csv_import.py` exists, is used by tests, has its own sample-CSV generator, and is invisible to the GUI user. A user with a 30-row coordinates CSV (the most natural way to model 30 lots) cannot import it without writing Python. *Fix:* Add `File > Import from CSV...` that opens a two-file QFileDialog (nodes + pipes) and calls the existing function. **STATUS: RESOLVED** in commit after 2026-04-25 walkthrough — `api.import_from_csv()` added to `epanet_api/core.py` (CoreMixin) wrapping the importer, and `File > Import from CSV...` menu action wired through `desktop/main_window.py:_on_import_csv` with two sequential file pickers (nodes then pipes, second defaults to the same folder). 5 new unit tests + 2 UI-wiring smoke tests in `tests/test_importers.py`.

4. **Asymmetric bulk editing.** `Edit > Bulk Edit Pipes...` exists and is excellent (material picker, DN dropdown, roughness). There is no equivalent `Edit > Bulk Edit Junctions` for elevation or demand. To apply a uniform per-lot demand of 0.05 LPS to 13 junctions I had no GUI option — every junction would need its own dialog. *Fix:* mirror the Bulk Edit Pipes dialog for junctions — multi-select + bulk set elevation/demand/pattern. **STATUS: RESOLVED** in PR #3 of the cold-start roadmap. `desktop/canvas_editor.py:BulkJunctionEditDialog` adds tickable elevation / absolute-demand / percentage-demand-factor / pattern fields with mutual exclusion between the two demand modes. `editor.bulk_edit_junctions(junction_ids=None)` defaults to all junctions (the cold-start case) but accepts a subset. 12 tests in `tests/test_bulk_edit_junctions.py`.

5. **Status-bar `WSAA: --` on cold start** (already in `docs/blockers.md`, confirmed live). Looks unfinished. Either show `(load network)` or hide the badge until something has been loaded.

6. **Menu organisation.**
   - `&Settings...` appears in *both* `File` and `Tools` menus — same action, two places.
   - `&Pipe Profile...` appears in *both* `Analysis` and `View` menus.
   - `Analysis` menu has 19 items, mixing run-now actions (Run Steady, Run Transient) with configurators (Slurry Mode toggle, Demand Patterns) with one-shot dialogs (Pipe Profile, Pump Energy). Hard to scan.
   - `Tools` menu mixes Auto-place BPTs (advanced design helper) with Settings (config) with Network Validator (diagnostic). No coherent grouping.
   - `View` menu mixes layout actions (Reset Layout, Project Explorer, Properties dock toggles) with rendering options (Scale Pipes, GIS Basemap) with workflow modes (Split Screen, 3D View).

   *Fix (low-risk):* deduplicate Settings and Pipe Profile. Group Analysis into three submenus: **Run** (steady, transient, EPS, fire flow, quality), **Configure** (slurry mode/params, demand patterns, water-quality config), **Reports** (compliance check, safety case, pump energy). **STATUS: RESOLVED** in PR #5 of the cold-start roadmap. Tools > Settings (the broken stub) removed; View > Pipe Profile renamed to "Pipe Profile Dock" to disambiguate from Analysis > Reports > Pipe Profile (HGL) which is a separate one-shot calculation, not a duplicate. Analysis menu reorganised into 4 submenus (Run / Configure / Calibration / Reports) — calibration emerged as its own group during the work because the four calibration items (Wizard / Field Data / Residuals / Dashboard / Sensitivity) form a workflow distinct from Configure. Help menu gains User Guide and Theory Manual links pointing at `docs/USER_GUIDE.md` and `docs/THEORY_MANUAL.md`. 11 tests in `tests/test_menu_shape.py` pin the new shape so future menu edits cannot silently flatten or re-introduce duplicates.

## Strengths verified

These were genuine pleasant surprises:

1. **Fire-flow defaults match WSAA exactly** — `FireFlowDialog` opens with flow = 25 LPS and residual = 12 m, the precise values in WSAA WSA 03-2011 §3.3. A new engineer doesn't need to look up the standard.

2. **`AddPipeDialog` has a smart pipe-sizing suggestion.** It walks downstream demand, applies a 1.5× peak factor, targets 1.0 m/s, and rounds up to the nearest standard DN. The suggestion is shown on a styled label inside the dialog with a tooltip explaining the calculation. This is the right kind of in-context help.

3. **Steady-state through F5 is fast and asynchronous.** On the 13-junction tutorial it completes in ~0.5 s, the AnalysisWorker dispatches off-thread (Phase-2 fix), the WSAA badge in the status bar updates immediately to `WSAA: PASS (3i)` showing pass + issue count. One-glance verdict.

4. **`AddJunctionDialog` carries Australian-specific defaults.** Elevation range −100 to 2500 m AHD (literally Lake Eyre to Kosciuszko), tooltip says "Elevation in metres above Australian Height Datum (m AHD)". Coordinate fields support MGA94/GDA2020 ranges. The product knows its market.

5. **`ComplianceDialog` (F9) is the right primitive for engineering sign-off.** Formal per-standard pass/fail dialog, dedicated for the compliance certificate output. Distinct from the in-status-bar badge.

6. **Tutorials load instantly and are clean templates.** The 11 tutorial networks are well-curated, the `australian_subdivision` one has 13 junctions / 17 pipes — close enough to the brief to be a working template.

## Gaps surfaced (not friction, but missing primitives)

- **No "from a brief" wizard** — there's no flow that asks the engineer "lots? area? topography? source?" and bootstraps a reasonable network skeleton. Every cold start is from a tutorial or an external `.inp`.
- **No GUI-exposed `Add Reservoir` / `Add Tank`** anywhere. The HydraulicAPI has these (`api.add_reservoir`, `api.add_tank`), they are callable from Python, they are in the AS/NZS-aligned `epanet_api.core` module, and the canvas editor has no path to them.
- **No bulk junction editor** (covered above as friction).
- **No template-pattern library** (e.g. "linear cul-de-sac with 30 lots", "loop main with 4 branches"). Even a tiny library of 3-4 generators would convert the cold-start path from "edit this tutorial" to "generate this pattern".
- **`Help` menu has no link to `docs/THEORY_MANUAL.md` or `docs/USER_GUIDE.md`.** Both exist on disk; neither is reachable from the running app.

## Tactical recommendations (next 5 PRs of UX work)

In rough order of value-per-PR:

1. **Add `File > Import from CSV...`** — wire `importers/csv_import.py` to a small two-file picker. ~30 LOC change. Unblocks the most common cold-start pattern (engineer has coordinates).

2. **Add a "New Project" wizard** behind the Welcome dialog and `File > New` actions — collects project name, source (reservoir / tank / connection node), source head, target standard, and creates a non-empty `WaterNetworkModel` with the source node. The user lands in a state where they can immediately open Edit mode and start clicking junctions.

3. **Add `Edit > Bulk Edit Junctions...`** mirroring the existing `Bulk Edit Pipes...` — multi-select on canvas, set elevation / demand / pattern. ~100 LOC. Makes the 30-junction case tractable in the GUI.

4. **Add `AddReservoirDialog` and `AddTankDialog`** in `desktop/canvas_editor.py`, plus an `Edit > Add Source...` menu action. The canvas should be able to introduce a source primitive without requiring an `.inp` import.

5. **Menu cleanup PR** — deduplicate `Settings` and `Pipe Profile`; reorganise the `Analysis` menu into Run / Configure / Reports submenus; move `Settings` out of Tools. ~50 LOC, big readability win for new users.

## What this walkthrough did *not* cover

- **Visual / DPI / 4K** — I cannot see pixels. The status-bar layout, dialog cramping at small window sizes, colour-blind contrast, and 4K scaling all need a human session. `docs/blockers.md` already has these on the list.
- **Editing experience on the canvas** — I tested through the dialog APIs, not through synthetic mouse events. Whether the click-to-add-junction behaviour is intuitive, whether the rubber-band pipe drawing feels right, whether tooltips appear at the right time — those need a sighted user.
- **Long-running workflow with iterative refinement** — I ran a single steady-state and stopped. A real engineer would iterate on pipe sizes, re-run, compare scenarios, etc. The Phase-2 work made these paths thread-safe; their UX is untested.

## Reproducing this walkthrough

```bash
python docs/walkthroughs/2026-04-25-cold-start/driver.py
```

The driver prints the live observations and writes them to `log.txt` in the same folder. The driver intentionally does NOT use any HydraulicAPI method that isn't reachable from the GUI — when it must (e.g. to load the tutorial as a fallback in Phase 3), it logs that as friction.

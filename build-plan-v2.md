# Hydraulic Analysis Tool — Full Build Plan v2
# Resume point: Review cycle complete (2026-04-03). 47 findings logged.
# All review files exist in docs/reviews/2026-04-03/

## Your Mission
You are resuming an autonomous build session. The review cycle has already run
and produced 47 findings (7 blockers, 18 high, 19 medium, 3 low).

Work autonomously through every phase in order. After each phase, run
/review-cycle and fix all BLOCKER and HIGH findings before proceeding.
Document every non-trivial decision in docs/decisions/{date}.md.
Do not stop to ask questions — make reasonable decisions and document them.
If you hit a blocker, write it to docs/blockers.md and move to the next task.
Commit to git after each phase with a descriptive message.

---

## Phase -1 — Write Expanded CLAUDE.md with GodMode Orchestration

Rewrite CLAUDE.md in full. This is the shared brain for every agent and every
future session. Every agent reads this file — the rules here propagate to all
future review cycles automatically.

The new CLAUDE.md must contain ALL of the following sections:

### 1. Project Identity
- What this software is: professional hydraulic analysis desktop tool
- Target users: Australian water and mining engineers
- Applicable standards: WSAA, AS/NZS 1477, AS 2280, AS/NZS 4130, AS 4058
- Tech stack: Python, WNTR, TSNet, PyQt6, PyInstaller

### 2. Architecture Layers (strict — never violate)
```
Layer 1 — Solvers:  wntr, tsnet (never import directly from UI or reports)
Layer 2 — API:      epanet_api.py (single orchestration point for all analysis)
Layer 3 — Domain:   slurry_solver.py, pipe_stress.py, data/
Layer 4 — UI:       app/ (PyQt6 — imports API only, never solvers directly)
Layer 5 — Output:   reports/ (reads from API result dicts, never solver objects)
```
Rule: No layer may import from a layer above it.
Rule: The UI layer (app/) may never import wntr or tsnet directly.
Rule: All network mutations must go through HydraulicAPI methods — never
      mutate api.wn directly from outside epanet_api.py.
Rule: report generators receive plain dicts, never raw WNTR result objects.

### 3. Unit Conventions (enforce in every file touched)
- Pressures:    kPa inside API calculations; metres head in all UI display
- Velocities:   m/s everywhere, always absolute value (never signed)
- Pipe sizes:   DN (mm nominal) in UI; metres internal diameter inside WNTR
- Flow rates:   LPS in UI display; m³/s inside WNTR and solvers
- Wave speed:   m/s
- Stress:       MPa
- Water age:    WNTR returns seconds — divide by 3600 before any hour comparison
- Display rule: Every value shown to the user must include its unit.
                No bare floats anywhere in app/ or reports/.

### 4. Hydraulic Domain Rules (encode all known bugs as permanent constraints)
- Steady-state pressure compliance: gauge pressure only — never total head
- Transient compliance: subtract junction elevation before comparing to PN rating
- WSAA thresholds: min 20 m, max 50 m residential, max 2.0 m/s velocity
- Mining/industrial override: max pressure threshold 120 m — document when used
- Slurry laminar friction factor: Darcy (64/Re_B), NEVER Fanning (16/Re_B)
- Buckingham-Reiner guard: max(f_BP, 64/Re_B) — higher value is the floor
- PVC pipe OD: use AS/NZS 1477 OD series — OD is never equal to DN
  Correct values: DN100→110, DN150→160, DN200→225, DN250→280, DN300→315, DN375→400
- PE100 short-term design yield: 20–22 MPa per AS/NZS 4130 (not 10 MPa)
- Concrete HW-C by size: DN375/450→C=110, DN600/750→C=100, DN900→C=90
- DI wave speed lower bound: 1100 m/s minimum for all sizes
- Velocity on reversing pipes: abs(flow).max() — never signed flow.max()
- Zero-diameter guard: always check area > 0 before computing velocity
- Joukowsky: use actual fluid density — never hardcode 1000 kg/m³ for slurry
- Water age stagnation: WNTR returns seconds, threshold is in hours —
  convert: age_hours = wntr_value / 3600, then compare to 24.0
- Slurry settling check: flag pipes with velocity == 0 as highest risk,
  not just pipes with velocity > 0

### 5. GodMode Orchestration Rules

#### Autonomous work policy
- Task is unambiguous and reversible → proceed without asking
- Task modifies a calculation formula → run relevant benchmark before AND
  after, confirm PASS, then proceed
- Task touches au_pipes.py → run scripts/validate_pipe_db.py before AND
  after, confirm no regressions
- Uncertain about a standard value → check AS/NZS source, document reference
  in a code comment before writing the value
- Two agents disagree on a finding that affects a calculation → stop and
  surface to the human

#### Sub-Agent Routing Rules
Parallel dispatch (run together — independent, no shared state):
  - code-reviewer + data-validator
  - ui-reviewer + hydraulic-tester

Sequential dispatch (strict order):
  architect
    → (code-reviewer + data-validator)
      → (ui-reviewer + hydraulic-tester)
        → feedback-synthesizer

Background dispatch (non-blocking, results not immediately needed):
  - Any read-only audit or analysis task
  - Benchmark runs that do not modify files

Never parallelize:
  - Any two tasks that write to the same file
  - au_pipes.py schema changes with any other task
  - epanet_api.py edits while any agent is reading epanet_api.py

#### Self-review gate (mandatory before marking any phase complete)
1. Run /review-cycle
2. BLOCKER findings exist → fix all, run /review-cycle again
3. HIGH findings exist → fix all, or document deferral reason in
   docs/decisions/{date}.md with justification
4. Write phase summary to docs/progress.md
5. Commit to git: "Phase X complete — N blockers fixed, N high fixed"

#### Decision logging (every non-trivial decision)
Write to docs/decisions/{YYYY-MM-DD}.md:
- What was decided
- Why (alternatives considered)
- Standard or reference that supports it
- What would need to change if this decision is reversed

#### Stop and surface to human when
- A benchmark FAILs after a fix (regression introduced)
- A standard value cannot be confirmed from available sources
- Any change would modify the .inp file format or the HydraulicAPI public interface

### 6. Code Conventions
- Every hydraulic formula must cite its source:
  # Darcy-Weisbach: hL = f*(L/D)*(V²/2g) — ref: White, Fluid Mechanics 8th ed.
- Unit conversions must be explicit with a comment:
  # convert LPS to m³/s
  Q_m3s = Q_lps / 1000
- No magic numbers without a named constant:
  WSAA_MIN_PRESSURE_M = 20.0  # WSAA WSA 03-2011 Table 3.1
- Division: always guard zero denominators in hydraulic calculations
- Physical bounds in steady-state: pressure >= 0, velocity >= 0

### 7. Known Deferred Items (do not re-flag in reviews)
- TSNet pump transient tests are xfail — known solver limitation, not a bug
- server.py (FastAPI) is legacy — review shallowly, do not refactor
- epanet_api.py size (~1200 lines) is an accepted tradeoff — flag only if a
  new responsibility is added, not for its current size
- pipe_stress.py is implemented but not yet wired to UI — planned for Phase 5

### 8. File and Path Conventions
- Review outputs:   docs/reviews/{YYYY-MM-DD}/
- Decision log:     docs/decisions/{YYYY-MM-DD}.md
- Progress log:     docs/progress.md
- Blockers:         docs/blockers.md
- Pipe DB script:   scripts/validate_pipe_db.py
- Audit trail:      docs/audit/{YYYY-MM-DD}/
- Phase outputs:    all new source files under src/ (not project root)

After writing CLAUDE.md, print it in full and wait for my confirmation
before proceeding to Phase 0.

---

## Phase 0 — Fix All 7 Blockers
# Source: docs/reviews/2026-04-03/SUMMARY.md
# All fixes must be verified before proceeding to Phase 1.
# Run the relevant benchmark or test after EACH fix, not all at once.

### B1 — slurry_solver.py:136 (fix first — highest engineering risk)
Problem: Fanning friction factor (16/Re_B) used where Darcy (64/Re_B) needed.
         Causes 4× headloss underestimate for all Bingham plastic fluids.
         Confirmed by hydraulic benchmark #6 (got 0.006 m, expected 0.026 m).
Fix:
- Change 16/Re_B to 64/Re_B in the laminar friction factor line
- Fix the inverted max() guard at lines 136-137:
  should be max(f_BP, 64/Re_B) not max(f_BP, 16/Re_B)
- Add comment: # Darcy friction factor for laminar Bingham plastic — Buckingham-Reiner
Verify: re-run hydraulic benchmark #6 — must return ~0.026 m (not 0.006 m)
        re-run benchmark #6 with water baseline — must still pass

### B2 — epanet_api.py:644-908
Problem: Transient compliance uses total hydraulic head (elevation + pressure head)
         instead of gauge pressure. Understates transient exceedances at elevated
         junctions — false-safe results.
Fix:
- In both valve transient path (line ~644) and pump transient path (line ~887):
  gauge_pressure_m = total_head_m - junction_elevation_m
  use gauge_pressure_m for PN35 compliance comparison
- Add comment: # WSAA compliance checks gauge pressure, not total head
Verify: create a test junction at elevation 20 m with total head 55 m
        (gauge = 35 m, exactly at PN35 limit — should flag as marginal)

### B3 — epanet_api.py:491-500
Problem: WNTR returns water age in seconds. Code stores raw values and compares
         to a 24.0 threshold (implying hours). Stagnation check never fires.
Fix:
- After retrieving water age from WNTR results, divide by 3600:
  age_hours = raw_age_seconds / 3600
- Store age_hours in result dict under the _hrs key
- Add comment: # WNTR water age is in seconds — convert to hours for WSAA comparison
- Change threshold comparison to use age_hours against 24.0
Verify: confirm stagnation check fires when age > 24 hours in a test case

### B4 — data/au_pipes.py (do all sub-fixes in one commit)
Problem: PVC OD = DN (wrong). Should use AS/NZS 1477 OD series.
         Multiple other database errors across materials.

PVC — rebuild from AS/NZS 1477:
  DN100: OD=110, recalculate wall and ID for each PN class
  DN150: OD=160 (already correct — verify only)
  DN200: OD=225, recalculate wall and ID
  DN250: OD=280, recalculate wall and ID
  DN300: OD=315, recalculate wall and ID
  DN375: OD=400, recalculate wall and ID
  Add missing standard sizes if any

PE100:
  Fix yield_MPa from 10 to 20 (AS/NZS 4130 short-term design strength)
  Add comment: # AS/NZS 4130 short-term design yield ~20-22 MPa

Concrete (AS 4058):
  Fix HW-C: DN375/450 → C=110, DN600/750 → C=100, DN900 → C=90

Ductile Iron:
  Fix DN375/450/600 internal diameters (currently 5-9 mm too wide)
  Fix wave speeds: DN450 must be >= 1100 m/s, DN600 must be >= 1100 m/s
  Add missing DN500

After all changes:
  Write scripts/validate_pipe_db.py that cross-checks every entry
  against the standard values above and prints PASS/FAIL per entry.
  Run it — all entries must pass before committing.

### B5 — data/pump_curves.py
Problem: Slurry pump shaft power grossly inconsistent with motor ratings.
  SLP-200-30: shaft 16.4 kW vs 45 kW motor (ratio 0.26 — should be ~0.75-0.85)
  SLP-400-50: shaft 47.1 kW vs 110 kW motor (ratio 0.43)
Fix:
  Correct either the head/flow curve values or the motor ratings so that
  shaft_power / motor_power is in the range 0.70-0.90 at rated duty.
  Document the source/reference for corrected values in a comment.
Verify: re-run pump affinity benchmark — must still PASS

### B6 — network_editor.py + scenario_manager.py
Problem: UI layer directly imports wntr and mutates api.wn bypassing HydraulicAPI.
Fix:
  network_editor.py:14 — remove direct wntr import
  network_editor.py:162-265 — route all add/remove/modify operations through
    HydraulicAPI methods. Add methods to HydraulicAPI if they don't exist:
      api.add_pipe(), api.remove_pipe(), api.update_pipe()
      api.add_junction(), api.remove_junction(), api.update_junction()
      api.write_inp(path)
  scenario_manager.py:13-15 — remove direct wntr import, use API only
  steady_state.py:115, transient.py:89 — replace direct access to
    api.steady_results and api.tm with API getter methods if needed
  view_3d.py:687-770 — replace direct api.wn reads with API getter methods
Verify: grep -r "import wntr" app/ must return no results after fix

### B7 — epanet_api.py:213-245
Problem: Velocity uses signed f.max() — misses peak speed on reversing pipes.
         No guard for zero pipe area — ZeroDivisionError on user-edited .inp.
Fix:
  Change f.max() to f.abs().max() for all velocity calculations
  Add before area calculation:
    if pipe_area <= 0:
        continue  # skip degenerate pipe, log warning
  Add comment: # abs() required — flow can be negative on reversing pipes
Verify: re-run hydraulic benchmark #9 (velocity = Q/A) — must still PASS
        re-run benchmark #5 (mass balance) — must still PASS

### After Phase 0
Run /review-cycle.
All 7 blockers must show as FIXED in the new SUMMARY.md.
If any remain, fix them before proceeding to Phase 1.
Write to docs/progress.md: "Phase 0 complete — 7 blockers resolved"
Commit: "Phase 0: fix all 7 blockers — slurry friction, PVC geometry,
         transient compliance, water age units, layer violations, velocity"

---

## Phase 1 — Walking Skeleton (PyQt6 app shell)

Build a native Windows PyQt6 application shell. This replaces NiceGUI entirely.
The existing backend (epanet_api.py, solvers, data) must not be modified.

Deliverables:
- main_window.py: QMainWindow with menu bar, status bar, central widget
- Menu bar: File | Analysis | Tools | Reports | View | Help
  File:     New, Open (.inp), Save, Save As (.hap), Exit
  Analysis: Run Steady State, Run Transient, Slurry Mode (toggle)
  Tools:    Quality Review (triggers /review-cycle), Settings
  Reports:  Generate Report (DOCX), Generate Report (PDF)
  View:     Reset Layout, Toggle panels
- Three QDockWidget panels:
  Left:   Project Explorer (tree: model name, scenarios, results runs)
  Right:  Properties (selected element properties)
  Bottom: Results (tabular node/pipe results)
- Central widget: placeholder QLabel("Network View") — replaced in Phase 2
- Status bar showing 4 segments:
  Analysis Type | Nodes: N | Pipes: N | WSAA: PASS/FAIL
- File > Open: loads .inp via epanet_api.py, populates Project Explorer
- File > Save/Save As: saves project state as .hap (JSON) file
  .hap format: {inp_path, scenarios: [], last_run: {}, settings: {}}
- App entry point: python main_app.py (not a browser, not a script)
- requirements_desktop.txt listing PyQt6 and all dependencies

Do NOT start the NiceGUI server. The old app/ directory is reference only.

After Phase 1, run /review-cycle. Fix all BLOCKER and HIGH issues.
Write to docs/progress.md. Commit: "Phase 1: PyQt6 walking skeleton"

---

## Phase 2 — Network Canvas

Replace the Phase 1 placeholder with a real interactive network view.
Use PyQtGraph for the 2D canvas (already fast, no browser dependency).

Deliverables:
- network_canvas.py: PyQtGraph-based interactive canvas
  - Nodes as circles, pipes as lines, tanks as squares, pumps as triangles
  - Click node or pipe → populates Properties panel with element data
  - Right-click → context menu (edit properties, delete, add connected pipe)
  - Color mode dropdown: Pressure | Velocity | Headloss | Status
  - Live WSAA compliance overlay:
      green  = pass (pressure 20-50 m, velocity < 2.0 m/s)
      orange = warning (pressure 15-20 m or velocity 1.5-2.0 m/s)
      red    = fail (pressure < 15 m or > 50 m, velocity > 2.0 m/s)
      grey   = no results yet
  - Zoom: scroll wheel
  - Pan: middle mouse button or space+drag
  - Fit to view: double-click empty canvas or View > Fit
  - Node/pipe labels toggle: View > Show Labels
- Color scale legend in bottom-right corner (updates with color mode)
- Toolbar with: Open, Run, Zoom Fit, Color Mode selector

After Phase 2, run /review-cycle. Fix all BLOCKER and HIGH issues.
Write to docs/progress.md. Commit: "Phase 2: interactive network canvas"

---

## Phase 3 — Analysis Integration

Wire the existing backend to the PyQt6 UI. All analysis must run in a
QThread — the UI must never freeze during a solve.

Deliverables:
- analysis_worker.py: QThread subclass wrapping epanet_api.py calls
  Signals: started, progress(int), finished(dict), error(str)
- Analysis > Run Steady State:
  - Triggers analysis_worker with run_steady_state()
  - Progress bar in status bar during solve
  - On finish: update canvas colors, populate Results panel, update status bar
  - On error: show QMessageBox with human-readable message (no Python tracebacks)
- Analysis > Run Transient:
  - Triggers analysis_worker with run_transient()
  - Same progress/finish/error handling
- Analysis > Slurry Mode toggle:
  - Checked state → use slurry_solver.py for headloss
  - Status bar shows "Analysis Type: Slurry (Bingham Plastic)"
  - Slurry parameters panel appears in Properties dock when toggle is on:
    yield stress (Pa), plastic viscosity (Pa·s), particle density (kg/m³)
- Results panel: QTableWidget showing per-node and per-pipe results
  All values rounded and with units per CLAUDE.md unit conventions
  Columns: ID | Elevation (m) | Pressure (m) | Head (m) | WSAA Status
  Pipes:   ID | Diameter (DN) | Length (m) | Velocity (m/s) | Headloss (m/km)
- WSAA compliance summary card below results table:
  Shows pass/fail counts, cites standard ("WSAA WSA 03-2011 Table 3.1")

After Phase 3, run /review-cycle. Fix all BLOCKER and HIGH issues.
Write to docs/progress.md. Commit: "Phase 3: analysis integration"

---

## Phase 4 — Scenario Comparison

Deliverables:
- Scenario panel in Project Explorer: tree shows Base, Peak, Fire Demand etc.
- Scenario Manager dialog: create, rename, duplicate, delete scenarios
  Each scenario stores: demand multipliers, pipe closures, pump settings
  Routes mutations through HydraulicAPI (not direct wntr access)
- Run All Scenarios: executes all scenarios sequentially, stores all results
- Split view comparison: two canvas panes side by side
  Left: Scenario A | Right: Scenario B (selectable from dropdown)
- Difference overlay mode: single canvas showing delta between two scenarios
  Blue pipes: velocity increased > 10%
  Red pipes:  pressure decreased > 10%
  Green pipes: no significant change
- Scenario results table: one row per scenario, columns for min/max pressure,
  max velocity, WSAA pass/fail count

After Phase 4, run /review-cycle. Fix all BLOCKER and HIGH issues.
Write to docs/progress.md. Commit: "Phase 4: scenario comparison"

---

## Phase 5 — Reports, Audit Trail, Quality Review Panel

Deliverables:

Reports:
- Report Builder dialog: checklist of sections to include
  (Executive Summary, Network Summary, Node Results, Pipe Results,
   Compliance Table, Scenario Comparison, Appendix: Input Parameters)
- One-click generate to DOCX or PDF using existing reports/ module
- Fix all raw-float display issues from ui-review findings:
  All table cells rounded to appropriate precision with units
  Consistent column headers between DOCX and PDF reports
  Compliance messages cite specific standard and clause

Audit trail:
- Every analysis run auto-logged to docs/audit/{YYYY-MM-DD}/{timestamp}/
  Contents: input .inp file snapshot, parameters used, full results JSON,
  solver version, timestamp, WSAA compliance summary
- Audit viewer: Tools > View Audit Trail opens a dialog showing past runs
  with ability to reload any previous result set

Quality Review panel:
- Tools > Quality Review triggers /review-cycle from inside the app
- Findings appear in a new docked panel (right side, below Properties)
- Findings grouped by severity: BLOCKER | HIGH | MEDIUM | LOW
- Each finding shows: file:line, description, fix suggestion
- "Fix All Blockers" button: asks Claude Code to fix all BLOCKER items

Wire pipe_stress.py to UI:
- Add "Pipe Stress Analysis" tab in Results panel
- Shows hoop stress, von Mises, safety factor per pipe
- Highlights pipes where safety factor < 1.5 in red

After Phase 5, run /review-cycle. Fix all BLOCKER and HIGH issues.
Write to docs/progress.md. Commit: "Phase 5: reports, audit, quality panel"

---

## Phase 6 — Packaging and Installer

Deliverables:
- hydraulic_tool.spec: PyInstaller spec file
  Bundles: Python runtime, PyQt6, WNTR, TSNet, all domain modules
  Mode: --onefile or --onedir (choose based on startup time test)
  Hidden imports: list all dynamic imports discovered during testing
  Data files: data/au_pipes.py, data/pump_curves.py, any .inp examples
- build.bat: one-command build script
    pyinstaller hydraulic_tool.spec --clean
- installer/setup.iss: Inno Setup script
  App name: "Hydraulic Analysis Tool"
  Publisher: [your name/company]
  File associations: .hap opens the app, .inp opens the app
  Install locations: Program Files, Desktop shortcut, Start Menu entry
  Uninstaller included
- Test the installer on a clean Windows VM or machine with no Python installed
  Must launch, open a .inp file, run steady state, generate a report
  Without any Python or dependency installation by the user

After Phase 6, run /review-cycle one final time.
Write to docs/progress.md: "Phase 6 complete — application ready for distribution"
Final commit: "v1.0.0 — full desktop application, installer, all blockers resolved"

---

## Definition of Done
A senior hydraulic engineer with no Python knowledge can:
1. Run the installer on a clean Windows machine
2. Double-click a .inp file and have it open in the application
3. Run a steady state analysis and see WSAA compliance on the network canvas
4. Switch to slurry mode, enter slurry parameters, run analysis
5. Compare two demand scenarios side by side
6. Generate a professional DOCX report with correct units and standard citations
7. Trust the numbers — all 7 original blockers resolved and benchmarks passing
8. Run Tools > Quality Review and see current code health

---

## Progress Tracking
After each phase write to docs/progress.md:
- Phase name and completion date
- What was built
- Decisions made and why (or link to docs/decisions/{date}.md)
- What /review-cycle found and what was fixed
- Any items deferred to a later phase with justification
- Git commit hash for the phase

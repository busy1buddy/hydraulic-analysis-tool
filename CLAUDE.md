# EPANET Hydraulic Analysis Toolkit — Development Guide

## 1. Project Identity

Professional hydraulic analysis desktop tool for Australian water supply and mining engineers. Competes with PumpSim ($15K), AFT Fathom ($10K), and WaterGEMS ($15K). Covers steady-state, transient/water hammer, non-Newtonian slurry, fire flow, water quality, pump engineering, pipe stress, and network visualization.

- **Target users:** Australian water and mining engineers
- **Standards:** WSAA WSA 03-2011, AS/NZS 1477, AS 2280, AS/NZS 4130, AS 4058
- **Tech stack:** Python, WNTR, TSNet, PyQt6, PyQtGraph, PyInstaller
- **Entry point:** `python main_app.py` (PyQt6 desktop app)
- **Legacy UI:** `app/` (NiceGUI — reference only, do not start)
- **Legacy server:** `server.py` (FastAPI — do not refactor)

## 2. Architecture Layers (strict — never violate)

```
Layer 1 — Solvers:  wntr, tsnet (never import directly from UI or reports)
Layer 2 — API:      epanet_api.py (single orchestration point for all analysis)
Layer 3 — Domain:   slurry_solver.py, pipe_stress.py, data/
Layer 4 — UI:       desktop/ (PyQt6 — imports API only, never solvers directly)
Layer 5 — Output:   reports/ (reads from API result dicts, never solver objects)
Layer 6 — Import:   importers/ (produce .inp files, never run simulations)
```

**Rules:**
- No layer may import from a layer above it.
- The UI layer (`desktop/`) may never import `wntr` or `tsnet` directly.
- All network mutations must go through `HydraulicAPI` methods — never mutate `api.wn` directly from outside `epanet_api.py`.
- Report generators receive plain dicts, never raw WNTR result objects.
- Importers produce `.inp` files only — they never run simulations.

## 3. Unit Conventions (enforce in every file touched)

| Quantity | Internal (solver) | Display (UI/reports) | Conversion |
|----------|-------------------|---------------------|------------|
| Pressure | m head | m head (hydraulic), kPa (stress) | 1 m head = 9.81 kPa |
| Flow | m³/s (WNTR) | LPS | × 1000 |
| Velocity | m/s | m/s | none, always absolute value |
| Pipe diameter | m (WNTR) | DN mm | × 1000 |
| Pipe length | m | m | none |
| Elevation | m AHD | m AHD | none |
| Roughness | C-factor | C-factor | none |
| Wave speed | m/s | m/s | none |
| Stress | MPa | MPa | none |
| Water age | seconds (WNTR) | hours | ÷ 3600 |

**Critical rules:**
- WNTR stores diameter in metres. Multiply by 1000 for display. Every `pipe.diameter` access in UI code must convert.
- WNTR returns water age in seconds — divide by 3600 before any hour comparison.
- Every value shown to the user must include its unit. No bare floats anywhere in `desktop/` or `reports/`.
- Pressure display: 1 decimal place (e.g., 30.2 m)
- Velocity display: 2 decimal places (e.g., 1.45 m/s)
- Pipe diameter display: integer mm (e.g., 300 mm, not 300.0 mm)

## 4. Hydraulic Domain Rules

### Australian Standards (always enforce)

| Standard | What | Threshold |
|----------|------|-----------|
| WSAA WSA 03-2011 | Min service pressure | 20 m head |
| WSAA WSA 03-2011 | Max service pressure | 50 m head (residential) |
| WSAA WSA 03-2011 | Max pipe velocity | 2.0 m/s |
| WSAA WSA 03-2011 | Fire flow residual | 12 m head at 25 LPS |
| Mining/industrial | Max pressure override | 120 m — document when used |
| AS 2280 | Ductile iron pipe | PN25/PN35, C=120-140 |
| AS/NZS 1477 | PVC pipe | PN12/PN18, C=145-150 |
| AS/NZS 4130 | PE/HDPE pipe | SDR11 PN16, C=140-150 |
| AS 4058 | Concrete pipe | PN25-PN35, C=90-120 |

### Encoded constraints (permanent — derived from resolved bugs)

- **Steady-state pressure compliance:** gauge pressure only — never total head
- **Transient compliance:** subtract junction elevation before comparing to PN rating
- **Slurry laminar friction factor:** Darcy (64/Re_B), NEVER Fanning (16/Re_B)
- **Buckingham-Reiner guard:** `max(f_BP, 64/Re_B)` — higher value is the floor
- **PVC pipe OD:** use AS/NZS 1477 OD series — OD is never equal to DN
  Correct values: DN100->110, DN150->160, DN200->225, DN250->280, DN300->315, DN375->400
- **PE100 short-term design yield:** 20-22 MPa per AS/NZS 4130 (not 10 MPa)
- **Concrete HW-C by size:** DN375/450->C=110, DN600/750->C=100, DN900->C=90
- **DI wave speed lower bound:** 1100 m/s minimum for all sizes
- **Velocity on reversing pipes:** `abs(flow).max()` — never signed `flow.max()`
- **Zero-diameter guard:** always check area > 0 before computing velocity
- **Joukowsky:** use actual fluid density — never hardcode 1000 kg/m³ for slurry
- **Water age stagnation:** WNTR returns seconds, threshold is in hours — `age_hours = wntr_value / 3600`, then compare to 24.0
- **Slurry settling check:** flag pipes with velocity == 0 as highest risk, not just pipes with velocity > 0

## 5. GodMode Orchestration Rules

### Autonomous work policy
- Task is unambiguous and reversible -> proceed without asking
- Task modifies a calculation formula -> run relevant benchmark before AND after, confirm PASS, then proceed
- Task touches `au_pipes.py` -> run `scripts/validate_pipe_db.py` before AND after, confirm no regressions
- Uncertain about a standard value -> check AS/NZS source, document reference in a code comment before writing the value
- Two agents disagree on a finding that affects a calculation -> stop and surface to the human

### Automated Review Loop

After completing any phase, feature, or significant fix:

1. Check bridge: `curl -s localhost:7771/health`
2. If not running: `scripts\start_review_loop.bat`
3. Collect summary of what was built (files, test counts, key decisions)
4. Submit:
   ```
   python scripts/submit_for_review.py ^
     --output "[summary]" ^
     --context "[task name]" ^
     --question "[what to assess]"
   ```
5. Read `docs/review_loop/next_instructions.md`
6. `can_continue: true` -> proceed to next task
7. `can_continue: false` -> fix issues, resubmit, do not proceed

### Sub-Agent Routing Rules

**Agents** (defined in `.claude/agents/`):

| Agent | Model | Tools | Trigger |
|-------|-------|-------|---------|
| `architect` | opus | read-only | Module structure changes, new files, import changes |
| `code-reviewer` | sonnet | read-only | Any Python code change in core calculation files |
| `ui-reviewer` | sonnet | read-only | Changes to `desktop/`, user-facing strings, error messages |
| `hydraulic-tester` | sonnet | read + bash | Changes to solver code, formulas, compliance thresholds |
| `data-validator` | sonnet | read + bash | Changes to `data/au_pipes.py`, `data/pump_curves.py` |
| `feedback-synthesizer` | sonnet | read-only | After any review cycle completes |

**Routing logic:**
- Editing `epanet_api.py` -> triggers `code-reviewer` + `hydraulic-tester`
- Editing `slurry_solver.py` or `pipe_stress.py` -> triggers `code-reviewer` + `hydraulic-tester`
- Editing `desktop/**/*.py` -> triggers `ui-reviewer`
- Editing `data/*.py` -> triggers `data-validator`
- Adding/removing/moving files -> triggers `architect`
- Running `/review-cycle` -> triggers all agents in sequence, then synthesizer

**Parallel dispatch** (independent, no shared state):
- `code-reviewer` + `data-validator`
- `ui-reviewer` + `hydraulic-tester`

**Sequential dispatch** (strict order):
```
architect
  -> (code-reviewer + data-validator)
    -> (ui-reviewer + hydraulic-tester)
      -> feedback-synthesizer
```

**Never parallelize:**
- Any two tasks that write to the same file
- `au_pipes.py` schema changes with any other task
- `epanet_api.py` edits while any agent is reading `epanet_api.py`

**Review output location:** `docs/reviews/{YYYY-MM-DD}/`

### Self-review gate (mandatory before marking any phase complete)
1. Run `/review-cycle`
2. BLOCKER findings exist -> fix all, run `/review-cycle` again
3. HIGH findings exist -> fix all, or document deferral reason in `docs/decisions/{date}.md`
4. Write phase summary to `docs/progress.md`
5. Commit to git: "Phase X complete — N blockers fixed, N high fixed"
6. Push to remote: `git push origin master`

### Decision logging (every non-trivial decision)
Write to `docs/decisions/{YYYY-MM-DD}.md`:
- What was decided
- Why (alternatives considered)
- Standard or reference that supports it
- What would need to change if this decision is reversed

### Stop and surface to human when
- A benchmark FAILs after a fix (regression introduced)
- A standard value cannot be confirmed from available sources
- Any change would modify the `.inp` file format or the `HydraulicAPI` public interface

## 6. Code Conventions

- Every hydraulic formula must cite its source:
  `# Darcy-Weisbach: hL = f*(L/D)*(V^2/2g) — ref: White, Fluid Mechanics 8th ed.`
- Unit conversions must be explicit with a comment:
  `# convert LPS to m³/s`
  `Q_m3s = Q_lps / 1000`
- No magic numbers without a named constant:
  `WSAA_MIN_PRESSURE_M = 20.0  # WSAA WSA 03-2011 Table 3.1`
- Division: always guard zero denominators in hydraulic calculations
- Physical bounds in steady-state: pressure >= 0, velocity >= 0
- Error messages to users must never expose Python tracebacks
- Compliance checks must reference the specific standard (e.g., "WSAA WSA 03-2011 minimum 20 m" not "below threshold")

## 7. Known Deferred Items (do not re-flag in reviews)

- TSNet pump transient tests are xfail — known solver limitation, not a bug
- `server.py` (FastAPI) is legacy — review shallowly, do not refactor
- `epanet_api.py` size (~1200 lines) is an accepted tradeoff — flag only if a new responsibility is added, not for its current size
- `pipe_stress.py` is implemented but wired to UI in Phase 5
- EPyT is in requirements but unused — legacy dependency
- WNTR 1.4.0 `base_demand` is read-only — use `demand_timeseries_list[0].base_value`
- `app/` (NiceGUI) is legacy reference — superseded by `desktop/` (PyQt6)

## 8. File and Path Conventions

| Path | Purpose |
|------|---------|
| `desktop/` | PyQt6 application (new UI layer) |
| `app/` | NiceGUI dashboard (legacy reference) |
| `epanet_api.py` | Core API |
| `slurry_solver.py` | Slurry rheology solver |
| `pipe_stress.py` | Pipe stress calculations |
| `data/` | Australian pipe and pump databases |
| `reports/` | DOCX and PDF report generators |
| `importers/` | CSV, DXF, shapefile importers |
| `models/` | Example `.inp` network files |
| `tests/` | Test suite |
| `scripts/` | Validation and utility scripts |
| `docs/reviews/{YYYY-MM-DD}/` | Review cycle outputs |
| `docs/decisions/{YYYY-MM-DD}.md` | Decision log |
| `docs/progress.md` | Phase progress tracking |
| `docs/blockers.md` | Active blockers |
| `docs/audit/{YYYY-MM-DD}/` | Analysis audit trail |

## Running the Project

```bash
python main_app.py              # PyQt6 desktop application
python -m pytest tests/ -v      # Test suite
python scripts/validate_pipe_db.py  # Pipe database validation
```

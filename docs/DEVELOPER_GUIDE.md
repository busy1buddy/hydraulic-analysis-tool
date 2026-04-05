# Developer Guide

This guide is for contributors adding new features to the Hydraulic
Analysis Toolkit. Read `CLAUDE.md` first — it defines the architecture
rules, unit conventions, and hydraulic constraints that every change
must respect.

---

## 1. Architecture overview

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 6 — Importers: importers/                             │
│  Produce .inp files, never run simulations                   │
├──────────────────────────────────────────────────────────────┤
│  Layer 5 — Output: reports/, desktop/*_dialog.py             │
│  Read plain dicts, produce DOCX/PDF/JSON                     │
├──────────────────────────────────────────────────────────────┤
│  Layer 4 — UI: desktop/                                      │
│  PyQt6 — imports API only, never solvers directly            │
├──────────────────────────────────────────────────────────────┤
│  Layer 3 — Domain: slurry_solver.py, pipe_stress.py, data/   │
├──────────────────────────────────────────────────────────────┤
│  Layer 2 — API: epanet_api/ (12-mixin package)               │
│  Single orchestration point for all analysis                 │
├──────────────────────────────────────────────────────────────┤
│  Layer 1 — Solvers: wntr, tsnet                              │
│  Never import directly from UI or reports                    │
└──────────────────────────────────────────────────────────────┘
```

**Iron rules** (from `CLAUDE.md`):

- No layer may import from a layer above it.
- `desktop/` must never `import wntr` or `import tsnet`.
- All network mutations go through `HydraulicAPI` methods — never
  mutate `api.wn` from outside the API package.
- Report generators receive plain dicts, never raw WNTR result objects.

---

## 2. Package structure

```
epanet_api/
  __init__.py        # HydraulicAPI class, 12 mixins composed here
  core.py            # CoreMixin — load, create, CRUD, summary
  analysis.py        # AnalysisMixin — steady-state, EPS, WQ, fire flow
  slurry.py          # SlurryMixin — slurry_design_report
  compliance.py      # ComplianceMixin — WSAA checks, thresholds
  assets.py          # AssetsMixin — rehab, deterioration, Lamont
  topology.py        # TopologyMixin — skeletonise, analyse_topology
  resilience.py      # ResilienceMixin — Todini, reliability, water security
  calibration.py     # CalibrationMixin — auto-calibrate, Monte Carlo
  forecasting.py     # ForecastingMixin — demand, climate
  surge.py           # SurgeMixin — Joukowsky, surge mitigation
  comparison.py      # ComparisonMixin — scenario diff, portfolio
  advanced.py        # AdvancedMixin — everything else (zones, patterns,
                     #   KB, sensitivity, safety case, root cause, etc.)
```

Composition is:

```python
class HydraulicAPI(CoreMixin, AnalysisMixin, SlurryMixin, ComplianceMixin,
                   AssetsMixin, AdvancedMixin, TopologyMixin, ResilienceMixin,
                   CalibrationMixin, ForecastingMixin, SurgeMixin,
                   ComparisonMixin):
    ...
```

Method-resolution order means earlier mixins win on conflicts. Keep
each mixin focused on one domain.

---

## 3. How to add a new analysis feature

### Steps

1. **Pick the right mixin.** If it doesn't fit, add to `AdvancedMixin`.
2. **Write a public method** with:
   - A docstring (parameters, return shape, references).
   - `if self.wn is None: return {'error': 'No network loaded. Fix: ...'}`
     as the first line.
   - A structured `dict` return (never `None`).
   - Every formula commented with its source
     (e.g. `# Hazen-Williams: hL = 10.67*L*Q^1.852/(C^1.852*D^4.87) — WSAA WSA 03-2011`).
3. **Respect unit conventions** (`CLAUDE.md` §3). Convert at boundaries.
4. **Never hardcode magic numbers** — use named constants or the
   class-level `DEFAULTS` dict.
5. **Add tests** in `tests/test_<mixin>.py`:
   - `test_no_network_error` asserts `'error' in result` and `'Fix:' in result['error']`.
   - Happy-path tests on the demo network or a small synthetic one.
   - Assumption-documentation tests — every result dict with numeric
     outputs must carry an `assumptions` or `reference` field.

### Example skeleton

```python
def my_new_analysis(self, some_param=1.0):
    """
    Short description.

    Parameters
    ----------
    some_param : float
        What it does, units.

    Returns dict with keys 'x', 'y', 'assumptions'.
    Ref: Author (Year), Journal.
    """
    if self.wn is None:
        return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

    # ... analysis ...

    return {
        'x': 1.0,
        'y': 2.0,
        'assumptions': {
            'method': 'Name',
            'limitations': 'Describe limits.',
        },
        'reference': 'Author (Year)',
    }
```

---

## 4. How to add a new UI dialog

1. **Create `desktop/my_feature_dialog.py`** subclassing `QDialog`.
2. **Accept `api` as the first constructor argument** — never call
   solvers directly.
3. **Add a yellow warning banner** if the output has legal/regulatory
   implications.
4. **Tooltip every input widget** (Q2 enforced by
   `tests/test_ui_polish.py`).
5. **Wire to a menu** in `desktop/main_window.py`. Add a handler
   method `_on_my_feature`.
6. **Write smoke tests** in `tests/test_r_ui.py`-style module:
   - Dialog constructs without crash (use `QT_QPA_PLATFORM=offscreen`).
   - Running the underlying API call from the dialog produces a
     non-empty result.
   - Escape closes the dialog.

---

## 5. How to add a new tutorial network

1. **Create `tutorials/my_network/`** with:
   - `network.inp` — built via `HydraulicAPI.create_network()` and
     `api.write_inp()`, not hand-written.
   - `README.md` — layout diagram, deliberate flaws (if demo), expected
     metrics, suggested analysis steps.
2. **Add to `TUTORIAL_NETWORKS` list** in
   `tests/test_regression.py` so the network gets baselined.
3. **Run** `python tests/test_regression.py --update` to capture the
   baseline metrics.
4. If the network is used in the demo flow, also reference it from
   `docs/DEMO_SCRIPT.md`.

---

## 6. Running tests

```bash
# All tests except unstable TSNet transients:
python -m pytest tests/ -k "not transient" -q

# Specific module:
python -m pytest tests/test_safety_case.py -v

# Specific test:
python -m pytest tests/test_t_series.py::TestPumpEfficiency::test_summary_aggregates

# Rebuild regression baselines after an intentional calculation change:
python tests/test_regression.py --update
```

CI runs on `push: master` and PRs via `.github/workflows/tests.yml`
with pip caching and `-k "not transient"`.

---

## 7. Building the installer

```bash
# Windows:
pyinstaller hydraulic_tool.spec

# Outputs:
#   dist/HydraulicTool.exe
#   dist/HydraulicTool/ (onedir mode)
```

When adding new modules or data files, update `hydraulic_tool.spec`:

- New `desktop/*.py` modules get auto-picked up via hidden imports
  if they're imported from `main_window.py`, but always double-check.
- New tutorial networks: add to the `datas` tuple in the spec file.
- New data files in `data/`: ditto.

Always test the built exe against a fresh network to confirm
nothing was missed.

---

## 8. Coding standards

- **Units in every displayed value** — no bare floats in `desktop/`
  or `reports/`.
- **Comment every formula with its source** — cite the text or
  standard.
- **Pressure display:** 1 decimal place ("30.2 m").
- **Velocity display:** 2 decimal places ("1.45 m/s").
- **Pipe diameter display:** integer mm ("300 mm", never "300.0 mm").
- **Error messages to users** must include `Fix:` actionable guidance
  and never expose Python tracebacks.
- **Compliance messages** must cite the specific standard — "WSAA WSA
  03-2011 minimum 20 m" not "below threshold".
- **Formulas that are hydraulic domain rules** (encoded constraints
  in `CLAUDE.md` §4): follow them without exception.
- **Don't use destructive git operations** without checking with the
  user first.

---

## 9. Review loop

The `scripts/start_review_loop.bat` script runs a bridge that accepts
review submissions via `scripts/submit_for_review.py`. After completing
a feature or phase, submit a summary and any BLOCKER/HIGH findings
must be addressed before shipping.

See `CLAUDE.md` §5 "GodMode Orchestration Rules" for the full workflow.

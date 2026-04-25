---
name: pyqt-architect
description: Use when editing any file under desktop/, adding a new QDialog or QWidget, wiring a menu action, or threading a long-running operation. The skill carries the layer-purity rules, the AnalysisWorker QThread pattern, the unit-display conventions, and the five natural seams for the future main_window.py decomposition. Trigger words: "new dialog", "QThread", "freezes the UI", "AnalysisWorker", "main window is too big", "QMessageBox", "where should this UI live".
---

# PyQt6 UI Architect

## Overview

This skill encodes the **structural rules** for the desktop/ UI layer. Use it when writing or reviewing any PyQt6 code in this project. The skill answers four recurring questions:

1. *Where should this code live?* — Layer-4 (desktop/) is the UI. Solver code, formulas, and `wntr`/`tsnet` imports do not belong here.
2. *Should this run on a thread?* — Anything that calls a solver must run on `desktop/analysis_worker.py:AnalysisWorker`, never on the GUI thread.
3. *What do values look like to the user?* — Pressure 1 dp, velocity 2 dp, DN integer mm, every value carries a unit suffix.
4. *Where do I split `main_window.py`?* — Five natural seams documented below.

## Layer-4 Purity Checklist

Forbidden imports inside `desktop/`:

```
import wntr
import tsnet
from epanet_api.slurry_solver import ...
from epanet_api.pipe_stress import ...
```

Forbidden patterns inside `desktop/`:

```python
api.wn.options.time.duration = ...        # mutate via api.set_simulation_options(...)
api.wn.add_pipe(...)                       # mutate via HydraulicAPI methods
api.wn.options.quality.parameter = "AGE"   # mutate via api.set_water_quality_mode(...)
results = api.run_steady_state(...)        # call from a slot — must dispatch to AnalysisWorker
results = api.run_transient(...)           # same
results = api.run_water_quality_analysis() # same
```

Read access to `api.wn` (e.g. `api.wn.junction_name_list`, `api.wn.get_link(name)`) is allowed.

## QThread / AnalysisWorker Pattern

The single approved pattern for long-running solver calls:

```python
# desktop/some_dialog.py or main_window.py slot
from desktop.analysis_worker import AnalysisWorker

def _on_run_my_analysis(self):
    if self.api.wn is None:
        QMessageBox.warning(self, "No Network",
            "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
        return

    self.status_bar.showMessage("Running my analysis...")
    self.progress_bar.setVisible(True)

    self._worker = AnalysisWorker(self.api, analysis_type='steady', params={...})
    self._worker.progress.connect(self.progress_bar.setValue)
    self._worker.finished.connect(self._on_my_analysis_done)
    self._worker.error.connect(self._on_my_analysis_error)
    self._worker.start()
```

Three known sites that need to migrate to this pattern (recommendation #1 in the active plan):

- `desktop/main_window.py:1634` — `_on_run_all_scenarios` calls `api.run_steady_state` in a for-loop
- `desktop/main_window.py:2326` — `_on_demo` calls `api.run_steady_state` synchronously
- `desktop/main_window.py:2818` — `_on_quality_review` calls a 48 h `run_water_quality_analysis` synchronously

`AnalysisWorker` already exists; extend it if a new analysis type is needed (do not write a parallel worker class).

## Unit Display Rules

| Quantity | Internal | Display | Decimals | Suffix |
|---|---|---|---|---|
| Pressure | m head | m head | 1 | "m" |
| Pressure (stress) | m head | kPa | 0 | "kPa" |
| Velocity | m/s | m/s | 2 | "m/s" |
| Flow | m³/s (WNTR) | LPS | 1-2 | "LPS" or "L/s" |
| Pipe diameter | m (WNTR) | DN mm | 0 (integer) | "mm" |
| Pipe length | m | m | 0-1 | "m" |
| Stress | MPa | MPa | 1 | "MPa" |
| Water age | seconds (WNTR) | hours | 1 | "h" |
| Wave speed | m/s | m/s | 0 | "m/s" |

**No bare floats.** Every value shown to the user must carry its unit. Use the converters in `desktop/units.py`.

## Compliance Messaging

Every warning cites a specific standard:

- "WSAA WSA 03-2011 minimum 20 m exceeded — junction J5 at 18.2 m"  ✓
- "Low pressure"  ✗
- "Velocity 2.34 m/s exceeds WSAA max 2.0 m/s — pipe P17"  ✓
- "Velocity high"  ✗
- "Exceeds PN35 rating of 3500 kPa — pipe DI-300 at 3812 kPa"  ✓
- "Pipe over-pressurised"  ✗

Colour rules: green PASS, amber WARNING, red CRITICAL. Never red-only — accessibility.

## Error Handling Rules

- Catch with `except Exception as e:`, never bare `except:`
- Surface to user via `QMessageBox.warning/critical` or `desktop/crash_dialog.py:CrashDialog`
- Never let a Python traceback land in a slot's stdout
- Add `if self.api.wn is None:` guards on every menu slot — the canonical message is `"No network loaded. Use File > Open (Ctrl+O) to load an .inp file."`

## main_window.py Decomposition (deferred — design only)

`main_window.py` is ~3,000 LOC with ~80 `_on_*` slots. Splitting now would touch every UI test at once, so it is **deferred to a future multi-PR effort** (Phase 6 in the active plan). When it does land, these are the seams:

| New module | Owns | Approx slots |
|---|---|---|
| `desktop/analysis_dispatch.py` | All `_on_run_*` / `_on_*_analysis` slots; threading orchestration | ~20 |
| `desktop/tools_launcher.py` | Calibration / fire-flow / topology / diagnostics / LCC / safety-case / asset-mgmt openers | ~15 |
| `desktop/results_controller.py` | Node/pipe table population, animation, EPS frame selection, WSAA badges | ~15 |
| `desktop/edit_controller.py` | Canvas editor integration, undo/redo, Ctrl+Z/Y wiring | ~10 |
| (extend) `desktop/scenario_panel.py` | Scenario CRUD/run-all (already partially split) | ~10 |

When proposing a UI change, place new code in the future-target module **if it already exists**. Otherwise, add it to `main_window.py` for now and tag the slot with `# TODO: belongs in <future-module>` so the eventual split is mechanical.

## Bundled Resources

- `references/ui_conventions.md` — extended unit/decimal/colour rules and dialog templates

## When NOT to use this skill

- Pure data/data-structure questions about the network model (use `hydraulic-sme`)
- Solver formula questions (use `hydraulic-sme`)
- Build / packaging / PyInstaller (use the spec at `hydraulic_tool.spec`)
- The legacy NiceGUI `app/` — that layer is reference-only; do not edit it

# Architectural Review -- 2026-04-03

## Summary

The EPANET toolkit has a well-structured 5-layer architecture with clean separation between solvers, core API, domain modules, UI, and reports. Two layer violations exist: `network_editor.py` directly imports `wntr` and directly mutates `api.wn`, and `scenario_manager.py` imports both `wntr` and `epanet_api`, creating upward coupling. The data flow pattern (solver -> API -> dict -> consumer) is consistently followed elsewhere, and the codebase is in good shape for a project of this scope.

## Blockers (must fix)

### B1: UI page directly imports wntr (layer violation)

`app/pages/network_editor.py:14` has `import wntr`. The UI layer must not import solver modules directly. This import is used at line 285 (`wntr.network.write_inpfile`) for saving networks. This should be wrapped as an API method (e.g., `api.save_network(filename)`).

### B2: Network editor directly mutates api.wn (bypasses HydraulicAPI)

`app/pages/network_editor.py` directly manipulates the WNTR network object in multiple places:
- Line 172-174: `node.elevation = ...`, `node.demand_timeseries_list[0].base_value = ...`
- Line 210: `node.base_head = ...`
- Line 196-198: `pipe.length = ...`, `pipe.diameter = ...`, `pipe.roughness = ...`
- Line 221-225: `api.wn.add_junction(...)` directly
- Line 238-244: `api.wn.add_pipe(...)` directly
- Line 263: `api.wn.remove_node(elem)` directly
- Line 265: `api.wn.remove_link(elem)` directly

All of these should be wrapped as HydraulicAPI methods to maintain the single-orchestration-point pattern.

### B3: scenario_manager.py imports both wntr and epanet_api (tight coupling + layer confusion)

`scenario_manager.py:13-15` imports both `wntr` and `from epanet_api import HydraulicAPI`. It directly calls `wntr.network.write_inpfile()` at line 93. The ScenarioManager should either be part of the API layer or use HydraulicAPI exclusively without touching wntr directly.

## Warnings (should fix)

### W1: Steady-state results accessed directly in UI pages

`app/pages/steady_state.py:115-116` accesses `api.steady_results` (the raw WNTR SimulationResults object) to extract time-series data for Plotly charts. This bypasses the dict-based data flow. Similarly, `app/pages/view_3d.py:438-440` accesses `api.steady_results` for EPS animation. The API should return time-series data as part of the results dict (as `server.py` already does at lines 186-199).

### W2: Transient page accesses api.tm directly

`app/pages/transient.py:89-97` accesses `api.tm` (the raw TSNet TransientModel) to extract head time-series for charts. This raw solver object should not leak into the UI. The API should include time-series in the returned dict.

### W3: View 3D page accesses api.wn for element properties (read-only)

`app/pages/view_3d.py:687-770` reads element properties from `api.wn` directly for the selection panel. While read-only and not a hard violation, it creates coupling between the UI and WNTR's data model. Consider adding `api.get_element_properties(id)` to the API.

### W4: server.py has a module-level api singleton

`server.py:37` creates `api = HydraulicAPI(WORK_DIR)` at module level. Each route then creates `api_instance = HydraulicAPI(WORK_DIR)` locally (lines 126, 181, 213, etc.), which means the module-level singleton is unused except for the `api` variable name. The singleton pattern is inconsistent -- either use it everywhere or remove it.

### W5: Shared state (api.wn, api.steady_results, api.tm) is not thread-safe

The shared `api` instance in `app/main.py:23` holds mutable state (`wn`, `steady_results`, `tm`). If two browser tabs trigger concurrent analyses, one will overwrite the other's state. For single-user desktop use this is acceptable, but it blocks cloud deployment.

### W6: Duplicated helper functions in report modules

`reports/pdf_report.py:426-464` duplicates `_collect_compliance()` and `_build_conclusions()` from `reports/docx_report.py:414-463`. These should be extracted to a shared `reports/_helpers.py` module.

### W7: importers use wntr directly (expected but should be documented)

`importers/csv_import.py:13`, `importers/shapefile_import.py:49`, `importers/dxf_import.py:58` all import wntr. Per the architecture rules, importers "produce .inp files" and do not run simulations, which they correctly follow. However, they create and manipulate WNTR objects to build the network model before writing the .inp file. This is acceptable (no simulation is run), but it means importers depend on wntr as a library, not as a solver.

### W8: network_plot.py component receives wn object directly

`app/components/network_plot.py:7` `create_network_figure(wn)` takes a WNTR WaterNetworkModel directly. The component should accept a data dict (node coordinates, link endpoints) to decouple from WNTR. Currently called from `steady_state.py:77`, `network_editor.py:142`.

## Observations (consider)

### O1: Root-level scripts that belong in a subdirectory

- `run_hydraulic_analysis.py` -- CLI runner, should be in `scripts/` or `examples/`
- `run_transient_analysis.py` -- CLI runner, should be in `scripts/` or `examples/`
- `validate_3d_enhancements.py` -- test/validation utility, should be in `tests/` or `scripts/`
- `capture_3d_ui.py` -- Playwright capture utility, should be in `tests/` or `scripts/`

### O2: Dead/unused code

- `server.py:37` module-level `api = HydraulicAPI(WORK_DIR)` is never used by any route (each route creates its own `api_instance`).
- `pipe_stress.py` is independently importable and well-structured, but is not imported by any other module in the project (only by tests). It appears to be feature-complete but not yet integrated into the UI or API.

### O3: epanet_api.py natural split points

At ~1200 lines, `epanet_api.py` is manageable but approaching the point where splitting would aid maintainability. Natural split points:
1. **Network creation/management** (lines 60-173): `create_network`, `load_network`, `get_network_summary`, `list_networks` -> `api/network.py`
2. **Steady-state + fire flow + water quality** (lines 178-564): -> `api/steady.py`
3. **Transient + pump transient** (lines 569-1015): -> `api/transient.py`
4. **Report generation** (lines 1021-1137): -> `api/reporting.py`
5. **Joukowsky + utilities** (lines 1139-1199): -> `api/utils.py`

All methods share `self.wn`, `self.tm`, `self.steady_results` state, so the split would require a shared state container or base class.

### O4: Cloud deployment barriers

If the API were run in a separate process:
- `api.wn` and `api.steady_results` hold large in-memory objects that cannot be serialized cheaply
- `api.tm` (TSNet TransientModel) holds simulation state in numpy arrays
- File paths are hardcoded to local filesystem (`self.model_dir`, `self.output_dir`)
- The NiceGUI dashboard accesses `api.wn` directly (see B2, W1, W2, W3)

For cloud deployment, the API would need to serialize results to a database/cache and the UI would need to consume only dicts via HTTP.

### O5: slurry_solver.py imports wntr inside function (acceptable)

`slurry_solver.py:339` has `import wntr` inside `analyze_slurry_network()`. This keeps the module independently importable for the pure headloss functions while allowing the network analysis function to use wntr. This is a good pattern.

### O6: `__init__.py` files

- `data/__init__.py` -- useful, re-exports public API from `au_pipes.py`
- `reports/__init__.py` -- useful, re-exports generators
- `importers/__init__.py` -- partially useful, only imports `csv_import` (missing shapefile/dxf)
- `app/__init__.py` -- empty, serves as package marker (fine)
- `app/pages/__init__.py` -- empty, serves as package marker (fine)
- `app/components/__init__.py` -- empty, serves as package marker (fine)
- `tests/__init__.py` -- empty, serves as package marker (fine)

## Checklist Results

### Module Boundaries

| # | Item | Status | Reference |
|---|------|--------|-----------|
| 1 | UI pages access data only through HydraulicAPI or its returned dicts | **FAIL** | `app/pages/network_editor.py:14,162-265` -- directly imports wntr, directly mutates `api.wn` |
| 2 | No circular imports between any modules | **PASS** | Import graph is acyclic: solvers <- epanet_api <- app, data standalone, reports standalone, importers standalone. `scenario_manager` imports `epanet_api` (one-way). |
| 3 | slurry_solver.py and pipe_stress.py are independently importable | **PASS** | `slurry_solver.py` imports only `math`, `numpy` at module level (wntr is function-scoped). `pipe_stress.py` imports only `math`. |
| 4 | data/au_pipes.py and data/pump_curves.py contain no simulation logic | **PASS** | `au_pipes.py` is pure data + lookup functions. `pump_curves.py` has hydraulic formulas (Hazen-Williams in `generate_system_curve`) but no simulation calls -- this is domain math, not simulation logic. |
| 5 | reports/*.py receive dicts, never call simulation methods | **PASS** | Both `docx_report.py` and `pdf_report.py` accept `results` and `network_summary` dicts. No wntr/tsnet imports. |
| 6 | importers/*.py produce .inp files, never call simulation methods | **PASS** | All three importers build WNTR network objects and call `write_inpfile()` but never call `EpanetSimulator` or any simulation method. |

### Data Flow

| # | Item | Status | Reference |
|---|------|--------|-----------|
| 7 | All analysis results flow: solver -> API -> dict -> consumer | **WARN** | Mostly followed. Exceptions: `steady_state.py:115` and `transient.py:89` access raw solver result objects on the API instance for time-series charting. |
| 8 | No result data stored in global/module-level variables (except api.wn and api.steady_results) | **WARN** | `server.py:37` has unused module-level `api` instance. `scenario_manager.py` stores results in `self.scenarios[name]['results']` which is instance state (acceptable). |
| 9 | File I/O confined to API layer and reports -- UI pages don't write files directly | **WARN** | `app/pages/network_editor.py:285` writes .inp files via `wntr.network.write_inpfile()`. `app/pages/feedback.py:23-24` writes `feedback.json` to `output/`. The feedback file write is a UI concern (not analysis data) so it is borderline acceptable, but the network save is a clear violation. |

### Coupling Assessment

| # | Item | Status | Reference |
|---|------|--------|-----------|
| 10 | Count direct imports of wntr outside epanet_api.py and slurry_solver.py | **FAIL** | 5 additional locations: `app/pages/network_editor.py:14`, `importers/csv_import.py:13`, `importers/shapefile_import.py:49`, `importers/dxf_import.py:58`, `scenario_manager.py:13`. The importers are acceptable (they produce .inp files). The UI import and scenario_manager are violations. |
| 11 | scene_3d.py accesses wn directly or through API | **PASS** | `app/components/scene_3d.py` receives `wn` as a parameter from the calling page (`view_3d.py`), not by importing it. The component itself does not import wntr. `network_plot.py` follows the same pattern. This is acceptable component design but creates indirect coupling. |
| 12 | Any page directly mutates api.wn | **FAIL** | `app/pages/network_editor.py` mutates api.wn extensively (lines 162-265): modifying element properties, adding/removing nodes and pipes. This is by design for the editor but violates the single-orchestration-point pattern. |

### Scalability Readiness

| # | Item | Status | Reference |
|---|------|--------|-----------|
| 13 | Could epanet_api.py be split without breaking consumers? | **WARN** | Yes, with effort. Natural split points identified (see O3). The shared state (`self.wn`, `self.steady_results`, `self.tm`) would need a shared container. All consumers currently import only `HydraulicAPI`, so a facade class could maintain backward compatibility. |
| 14 | Features that would break if API were in a separate process | **FAIL** | UI pages access `api.wn`, `api.steady_results`, `api.tm` directly (in-process objects). The network editor mutates `api.wn`. `app/components/network_plot.py` and `scene_3d.py` traverse the wn object graph. All of these would break with a process boundary. |
| 15 | State management safe for concurrent requests | **FAIL** | `app/main.py:23` creates a single shared `HydraulicAPI` instance. Concurrent analysis requests would race on `api.wn`, `api.steady_results`, `api.tm`. No locking or request isolation exists. Acceptable for single-user desktop deployment only. |

### File Organisation

| # | Item | Status | Reference |
|---|------|--------|-----------|
| 16 | Files in project root that belong in a subdirectory | **WARN** | 4 scripts: `run_hydraulic_analysis.py`, `run_transient_analysis.py`, `validate_3d_enhancements.py`, `capture_3d_ui.py`. These are CLI runners and utilities that should be in `scripts/` or `examples/`. |
| 17 | Dead files (imported nowhere, tested nowhere) | **WARN** | `pipe_stress.py` is tested (`test_pipe_stress.py`) but not imported by any production code. It is feature-complete standalone code awaiting UI integration. `validate_3d_enhancements.py` and `capture_3d_ui.py` are one-off utilities. |
| 18 | All __init__.py files serve a purpose | **PASS** | `data/__init__.py` and `reports/__init__.py` re-export public APIs. `importers/__init__.py` partially re-exports (only csv_import). The empty `__init__.py` files in `app/`, `app/pages/`, `app/components/`, `tests/` serve as package markers. |

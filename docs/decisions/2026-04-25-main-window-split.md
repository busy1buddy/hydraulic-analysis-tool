# `desktop/main_window.py` Decomposition — Design Note

**Date:** 2026-04-25
**Status:** **Design only — no code movement in this phase.** Execution deferred to a future multi-PR effort.
**Owner:** Architect (per the multi-agent review plan, Phase 6).

## Why this is design-only

`desktop/main_window.py` is currently ≈3,000 LOC with ≈80 `_on_*` slot methods. Splitting it has long been on the table (HANDOVER.md flags it; CLAUDE.md §7 deferred items list now records it explicitly). It was deliberately kept as a single PR-sized seam in the multi-agent review plan because:

1. The class has good test coverage at the system level (Centurion stress, UI freeze, canvas state, results table tests). A single-PR rename storm would touch every UI test.
2. Phase 2 of the active plan removed the cross-layer violations (5 wntr/tsnet/api.wn.options leaks) and rerouted the 3 sync solver paths through `AnalysisWorker`. The class is now structurally cleaner, which makes a future split safer.
3. The 5 seams below are stable. Even without the split, contributors can place new code in the *intended* future module today (and tag it with `# TODO: belongs in <module>`), so the eventual extraction is mechanical rather than judgment-heavy.

## Five target modules (the seams)

The 80+ slots cluster naturally into 5 responsibility groups. Each row lists the slots the destination module owns; everything else stays in `MainWindow`.

### 1. `desktop/analysis_dispatch.py` — runs the solvers

Owns every slot that triggers a hydraulic/transient/EPS/quality solver and the worker plumbing that feeds them.

- `_on_run_steady`, `_on_run_transient`, `_on_run_eps`, `_on_run_quality`,
  `_on_run_demo`, `_on_run_lcc`, `_on_run_tutorial`,
  `_on_run_all_scenarios`, `_on_scenarios_batch_done`,
  `_on_quality_done`, `_on_analysis_started`, `_on_analysis_progress`,
  `_on_analysis_finished`, `_on_analysis_error`,
  `_on_design_compliance_check`, `_on_quick_assessment`, `_on_safety_case`,
  `_on_water_quality_age`, `_on_water_quality_chlorine`,
  `_on_water_quality_trace`, `_on_water_quality_config`,
  `_on_quality_review`

Outbound dependencies from `MainWindow`: progress bar, status bar, results-table populators (which live in module 3 below).

### 2. `desktop/tools_launcher.py` — opens dialogs

Owns the menu actions that simply construct and `exec()` a dialog or open a panel. No hydraulic logic; the launched dialogs already encapsulate it.

- `_on_calibration`, `_on_calibration_data`, `_on_calibration_residuals`,
  `_on_calibration_dashboard`, `_on_fire_flow`, `_on_diagnostics`,
  `_on_topology`, `_on_pressure_zones`, `_on_rehabilitation`,
  `_on_demand_patterns`, `_on_pump_energy`, `_on_pipe_profile`,
  `_on_sensitivity_analysis`, `_on_asset_management`, `_on_tco_dashboard`,
  `_on_validate_network`, `_on_apply_aging`, `_on_auto_place_bpts`,
  `_on_auto_place_booster_pumps`, `_on_health_check`,
  `_on_keyboard_shortcuts`, `_on_show_help`, `_on_about`,
  `_on_open_settings`, `_on_settings`, `_on_open_tutorial`,
  `_on_schedule_reports`

### 3. `desktop/results_controller.py` — populates result widgets

Owns the routines that take a `results` dict and push values into the node table, pipe table, dashboard, animation slider, etc.

- `_populate_node_results`, `_populate_pipe_results`,
  `_populate_eps_animation`, `_update_status_bar`,
  `_update_dashboard`, `_on_animation_frame`, `_on_results_table_context`

(These are largely already utility methods rather than slots; the move is a straight class extraction.)

### 4. `desktop/edit_controller.py` — canvas editing & undo

Owns canvas-edit-mode toggling and undo/redo stack interaction.

- `_on_edit_mode_toggled`, `_on_undo`, `_on_redo`,
  `_on_canvas_path_changed`, `_on_canvas_element_selected`,
  `_on_pump_selected_on_canvas`, `_on_probe_mode_toggled`,
  `_on_probe_requested`,
  `_on_slurry_toggle`, `_on_edit_slurry_params`,
  `_on_colourmap_changed`, `_on_values_toggled`,
  `_on_scale_pipes_toggled`, `_on_scale_nodes_toggled`,
  `_on_basemap_toggled`, `_on_3d_view`, `_on_split_screen`,
  `_on_reset_layout`

### 5. (extend) `desktop/scenario_panel.py` — scenarios

Already a separate module; absorb the few orchestration slots that currently live in `MainWindow`.

- `_on_scenario_selected`, `_apply_scenario_to_network`,
  `_apply_scenario_to_widgets`

(Note: `_on_run_all_scenarios` and `_on_scenarios_batch_done` belong in
**module 1** because they now dispatch through `AnalysisWorker`.)

## What stays in `MainWindow`

After extraction, `MainWindow` retains roughly:

- File I/O: `_on_new`, `_on_open_inp`, `_on_save`, `_on_save_as`,
  `_on_export_bundle`, `_on_import_bundle`, `_on_auto_save`, `_on_report_docx`,
  `_on_report_pdf`, `_on_report_templates`
- Menu/toolbar/dock construction
- Tree explorer interaction: `_on_tree_item_clicked`, `_populate_explorer`
- Session restore/save
- Drag-and-drop `.inp` handling
- Welcome dialog
- Wiring the five extracted modules together via signals

That keeps `MainWindow` focused on **window-level concerns** rather than feature dispatch — the right shape for a Qt main window.

## Migration order (when execution starts)

Each step is its own PR. Each step's gate is **the existing test suite plus
the layer-purity AST scanner**. A failure means the slot moved without its
state, or a forbidden import sneaked into the new module.

1. **Step 1 — `results_controller.py`** (lowest risk: pure data → widget
   population, no dialogs, no solvers). Establishes the migration pattern
   and lets later modules depend on its public interface.
2. **Step 2 — `tools_launcher.py`** (next-lowest: opens dialogs that already
   encapsulate their state).
3. **Step 3 — `edit_controller.py`** (touches canvas; medium risk).
4. **Step 4 — `analysis_dispatch.py`** (highest risk: owns the solver wiring).
5. **Step 5 — finish `scenario_panel.py` extraction** (small cleanup once
   step 4 has clarified the scenario/analysis boundary).

## Dependencies on other plan deliverables

- `tests/test_layer_purity.py` (already landed, Phase 2): every step must
  keep this green — no `import wntr` / `import tsnet` / `from
  epanet_api.slurry_solver` etc. in the new modules.
- `pyqt-architect` skill: documents the AnalysisWorker pattern and the
  unit-display rules that the extracted modules must keep using.
- `qa-engineer` skill: each step's gate is `python scripts/quality_gate.py`.

## What would need to change if this decision is reversed

If a future review concludes the split is more painful than valuable —
e.g. signal/slot wiring overhead becomes excessive — revert by:

1. Re-merging the modules into `MainWindow`, preserving slot signatures.
2. Removing the seam-cited `# TODO: belongs in <module>` comments.
3. Updating CLAUDE.md §7 to drop the deferred-item entry.

The five seams identified here are **mechanical groupings, not invented
abstractions**, so reversal is also mechanical.

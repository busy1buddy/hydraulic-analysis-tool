# UI Review — 2026-04-03

## Summary

The dashboard is well-structured and uses consistent dark-theme styling throughout. Most engineering values carry units, chart axes are labelled, and exceptions are generally caught and surfaced to the user via `ui.notify`. However, a cluster of precision and formatting issues in the transient and 3D-view panels could make results look amateurish, several compliance messages lack the specific standard citation required by the review checklist, and the DOCX/PDF reports pass raw float strings into tables without rounding.

---

## Critical (user gets wrong impression or no information)

### C1 — Transient page: raw floats displayed in compliance badges (no rounding)
**File:** `app/pages/transient.py`, lines 150–152

```python
ui.label(f'{name}: surge {surge}m ({d["surge_kPa"]} kPa), '
         f'max {d["max_head_m"]}m')
```

`surge`, `surge_kPa`, and `max_head_m` are raw numeric values from the results dict — they may carry 10+ decimal places (e.g. `"surge 47.382918273m"`). No `:.1f` or `:.0f` formatting is applied. This makes the compliance panel look like a debug dump rather than an engineering report.

### C2 — Transient metrics: raw floats in metric cards
**File:** `app/pages/transient.py`, lines 164–165

```python
update_metric(surge_label, str(surge_m), surge_color)
update_metric(surge_kpa_label, str(result['max_surge_kPa']), surge_color)
```

`str()` on a float produces arbitrary decimal places. The metric cards show values like `47.3829...`. Both should be formatted: `f'{surge_m:.1f}'` and `f'{result["max_surge_kPa"]:.0f}'`.

### C3 — Joukowsky: raw floats in result metric cards
**File:** `app/pages/joukowsky.py`, lines 86–87

```python
update_metric(head_label, str(result['head_rise_m']), COLORS['cyan'])
update_metric(pressure_label, str(result['pressure_rise_kPa']), COLORS['cyan'])
```

Same issue — `str()` on API floats. Should be `f'{result["head_rise_m"]:.1f}'` (metres of head, 1 dp) and `f'{result["pressure_rise_kPa"]:.0f}'` (kPa, whole number).

### C4 — Joukowsky: unit label "metres of head" is non-standard
**File:** `app/pages/joukowsky.py`, line 53

```python
head_label = metric_card('--', 'metres of head', 'Pressure Rise (dH)')
```

"metres of head" is verbose and inconsistent with every other pressure display in the application (all use "m"). Should be "m".

### C5 — 3D info panel: Tank diameter shown in metres, not mm
**File:** `app/pages/view_3d.py`, line 729

```python
ui.label(f'Diameter: {node.diameter} m').style(...)
```

`node.diameter` for tanks in WNTR is stored in metres (e.g. `1.5` for a 1500 mm tank). Showing "1.5 m" is misleading — tanks are sized in mm by convention. This should either convert to mm (`{node.diameter*1000:.0f} mm`) or state clearly it is the tank internal diameter in metres with context. Compare pipe diameter on line 742 which correctly converts: `{pipe.diameter*1000:.0f} mm`.

### C6 — Network topology hover: elevation lacks precision control
**File:** `app/components/network_plot.py`, line 75

```python
txt += f'<br>Elev: {node.elevation}m'
```

`node.elevation` is a raw float — hover text may show `Elev: 39.99999999999m`. Should be `f'{node.elevation:.1f}m'`.

### C7 — Network topology hover: head lacks precision control
**File:** `app/components/network_plot.py`, line 79

```python
txt += f'<br>Head: {node.base_head}m'
```

Same issue as C6 — raw float for reservoir head. Should be `f'{node.base_head:.1f}m'`.

### C8 — 3D element info: junction elevation and reservoir head are raw floats
**File:** `app/pages/view_3d.py`, lines 691, 716

```python
ui.label(f'Elevation: {node.elevation} m')   # line 691
ui.label(f'Head: {node.base_head} m')          # line 716
```

Both use unformatted floats. Should be `f'{node.elevation:.1f} m'` and `f'{node.base_head:.1f} m'`.

---

## High (unprofessional or confusing)

### H1 — Transient compliance: surge thresholds cite no standard
**File:** `app/pages/transient.py`, lines 140–152

The surge severity bands (`surge > 30` → HIGH, `surge > 15` → MOD) are hardcoded thresholds with no standard cited. The message labels read only "HIGH", "MOD", "OK" — an engineer cannot tell what standard these relate to. A WSAA or AS 2885 reference should appear in the badge or tooltip, e.g. `'HIGH — Exceeds PN35 threshold (WSAA)'`.

### H2 — Compliance component: messages pass through unfiltered with no standard citation guarantee
**File:** `app/components/compliance.py`, lines 43–44

```python
text = f'{element} {message}' if element else message
```

The component blindly renders whatever `message` string arrives from the API. There is no enforcement that messages cite a standard. If the upstream API produces generic strings like "Low pressure", the UI will display them. The component should at minimum not strip or alter messages, and a checklist note should be raised for the API to ensure WSAA citation is present (see also M1 in Medium section).

### H3 — Scenarios page: modification display is a raw dict repr
**File:** `app/pages/scenarios.py`, line 49

```python
ui.label(f'  + {mod}').style(...)
```

Displaying `+ {'type': 'pipe_diameter', 'target': 'P6', 'value': 250.0}` is developer-facing Python dict syntax. A user-facing string such as `+ Pipe P6: diameter → 250 mm` should be constructed.

### H4 — Scenarios page: "Value (mm/C-factor/multiplier)" label is confusing
**File:** `app/pages/scenarios.py`, line 38

```python
mod_value = ui.number('Value (mm/C-factor/multiplier)', value=250)
```

The field label combines three incompatible units. The expected unit depends on the selected `mod_type`. When `pipe_diameter` is selected the value is in mm; when `pipe_roughness` it is a Hazen-Williams C-factor (dimensionless); when `demand_factor` it is a multiplier. A user could enter 250 as a roughness C-value and not realize that is extremely high. The label should update dynamically when `mod_type` changes.

### H5 — Steady-state metrics: "LPS" used while charts use "LPS" — inconsistent capitalisation with "m/s"
**File:** `app/pages/steady_state.py`, line 56

```python
demand_label = metric_card('--', 'LPS', 'Total Demand')
```

The unit "LPS" is fine, but note the checklist permits both "L/s" and "LPS". The flow chart y-axis label (line 140) uses "LPS" while the 3D scene flow labels (scene_3d.py, line 349) use "L/s". Pick one form and use it consistently across all surfaces.

### H6 — 3D pressure legend: "20-30m — ADEQUATE" but compliance minimum is 20m
**File:** `app/pages/view_3d.py`, lines 167–184

The floating legend labels the 20–30 m band "ADEQUATE — WSAA compliant" with a yellow-amber colour (`#f59e0b`). Amber/yellow typically signals caution; using it for "compliant" pressures may confuse engineers who expect green for passing. Consider using `#10b981` (green) for the 20–30 m band to match the colour-science convention stated in the review checklist (green=good).

### H7 — Transient page: "Run Water Hammer Analysis" button uses `color=warning` (amber)
**File:** `app/pages/transient.py`, line 34

```python
run_btn = ui.button('Run Water Hammer Analysis', ...).props('color=warning')
```

Using warning/amber colour for the primary action button implies the action itself is dangerous. The steady-state analysis button (steady_state.py line 37) uses `color=primary`. Transient analysis should also use `color=primary` unless the intent is deliberately to caution.

### H8 — Steady-state pressure chart: annotation for WSAA limit lacks unit
**File:** `app/pages/steady_state.py`, line 126

```python
p_fig.add_hline(y=20, line_dash='dash', line_color=COLORS['red'],
               annotation_text='Min 20m (WSAA)')
```

The annotation "Min 20m (WSAA)" is good — it cites the standard and includes the value. However it does not cite the full WSAA document reference. Consider "WSAA Min: 20 m" (acceptable as-is) but note the transient page does not include any equivalent annotations (see H1).

### H9 — DOCX/PDF reports: pressure and flow values written without rounding
**File:** `reports/docx_report.py`, lines 211–216; `reports/pdf_report.py`, lines 152–155

```python
p_rows.append([
    junc,
    str(data.get('min_m', '-')),   # raw float
    str(data.get('max_m', '-')),
    str(data.get('avg_m', '-')),
])
```

`str()` on raw floats produces values like `"30.12345678"` in report tables. Professional engineering reports require controlled precision: pressures 1 dp, flows 1–2 dp, velocities 2 dp. The same issue exists for flow table columns (`min_lps`, `max_lps`, `avg_lps`, `avg_velocity_ms`) and transient surge data.

### H10 — PDF report: pipe table header "Rough." is truncated jargon
**File:** `reports/pdf_report.py`, line 140

```python
_pdf_table(pdf, ['ID', 'Start', 'End', 'Length', 'Dia (mm)', 'Rough.'], link_rows)
```

"Rough." is an abbreviation a user may not understand. The DOCX report (docx_report.py, line 192) uses "Roughness" in full. The PDF should match: "Roughness" or "C (H-W)".

### H11 — PDF report: pipe table header "Length" has no unit
**File:** `reports/pdf_report.py`, line 140

The DOCX version (docx_report.py, line 192) has `'Length (m)'` but the PDF version has just `'Length'`. The unit is missing.

### H12 — PDF report: flow table headers use "Min LPS" / "Vel m/s" without brackets
**File:** `reports/pdf_report.py`, line 163

```python
_pdf_table(pdf, ['Pipe', 'Min LPS', 'Max LPS', 'Avg LPS', 'Vel m/s'], f_rows)
```

Compare DOCX (docx_report.py, line 231): `['Pipe', 'Min (LPS)', 'Max (LPS)', 'Avg (LPS)', 'Velocity (m/s)']`. The PDF headers drop the parentheses and abbreviate "Velocity". This is inconsistent.

---

## Medium (polish and consistency)

### M1 — Compliance component: no visual distinction between OK messages and absent messages
**File:** `app/components/compliance.py`, lines 19–21

When `compliance_list` is empty the component shows "No compliance data" in muted grey. This is indistinguishable from "analysis not run yet". Consider showing "All checks passed" in green when an empty list is returned after a successful analysis, versus the pre-run placeholder text.

### M2 — Network editor: "Roughness (C)" label but roughness input is just a number
**File:** `app/pages/network_editor.py`, line 96

```python
pipe_rough_input = ui.number('Roughness (C)', value=130)
```

"Roughness (C)" correctly signals Hazen-Williams C. The element properties panel (line 193) similarly uses `'Roughness (C)'`. This is good, but the display on show_properties (line 193) shows `round(pipe.roughness)` — no units. Consider showing it as `f'C = {round(pipe.roughness)}'` to be explicit.

### M3 — 3D element info: "Roughness: 130 (C)" — unit placement is awkward
**File:** `app/pages/view_3d.py`, line 744

```python
ui.label(f'Roughness: {pipe.roughness} (C)')
```

`pipe.roughness` is a raw float. Should be `f'C = {pipe.roughness:.0f}'` (consistent with Hazen-Williams notation). The raw float may display many decimal places.

### M4 — 3D element info: Tank init/max level are raw floats
**File:** `app/pages/view_3d.py`, lines 725–728

```python
ui.label(f'Init Level: {node.init_level} m')
ui.label(f'Max Level: {node.max_level} m')
```

Raw floats. Should be `f'{node.init_level:.1f} m'` and `f'{node.max_level:.1f} m'`.

### M5 — 3D view: floating legend does not update when "Run Analysis + Color" changes colour mode
**File:** `app/pages/view_3d.py`, lines 453–454

`update_legend(color_select.value.lower())` is called after "Run Analysis + Color". This is correct. However the right-side static panel (lines 333–365) always shows both PRESSURE SCALE and VELOCITY SCALE simultaneously regardless of the active colour mode. When "Velocity" is selected the pressure scale is still visible and vice versa. These static scales should be conditionally hidden or the legend panel should only show the active scale.

### M6 — Scenarios page: comparison chart y-axis for flows uses "Avg Flow (LPS)" — no context
**File:** `app/pages/scenarios.py`, line 174

```python
f_fig.update_layout(..., yaxis_title='Avg Flow (LPS)', ...)
```

"Avg Flow" is clear, but the chart title card reads only "FLOW COMPARISON". A more descriptive title such as "Average Pipe Flow — Scenario Comparison" would help. Similarly the pressure chart title (line 73) reads "PRESSURE COMPARISON" — "Minimum Junction Pressure — Scenario Comparison" better describes what is shown (minimum pressure, not average).

### M7 — 3D scene label for diameter: uses "DN" notation without explanation
**File:** `app/components/scene_3d.py`, line 342

```python
dia_label = self.scene.text3d(f'DN{dia_mm:.0f}', style=fs)
```

"DN" is standard DN (Diameter Nominal) notation in Australian practice and is acceptable. However the label toggle checkbox in view_3d.py line 83 reads "Diameters", which implies it will show mm values. Engineers will see "DN200" and understand it, but consistency with the "Diameter (mm)" label in the editor panel (network_editor.py line 95) would be cleaner. This is low-severity.

### M8 — Steady-state flow chart: no WSAA velocity reference line
**File:** `app/pages/steady_state.py`, lines 132–141

The pressure chart correctly shows a dashed WSAA 20 m reference line (line 125). The flow chart does not show any velocity limit reference. Adding `f_fig.add_hline(y=<wsaa_max_lps>, ...)` is difficult because different pipes have different diameters, so a velocity-equivalent flow limit is not pipe-agnostic. However, a note in the chart title or annotation explaining why no limit line exists would help. Alternatively the chart should show velocity (m/s) rather than flow (LPS) to allow a direct 2.0 m/s WSAA limit line.

### M9 — No loading indicator while 3D network renders
**File:** `app/pages/view_3d.py`, lines 369–404 (render_network function)

The render function does not set `run_btn.props('loading')` before or after the render call, unlike steady_state.py (lines 91, 153) and transient.py (lines 77, 176) which correctly use loading state. For large networks the 3D render could take several seconds with no visual feedback.

### M10 — Scenarios page: "Run" button on scenario list has no loading state
**File:** `app/pages/scenarios.py`, line 117

```python
ui.button('Run', on_click=lambda n=s['name']: run_scenario(n)).props('size=sm color=primary')
```

`run_scenario()` calls `manager.run_scenario()` synchronously with no loading feedback. For large networks this will freeze the UI without indication. Should use `run_btn.props('loading')` pattern.

### M11 — Feedback page: no error handling on file I/O
**File:** `app/pages/feedback.py`, lines 14–18, 20–24

`load_feedback()` and `save_feedback()` have no try/except. If the output directory is read-only or the JSON file is corrupted, a Python exception will propagate to NiceGUI and may surface as a traceback. Should wrap in try/except with `ui.notify(type='negative')`.

### M12 — Measurement result: distance values lack explicit units in label
**File:** `app/pages/view_3d.py`, lines 269–272

```python
ui.label(f"3D: {result['distance_3d']}m  |  "
         f"Horiz: {result['distance_horizontal']}m  |  "
         f"Vert: {result['distance_vertical']}m")
```

`result['distance_3d']` etc. are raw floats — may show many decimal places. Should format to 1 dp: `f'{result["distance_3d"]:.1f}m'`.

### M13 — Material colour for PE/HDPE is very dark (`#1a1a2e`)
**File:** `app/components/scene_3d.py`, line 33; `app/pages/view_3d.py`, lines 228, 359

The PE/HDPE material colour `#1a1a2e` is almost identical to the dark scene background `#0d1117`. PE pipes will be nearly invisible in the 3D view unless zoomed close. Consider a lighter shade such as `#2244aa` or `#4455cc`.

### M14 — DOCX report: "Roughness" column has no unit or qualifier
**File:** `reports/docx_report.py`, line 192

```python
_add_styled_table(doc, ['ID', 'Start', 'End', 'Length (m)', 'Diameter (mm)', 'Roughness'], ...)
```

The header "Roughness" gives no indication it is Hazen-Williams C. Should be "Roughness (C H-W)" or "C-factor".

### M15 — DOCX/PDF: DOCX compliance section header says "Australian standards (WSAA Guidelines)" but transient surge thresholds reference no AS standard
**File:** `reports/docx_report.py`, lines 253–255

The text claims "The following compliance checks have been performed against Australian standards (WSAA Guidelines)." If transient surge thresholds are based on pipe pressure ratings (e.g. PN class), the body text should additionally reference the relevant AS standard (e.g. AS/NZS 4130 for PE pipe pressure rating or AS 2885 for steel).

---

## Page-by-Page Findings

### Steady-State Tab

- **Units:** Pressure in "m" (OK), velocity in "m/s" (OK), flow in "LPS" (OK). All metric cards have unit labels. Chart axes correctly labelled with units (lines 127–128, 139–140).
- **Precision:** Metric card values use correct formatting: `f'{min_p:.1f}'` (line 108), `f'{max_v:.2f}'` (line 110), `f'{total_demand:.1f}'` (line 112). Good.
- **Compliance:** WSAA 20 m reference line shown with annotation (line 126). Compliance panel populated from `render_compliance()` — quality depends on API output.
- **Error handling:** Network load and run_analysis both wrapped in try/except with `ui.notify(type='negative')` (lines 79–80, 150–151). Loading state set on run button (lines 91, 153). Good.
- **Charts:** Both pressure and flow charts have axis titles with units. Legends enabled. No chart titles (using card header labels instead — acceptable).
- **Issues:** See H5 (LPS vs L/s inconsistency), H8 (annotation could be more specific), M8 (no velocity reference line on flow chart).

### Transient / Water Hammer Tab

- **Units:** Wave speed input labelled "Wave Speed (m/s)" (OK). Duration "Duration (s)" (OK). Head chart y-axis "Head (m)" (line 105). Envelope y-axis "Head (m)" (line 131). All correct.
- **Precision:** CRITICAL issues C1, C2 — raw floats in compliance badges and metric cards.
- **Compliance:** No standard cited in surge severity bands (H1). Compliance list passed to `render_compliance()` — same dependency as steady-state.
- **Error handling:** try/except with `ui.notify` present (lines 173–175). Loading state used (lines 76, 176). Good.
- **Charts:** Valve closure vline annotation is "Valve closure" (line 103) — no time value shown in annotation. Consider `f'Valve closure @ {start_input.value}s'`.

### Joukowsky Calculator Tab

- **Units:** Wave speed input "Wave Speed, a (m/s)" (OK). Velocity input "Velocity Change, dV (m/s)" (OK). Formula shown.
- **Precision:** CRITICAL issues C3, C4 — raw floats and non-standard unit label.
- **Chart:** Wave speed reference bar chart has x-axis labelled "Wave Speed (m/s)" (line 74). Y-axis has no label (just material names, which is acceptable for a horizontal bar chart). Bar labels show values with units "m/s" (line 69). Good.
- **No error handling:** The `calculate()` function (line 81) has no try/except. If `wave_input.value` or `vel_input.value` is invalid (e.g. None), an unhandled exception could surface. Should wrap in try/except.

### 3D View Tab

- **Units:** Legend labels use "m" for pressure and "m/s" for velocity (lines 150, 187). Static scales use "m" and "m/s" with range values (lines 335–354). Good.
- **Precision:** Issues C5, C6 (in network_plot), C8, M3, M4, M12 above.
- **Legend:** Floating colour legend updates correctly when colour mode changes (update_legend called at lines 401, 453). Static right-panel shows all three scales simultaneously (M5).
- **Error handling:** render_network and run_and_color wrapped in try/except (lines 402–404, 455–456). No loading state on render buttons (M9).
- **Charts:** 3D view is a ui.scene, not a Plotly chart — no axis labels applicable. Measurement results have raw float issue (M12).

### Scenarios Tab

- **Units:** Pressure comparison y-axis "Min Pressure (m)" (line 159 — OK). Flow comparison y-axis "Avg Flow (LPS)" (line 174 — OK).
- **Precision:** Charts pass floats from API directly to Plotly, which formats them appropriately for bar charts.
- **Compliance:** No compliance display on this tab — the tab purpose is comparison, not standalone compliance. Acceptable.
- **Error handling:** create_scenario, run_scenario, run_comparison all have try/except (lines 94–95, 124–125, 135–137). Good.
- **Issues:** H3 (raw dict display), H4 (ambiguous value label), M6 (chart titles), M10 (no loading state on Run button).

### Network Editor Tab

- **Units:** Dialog inputs labelled with units: "Elevation (m)", "Demand (LPS)", "Length (m)", "Diameter (mm)", "Roughness (C)" (lines 79–96). Good.
- **Precision:** Properties panel uses `round(node.elevation, 1)` (line 164), `round(demand_val, 2)` (line 167), `round(node.coordinates[0], 1)` (line 168). Pipe uses `round(pipe.diameter * 1000)` (line 191) — integer mm. All correct.
- **Error handling:** load_network, confirm_add_junction, confirm_add_pipe, delete_selected, save_network all have try/except (lines 136–137, 232–233, 250–251, 273–274, 287–288). Good.
- **"No network loaded":** When `api.wn is None` the canvas is empty with no instruction. The properties panel shows "Select an element to view its properties" which is appropriate. However the element selector (line 309) silently returns if `api.wn is None` with no notification. Consider `ui.notify('Load a network first', type='warning')`.

### Feedback Tab

- **No engineering values** — not applicable for units/precision checklist.
- **Error handling:** `submit_feedback()` does not catch I/O errors (M11). `load_feedback()` and `save_feedback()` not wrapped.
- **UX:** Form is clear and professional. Severity options are well-worded.

### Reports (DOCX and PDF)

- **Title page:** Includes project name/title, engineer name (if provided), date, and "Analysis per WSAA Guidelines". All required fields present.
- **Table headers:** DOCX has units in headers for most columns. PDF has inconsistencies (H10, H11, H12).
- **Compliance section:** Status column colour-coded (green/amber/red) in both DOCX and PDF. Compliance messages passed through as-is — quality depends on API.
- **Conclusions:** Auto-generated and actionable at the high level. Transient conclusion references surge value and points to Section 4 (good). Could be more specific about which junctions were non-compliant.
- **Precision in tables:** Raw floats in table cells (H9) — applies to both DOCX and PDF.
- **Roughness column heading:** "Roughness" with no H-W qualifier (M14).

---

## Summary Table of Issues by Priority

| ID  | Priority | File | Line(s) | Description |
|-----|----------|------|---------|-------------|
| C1  | Critical | transient.py | 150–152 | Raw float surge values in compliance badge labels |
| C2  | Critical | transient.py | 164–165 | Raw float surge metrics in metric cards |
| C3  | Critical | joukowsky.py | 86–87 | Raw float results in metric cards |
| C4  | Critical | joukowsky.py | 53 | "metres of head" non-standard unit label |
| C5  | Critical | view_3d.py | 729 | Tank diameter shown in metres not mm |
| C6  | Critical | network_plot.py | 75 | Raw float elevation in hover tooltip |
| C7  | Critical | network_plot.py | 79 | Raw float head in hover tooltip |
| C8  | Critical | view_3d.py | 691, 716 | Raw float elevation/head in element info panel |
| H1  | High | transient.py | 140–152 | No standard cited in transient surge severity bands |
| H2  | High | compliance.py | 43–44 | No enforcement of standard citation in messages |
| H3  | High | scenarios.py | 49 | Raw Python dict displayed as modification summary |
| H4  | High | scenarios.py | 38 | Ambiguous value field label mixing mm/C/multiplier |
| H5  | High | steady_state.py / scene_3d.py | 56 / 349 | "LPS" vs "L/s" inconsistency |
| H6  | High | view_3d.py | 167–184 | "ADEQUATE" 20–30 m band shown in amber not green |
| H7  | High | transient.py | 34 | Run button colour=warning signals danger for primary action |
| H8  | High | steady_state.py | 126 | WSAA reference annotation could be more specific |
| H9  | High | docx_report.py / pdf_report.py | 211–216, 152–155 | Raw floats in report table cells |
| H10 | High | pdf_report.py | 140 | "Rough." truncated jargon in PDF table header |
| H11 | High | pdf_report.py | 140 | "Length" missing unit in PDF pipe table |
| H12 | High | pdf_report.py | 163 | Flow table headers inconsistent with DOCX |
| M1  | Medium | compliance.py | 19–21 | "No compliance data" indistinguishable from pre-run state |
| M2  | Medium | network_editor.py | 193 | Roughness shown without "C =" prefix |
| M3  | Medium | view_3d.py | 744 | Raw float roughness in element info panel |
| M4  | Medium | view_3d.py | 725–728 | Raw float tank levels in element info panel |
| M5  | Medium | view_3d.py | 333–365 | Static legend panel shows all scales simultaneously |
| M6  | Medium | scenarios.py | 73–77, 174 | Vague chart card titles for comparison charts |
| M7  | Medium | scene_3d.py | 342 | "DN" notation not explained; minor inconsistency |
| M8  | Medium | steady_state.py | 132–141 | No velocity reference line on flow chart |
| M9  | Medium | view_3d.py | 369–404 | No loading indicator during 3D render |
| M10 | Medium | scenarios.py | 117 | No loading state on per-scenario Run button |
| M11 | Medium | feedback.py | 14–24 | No error handling on feedback file I/O |
| M12 | Medium | view_3d.py | 269–272 | Raw float distances in measurement result label |
| M13 | Medium | scene_3d.py | 33 | PE/HDPE colour nearly invisible against dark background |
| M14 | Medium | docx_report.py | 192 | "Roughness" column missing H-W qualifier |
| M15 | Medium | docx_report.py | 253–255 | Compliance section text omits AS standard refs for transient |

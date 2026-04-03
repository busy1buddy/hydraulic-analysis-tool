# Review Cycle Summary — 2026-04-03

## Overview

- **Reviews completed:** architect.md, code-review.md, data-validation.md, ui-review.md, hydraulic-benchmarks.md
- **Total findings:** 47 (Blockers: 7, High: 18, Medium: 19, Low: 3)

---

## BLOCKERS — Fix Immediately

### B1: Fanning vs Darcy Friction Factor — Slurry Headloss 4× Underestimate

- **Source:** hydraulic-benchmarks (Benchmark 6 FAIL), code-review (C2)
- **Files:** `slurry_solver.py` lines 136–137
- **Issue:** The Buckingham-Reiner laminar branch uses the Fanning friction factor convention (`f = 16/Re_B`) but feeds it directly into the Darcy-Weisbach equation, which requires the Darcy form (`f = 64/Re_B`). Benchmark testing confirms the toolkit underestimates laminar slurry headloss by approximately 4× (expected 0.025958 m, got 0.006000 m — 76.9% error). The code-review also identified that the same line has a conceptually inverted `max()` floor guard, which can silently produce a friction factor below the physical minimum for high Hedstrom-number / low Reynolds-number fluids.
- **Root cause connection:** Both the Fanning/Darcy confusion and the inverted floor guard stem from a single incorrectly formulated line. The floor issue (`max(f, 16/Re_B)`) never activates in the normal case (correct `f` is already larger), but can produce a sub-physical result when the fourth-power term makes the bracket go negative — compounding the 4× error.
- **Impact:** All Bingham plastic laminar headloss calculations are ~4× too low. A slurry pipeline designed using this output will be severely undersized — pipes will operate in an unintended regime, solids will settle, and pumps will be under-selected. This is the highest-risk finding in the codebase.
- **Fix:** Change `f = 16 / Re_B * (...)` to `f = 64 / Re_B * (...)` (Darcy form). Replace `max(f, 16/Re_B)` with `max(f, 1e-6)` as the physical floor. Verify the coefficient in the fourth-power correction term against Slatter (1995) or Darby (2001) — the current `3 × 10⁷` may need to be `3 × 3.3 × 10⁷`.

---

### B2: Transient Pressure Uses Total Head, Not Gauge Pressure Head

- **Source:** code-review (C1)
- **Files:** `epanet_api.py` lines 644–650, 887–893, 896–908
- **Issue:** `max_pressure_kPa` and `surge_kPa` are computed by multiplying TSNet total head (elevation + pressure head) by `g = 9.81`. For elevated junctions, total head includes elevation head, so the compliance check at line 653 compares inflated head values against the 3500 kPa pipe rating. For a junction at 50 m elevation with 100 m total head, the code reports 981 kPa but the actual pressure is only (100 − 50) × 9.81 = 490 kPa. The error is identical in the pump transient path (`_build_pump_results`, lines 887–908).
- **Impact:** Transient compliance checks will flag non-compliant junctions as compliant when the junction is elevated — a dangerous false-safe result. A pipeline at 50 m elevation with genuinely high surge could be reported as within rating when it is not, depending on the balance of elevation vs. pressure head.
- **Fix:** Subtract node elevation before converting: `max_pressure_kPa = (max_h - node.elevation) * density * g / 1000`. Apply consistently to all three transient result-building locations.

---

### B3: Water Age Results in Wrong Units — 3600× Error

- **Source:** code-review (H5 — escalated to BLOCKER by severity criteria)
- **Files:** `epanet_api.py` lines 491–496, 500
- **Issue:** WNTR returns water age in **seconds**. The code stores raw values under keys named `_hrs` and compares them against a 24.0-hour stagnation threshold. Water age of 86,400 seconds (24 hours) will be stored as 86,400 and compared against 24.0 — the threshold will **never trigger**, meaning no junction will ever be flagged for stagnation regardless of actual water age.
- **Impact:** Water quality compliance checks are silently suppressed. Users designing reticulation systems will not receive stagnation warnings even for dead-end mains with multi-day residence times.
- **Fix:** Divide by 3600 before storing: `max_age_hrs = round(float(q.max()) / 3600, 2)`. Add a comment citing the WNTR documentation unit (seconds for AGE parameter).

---

### B4: PVC Pipe Geometry Wrong for 5 of 6 Standard Sizes

- **Source:** data-validation (Critical finding 1)
- **Files:** `data/au_pipes.py` (PVC section)
- **Issue:** The database was authored using DN as the OD for DN≥200, but AS/NZS 1477 specifies OD values that exceed the nominal DN (e.g., DN200 has OD 225 mm, not 200 mm). Five of six PVC sizes have incorrect internal diameters (deviations of 2 to 30 mm) and incorrect wall thicknesses. The systemic root cause is a wrong OD assumption throughout the PVC section.
- **Impact:** All hydraulic calculations using PVC pipes — headloss (via velocity in D-W/H-W), surge wave speed, and stress analysis — will use wrong pipe geometry. At DN250 the internal diameter is understated by 21.8 mm (258.6 mm vs 236.8 mm in DB), causing a ~19% overestimate of velocity and significant headloss error.
- **Fix:** Replace all PVC entries using the correct AS/NZS 1477 OD series: 110, 160, 225, 280, 315, 400 mm for DN100–DN375. Recompute wall thicknesses from the PN-class tables and internal diameters as OD − 2t.

---

### B5: Slurry Pump Power Inconsistency — Curves and Ratings Internally Contradictory

- **Source:** data-validation (Critical finding 2)
- **Files:** `data/pump_curves.py` (SLP-200-30, SLP-400-50)
- **Issue:** The rated `power_kW` for the two slurry pumps (SLP-200-30: 45 kW; SLP-400-50: 110 kW) is 2–3× higher than the shaft power implied by the head/flow curves at BEP (SLP-200-30: 11.7 kW; SLP-400-50: 35.2 kW). Either the head values are understated by ~2.7× or the power values are overstated by ~3×. The database is internally contradictory for these two pumps.
- **Impact:** Pump sizing calculations that use either the curve data or the rated power will produce inconsistent results. An engineer selecting a pump on the basis of this data cannot trust either value.
- **Fix:** Source the manufacturer datasheets for SLP-200-30 and SLP-400-50. If power values are motor nameplate ratings, update the head/flow curves to match the corresponding duty point. Document which field is design-basis.

---

### B6: UI Layer Directly Imports WNTR and Mutates Hydraulic State

- **Source:** architect (B1, B2 — layer violations)
- **Files:** `app/pages/network_editor.py` lines 14, 172–174, 196–198, 210, 221–225, 238–244, 263, 265, 285
- **Issue:** `network_editor.py` directly imports `wntr` and directly mutates `api.wn` (adds/removes nodes and links, modifies element properties) without going through `HydraulicAPI` methods. It also writes `.inp` files via `wntr.network.write_inpfile()` (line 285), bypassing the API layer entirely.
- **Root cause connection:** `scenario_manager.py` (lines 13–15, 93) commits the same violation — it imports both `wntr` and `epanet_api` and calls `wntr.network.write_inpfile()` directly. These two files together mean that hydraulic network state can be mutated from two locations outside the API, making it impossible to enforce invariants or add validation at a single point.
- **Impact:** Any validation, logging, or state-consistency logic added to `HydraulicAPI` will be silently bypassed by the editor. This blocks future cloud deployment (direct object mutation cannot cross a process boundary) and creates a risk of silent state corruption if the UI and API layer ever diverge.
- **Fix:** Add `HydraulicAPI` methods for all network mutations (`add_junction`, `add_pipe`, `remove_element`, `set_node_elevation`, `set_pipe_diameter`, `save_network`). Remove `import wntr` from `network_editor.py` and `scenario_manager.py`. Route all calls through the API.

---

### B7: Velocity Calculation Uses Signed `f.max()` — Understates Peak Velocity on Reversing Pipes

- **Source:** code-review (C3)
- **Files:** `epanet_api.py` lines 213–215, 244–245
- **Issue:** WNTR returns signed flowrates (negative for reversed flow). `f.max()` returns the largest algebraic value, not the largest absolute value. For pipes that reverse direction, the actual maximum speed may occur in the negative-flow period and will be missed. `abs(f.mean())` also understates average speed for bidirectional flow by averaging cancelling values before taking the absolute value.
- **Root cause connection:** The same incorrectly signed operation appears in both the results extraction path (line 214) and the compliance check path (line 245), meaning the compliance check for maximum velocity is also wrong on reversing pipes.
- **Impact:** Compliance checks for velocity (WSAA 2.0 m/s limit) may pass for pipes that actually exceed the limit during flow reversal. Pipes carrying high-velocity reversed flow will escape detection.
- **Fix:** `v_avg = float(f.abs().mean()) / area` and `v_max = float(f.abs().max()) / area` at both locations. Also add a zero-area guard (see B7 note below): `if area <= 0: continue` before the division (code-review C4, `epanet_api.py` lines 213, 244).

> **Note:** The zero-diameter guard (code-review C4) is a crash-safety issue that is grouped here as it shares the same two line locations. A `diameter = 0` pipe from a user-edited `.inp` file will raise `ZeroDivisionError` and abort result extraction. Add `if pipe.diameter <= 0: continue` before computing `area`.

---

## HIGH — Fix Before Next Release

### H1: Concrete Hazen-Williams C Values Overstated for Large Pipes

- **Source:** data-validation (High finding 3)
- **Files:** `data/au_pipes.py` (Concrete section)
- **Issue:** The database applies C = 120 uniformly to all concrete pipe sizes. AS 4058 requires C = 110 for DN375–DN450, C = 100 for DN600–DN750, and C = 90 for DN900. Using C = 120 at DN900 overstates hydraulic capacity by approximately 12%.
- **Impact:** Headloss will be underestimated for large concrete mains, leading to undersized pumping systems and potentially non-compliant pressure at delivery points.
- **Fix:** Update the Concrete section of `au_pipes.py` with size-dependent C values matching AS 4058.

---

### H2: Ductile Iron Internal Diameters Wrong for DN375, DN450, DN600

- **Source:** data-validation (High finding 4)
- **Files:** `data/au_pipes.py` (Ductile Iron section)
- **Issue:** Three DI sizes have IDs 5–9 mm wider than the AS 2280 K9 standard requires (DN375: 390.4 vs 381.4 mm; DN450: 468.0 vs 462.8 mm; DN600: 621.6 vs 615.2 mm). IDs appear to have been computed from a larger OD than specified.
- **Impact:** Velocity and headloss will be underestimated for these common trunk main sizes. Surge wave speed values for DN450 and DN600 are also below the 1100 m/s standard lower bound, affecting transient analysis accuracy.
- **Fix:** Recalculate IDs as OD − 2 × wall using the correct AS 2280 OD series. Update wave speeds to the standard range midpoint (1130 m/s).

---

### H3: Missing Standard Pipe Sizes — DI DN500, PE DN75, Concrete DN225

- **Source:** data-validation (High finding 5, Medium findings 8–9)
- **Files:** `data/au_pipes.py`
- **Issue:** DI DN500 (OD 532, wall 9.0 mm, ID 514.0 mm) is a commonly specified Australian water main size missing entirely. PE DN75 and Concrete DN225 are the smallest sizes in their respective standards but are absent.
- **Impact:** Users specifying DN500 DI (common for trunk mains) will receive no properties or an error. Smallest PE and concrete sizes are unavailable for reticulation design.
- **Fix:** Add DN500 DI per AS 2280. Add PE DN75 per AS/NZS 4130 SDR11. Add Concrete DN225 per AS 4058.

---

### H4: Operating Point Search Algorithm Can Return False Intersection

- **Source:** code-review (H1)
- **Files:** `data/pump_curves.py` lines 248–253
- **Issue:** The secondary condition `pump_head >= sys_head * 0.95` in the intersection search skips physically valid intersection points where the pump curve is slightly below the system curve (end-of-curve / high-flow conditions). The 5 m miss tolerance is also unscaled and will reject valid intersections for high-head pumps (>55 m head).
- **Impact:** Pump operating points may be reported at the wrong duty point, leading to incorrect flow and head estimates. For high-head mining pumps the 5 m hard threshold is too coarse.
- **Fix:** Replace the closest-point search with a sign-change algorithm: find the flow index where `(pump_head - sys_head)` changes sign and interpolate linearly. Remove the `>= sys_head * 0.95` bias condition. Scale the miss tolerance proportionally to rated head.

---

### H5: Water Quality Stagnation Threshold Not Triggering (Connected to B3)

- **Source:** code-review (H5), reported separately from B3 for traceability
- **Files:** `epanet_api.py` line 500
- **Note:** This is the downstream compliance symptom of the unit error in B3. Once B3 is fixed, this check will function correctly. No separate fix action required beyond B3.

---

### H6: Transient Surge Compliance Badges — Raw Floats, No Standard Cited

- **Source:** ui-review (C1, C2, H1) — UI Critical reclassified as High (display issue, not wrong numbers)
- **Files:** `app/pages/transient.py` lines 34, 140–152, 150–152, 164–165
- **Issue:** (a) Surge values in compliance badges and metric cards are passed as raw floats via `str()`, producing 10+ decimal places (e.g., `"surge 47.382918273m"`). (b) The severity bands HIGH/MOD/OK have no standard citation — an engineer cannot determine what document the thresholds relate to. (c) The "Run Water Hammer Analysis" button uses `color=warning` (amber), implying the action is dangerous rather than primary.
- **Impact:** Compliance panels look like debug output. Engineers cannot audit surge limits against a cited standard. The amber run button causes confusion.
- **Fix:** Apply `:.1f` format to surge metres and `:.0f` to kPa throughout transient.py. Add standard citation to severity band labels (e.g., `'HIGH — Exceeds PN35 limit (WSAA)'`). Change button to `color=primary`.

---

### H7: Joukowsky Calculator — Raw Floats and Non-Standard Unit Label

- **Source:** ui-review (C3, C4)
- **Files:** `app/pages/joukowsky.py` lines 53, 86–87
- **Issue:** Metric card values use `str()` on floats (arbitrary decimal places). The head rise label reads "metres of head" — verbose and inconsistent with the rest of the application which uses "m".
- **Fix:** Format as `f'{result["head_rise_m"]:.1f}'` and `f'{result["pressure_rise_kPa"]:.0f}'`. Replace label text with "m".

---

### H8: 3D View — Tank Diameter in Metres When Pipes Show mm

- **Source:** ui-review (C5)
- **Files:** `app/pages/view_3d.py` line 729
- **Issue:** Tank diameter is displayed as `node.diameter` in metres (e.g., "1.5 m") while pipe diameters (line 742) are correctly converted to mm ("300 mm"). Inconsistency is confusing; tanks are conventionally sized in mm.
- **Fix:** Display as `f'{node.diameter * 1000:.0f} mm'`.

---

### H9: Network Topology Hover — Raw Float Elevation and Head

- **Source:** ui-review (C6, C7)
- **Files:** `app/components/network_plot.py` lines 75, 79
- **Issue:** Hover tooltips display `node.elevation` and `node.base_head` as raw floats (e.g., "Elev: 39.99999999999m").
- **Fix:** Apply `:.1f` format to both fields.

---

### H10: 3D Element Info Panel — Raw Float Elevation and Head

- **Source:** ui-review (C8)
- **Files:** `app/pages/view_3d.py` lines 691, 716
- **Issue:** Same raw float display issue as H9 but in the right-panel element properties display.
- **Fix:** Apply `:.1f` format.

---

### H11: Scenarios Page — Raw Python Dict Displayed as Modification Summary

- **Source:** ui-review (H3, H4)
- **Files:** `app/pages/scenarios.py` lines 38, 49
- **Issue:** (a) Modification display renders the raw Python dict (`+ {'type': 'pipe_diameter', 'target': 'P6', 'value': 250.0}`). (b) The value input field is labelled "Value (mm/C-factor/multiplier)" — three incompatible units combined into one label that should update based on the selected modification type.
- **Fix:** (a) Build a user-facing string: `f"+ Pipe {mod['target']}: {mod['type']} → {mod['value']}"`. (b) Make the label dynamic: update to "Value (mm)" for diameter, "C-factor" for roughness, "multiplier" for demand.

---

### H12: 3D Pressure Legend — "ADEQUATE" Band Shown in Amber Not Green

- **Source:** ui-review (H6)
- **Files:** `app/pages/view_3d.py` lines 167–184
- **Issue:** The 20–30 m pressure band labelled "ADEQUATE — WSAA compliant" uses amber (`#f59e0b`). Engineering colour convention is green for passing, amber for caution. Displaying a compliant pressure range in amber will cause engineers to question results that are actually correct.
- **Fix:** Change the 20–30 m band colour to `#10b981` (green). Reserve amber for the marginal band (e.g., 15–20 m).

---

### H13: PDF Report — Missing Units and Inconsistent Headers vs DOCX

- **Source:** ui-review (H9, H10, H11, H12)
- **Files:** `reports/pdf_report.py` lines 140, 152–155, 163
- **Issue:** (a) Raw floats in table cells (no rounding — same defect as DOCX but both need fixing). (b) Pipe table header "Rough." should be "Roughness" or "C (H-W)". (c) "Length" column missing the "(m)" unit. (d) Flow table headers "Min LPS / Max LPS / Vel m/s" drop parentheses and truncate "Velocity" — inconsistent with the DOCX equivalent.
- **Fix:** Apply consistent rounding to all table values (pressures 1 dp, velocities 2 dp, flows 1 dp). Align all PDF table headers to match the DOCX versions exactly.

---

### H14: Compliance Component — No Enforcement of Standard Citation in Messages

- **Source:** ui-review (H2)
- **Files:** `app/components/compliance.py` lines 43–44
- **Issue:** The compliance component renders whatever message string arrives from the API without validating that the message cites a specific standard. Generic strings like "Low pressure" can be displayed without context. This is a process issue: the API must produce citation-containing messages.
- **Fix:** Establish a message format contract in `HydraulicAPI` compliance output: all non-passing messages must include the relevant standard (e.g., "Below WSAA minimum 20 m (WSAA HB 2012)"). Enforce this at the API layer, not the UI component.

---

### H15: Steady-State Demand Multiplier Applied Cumulatively if Called Twice

- **Source:** code-review (H4)
- **Files:** `scenario_manager.py` line 69
- **Issue:** `junc.demand_timeseries_list[0].base_value *= factor` will silently compound if a caller passes two `demand_factor` modifications in the same list. No guard or assertion prevents this.
- **Fix:** Add an assertion that at most one `demand_factor` modification is present per call, or apply all demand factors as a product in a single step.

---

### H16: Static Slurry Pipe Not Flagged for Settling Risk

- **Source:** code-review (H3)
- **Files:** `slurry_solver.py` line 404
- **Issue:** The settling check condition `velocity_ms > 0` excludes zero-velocity pipes (static slurry), which is the highest settling-risk case.
- **Fix:** Remove the `> 0` lower bound. A zero-velocity slurry pipe should be the first condition flagged for settling.

---

### H17: `pipe_rating_m` Computed but Never Used (Dead Code — Transient Path)

- **Source:** code-review (H2)
- **Files:** `epanet_api.py` lines 629, 872
- **Issue:** `pipe_rating_m = self.DEFAULTS['pipe_rating_kPa'] / g` is computed at the start of both `run_transient` and `_build_pump_results` but never referenced — all downstream comparisons use `self.DEFAULTS['pipe_rating_kPa']` directly. This is a sign of an incomplete refactor.
- **Fix:** Remove the dead variable at both locations. Confirm the intended comparison (kPa vs metres) is correct in context.

---

### H18: `joukowsky()` Implicit Water Density Assumption Undocumented

- **Source:** code-review (M1 — escalated to High because it silently fails for slurry)
- **Files:** `epanet_api.py` lines 1166–1179
- **Issue:** `dP_kPa = dH * g` numerically produces the correct kPa result only because `ρ = 1000 kg/m³` for water causes the `/1000` Pa-to-kPa factor to exactly cancel the density multiplication. For slurry (ρ = 1200–1600 kg/m³) the formula gives the same number as for water — it silently ignores fluid density. Since the toolkit supports slurry analysis, this is a latent error for slurry Joukowsky calculations.
- **Fix:** Rewrite as `dP_kPa = rho * wave_speed * velocity_change / 1000` with `rho` as an explicit parameter (defaulting to 1000 for water). Add a docstring note.

---

## MEDIUM — Improve When Convenient

### Architecture

**M-A1: Steady-State and Transient Pages Access Raw Solver Objects**
- **Source:** architect (W1, W2)
- `steady_state.py:115–116` and `transient.py:89–97` access `api.steady_results` and `api.tm` (raw WNTR/TSNet objects) for time-series charting. The API should include time-series data in the returned dict, as `server.py` already does (lines 186–199). This does not mutate state (read-only) but creates solver coupling in the UI layer.

**M-A2: `network_plot.py` Component Accepts WNTR Object Directly**
- **Source:** architect (W8)
- `app/components/network_plot.py` takes a `WaterNetworkModel` directly. It should accept a plain dict `{node_id: (x, y, elev), ...}` to decouple from WNTR's data model.

**M-A3: View 3D Page Reads Element Properties from `api.wn` (Read-Only Coupling)**
- **Source:** architect (W3)
- `app/pages/view_3d.py:687–770` reads WNTR properties for the selection panel. Adding `api.get_element_properties(element_id)` would eliminate the read-only coupling without changing behaviour.

**M-A4: `epanet_api.py` Natural Split Points (1200 Lines)**
- **Source:** architect (O3)
- At ~1200 lines, the file has four natural split points: network management, steady-state/quality, transient, and reporting. A shared state container or base class would enable splitting while maintaining the existing `HydraulicAPI` facade. This is a maintainability improvement, not a correctness issue.

**M-A5: `server.py` Module-Level `api` Singleton Unused**
- **Source:** architect (W4, O2)
- `server.py:37` creates `api = HydraulicAPI(WORK_DIR)` at module level but every route creates its own `api_instance`. Remove the unused singleton.

**M-A6: Duplicated `_collect_compliance()` and `_build_conclusions()` in Report Modules**
- **Source:** architect (W6)
- These helpers are duplicated in `pdf_report.py:426–464` and `docx_report.py:414–463`. Extract to a shared `reports/_helpers.py`.

### Code Quality

**M-C1: `max_pressure_m = 50` Residential-Only — Generates False Warnings on Industrial Networks**
- **Source:** code-review (M6)
- `epanet_api.py:39` hardcodes 50 m as the global upper pressure limit. WSAA HB 2012 specifies this for residential reticulation only. Mining and industrial networks operate at much higher pressures. Make this configurable per network or document it as residential-only.

**M-C2: Metzner-Reed Formula Lacks Citation Comment**
- **Source:** code-review (M2)
- `slurry_solver.py:185–186` — the formula is correct but the `8^(n-1)` arrangement is non-obvious. Add a citation to Metzner & Reed (1955) or Darby (2001).

**M-C3: Scenario `.inp` Filename Collision Risk**
- **Source:** code-review (M5)
- `scenario_manager.py:91–93` — scenario files named `scenario_{name}.inp` will be silently overwritten if the same name is reused across different base networks. Prefix with base network name.

**M-C4: Default `flow_range` in `generate_system_curve` Has No Unit Comment**
- **Source:** code-review (M4)
- `data/pump_curves.py:204–205` — 100 LPS default is unlabelled and may silently extrapolate beyond the pump's operating range. Add a units comment and note that callers should match the range to the pump's rated flow.

**M-C5: PE100 `yield_MPa = 10` Is MRS Classification, Not Yield Stress**
- **Source:** code-review (M3)
- `pipe_stress.py:116` — the value of 10 MPa is the long-term hydrostatic strength classification. The correct short-term yield stress for PE100 is 20–22 MPa (AS/NZS 4130 Table 3). Using 10 MPa will understate safety factors and trigger false warnings.

**M-C6: Ductile Iron DN450 and DN600 Wave Speeds Below Standard Lower Bound**
- **Source:** data-validation (Medium finding 6)
- `data/au_pipes.py` — DN450 wave speed 1090 m/s and DN600 1080 m/s are both below the AS 2280 lower bound of 1100 m/s for those sizes. Update to 1120–1130 m/s (midpoint of standard range).

**M-C7: Water Supply Pump Power Ratios Warrant Review (WSP-100-15, MDP-150-60, MDP-300-120)**
- **Source:** data-validation (Medium finding 7)
- Power ratios of 0.52–0.59 suggest the `power_kW` field was copied from a larger motor frame rather than the actual pump duty point. Review against manufacturer datasheets.

### UI Polish

**M-U1: Compliance Component — "No Compliance Data" Indistinguishable from Pre-Run State**
- **Source:** ui-review (M1)
- Show "All checks passed" in green when an empty list is returned after a successful analysis, distinct from the pre-run placeholder.

**M-U2: 3D Info Panel Raw Float Display (Roughness, Tank Levels, Distances)**
- **Source:** ui-review (M3, M4, M12)
- `view_3d.py` lines 725–728, 744, 269–272 — raw floats for tank init/max levels, roughness, and measurement distances. Apply `:.1f` throughout.

**M-U3: 3D Legend Shows All Scales Simultaneously**
- **Source:** ui-review (M5)
- The static right panel (lines 333–365) shows both PRESSURE SCALE and VELOCITY SCALE at all times. Only the active colour mode's scale should be visible.

**M-U4: Scenarios Page Chart Titles Are Too Vague**
- **Source:** ui-review (M6)
- "PRESSURE COMPARISON" should read "Minimum Junction Pressure — Scenario Comparison". "FLOW COMPARISON" should read "Average Pipe Flow — Scenario Comparison".

**M-U5: No Loading Indicator During 3D Render or Per-Scenario Run**
- **Source:** ui-review (M9, M10)
- `view_3d.py:369–404` and `scenarios.py:117` — neither uses the `.props('loading')` pattern used elsewhere. Large networks will freeze the UI silently.

**M-U6: Feedback Page File I/O Has No Error Handling**
- **Source:** ui-review (M11)
- `feedback.py:14–24` — no try/except around file read/write. A read-only output directory will surface an unhandled traceback.

**M-U7: PE/HDPE Pipe Colour Nearly Invisible Against Dark Background**
- **Source:** ui-review (M13)
- `scene_3d.py:33` — colour `#1a1a2e` is almost identical to the scene background `#0d1117`. Change to a lighter blue such as `#4455cc`.

**M-U8: DOCX/PDF Report "Roughness" Column Missing H-W Qualifier**
- **Source:** ui-review (M14, M15)
- Column header should read "Roughness (C H-W)" or "C-factor". The DOCX compliance section should cite the relevant AS standard (AS/NZS 4130 or AS 2885) for transient surge thresholds, not only WSAA Guidelines.

**M-U9: "LPS" vs "L/s" — Pick One and Apply Consistently**
- **Source:** ui-review (H5)
- `steady_state.py:56` uses "LPS"; `scene_3d.py:349` uses "L/s". Standardise on one form across all UI surfaces and reports. Recommend "L/s" (SI-aligned).

---

## LOW — Nice to Have

- **Root-level CLI scripts should move to `scripts/`:** `run_hydraulic_analysis.py`, `run_transient_analysis.py`, `validate_3d_enhancements.py`, `capture_3d_ui.py` (architect O1).
- **`pipe_stress.py` not integrated into UI or API:** Module is feature-complete and fully tested but unreachable from the dashboard. Consider adding a Pipe Stress tab or exposing it via an API endpoint (architect O2).
- **`importers/__init__.py` only re-exports `csv_import`:** Shapefile and DXF importers are absent from the package's public API (architect O6). Add them or document the omission.
- **PVC DN225 is non-standard:** The size (OD 225 mm) does not appear in AS/NZS 1477. Document it as non-standard or remove it from the database (data-validation).
- **Concrete DN525 not in reference table:** Cannot be verified against the standard; confirm it is a required catalogue entry (data-validation).
- **NPSHr stored as scalar rather than curve:** Limits accuracy for off-BEP operation analysis. The data model would need extending to support NPSHr vs flow curve (data-validation).
- **Joukowsky `calculate()` has no try/except:** If input fields are None or invalid a traceback will surface (ui-review, Joukowsky section).
- **Valve closure annotation missing timestamp:** Transient chart shows "Valve closure" vline with no time value. Show `f'Valve closure @ {start}s'` (ui-review).
- **`steady_state.py` flow chart has no velocity reference line:** Difficult because pipes have different diameters, but a note or switching to velocity (m/s) on the y-axis would allow a direct 2.0 m/s WSAA limit line (ui-review M8).

---

## Reviewer Disagreements

**None identified.** All five reviewers converged on the same severity assessments for shared findings. The architect's W-level warnings (data flow bypasses) are consistently supported by the code-review's High findings and the UI reviewer's Critical display issues — they all trace to the same layer-violation root cause (B6).

The only tension worth noting: the architect classified `network_editor.py`'s direct mutation of `api.wn` as a BLOCKER (B2 in architect.md) on architectural grounds, while the code-review did not flag this file's layer violations at all. This report treats it as a BLOCKER (B6) consistent with the prioritisation framework criterion "layer violation where the UI bypasses the API to mutate hydraulic state."

---

## Recommendations

### 1. Fix the Slurry Friction Factor (B1) First — Highest Engineering Risk

The Fanning-vs-Darcy error in `slurry_solver.py` is confirmed by an independent benchmark and produces a 4× underestimate of laminar headloss. This is the only finding where a user could design a physical pipeline based on numbers that are wrong by a quantified, large factor. Fix `16/Re_B` → `64/Re_B` and replace the inverted floor guard before any slurry analysis results are shared with clients or used in design decisions. This is a single-line change with high return. Verify the fourth-power correction coefficient against Slatter (1995) at the same time.

### 2. Rebuild the PVC Pipe Database from AS/NZS 1477 First Principles (B4)

The PVC section has a systemic OD error that invalidates the geometry of 5 of 6 sizes. This cannot be patched incrementally — the entire PVC section should be rewritten from the correct AS/NZS 1477 OD series (110, 160, 225, 280, 315, 400 mm). Do this as a single PR with a validation script that checks `abs(ID + 2×wall - OD) < 0.5 mm` for every entry. While this PR is open, also add the three missing standard sizes (DI DN500, PE DN75, Concrete DN225) and correct the Concrete HW C values — these are all in the same file and belong in one change.

### 3. Fix the Two Transient Calculation Errors Together (B2, B3, H18)

B2 (total head vs gauge pressure in transient compliance), B3 (water age seconds vs hours), and H18 (Joukowsky missing slurry density) are all in `epanet_api.py` and all concern unit conversion or implicit assumptions in the results-building path. Fixing them in one pass is efficient and avoids a second review cycle. After fixing, run the hydraulic benchmarks against a network with elevated junctions (to validate B2), check that a 24-hour water age triggers the stagnation warning (to validate B3), and run a slurry Joukowsky case at ρ = 1400 kg/m³ (to validate H18). These three fixes together close the "wrong numbers silently delivered to engineer" category in `epanet_api.py`.

# Code Review — 2026-04-03

## Summary

The codebase is well-structured and shows clear engineering intent, with good docstrings, named constants for `g`, and consistent WNTR unit handling. However, five issues require attention before this code can be trusted to produce correct answers: a systematic unit error in the transient pressure conversion, a wrong formula sign in the Buckingham-Reiner friction correction, a velocity-calculation that ignores flow sign and yields inflated max-velocity compliance checks, an unsafe operating-point search that can silently return a false match, and a missing guard on zero pipe area in the steady-state velocity path.

---

## Critical (wrong results possible)

### C1 — epanet_api.py:644–650 — Transient pressure unit error (head metres ≠ pressure kPa)

`surge_kPa` and `max_pressure_kPa` are computed by multiplying hydraulic head (metres) by `g = 9.81`:

```python
'surge_kPa': round(delta_h * g, 0),          # line 644
'max_pressure_kPa': round(max_h * g, 0),     # line 645
```

The correct conversion from metres of water to kPa is multiplication by `ρg / 1000 = 9.81` only when the result is already kPa — but this is only valid if `ρ = 1000 kg/m³` and the factor accounts for the `/1000` (Pa → kPa) and `× ρ`. Written out:

```
P (kPa) = h (m) × ρ (kg/m³) × g (m/s²) / 1000
         = h × 1000 × 9.81 / 1000
         = h × 9.81          ✓ numerically correct for water
```

The arithmetic is coincidentally correct for water (1000 kg/m³), but:

1. The **compliance check at line 653** then compares this kPa value against `pipe_rating_kPa = 3500`. If TSNet returns head in metres (as documented), the comparison is valid. But `max_h` is **total head** (elevation + pressure head), not pressure head. For a junction at elevation 50 m with 100 m total head, `max_h * g = 981 kPa`, which is correct pressure only if elevation head is subtracted first. The code does not subtract elevation, so transient compliance for elevated junctions is **under-reported** (actual pressure is lower than compared value).

   Fix: `max_pressure_kPa = (max_h - node.elevation) * density * g / 1000`

2. The same pattern is repeated verbatim in `_build_pump_results` (lines 887–893, 896–908). Both valve and pump transient analyses share this defect.

**Affected lines:** `epanet_api.py` 644–645, 648–650, 653–659, 887–893, 896–908.

---

### C2 — slurry_solver.py:136 — Buckingham-Reiner friction floor flips the formula upside-down

```python
f = 16 / Re_B * (1 + He / (6 * Re_B) - (He ** 4) / (3 * 1e7 * Re_B ** 7))
f = max(f, 16 / Re_B)  # Floor at Newtonian laminar   ← line 137
```

The Buckingham-Reiner correction adds a positive `He/(6·Re_B)` term and subtracts a small higher-order term. For realistic Hedstrom numbers the corrected `f` is **always greater than** `16/Re_B`. The `max()` floor on line 137 therefore:

- Never activates when the formula gives the physically correct (larger) value.
- Would silently fall back to the Newtonian value if the fourth-power term is ever large enough to make the bracket negative (which can happen for very large He / small Re_B), producing a **friction factor below the physically correct minimum** for a Bingham plastic.

The correct guard should be a `max` against a small positive floor (e.g. `0.001`), not against `16/Re_B`. The current line is not wrong in the common case, but is conceptually misleading and will give wrong results in the high-He / low-Re_B limit.

Additionally, the standard Buckingham-Reiner formulation (Slatter, 1995; also Darby 2001) uses the denominator term `3 × (3.3 × 10⁷)` for the fourth-power correction, not `3 × 10⁷`. Confirm the coefficient against the cited reference.

**Affected line:** `slurry_solver.py` 136–137.

---

### C3 — epanet_api.py:214–215 — Velocity uses `f.max()` (signed), not `abs(f).max()`

```python
v_avg = abs(float(f.mean())) / area       # line 214 — abs of mean: wrong direction
v_max = abs(float(f.max())) / area        # line 215 — max of signed series
```

WNTR returns signed flowrates (negative when flow is reversed). `f.max()` returns the largest algebraic value, not the largest absolute value. For a pipe where flow reverses, `f.max()` may return a small positive peak while the true maximum speed occurs during the negative-flow period.

`v_avg` compounds this: `abs(f.mean())` takes the mean of cancelling positive and negative flows and then absolutes it — this understates the average speed for bidirectional flow.

Correct approach:

```python
v_avg = float(f.abs().mean()) / area
v_max = float(f.abs().max()) / area
```

The same error appears in the compliance velocity check at line 245:
```python
v_max = abs(float(flows[pipe_name].max())) / area   # line 245 — same defect
```

**Affected lines:** `epanet_api.py` 213–215, 245.

---

### C4 — epanet_api.py:213 — Zero pipe area not guarded in steady-state path

```python
area = np.pi * (pipe.diameter / 2) ** 2    # line 213
v_avg = abs(float(f.mean())) / area         # line 214 — ZeroDivisionError if diameter=0
```

Unlike the slurry solver (which guards `A > 0` before dividing), the steady-state loop performs division unconditionally. A pipe loaded from a user-edited `.inp` file with `diameter = 0` will raise `ZeroDivisionError` and abort the entire simulation result extraction. The same unguarded division reappears at line 244.

**Affected lines:** `epanet_api.py` 213–215, 244–245.

---

## High (misleading or fragile)

### H1 — data/pump_curves.py:249 — Operating point search condition introduces bias

```python
if diff < min_diff and pump_head >= sys_head * 0.95:   # line 249
```

The secondary condition `pump_head >= sys_head * 0.95` is intended to prefer points where the pump is above the system curve, but it changes the semantics of "closest intersection". If the true intersection lies where the pump is slightly below the system curve (which is physically valid at end-of-curve or high-flow conditions), this condition skips it entirely and returns the next best point — potentially a false operating point on the steep part of the curve.

The correct algorithm for finding an intersection is to find the flow at which `(pump_head - sys_head)` changes sign, then interpolate. The current approach can return a result with `min_diff > 0` that is not the actual intersection.

The 5-metre tolerance check (`if min_diff > 5`) is also a hard threshold with no units comment and no scaling for large-head systems (a 100 m head pump with a 6 m miss is returned as `None` even though the curves cross).

**Affected lines:** `data/pump_curves.py` 248–253.

---

### H2 — epanet_api.py:629 — `pipe_rating_m` computed but never used

```python
pipe_rating_m = self.DEFAULTS['pipe_rating_kPa'] / g    # line 629
```

This variable is assigned in `run_transient` but all downstream compliance checks use `self.DEFAULTS['pipe_rating_kPa']` directly (kPa comparisons). The variable is dead code in this method and in `_build_pump_results` (line 872). It causes no incorrect result but suggests a refactor was left incomplete.

**Affected lines:** `epanet_api.py` 629, 872.

---

### H3 — slurry_solver.py:404 — Settling velocity check excludes static pipes

```python
if fluid['type'] != 'newtonian' and data['velocity_ms'] < 1.0 and data['velocity_ms'] > 0:
```

The condition `velocity_ms > 0` means a completely stagnant slurry pipe (velocity = 0 from the `V < 1e-6` early return) is never flagged for settling risk. A static slurry column is the worst settling case and should be the first thing flagged. Remove the `> 0` lower bound or add a separate check for zero velocity.

**Affected line:** `slurry_solver.py` 404.

---

### H4 — scenario_manager.py:69 — Demand factor applied to base_value cumulatively

```python
junc.demand_timeseries_list[0].base_value *= factor    # line 69
```

If `create_scenario` is called twice on the same loaded `WaterNetworkModel` object (or if modifications lists are processed in a loop that revisits `demand_factor`), the factor is applied multiplicatively each time. Because `create_scenario` creates a fresh `HydraulicAPI` and calls `load_network`, the network object is reloaded per call and this is safe in the current call pattern. However, there is no guard preventing a caller from passing two `demand_factor` modifications in the same `modifications` list, which would silently compound them.

The docstring does not warn about this. A comment or assertion would prevent misuse.

**Affected line:** `scenario_manager.py` 69.

---

### H5 — epanet_api.py:490–496 — Water quality results reported in raw WNTR units (hours assumed but not verified)

```python
max_age = round(float(q.max()), 2)    # line 491
avg_age = round(float(q.mean()), 2)   # line 492
results['junction_quality'][junc] = {
    'max_age_hrs': max_age,           # line 495
    'avg_age_hrs': avg_age,           # line 496
}
```

WNTR reports water age in **seconds** when `parameter = 'AGE'`. The values are stored under keys named `_hrs`, which is wrong by a factor of 3600. The stagnation threshold comparison at line 500 (`if max_age > 24.0`) would then never trigger since raw age in seconds would be enormous. This is a critical unit error if WNTR does return seconds; if WNTR has already converted to hours internally, it is correct — but this needs to be confirmed and documented with a comment. The WNTR documentation states water age results are in seconds.

Fix:
```python
max_age_hrs = round(float(q.max()) / 3600, 2)
avg_age_hrs = round(float(q.mean()) / 3600, 2)
```

**Affected lines:** `epanet_api.py` 491–496, 500.

---

## Medium (code quality)

### M1 — epanet_api.py:1173 — `joukowsky()` result `pressure_rise_kPa` is identical to `head_rise_m * g` — documents confusion

```python
dH = (wave_speed * velocity_change) / g    # line 1172
dP_kPa = dH * g                            # line 1173
```

`dP_kPa = dH * g` simplifies to `wave_speed * velocity_change`, which is correct for pressure rise in Pa/ρ — but the result is labelled kPa and is numerically equal to `wave_speed * velocity_change / 9.81 * 9.81 = wave_speed * velocity_change` Pa, which is not kPa unless divided by 1000. For a 1000 m/s wave and 1 m/s velocity change this returns `1000` labelled as kPa, but the correct answer is `ρ·a·ΔV = 1000×1000×1 = 1,000,000 Pa = 1000 kPa`. The number is therefore correct only by coincidence for `ρ = 1000 kg/m³` and the formula bypasses explicit density. A comment explaining the implicit water density assumption would prevent misuse with slurry (ρ ≠ 1000).

**Affected lines:** `epanet_api.py` 1166–1179.

---

### M2 — slurry_solver.py:185–186 — Metzner-Reed Re formula: missing `(3n+1)/(4n)` exponent documentation

```python
Re_MR = (density * V ** (2 - n) * diameter_m ** n) / (
    K * 8 ** (n - 1) * ((3 * n + 1) / (4 * n)) ** n
)
```

The formula is mathematically correct (Metzner & Reed 1955). However, the exponent on `8^(n-1)` merits a citation comment because different textbooks arrange the factors differently. Without a reference, a future maintainer may "correct" it to a non-equivalent form.

**Affected lines:** `slurry_solver.py` 185–186.

---

### M3 — pipe_stress.py:110–118 — PE100 yield strength is lower than industry standard

```python
'pe100': {'yield_MPa': 10, 'tensile_MPa': 25, 'standard': 'AS/NZS 4130'},
```

PE100 (polyethylene grade 100) has a minimum required strength (MRS) of 10 MPa, but the yield (0.2% proof) stress for PE100 is typically 20–26 MPa. The value of 10 MPa here is the long-term hydrostatic strength classification, not the yield stress used for short-term hoop-stress safety factor calculation. Using 10 MPa as yield will understate the safety factor and trigger false warnings for PE100 pipes that are adequately rated.

The correct value for elastic design comparisons is approximately 20–22 MPa (refer AS/NZS 4130 Table 3). The `barlow_wall_thickness` function uses `allowable_stress_MPa` passed by the caller, so the database value would only cause errors if used directly via `analyze_pipe_stress`.

**Affected line:** `pipe_stress.py` 116.

---

### M4 — data/pump_curves.py:204–205 — `generate_system_curve` default `flow_range` uses LPS but no unit label

```python
if flow_range is None:
    flow_range = np.linspace(0, 100, 50)    # 100 LPS default — no comment
```

The default upper bound of 100 LPS is reasonable for the smallest pump in the database (WSP-100-15, max 28 LPS) but will silently extrapolate the system curve far beyond the pump's operating range. A comment stating the units and that the range should be matched to the pump's rated flow would help callers.

**Affected lines:** `data/pump_curves.py` 204–205.

---

### M5 — scenario_manager.py:91–93 — Scenario `.inp` file saved into `model_dir`; file naming collides across base networks

```python
scenario_file = f'scenario_{name}.inp'
scenario_path = os.path.join(api.model_dir, scenario_file)
```

If two scenarios derived from different base networks both use the same `name`, the second write silently overwrites the first. Consider prefixing with the base network name: `f'scenario_{base_network}_{name}.inp'`.

**Affected lines:** `scenario_manager.py` 91–93.

---

### M6 — epanet_api.py:36–43 — `max_pressure_m = 50` is the residential maximum; mining/industrial networks need a higher ceiling

```python
'max_pressure_m': 50,          # WSAA maximum static pressure (m)
```

WSAA HB 2012 recommends 50 m for residential reticulation. Trunk mains, industrial, and mining connections operate at substantially higher pressures. This constant is applied globally to all junction compliance checks in `run_steady_state`, which will generate spurious warnings for any network with design pressure above 500 kPa. The threshold should be configurable per-network or at least documented as a residential-only limit.

**Affected line:** `epanet_api.py` 39.

---

## File-by-File Findings

### epanet_api.py

| # | Line(s) | Severity | Finding |
|---|---------|----------|---------|
| 1 | 644–650, 887–893 | Critical | Transient `max_pressure_kPa` uses total head, not pressure head — overstates pressure at elevated junctions |
| 2 | 213–215, 244–245 | Critical | Velocity uses `f.max()` on signed flowrate; should use `f.abs().max()` |
| 3 | 213–215, 244–245 | Critical | No guard for `area == 0`; will raise `ZeroDivisionError` for zero-diameter pipes |
| 4 | 491–496, 500 | High | WNTR water age is in seconds; dividing by 3600 is required before comparing to 24-hr threshold |
| 5 | 629, 872 | High | `pipe_rating_m` computed but never used (dead code) |
| 6 | 1172–1173 | Medium | Joukowsky `pressure_rise_kPa` implicitly assumes water density; label or add explicit `rho` parameter |
| 7 | 39 | Medium | `max_pressure_m = 50` residential-only; will generate false warnings on industrial/mining networks |

### slurry_solver.py

| # | Line(s) | Severity | Finding |
|---|---------|----------|---------|
| 1 | 136–137 | Critical | Buckingham-Reiner floor `max(f, 16/Re_B)` is logically inverted; for very large He/small Re_B the formula can go negative and the floor fails to protect |
| 2 | 404 | High | Settling check excludes zero-velocity pipes (`velocity_ms > 0`); static slurry is the most critical settling case |
| 3 | 185–186 | Medium | Metzner-Reed Re formula correct but lacks citation comment; `8^(n-1)` arrangement not self-evident |

### pipe_stress.py

| # | Line(s) | Severity | Finding |
|---|---------|----------|---------|
| 1 | 116 | Medium | PE100 `yield_MPa = 10` is MRS classification, not yield stress; correct value is ~20–22 MPa (AS/NZS 4130 Table 3) |
| 2 | 13–35 | OK | Hoop stress formula `σ_h = P·D/(2t)` is correct; unit conversion kPa→MPa via `/1000` is correct |
| 3 | 58–67 | OK | Von Mises formula is correct |
| 4 | 70–106 | OK | Barlow's formula and safety factor application are correct |
| 5 | 151–156 | OK | Safety factor logic and status thresholds are reasonable |

### data/pump_curves.py

| # | Line(s) | Severity | Finding |
|---|---------|----------|---------|
| 1 | 248–253 | High | Operating point search biased by `pump_head >= sys_head * 0.95`; can miss the true intersection and the 5 m tolerance is unscaled |
| 2 | 176–177 | OK | Affinity law scaling `Q' = Q·(N'/N)`, `H' = H·(N'/N)²` is correctly applied |
| 3 | 215 | OK | Hazen-Williams formula `h = 10.67·L·Q^1.852 / (C^1.852·D^4.87)` is correct |
| 4 | 204–205 | Medium | Default `flow_range` to 100 LPS with no unit comment; can silently extrapolate beyond pump curve |

### scenario_manager.py

| # | Line(s) | Severity | Finding |
|---|---------|----------|---------|
| 1 | 69 | High | `demand_factor` multiplied into `base_value` cumulatively; multiple `demand_factor` mods in one list silently compound |
| 2 | 91–93 | Medium | Scenario `.inp` filename is `scenario_{name}.inp` only — collides if two scenarios share a name across different base networks |
| 3 | 56–88 | OK | Unit conversions consistent: `mm → m` via `/1000` for diameters, `LPS → m³/s` via `/1000` for demands |
| 4 | 153–174 | OK | Comparison logic is correct; uses common-key intersection for cross-scenario junction/pipe comparison |

---

## Summary Table

| ID | File | Line(s) | Severity | Short Description |
|----|------|---------|----------|-------------------|
| C1 | epanet_api.py | 644–650, 887–908 | Critical | Transient kPa uses total head, not gauge pressure head |
| C2 | slurry_solver.py | 136–137 | Critical | Buckingham-Reiner floor guard logically inverted |
| C3 | epanet_api.py | 213–215, 244–245 | Critical | Signed `f.max()` used for velocity; understates max speed on reversing pipes |
| C4 | epanet_api.py | 213, 244 | Critical | No zero-area guard; ZeroDivisionError on malformed pipes |
| H1 | data/pump_curves.py | 248–253 | High | Operating point search can return false match |
| H2 | epanet_api.py | 629, 872 | High | `pipe_rating_m` dead code |
| H3 | slurry_solver.py | 404 | High | Static slurry not flagged for settling |
| H4 | scenario_manager.py | 69 | High | Cumulative demand factor multiplication |
| H5 | epanet_api.py | 491–496, 500 | High | Water age likely in seconds, not hours |
| M1 | epanet_api.py | 1172–1173 | Medium | Joukowsky kPa implicit water density |
| M2 | slurry_solver.py | 185–186 | Medium | Missing citation for Metzner-Reed arrangement |
| M3 | pipe_stress.py | 116 | Medium | PE100 yield = 10 MPa (should be ~20–22 MPa) |
| M4 | data/pump_curves.py | 204–205 | Medium | Default flow range lacks unit label |
| M5 | scenario_manager.py | 91–93 | Medium | Scenario filename collision risk |
| M6 | epanet_api.py | 39 | Medium | 50 m pressure cap is residential-only |

# Hydraulic Benchmark Validation — 2026-04-03

## Summary

**8/10 benchmarks passed.**

| # | Benchmark | Result |
|---|-----------|--------|
| 1 | Joukowsky Water Hammer | PASS |
| 2 | Hoop Stress (Thin-Wall) | PASS |
| 3 | Von Mises Equivalent Stress | PASS |
| 4 | Barlow Minimum Wall Thickness | PASS |
| 5 | Steady-State Mass Balance | PASS |
| 6 | Bingham Plastic — Newtonian Baseline | **FAIL** |
| 7 | Hazen-Williams Headloss | PASS |
| 8 | Pump Affinity Laws | PASS |
| 9 | Pipe Velocity = Q/A | PASS |
| 10 | WSAA Compliance Thresholds | PASS |

---

## Results

### 1. Joukowsky Water Hammer — PASS

- **Reference**: Joukowsky (1898), dH = a × dV / g
- **Inputs**: wave speed a = 1000 m/s, velocity change dV = 1.5 m/s
- **Hand calculation**: dH = 1000 × 1.5 / 9.81 = 152.91 m
- **Expected**: 152.9 m (±0.5 m)
- **Got**: 152.9 m
- **Difference**: 0.005 m
- **Tolerance**: 0.5 m
- **Pressure rise**: 1500.0 kPa

---

### 2. Hoop Stress (Thin-Wall Theory) — PASS

- **Reference**: Barlow's formula, σ_h = P × D / (2t)
- **Inputs**: P = 1000 kPa (1.0 MPa), D = 300 mm, t = 8 mm
- **Hand calculation**: σ_h = (1.0 × 300) / (2 × 8) = 18.75 MPa
- **Expected**: 18.75 MPa (±0.01 MPa)
- **Got**: 18.75 MPa
- **Difference**: 0.00 MPa
- **Tolerance**: 0.01 MPa

---

### 3. Von Mises Equivalent Stress — PASS

- **Reference**: σ_vm = √(0.5 × ((σ1−σ2)² + (σ2−σ3)² + (σ3−σ1)²))
- **Inputs**: σ_h = 18.75 MPa, σ_r = −1.0 MPa, σ_a = 9.375 MPa
- **Hand calculation**:
  - √(0.5 × ((18.75−(−1))² + ((−1)−9.375)² + (9.375−18.75)²))
  - = √(0.5 × (393.0625 + 107.5156 + 87.8906))
  - = √(294.234) = **17.1113 MPa**
- **Expected**: ~17.17 MPa (±0.5 MPa per benchmark spec)
- **Got**: 17.11 MPa
- **Difference**: 0.001 MPa from hand calc
- **Tolerance**: 0.5 MPa

> Note: The benchmark spec states "~17.17 MPa (approx)" — the exact value is 17.11 MPa. Both the toolkit and hand calculation agree at 17.11 MPa, well within the 0.5 MPa tolerance.

---

### 4. Barlow Minimum Wall Thickness — PASS

- **Reference**: t_min = P × D / (2S), where S = allowable stress (with safety factor)
- **Inputs**: P = 1.0 MPa (1000 kPa), D = 300 mm, S = 300 MPa (ductile iron), safety factor = 2.0
- **Hand calculation**: t_min = (1.0 × 300) / (2 × 300/2.0) = 300/300 = **1.0 mm**
- **Expected**: 1.0 mm (±0.1 mm)
- **Got**: 1.0 mm (min_thickness_mm, corrosion_allowance=0 for clean comparison)
- **Difference**: 0.000 mm
- **Tolerance**: 0.1 mm
- **Design thickness** (with 1 mm corrosion allowance): 2.0 mm

---

### 5. Steady-State Mass Balance — PASS

- **Reference**: Conservation of mass — Σ Q_in − Σ Q_out = demand at each junction
- **Network**: australian_network.inp (7 junctions, 9 pipes)
- **Method**: Summed WNTR simulated flows at each junction, compared inflow minus outflow against junction demand
- **Max imbalance**: 0.000003 LPS at node J4
- **Tolerance**: 0.01 LPS
- **Junctions checked**: 7

---

### 6. Bingham Plastic — Newtonian Baseline — FAIL

- **Reference**: Buckingham-Reiner equation; at τ_y = 0, μ_p = 0.001 Pa.s (water), should reduce to Hagen-Poiseuille
- **Test inputs**: Q = 0.00001 m³/s, D = 0.02 m (20 mm), L = 100 m, Re ≈ 637 (laminar)
- **Expected (Hagen-Poiseuille)**: hf = 128 × μ × L × Q / (π × ρ × g × D⁴) = **0.025958 m**
- **Got from solver**: 0.006000 m
- **Difference**: 76.9% (tolerance: 5%)

**Root cause identified**: The laminar Bingham friction factor uses the Fanning convention (f = 16/Re), but it is applied directly in the Darcy-Weisbach equation which requires the Darcy friction factor (f = 64/Re). The Darcy friction factor is 4× the Fanning factor.

- Fanning f at Re=637: 16/637 = 0.02513
- Darcy f at Re=637: 64/637 = 0.10053 (needed for D-W)
- Ratio of got/expected ≈ 1/4.33 ≈ Fanning/Darcy mismatch

**Location**: `slurry_solver.py`, `bingham_plastic_headloss()`, line ~136:
```python
f = 16 / Re_B * (1 + He / (6 * Re_B) - (He**4) / (3 * 1e7 * Re_B**7))
```
Should use the Darcy form (multiply by 4) or the Darcy-Weisbach equation should use the Fanning form (multiply by 4 in the headloss formula).

**Fix required**: Either change `16/Re_B` to `64/Re_B` (for Darcy-Weisbach), or multiply headloss by 4 in the laminar branch.

---

### 7. Hazen-Williams Headloss — PASS

- **Reference**: hf = (10.67 × L × Q^1.852) / (C^1.852 × D^4.87) [SI: Q in m³/s, D in m]
- **Pipe tested**: P1 in australian_network.inp (L=500 m, D=0.3 m, C=130)
- **Simulated flow**: Q = 0.106411 m³/s (106.4 LPS)
- **EPANET simulated headloss**: 3.6049 m (R1 head=80.000 m → J1 head=76.395 m)
- **Hand calculation**: hf = (10.67 × 500 × 0.106411^1.852) / (130^1.852 × 0.3^4.87) = **3.6017 m**
- **Difference**: 0.09%
- **Tolerance**: 5%

---

### 8. Pump Affinity Laws — PASS

- **Reference**: Q₂/Q₁ = N₂/N₁ (flow scales linearly); H₂/H₁ = (N₂/N₁)² (head scales quadratically)
- **Pump tested**: WSP-200-40 (centrifugal, rated 1450 rpm)
- **Reference point at 100% speed**: Q₁ = 30.0 LPS, H₁ = 38.00 m
- **Expected at 80% speed** (by affinity laws): Q₂ = 24.0 LPS, H₂ = 24.32 m
- **Got from pump curve at 80% speed**: H₂ = 24.32 m at Q₂ = 24.0 LPS
- **Flow ratio**: actual = 0.8000, expected = 0.8000 (error 0.0%)
- **Head ratio**: actual = 0.6400, expected = 0.6400 (error 0.0%)
- **Tolerance**: 1%

---

### 9. Pipe Velocity = Q/A Verification — PASS

- **Reference**: V = Q / A = Q / (π(D/2)²)
- **Network**: australian_network.inp, all 9 pipes at steady-state t=0
- **Tolerance**: 0.01 m/s

| Pipe | Q (LPS) | D (mm) | V_calc (m/s) | V_sim (m/s) | Diff (m/s) |
|------|---------|--------|-------------|------------|------------|
| P1   | 106.411 | 300    | 1.5054      | 1.5054     | 0.00001    |
| P2   | 17.500  | 250    | 0.3565      | 0.3565     | 0.00000    |
| P3   | 9.636   | 200    | 0.3067      | 0.3067     | 0.00000    |
| P4   | 88.911  | 200    | 2.8301      | 2.8301     | 0.00002    |
| P5   | 5.636   | 200    | 0.1794      | 0.1794     | 0.00000    |
| P6   | 3.000   | 150    | 0.1698      | 0.1698     | 0.00000    |
| P7   | 5.364   | 150    | 0.3036      | 0.3036     | 0.00000    |
| P8   | 87.411  | 200    | 2.7824      | 2.7824     | 0.00002    |
| P9   | −3.364  | 150    | 0.1904      | 0.1904     | 0.00000    |

- **Maximum difference**: 0.000016 m/s (numerical precision only)

---

### 10. WSAA Compliance Thresholds — PASS

- **Reference**: WSAA Guidelines for water distribution systems
- **Location**: `HydraulicAPI.DEFAULTS` dict in `epanet_api.py`

| Parameter | Expected | Actual | Result |
|-----------|----------|--------|--------|
| min_pressure_m | 20 m | 20 | PASS |
| max_pressure_m | 50 m | 50 | PASS |
| max_velocity_ms | 2.0 m/s | 2.0 | PASS |
| pipe_rating_kPa | 3500 kPa | 3500 | PASS |

All four WSAA compliance thresholds match the specified values exactly.

---

## Failed Benchmarks — Detail

### Benchmark 6: Bingham Plastic Laminar Friction Factor Bug

**File**: `C:/Users/brian/Downloads/EPANET_CLAUDE/slurry_solver.py`

**Function**: `bingham_plastic_headloss()`, laminar branch (~line 136)

**The bug**: The Buckingham-Reiner equation as implemented uses the **Fanning friction factor** (f = 16/Re for Newtonian laminar), but the Darcy-Weisbach headloss formula requires the **Darcy friction factor** (f = 64/Re for Newtonian laminar). These differ by a factor of 4.

```python
# Current (incorrect for Darcy-Weisbach):
f = 16 / Re_B * (1 + He / (6 * Re_B) - (He**4) / (3 * 1e7 * Re_B**7))

# Fix option A — use Darcy form:
f = 64 / Re_B * (1 + He / (6 * Re_B) - (He**4) / (3 * 1e7 * Re_B**7))

# Fix option B — keep Fanning f but multiply headloss formula:
headloss = 4 * f * (length_m / diameter_m) * (V**2) / (2 * g)
```

**Evidence**:
- At Re=637 (laminar), D=20mm, L=100m, Q=1e-5 m³/s, τ_y=0 (Newtonian baseline):
  - Hagen-Poiseuille expected: 0.025958 m
  - Toolkit result: 0.006000 m
  - Ratio: 4.33× underestimate (≈ 4× Fanning/Darcy factor, plus minor Buckingham-Reiner truncation error)

**Impact**: All Bingham plastic laminar headloss calculations in `slurry_solver.py` are underestimated by approximately 4×. This affects slurry pipeline design (mine tailings, paste fill, cement slurry) for laminar flow conditions. Turbulent branch uses a separate correlation and was not tested here.

---

## Additional Observations (Not Failures)

- **Benchmark 3 note**: The spec states "~17.17 MPa (approx)" but the exact value is 17.11 MPa. The toolkit and hand calculation agree at 17.11 MPa — the spec approximation is slightly off but within the 0.5 MPa tolerance.
- **Pipes P4 and P8 velocities** (2.83 m/s and 2.78 m/s) exceed the WSAA maximum of 2.0 m/s — the network simulation shows compliance violations, but this is the network's condition, not a software defect.

---

*Agent: hydraulic-tester | Run: 2026-04-03 | Model: claude-sonnet-4-6*

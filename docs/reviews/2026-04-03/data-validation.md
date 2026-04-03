# Data Validation — 2026-04-03

**Validator:** Data Validator Agent  
**Files checked:** `data/au_pipes.py`, `data/pump_curves.py`  
**Standards referenced:** AS 2280, AS/NZS 1477, AS/NZS 4130, AS 4058

---

## Summary

- **Pipe database entries checked:** 29 entries across 4 materials
- **Pump entries checked:** 7 pumps, 5 properties each
- **Pipe discrepancies found:** 27 (spanning 4 categories: missing entries, wrong IDs, wrong walls, wrong HW C values)
- **Pump discrepancies found:** 6 of 7 pumps have power/curve inconsistencies; 0 monotonicity failures

---

## Discrepancies — Pipe Database

### Ductile Iron (AS 2280, Class K9)

| Material | DN | Property | Database Value | Standard Value | Standard Ref |
|---|---|---|---|---|---|
| Ductile Iron | 375 | internal_diameter_mm | 390.4 mm | 381.4 mm (OD 397 − 2×7.8) | AS 2280 |
| Ductile Iron | 450 | internal_diameter_mm | 468.0 mm | 462.8 mm (OD 480 − 2×8.6) | AS 2280 |
| Ductile Iron | 450 | wave_speed_ms | 1090 m/s | 1100–1160 m/s | AS 2280 |
| Ductile Iron | 500 | ALL FIELDS | MISSING | Entry required | AS 2280 |
| Ductile Iron | 600 | internal_diameter_mm | 621.6 mm | 615.2 mm (OD 635 − 2×9.9) | AS 2280 |
| Ductile Iron | 600 | wave_speed_ms | 1080 m/s | 1100–1160 m/s | AS 2280 |

**Notes on DI discrepancies:**

- **DN375 ID:** The DB stores 390.4 mm. The standard OD is 397 mm; with the standard K9 wall of 7.8 mm the correct ID is 381.4 mm. The DB wall is listed as 7.9 mm — one extra tenth — yet the ID is 9 mm too wide, suggesting the ID was computed from a different (larger) OD. The wall value of 7.9 mm is within 0.1 mm of the standard 7.8 mm and can be considered acceptable rounding, but the ID is wrong.
- **DN450 ID:** DB shows 468.0 mm; correct is 480 − 2×8.6 = 462.8 mm. The ID is 5.2 mm too wide.
- **DN450 wave speed:** 1090 m/s falls below the standard lower bound of 1100 m/s.
- **DN500 missing:** AS 2280 lists DN500 (OD 532, wall 9.0 mm, ID 514.0 mm, wave 1100–1160 m/s). The database skips directly from DN450 to DN600.
- **DN600 ID:** DB shows 621.6 mm; correct is 635 − 2×9.9 = 615.2 mm. The ID is 6.4 mm too wide.
- **DN600 wave speed:** 1080 m/s is below the standard lower bound of 1100 m/s. The wave speed across DN375–DN600 is trending downward (1100→1090→1080) when the standard specifies 1100–1160 for those sizes.

---

### PVC (AS/NZS 1477)

The PVC section has a systemic root-cause error: for most sizes the implied OD (= ID + 2×wall) does not match the AS/NZS 1477 OD series. This causes both the internal diameter and the wall thickness to be wrong for five of the six standard sizes.

**Implied ODs versus standard ODs:**

| DN | DB implied OD (ID+2×wall) | Standard OD (AS/NZS 1477) | Match? |
|---|---|---|---|
| 100 | 108.0 mm | 110 mm | NO — 2 mm too small |
| 150 | 160.0 mm | 160 mm | OK |
| 200 | 212.0 mm | 225 mm | NO — 13 mm too small |
| 250 | 250.0 mm | 280 mm | NO — 30 mm too small |
| 300 | 300.0 mm | 315 mm | NO — 15 mm too small |
| 375 | 375.0 mm | 400 mm | NO — 25 mm too small |

The DB appears to have been authored using DN as OD (i.e., using OD = DN for DN≥200), which is incorrect for PVC pipe under AS/NZS 1477. The OD series for PVC exceeds the nominal DN.

**Individual discrepancy table:**

| Material | DN | Property | Database Value | Standard Value | Standard Ref |
|---|---|---|---|---|---|
| PVC | 100 | wall_thickness_mm | 5.6 mm | 5.3 mm (PN18) | AS/NZS 1477 |
| PVC | 100 | internal_diameter_mm | 96.8 mm | 99.4 mm (OD 110 − 2×5.3) | AS/NZS 1477 |
| PVC | 150 | wall_thickness_mm | 6.9 mm | 7.7 mm (PN18) | AS/NZS 1477 |
| PVC | 200 | wall_thickness_mm | 8.8 mm | 10.8 mm (PN18) | AS/NZS 1477 |
| PVC | 200 | internal_diameter_mm | 194.4 mm | 203.4 mm (OD 225 − 2×10.8) | AS/NZS 1477 |
| PVC | 250 | wall_thickness_mm | 6.6 mm | 10.7 mm (PN12) | AS/NZS 1477 |
| PVC | 250 | internal_diameter_mm | 236.8 mm | 258.6 mm (OD 280 − 2×10.7) | AS/NZS 1477 |
| PVC | 300 | wall_thickness_mm | 8.0 mm | 12.1 mm (PN12) | AS/NZS 1477 |
| PVC | 300 | internal_diameter_mm | 284.0 mm | 290.8 mm (OD 315 − 2×12.1) | AS/NZS 1477 |
| PVC | 375 | wall_thickness_mm | 9.7 mm | 15.3 mm (PN12) | AS/NZS 1477 |
| PVC | 375 | internal_diameter_mm | 355.6 mm | 369.4 mm (OD 400 − 2×15.3) | AS/NZS 1477 |

**Additional PVC notes:**
- DN150 is the only size where the OD is correct (160 mm). Its wall of 6.9 mm vs 7.7 mm for PN18 is still wrong, and the ID of 146.2 mm vs expected 144.6 mm is within the 2 mm tolerance.
- DN225 is present in the DB but is **not a standard size** in AS/NZS 1477. It uses OD = 225 mm, wall = 6.0 mm — these values are unverifiable against the standard and the size should be noted as non-standard.
- Wave speeds for PVC (365–425 m/s) are all within the acceptable range and are consistent.
- HW C = 150 throughout — correct.

---

### PE100 (AS/NZS 4130, SDR11 PN16)

The PE section is largely correct. Wall thicknesses and internal diameters match SDR11 (OD/11 rounding) exactly for all seven sizes that are in the standard table.

| Material | DN | Property | Database Value | Standard Value | Standard Ref |
|---|---|---|---|---|---|
| PE | 75 | ALL FIELDS | MISSING | Entry required | AS/NZS 4130 |

**Notes:**
- DN75 (OD 75 mm, wall 6.8 mm, ID 61.4 mm) is absent from the database.
- The database includes three sizes beyond the agent standard table (DN400, DN500, DN630). All three correctly follow SDR11 geometry (implied SDR = exactly 11.0 for all three) and are legitimate AS/NZS 4130 catalogue sizes. These are acceptable extensions.
- Wave speeds for PE (265–310 m/s) are all within the acceptable 200–400 m/s range; they decrease monotonically with size, which is consistent with increasing wall-to-OD ratio under SDR11.

---

### Concrete (AS 4058)

| Material | DN | Property | Database Value | Standard Value | Standard Ref |
|---|---|---|---|---|---|
| Concrete | 225 | ALL FIELDS | MISSING | Entry required | AS 4058 |
| Concrete | 300 | wall_thickness_mm | 44.0 mm | 35–40 mm | AS 4058 |
| Concrete | 375 | wall_thickness_mm | 47.0 mm | 40–45 mm | AS 4058 |
| Concrete | 375 | hazen_williams_c | 120 | 110 | AS 4058 |
| Concrete | 450 | wall_thickness_mm | 51.0 mm | 45–50 mm | AS 4058 |
| Concrete | 450 | hazen_williams_c | 120 | 110 | AS 4058 |
| Concrete | 600 | hazen_williams_c | 120 | 100 | AS 4058 |
| Concrete | 750 | hazen_williams_c | 120 | 100 | AS 4058 |
| Concrete | 900 | hazen_williams_c | 120 | 90 | AS 4058 |

**Notes on Concrete discrepancies:**

- **DN225 missing:** The standard mandates this as the smallest concrete pipe size. The DB starts at DN300.
- **Wall thicknesses at DN300, DN375, DN450:** All are 4–5 mm above the upper bound of the AS 4058 range for that class. The DB values are not grossly wrong (they are ~10% high) but exceed the stated range for Class 2/3.
- **Hazen-Williams C — the most significant error:** The database applies a uniform C = 120 to every concrete size. AS 4058 reduces the C value for larger sizes to reflect surface roughness effects in large-bore pipes: DN375–DN450 should be C = 110, DN600–DN750 should be C = 100, and DN900 should be C = 90. Using C = 120 at DN900 overstates hydraulic capacity by approximately 12% compared to C = 90.
- **Wave speeds** for all concrete sizes (1100–1160 m/s) are within the 1000–1200 m/s standard range. No errors.
- **DN525:** Present in the DB but not in the AS 4058 table reproduced in the agent standard. This is a legitimate intermediate size in some catalogue ranges; it cannot be rejected but is not verifiable against the reference table provided.

---

## Missing Entries Summary

| Material | Missing DN | Expected Properties (from standard) |
|---|---|---|
| Ductile Iron | DN500 | OD 532, wall 9.0 mm, ID 514.0 mm, PN25, C=140, wave 1100–1160 m/s |
| PE | DN75 | OD 75, wall 6.8 mm, ID 61.4 mm, SDR11 PN16, C=150, wave 200–350 m/s |
| Concrete | DN225 | OD ~290, wall 30–35 mm, ID 225 mm, C=120, wave 1000–1200 m/s |

---

## Consistency Checks

### Internal Diameter Monotonicity

All four materials pass. Within each material, internal diameters increase strictly with nominal DN.

### Wall Thickness Monotonicity

- **Ductile Iron:** Wall increases with DN. PASS.
- **PVC:** Wall thickness decreases from DN200 (8.8 mm) to DN225 (6.0 mm) — this is expected because DN225 uses a different pressure class (PN12) with an OD of only 225 mm, but signals a potential usability issue where a user might assume the larger pipe has a thicker wall. The values are internally consistent with their stated pressure classes.
- **PE:** Wall increases with DN (SDR11 means wall proportional to OD). PASS.
- **Concrete:** Wall increases with DN. PASS.

### Hazen-Williams C Value Ranges

| Material | DB Range | Acceptable Range | Result |
|---|---|---|---|
| Ductile Iron | 140–140 | 130–140 (new) | PASS |
| PVC | 150–150 | 145–150 | PASS |
| PE | 150–150 | 140–150 | PASS |
| Concrete | 120–120 | 90–120 (size-dependent) | FAIL — C should decrease for DN375+ |

### Wave Speed Ranges

| Material | DB Range | Acceptable Range | Result |
|---|---|---|---|
| Ductile Iron | 1080–1140 m/s | 1000–1200 m/s | PASS (but DN450 and DN600 below the narrower 1100–1160 range stated for those sizes) |
| PVC | 365–425 m/s | 300–500 m/s | PASS |
| PE | 265–310 m/s | 200–400 m/s | PASS |
| Concrete | 1100–1160 m/s | 1000–1200 m/s | PASS |

---

## Pump Curve Validation

### Monotonicity (head decreasing as flow increases)

All 7 pumps pass. Shut-off head at Q=0 is the maximum for all pumps.

| Pump ID | Monotonic | Shut-off at Q=0 |
|---|---|---|
| WSP-100-15 | PASS | PASS |
| WSP-200-40 | PASS | PASS |
| WSP-300-80 | PASS | PASS |
| MDP-150-60 | PASS | PASS |
| MDP-300-120 | PASS | PASS |
| SLP-200-30 | PASS | PASS |
| SLP-400-50 | PASS | PASS |

### Efficiency Ranges

All 7 pumps have peak efficiency within the 60–85% range for centrifugal pumps.

| Pump ID | Peak Efficiency | Result |
|---|---|---|
| WSP-100-15 | 75% | PASS |
| WSP-200-40 | 78% | PASS |
| WSP-300-80 | 82% | PASS |
| MDP-150-60 | 76% | PASS |
| MDP-300-120 | 82% | PASS |
| SLP-200-30 | 68% | PASS |
| SLP-400-50 | 72% | PASS |

### NPSHr

All 7 pumps have positive NPSHr values. The database stores a single NPSHr scalar per pump rather than a curve (NPSHr values should normally increase with flow for centrifugal pumps). The scalar values are plausible (2.5–5.5 m). This is a data-model limitation rather than an error in the values themselves.

### Power Consistency (P = rhoQH / eta)

The rated `power_kW` field stores the motor nameplate power. Shaft power at the best-efficiency point should normally be 70–90% of motor rated power (accounting for motor efficiency and service factor). Six of seven pumps are outside this range.

| Pump ID | Rated Power (kW) | Shaft Power at BEP (kW) | Ratio | Result |
|---|---|---|---|---|
| WSP-100-15 | 5.5 | 2.8 | 0.52 | WARN |
| WSP-200-40 | 22.0 | 14.3 | 0.65 | BORDERLINE |
| WSP-300-80 | 75.0 | 54.6 | 0.73 | PASS |
| MDP-150-60 | 37.0 | 20.5 | 0.55 | WARN |
| MDP-300-120 | 160.0 | 93.8 | 0.59 | WARN |
| SLP-200-30 | 45.0 | 11.7 | 0.26 | FAIL |
| SLP-400-50 | 110.0 | 35.2 | 0.32 | FAIL |

**Analysis of power discrepancies:**

For the slurry pumps (SLP-200-30, SLP-400-50), the power calculation uses slurry density (1400 kg/m3 at ~30% solids). Even with slurry density applied, the shaft power at the rated duty point is only 26–43% of motor rated power. This indicates one of two errors:

1. **The head values in the pump curves are significantly understated.** For SLP-200-30 at Q=30 L/s, the curve gives H=27 m. For power to be consistent with the 45 kW motor rating, the head should be approximately 74 m — a factor of 2.7x higher.
2. **The rated power values are overstated by a factor of 2–3.** The `power_kW` may have been copied from a larger pump model or represents a motor frame size rather than the duty power.

For water supply pumps, WSP-300-80 is the only pump with an acceptable power ratio (0.73). WSP-100-15 and WSP-200-40 have ratios of 0.52 and 0.65 respectively — suggesting their rated power is approximately 1.5–2x the actual shaft demand at BEP. For these smaller pumps, a conservative motor selection with a large service factor could explain the discrepancy but the gap is larger than typical practice.

The most likely root cause for all pumps: the `power_kW` field represents the next standard motor frame size above the actual pump requirement, but the curve heads are lower than what those motor ratings imply. The head/flow curves and the power field are not internally consistent for 6 of 7 pumps.

---

## Lookup Function Tests

All five lookup functions were tested programmatically.

| Function | Valid Inputs | Invalid Inputs | Edge Cases | Result |
|---|---|---|---|---|
| `list_materials()` | Returns `['Concrete', 'Ductile Iron', 'PE', 'PVC']` sorted | N/A | N/A | PASS |
| `list_sizes(material)` | Returns correct sorted DN list for each material | Returns `[]` for unknown material ('Steel') | N/A | PASS |
| `get_pipe_properties(material, dn)` | Returns correct dict for all valid combos tested | Returns `None` for unknown material or unknown DN | Returns a copy (mutation-safe — verified) | PASS |
| `lookup_roughness(material, age)` | C(DI, 0)=140, C(DI, 30)=110, C(DI, 60)=90 (clamped), C(PVC, 100)=140 (clamped), C(Concrete, 40)=100 | Raises `KeyError` for unknown material | Negative age clamped to 0 correctly | PASS |
| `lookup_wave_speed(material)` | DI=1120, PVC=400, PE=290, Concrete=1130 m/s — all in valid range | Raises `KeyError` for unknown material | N/A | PASS |

**lookup_roughness detail:**

The linear degradation model `C = C_new - rate * age` with floor clamping is correctly implemented. All 10 test cases produced the expected value. Negative ages are handled by `max(age_years, 0)` in the implementation.

**Aging parameters assessed:**
- Ductile Iron: rate 1.0/yr, min 90 — consistent with literature (unlined CI degrades faster; cement-lined DI at 1.0/yr is slightly conservative but acceptable)
- PVC/PE: rate 0.1/yr, min 140 — consistent with practice (plastic pipes degrade very slowly)
- Concrete: rate 0.5/yr, min 80 — consistent with Australian utility asset management guidelines

---

## Priority Summary

### Critical (fix before use in calculations)

1. **PVC wall thicknesses and internal diameters** — 5 of 6 standard sizes have incorrect geometry because the OD does not match AS/NZS 1477. Using these IDs in head-loss calculations will produce systematically wrong results. The correct ODs are 110, 160, 225, 280, 315, 400 mm for DN100–DN375.
2. **Slurry pump power values (SLP-200-30, SLP-400-50)** — rated power is 2–3x higher than what the head/flow curves support. Either the curves or the power values need correction before pump sizing calculations can be trusted.

### High (fix before standard delivery)

3. **Concrete HW C values for DN375–DN900** — the database uses C=120 uniformly. AS 4058 specifies C=110 at DN375/450, C=100 at DN600/750, and C=90 at DN900. Using C=120 for large concrete mains overstates flow capacity.
4. **Ductile Iron DN375, DN450, DN600 internal diameters** — 3 IDs are 5–9 mm wider than OD−2t requires. This affects velocity calculations and may affect surge analysis.
5. **Ductile Iron DN500 missing** — a commonly specified Australian water main size.

### Medium (fix in next revision)

6. **Ductile Iron DN450 and DN600 wave speeds** (1090 and 1080 m/s) — below the 1100 m/s lower bound for those sizes.
7. **Water supply pump power ratios** (WSP-100-15, MDP-150-60, MDP-300-120) — ratios of 0.52–0.59 suggest the power field needs review.
8. **PE DN75 missing** — present in AS/NZS 4130 but absent from the database.
9. **Concrete DN225 missing** — smallest standard concrete pipe size absent.

### Low / Informational

10. **PVC DN225** — a non-standard intermediate size; should be documented as such or removed.
11. **Concrete DN525** — not in the reference table; verify it is a required catalogue entry.
12. **NPSHr as scalar** — the database stores a single NPSHr value rather than a curve. This limits accuracy for off-BEP operation analysis.

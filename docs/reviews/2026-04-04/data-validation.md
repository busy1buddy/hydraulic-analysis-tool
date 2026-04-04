# Data Validation — 2026-04-04

## Result: ALL PASS — 0 issues found

### PVC (AS/NZS 1477) — PASS (12/12)
- OD series correct: DN100→110, DN150→160, DN200→225, DN250→280, DN300→315, DN375→400
- HW-C = 150 (within 145-150 range)

### Ductile Iron (AS 2280) — PASS (27/27)
- All wave speeds ≥ 1100 m/s
- HW-C = 140 (cement-lined)

### PE100 (AS/NZS 4130) — PASS (20/20)
- SDR11 PN16 correct
- pipe_stress.py PE100 yield = 20 MPa (lower-bound per AS/NZS 4130)

### Concrete (AS 4058) — PASS (15/15)
- DN375/450→C=110, DN600/750→C=100, DN900→C=90

### Pump Curves — PASS (8/8)
- All curves monotonically correct
- Efficiency peaks realistic (45-82%)

### Validation Script — 58/58 PASS

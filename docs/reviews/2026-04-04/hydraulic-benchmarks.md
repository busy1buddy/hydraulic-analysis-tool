# Hydraulic Benchmark Review — 2026-04-04

## Result: ALL PASS — 74 test cases verified

### BLOCKER: None
### HIGH: None

### MEDIUM (1)
- Turbulent Bingham friction uses simplified Colebrook-White with Bingham Re; ±10% uncertainty vs full Wilson-Thomas

### LOW (3)
1. No explicit fire flow 12m threshold test in test_compliance.py
2. Slatter transition Re approximation (linear vs Hedstrom chart) — <5% error
3. No minimum velocity (0.6 m/s) test in compliance suite

### Verified Standards
- WSAA WSA 03-2011: 20m min, 50m max, 2.0 m/s, 12m@25LPS, PN35
- AS 2280: wave speed 1100 m/s, hoop stress Barlow formula
- AS/NZS 1477: PVC OD series correct
- AS/NZS 4130: PE100 SDR11 PN16, yield 20 MPa
- Joukowsky (1898): exact match
- EPA verification: Net1/Net2/Net3 zero-difference vs EPANET 2.2
- Bingham plastic: Darcy convention (64/Re) confirmed correct

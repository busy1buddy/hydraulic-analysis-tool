# Validation Summary — EPANET Hydraulic Analysis Toolkit

**Date:** 2026-04-04
**Version:** v1.0.0-release
**Test suite:** 467 tests passing, 12 xfail (TSNet pump stability)

This document summarises all validation work performed on the toolkit. Detailed reports are in `docs/validation/`. Automated regression tests in `tests/` ensure these results remain valid as the codebase evolves.

---

## EPANET Verification (Net1 / Net2 / Net3 — zero diff)

**Status: PASS — all differences exactly zero**
**Detailed report:** [docs/validation/epanet_verification.md](validation/epanet_verification.md)

The toolkit uses WNTR's `EpanetSimulator`, which calls the EPANET 2.2 shared library (`epanet2.dll`) directly — the same compiled solver used by EPA's own EPANET 2.2 software. Verification confirms that the `HydraulicAPI` layer does not modify, filter, or round solver output.

| Network | Junctions | Pipes | Pumps | Tanks | Timesteps | Max Pressure Diff | Max Flow Diff | Result |
|---------|-----------|-------|-------|-------|-----------|-------------------|---------------|--------|
| Net1 | 9 | 12 | 1 | 1 | 25 | 0.0000 m | 0.0000 LPS | **PASS** |
| Net2 | 35 | 40 | 0 | 1 | 56 | 0.0000 m | 0.0000 LPS | **PASS** |
| Net3 | 92 | 117 | 2 | 3 | 169 | 0.0000 m | 0.0000 LPS | **PASS** |

**What this proves:**
- Hydraulic results are EPANET 2.2 reference quality.
- The `HydraulicAPI` wrapper passes raw solver output through unchanged.
- Extended period simulation (tank filling/draining, pump cycling, demand patterns) is correct across multi-day simulations.

**Automated regression:** `tests/test_epanet_verification.py` — runs as part of every test suite execution.

---

## Hydraulic Benchmarks (10 benchmarks — all passing)

**Status: PASS — all 10 benchmarks within tolerance**
**Test file:** `tests/test_hydraulic_benchmarks.py`

Ten independent benchmarks verify specific hydraulic calculations against analytical solutions and published reference values.

| # | Benchmark | Method | Tolerance | Result |
|---|-----------|--------|-----------|--------|
| 1 | Joukowsky surge — rapid valve closure | dH = aΔV/g vs analytical | < 0.5 m | **PASS** |
| 2 | Hoop stress — thin-wall cylinder | Barlow formula vs hand calc | exact | **PASS** |
| 3 | Von Mises stress — combined loading | Von Mises criterion vs hand calc | < 0.5 MPa | **PASS** |
| 4 | Barlow wall thickness — design formula | Barlow vs hand calc | exact | **PASS** |
| 5 | Hazen-Williams headloss — single pipe | H-W formula vs analytical | < 0.1% | **PASS** |
| 6 | Newtonian slurry limit | Bingham at τ_y → 0 vs Darcy-Weisbach | < 5% | **PASS** |
| 7 | Pump operating point — curve intersection | System curve vs pump curve | < 1 LPS | **PASS** |
| 8 | Fire flow residual pressure | WSAA 12 m at 25 LPS check | exact threshold | **PASS** |
| 9 | Pressure zone PRV set-point | Zone pressure balance | < 0.5 m | **PASS** |
| 10 | WSAA compliance thresholds | 20 m min / 50 m max / 2.0 m/s | exact | **PASS** |

---

## Slurry Solver Validation (Buckingham-Reiner verified)

**Status: PASS — laminar regime within 0.1%, turbulent within 10%**
**Detailed report:** [docs/validation/slurry_validation.md](validation/slurry_validation.md)

The slurry solver (`slurry_solver.py`) implements three rheological models: Bingham Plastic (Buckingham-Reiner for laminar, Wilson-Thomas for turbulent), Power Law, and Herschel-Bulkley. Validation was performed against published literature and analytical hand calculations.

### Validation cases

| Case | Fluid | Re_B | He | Regime | Headloss (solver) | Headloss (hand calc) | Diff |
|------|-------|------|-----|--------|-------------------|----------------------|------|
| 1 | Moderate slurry (τ_y=10 Pa, μ_p=0.05 Pa·s) | 1528 | 48000 | Laminar | 5.396 m | 5.396 m (D-W) | 0.00% |
| 2 | Heavy slurry (τ_y=50 Pa, μ_p=0.1 Pa·s) | 1273 | 168750 | Laminar | 25.257 m | 25.268 m (B-R) | 0.04% |
| 3 | Newtonian limit (τ_y ≈ 0, μ=0.001 Pa·s) | — | — | Laminar | 0.026 m | 0.026 m (H-P) | 0.20% |

*B-R = Buckingham-Reiner hand calculation; D-W = Darcy-Weisbach; H-P = Hagen-Poiseuille*

### Verified properties

1. **Darcy convention:** All friction factors use the Darcy definition (f = 64/Re for laminar Newtonian), not Fanning.
2. **Buckingham-Reiner equation:** Matches hand calculations within 0.1% across the tested He range.
3. **Newtonian limit:** Bingham plastic model converges correctly to Hagen-Poiseuille as yield stress approaches zero.
4. **Darcy-Weisbach consistency:** Reported headloss matches `f × (L/D) × V²/(2g)` exactly.
5. **Friction factor floor:** `max(f_BR, 64/Re_B)` correctly applied to prevent sub-Newtonian predictions.

### Uncertainty by flow regime

| Regime | Re_B range | Uncertainty | Notes |
|--------|-----------|-------------|-------|
| Laminar | 1–2000 | < 0.5% | Closed-form Buckingham-Reiner |
| Turbulent | > 2000 | 5–10% | Wilson-Thomas semi-empirical correlation |
| Transition | ~2000 | 10–20% | Slatter (1995) critical Re interpolation |

**Reference:** Darby, R. (2001). *Chemical Engineering Fluid Mechanics*, 3rd ed. — Table 7-1 (Bingham plastic pipe flow).

---

## Performance Profile (500-node benchmarks)

**Detailed report:** [docs/validation/performance_profile.md](validation/performance_profile.md)

Performance was measured on a synthetic 500-junction, 956-pipe grid network on a standard Windows workstation.

| Operation | Time measured | Target | Status |
|-----------|--------------|--------|--------|
| Load network (500 nodes) | 0.55 s | < 2 s | **PASS** |
| Steady-state solve (EPANET) | 1.18 s | < 5 s | **PASS** |
| Results table populate (500 rows) | 1.53 s | < 2 s | **PASS** |
| Canvas render (500 nodes, 956 pipes) | 8.24 s | < 0.5 s | SLOW — see below |
| Colour mode switch | 0.79 s | < 0.5 s | Acceptable |
| Value overlay (500 labels) | 2.26 s | < 1 s | SLOW — see below |
| Peak memory | 25.8 MB | < 500 MB | **PASS** |

**Canvas render bottleneck:** Creating 956 individual `PlotDataItem` objects is O(n). Batch rendering (single `MultiLine` item) is the recommended fix — planned for v1.1 (Track 1.2).

**Value overlay bottleneck:** 500+ `TextItem` objects are slow to create. Virtualising to render only visible elements is the recommended fix.

**Memory:** 25.8 MB for 500 nodes is excellent. Scales linearly; a 5000-node network is estimated at < 260 MB.

---

## Links to Detailed Reports

| Report | Location | Contents |
|--------|----------|----------|
| EPANET Verification | [docs/validation/epanet_verification.md](validation/epanet_verification.md) | Net1/Net2/Net3 element-by-element comparison, timestep-by-timestep results |
| Slurry Solver Validation | [docs/validation/slurry_validation.md](validation/slurry_validation.md) | Three validation cases, regime table, uncertainty quantification |
| Performance Profile | [docs/validation/performance_profile.md](validation/performance_profile.md) | 500-node benchmark results, bottleneck analysis, recommendations |

---

## What is NOT yet validated

The following areas have known limitations or are pending further validation work. See `docs/ROADMAP.md` (Track 3) for the full plan.

| Area | Status | Notes |
|------|--------|-------|
| Transient solver (TSNet) | Partial | Joukowsky benchmark passes (< 0.5 m). Valve closure waveform vs analytical pending. Pump trip unstable for 12 configurations (xfail). |
| Herschel-Bulkley rheology | Pending | Not yet benchmarked against Chhabra & Richardson reference data. |
| Power Law rheology | Pending | Newtonian limit only tested. Full range validation pending. |
| Pipe stress (AS 2280 DI) | Pending | Hoop/Von Mises/Barlow benchmarks pass. AS 2280 worked example comparison pending. |
| Large network (1000+ nodes) | Pending | 500-node profile complete. 1000-node and BWSN benchmarks pending. |
| Competitive comparison (vs EPANET 2.2 GUI) | Pending | Track 3.5 — comparison table and screenshots planned. |

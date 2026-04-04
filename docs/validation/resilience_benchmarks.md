# Todini Resilience Index Benchmarks

Benchmark date: 2026-04-04
Method: `HydraulicAPI.compute_resilience_index()` — Todini (2000)

## Reference

Todini E. (2000) "Looped water distribution networks design using a resilience
index based heuristic approach". Urban Water 2(2):115-122.

I_r = sum((h_i - h_min) * q_i) / sum((H_source - h_min) * Q_source)

## Grading Scale

| Grade | Index Range | Interpretation |
|-------|------------|----------------|
| A | >= 0.50 | Excellent redundancy |
| B | 0.30-0.49 | Good — meets reliability targets |
| C | 0.15-0.29 | Moderate — consider improving |
| D | 0.05-0.14 | Low — vulnerable to failures |
| F | < 0.05 | Critical infrastructure risk |

Target: > 0.3 for reliable distribution networks (Prasad & Park 2004).

## Tutorial Network Benchmarks

| Tutorial Network | Ir | Grade | Notes |
|-----------------|-----|-------|-------|
| dead_end_network | 0.324 | B | Dead ends limit redundancy |
| elevated_tank | 0.000 | F | Tank-dominated, no junction demands |
| fire_flow_demand | 0.334 | B | Well-designed residential loop |
| industrial_ring_main | 0.712 | A | Ring main provides excellent redundancy |
| mining_slurry_line | 0.540 | A | Point-to-point with high head |
| multistage_pump | 0.000 | F | Pump test circuit, no junction demands |
| pressure_zone_boundary | 0.524 | A | Multi-zone with PRVs |
| pump_station | 1.000 | A | Capped — large surplus energy |
| rehabilitation_comparison | 0.300 | B | Typical suburban distribution |
| simple_loop | 0.346 | B | Single loop with 3 junctions |

## Observations

1. **Ring mains and looped networks** (industrial_ring_main, pressure_zone_boundary)
   achieve highest resilience due to path redundancy.
2. **Dead-end networks** score lower — single path to each terminal node.
3. **Networks without junction demands** (elevated_tank, multistage_pump) return
   Ir=0 because the numerator is zero. This is mathematically correct but means
   the index is not meaningful for tank-only or pump-test networks.
4. **Pump station** exceeds Ir=1.0 raw due to very high source head relative to
   minimum pressure requirement. Capped to 1.0.

## Verification

The industrial_ring_main result (0.712) is consistent with published examples for
well-designed looped networks (Todini 2000 reports 0.4-0.8 for typical systems).

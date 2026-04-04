# Performance Profile

**Date:** 2026-04-04
**Network:** Synthetic 500-junction 20x25 grid, 956 pipes

## Results

| Operation | Time | Target | Status |
|-----------|------|--------|--------|
| Load network | 0.55s | <2s | PASS |
| Canvas render (500 nodes, 956 pipes) | **68ms** | <500ms | **PASS** (was 8236ms before batching) |
| Steady-state solve (EPANET) | 1.18s | <5s | PASS |
| Results table populate (500 rows) | 1526ms | <2s | PASS |
| Colour mode switch | **142ms** | <500ms | **PASS** (was 791ms) |
| Value overlay (500 labels) | 2260ms | <1s | SLOW |
| Results + recolor | **113ms** | <500ms | **PASS** |
| Peak memory | 25.8 MB | <500 MB | PASS |

## Analysis

**Canvas render — FIXED:** Batched rendering groups pipes by colour into
NaN-separated PlotDataItems. 956 individual items reduced to ~5-10 colour
groups. Render time: 8236ms → 68ms (121x speedup).

**Value overlay:** Creating 500+ TextItems is slow. For large networks,
consider only showing labels for visible/zoomed elements.

**Memory:** 25.8 MB for 500 nodes is excellent — well under the 500 MB target.

**Solver:** 1.18s for 500-node steady state is fast — EPANET's compiled C
solver handles this efficiently.

## Recommendations

1. Canvas render: batch pipes into a single line collection (priority: MEDIUM)
2. Value overlay: virtualise to only render visible elements (priority: LOW)
3. All other operations are within acceptable bounds for professional use

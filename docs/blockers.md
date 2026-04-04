# Blockers — Items Requiring Human Judgment

**Last updated:** 2026-04-04

## No Active Blockers

All "stop and surface" conditions from CLAUDE.md were checked:
- No benchmark regressions introduced
- No unconfirmed standard values used
- No .inp format or HydraulicAPI interface changes made

## Deferred Items (not blockers, just not yet built)

| Item | Reason Deferred | Impact |
|------|----------------|--------|
| Split-screen comparison | Lower priority than water quality and fire flow | Engineers can use scenario comparison table instead |
| GIF export | Requires imageio dependency; lower priority | Users can use screen recording software |
| Percentile clip on colourbar | Edge case for extreme outlier networks | Engineers can manually adjust min/max range |
| Canvas batch rendering for 500+ nodes | Performance optimisation — render is 8s at 500 nodes | Acceptable for networks < 200 nodes (majority of use cases) |
| Calibration tools (Track 2.3) | 8-12 day effort, requires field data format spec | Most impactful remaining feature for professional adoption |
| Pressure zone management (Track 2.4) | Requires zone assignment UI design | Important for multi-zone Australian networks |
| GIS integration (Track 2.6) | 10-15 day effort, requires geopandas/pyproj | Critical for professional adoption but large scope |

## TSNet Known Issues (12 xfail tests)

These are upstream library issues, not fixable without patching TSNet:
- Pump trip: sqrt(negative head) on some pump configurations
- Pump curves: TSNet requires exactly 1 or 3 curve points
- PRV valves: TSNet converts to pipes with zero roughness

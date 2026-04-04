# Blockers — Items Requiring Human Judgment

**Last updated:** 2026-04-04 (v1.3.0 + I-series autonomous development)

## Active Items Needing Human Decision

| Item | Why Human Needed | Suggested Action |
|------|-----------------|------------------|
| Review bridge API key | Bridge server returns "Connection error" on Anthropic API calls. Health endpoint OK. API key may not be loaded in server process. | Check `.env` file is in project root, restart review bridge with `scripts\start_review_loop.bat` |
| GIS basemap for MGA coordinates | MGA-to-latlon conversion is approximate (~1m accuracy). For professional survey work, pyproj should be used instead. | Evaluate whether to add pyproj dependency for production use |
| Rehab scoring weights | Current weights (age 25%, condition 30%, breaks 25%, hydraulics 20%) are based on WSAA guidelines. Different utilities may use different weightings. | Consider making weights configurable via UI or config file |

## Deferred Items (not blockers, just not yet built)

| Item | Reason Deferred | Impact |
|------|----------------|--------|
| Split-screen comparison | Lower priority than C2-C5 features | Engineers use scenario comparison table |
| GIF export | Requires imageio dependency; lower priority | Screen recording as workaround |
| SCADA/real-time integration | Major feature, out of current scope | Desktop tool only |
| Multi-user collaboration | Architectural change needed | Share .inp/.hap files |
| Genetic algorithm roughness calibration | C1 delivers manual calibration; GA is next tier | Manual roughness adjustment works |
| Fire flow sweep on QThread | Currently uses processEvents(); works but not ideal for 500+ nodes | Lower priority — processEvents adequate for typical networks |

## TSNet Known Issues (12 xfail tests)

These are upstream library issues, not fixable without patching TSNet:
- Pump trip: sqrt(negative head) on some pump configurations
- Pump curves: TSNet requires exactly 1 or 3 curve points
- PRV valves: TSNet converts to pipes with zero roughness

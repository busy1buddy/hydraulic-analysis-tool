# Blockers — Items Requiring Human Judgment

**Last updated:** 2026-04-05 (v3.0.0-rc1 visual QA)

## Visual QA Items Needing Human Session (v3.0.0 release)

| Item | Why Human Needed | Suggested Action |
|------|-----------------|------------------|
| Layout cramping at 1200×800 min size | Headless tests can't verify visual overlap | 30-min session resizing the window, checking dock panels |
| Colour-blind accessibility of WSAA pass/fail | Red/green-only may fail WCAG contrast | Run through a colour-blind simulator |
| DPI scaling on 4K monitors | Unknown behaviour at 150%/200% system scaling | Launch on a 4K display |
| Slurry mode discoverability | Only in Analysis menu; no visible toolbar indicator when active | Consider a status-bar slurry indicator |
| Run Demo visible progress | 4-step QTimer chain shows only status-bar text during 1.5 s run | Consider a progress dialog with step counter |
| Status bar `--` placeholders pre-load | "Nodes: 0, Pipes: 0, WSAA: --" looks unfinished on launch | Consider `(load network)` or hide until loaded |

See `docs/VISUAL_QA.md` for the full 10-step walkthrough results.

---

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

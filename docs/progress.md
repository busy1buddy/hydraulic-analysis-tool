# Build Progress

## Phase -1 — Expanded CLAUDE.md (2026-04-04)
- Rewrote CLAUDE.md with all 8 sections: Project Identity, Architecture Layers, Unit Conventions, Hydraulic Domain Rules, GodMode Orchestration, Code Conventions, Known Deferred Items, File/Path Conventions
- Established PyQt6 as target UI framework (replacing NiceGUI)
- Encoded all 7 blocker constraints as permanent domain rules
- Defined agent routing, parallel dispatch, and self-review gate

## Phase 0 — Fix all 7 blockers (2026-04-04)
- B1: Fixed slurry friction factor from Fanning (16/Re) to Darcy (64/Re) in slurry_solver.py
- B2: Fixed transient compliance to use gauge pressure (total_head - elevation) in both valve and pump paths
- B3: Fixed water age units — WNTR returns seconds, now divides by 3600 before comparing to 24-hour threshold
- B4: Fixed PVC OD per AS/NZS 1477 series (DN100->110, DN200->225, DN250->280, DN300->315, DN375->400), concrete HW-C by size (DN375/450->110, DN600/750->100, DN900->90), DI wave speeds >= 1100, added DN500 DI, fixed DI internal diameters
- B5: Fixed slurry pump motor ratings (SLP-200-30: 45->22 kW, SLP-400-50: 110->75 kW) for realistic shaft/motor ratios
- B6: Removed direct wntr import from network_editor.py and scenario_manager.py, added CRUD methods to HydraulicAPI, routed all mutations through API
- B7: Fixed velocity to use abs(flow).max() for reversing pipes, added zero-area guard
- PE100 yield fixed from 10 to 20 MPa in pipe_stress.py
- Created scripts/validate_pipe_db.py — 58/58 checks pass
- All 185 tests pass, 12 xfail (known TSNet pump stability)

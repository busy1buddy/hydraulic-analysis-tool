# EPANET Tutorial Index

Ten worked examples for Australian water supply and mining hydraulic analysis using the EPANET Hydraulic Analysis Toolkit.

Each tutorial contains `network.inp` (EPANET model), `project.hap` (scenario configuration), and `README.md` (engineering context and expected results).

---

## Tutorial List

| # | Directory | Topic | Key Feature |
|---|-----------|-------|-------------|
| 1 | [`simple_loop/`](simple_loop/README.md) | 6-node looped residential network | Pressure distribution, loop flow-splitting, WSAA pressure compliance |
| 2 | [`dead_end_network/`](dead_end_network/README.md) | Branching tree with 800m dead-end branch | Water age stagnation, low-velocity dead ends, flushing program design |
| 3 | [`pump_station/`](pump_station/README.md) | Single pump lifting to elevated distribution zone | Pump curve intersection, operating point, energy analysis |
| 4 | [`pressure_zone_boundary/`](pressure_zone_boundary/README.md) | Two pressure zones with PRV at boundary | PRV set-point selection, zone pressure management, over-pressure prevention |
| 5 | [`fire_flow_demand/`](fire_flow_demand/README.md) | Residential network with 25 LPS fire hydrant test | WSAA fire flow residual (12m at 25 LPS), pipe velocity under fire demand |
| 6 | [`mining_slurry_line/`](mining_slurry_line/README.md) | Straight pipeline for slurry vs water comparison | Non-Newtonian rheology (Bingham, Power Law), deposition velocity |
| 7 | [`multistage_pump/`](multistage_pump/README.md) | Two pumps in series for high-elevation supply | Series pump head addition, single-pump failure, transient trip starting point |
| 8 | [`elevated_tank/`](elevated_tank/README.md) | Gravity-fed distribution from elevated steel tank | Tank level drawdown, pressure variation with level, storage adequacy |
| 9 | [`industrial_ring_main/`](industrial_ring_main/README.md) | Large ring main for mining/industrial estate | DN400–DN600 high-demand mains, 120m HGL mining threshold, N-1 security |
| 10 | [`rehabilitation_comparison/`](rehabilitation_comparison/README.md) | Old cast iron (C=80) vs relined pipe (C=130) | Hazen-Williams C-factor effect, headloss reduction, WSAA compliance recovery |

---

## Quick Start

1. Open a tutorial folder
2. Read the `README.md` for engineering context
3. Load `project.hap` in the dashboard (File > Open Project)
4. Run the Base scenario — check pressures and velocities
5. Switch to alternative scenarios to observe the key hydraulic behaviour

## Prerequisites

- Python environment with WNTR installed: `pip install wntr`
- NiceGUI dashboard running: `python -m app.main`
- Tutorials are self-contained — no external data files required

## Australian Standards Used Across These Tutorials

| Standard | Application |
|----------|-------------|
| WSAA — Minimum pressure 20 m | All tutorials — pressure compliance |
| WSAA — Maximum pressure 50 m | Tutorials 4, 8 — PRV and elevated tank |
| WSAA — Max velocity 2.0 m/s | All tutorials — pipe sizing adequacy |
| WSAA — Fire flow 12 m at 25 LPS | Tutorial 5 — fire flow analysis |
| AS 2280 — Ductile iron DI pipe | Tutorials 1, 2, 9 — DN200–DN600 |
| AS/NZS 1477 — PVC pipe | Not featured — see `data/au_pipes.py` |
| AS/NZS 4130 — PE/HDPE pipe | Not featured — see `data/au_pipes.py` |
| AS/NZS 4158 — Pipe relining | Tutorial 10 — rehabilitation comparison |

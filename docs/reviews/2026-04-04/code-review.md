# Code Review — 2026-04-04

## BLOCKER
1. **CLI wave speed default 1000 m/s** — epanet_api.py:1830 — should be 1100 (AS 2280)
2. **run_pump_trip() wave speed=1000** — epanet_api.py:1108 — shadows DEFAULTS dict, should be None

## HIGH
1. **Age score formula redundant** — epanet_api.py:1733 — `(age/100)*100` = `age`, needs named constant
2. **MGA magic numbers** — gis_basemap.py:54-56 — bounds not named constants
3. **Southern hemisphere hardcoded** — gis_basemap.py:121 — no hemisphere parameter

## MEDIUM (all resolved on inspection)
- Water age conversion: correct (÷3600)
- Velocity abs(): correct throughout
- Zero-diameter guards: present in all paths
- Pressure bounds: acceptable (WNTR prevents non-physical steady-state)

## LOW
1. Redundant age formula simplification
2. Missing named constants for WSAA chlorine/age thresholds
3. Joukowsky default density documentation

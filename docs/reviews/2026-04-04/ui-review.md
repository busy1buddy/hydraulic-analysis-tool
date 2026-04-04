# UI Review — 2026-04-04

## BLOCKER (5)
1. Error messages expose Python exception types in 6 files (calibration, water_quality, rehab, pressure_zone, report, analysis_worker)
2. Fire flow results table shows bare floats without "m" units
3. Scenario comparison table shows bare floats without units
4. Calibration dialog table shows bare floats without "m" units
5. Analysis worker error emit includes type(e).__name__

## HIGH (7)
1. Rehab dialog table values missing units (mm, m, m/s, years)
2. Water quality dialog table values missing units (hrs, mg/L)
3. Pressure zone report table values missing units (LPS, m)
4. Pipe stress panel values missing units (kPa, MPa)
5. Node/pipe results tables — some bare floats
6. X/Y coordinates in properties panel missing "m"
7. Fire flow error messages lack context

## MEDIUM (12)
- Canvas editor status messages generic
- Preferences silent fail on load/save errors
- Animation time label should say "Elapsed" not "t"
- Calibration NSE label needs "(dimensionless)" clarification
- Pattern editor "Multiplier" should be "Demand Multiplier"
- X/Y properties should say "(m)"
- Scenario status "done/pending" should be "Completed/Not Run"
- Roughness spin lacks explanatory tooltip
- Time units inconsistent ("hrs" vs "hours")
- Table headers mostly good but some abbreviated

## LOW (5)
- 9pt font may be small for accessibility
- Yellow warning text may have low contrast on dark theme
- Tooltip colours hardcoded to Catppuccin
- Missing tooltips on some spinboxes
- Summary labels inconsistent word-wrap

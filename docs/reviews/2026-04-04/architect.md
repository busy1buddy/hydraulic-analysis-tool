# Architect Review — 2026-04-04

## Findings

### HIGH: Desktop imports Reports directly
- `desktop/report_dialog.py:91,113` imports from `reports/docx_report` and `reports/pdf_report`
- Violates: "No layer may import from a layer above it" (Layer 4 -> Layer 5)
- Fix: Route through `epanet_api.py` generate_report() method

### MEDIUM: epanet_api imports reports/
- `epanet_api.py:1419,1427` — late-bound imports, technically allowed (Layer 2 -> Layer 5)
- Acceptable under strict rules, lazy imports mitigate coupling

## Pass
- Zero wntr/tsnet imports in desktop/ (22 files checked)
- Zero wntr/tsnet imports in reports/ (3 files checked)
- Importers produce .inp only, no simulation calls
- New files (pressure_zone_dialog, rehab_dialog, gis_basemap) all clean
- Reports receive plain dicts only, no WNTR objects

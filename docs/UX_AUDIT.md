# UX Audit -- Cycle 2, Role 4
**Date:** 2026-04-06

## First-Run Experience
**Rating: POOR**
- User sees empty canvas with no tutorial or onboarding dialog
- Only hint is a status bar message: "Ready -- open a network (File > Open, Ctrl+O)"
- A graduate engineer may not notice the status bar or know what an .inp file is

**Recommendation:** Add welcome dialog with "Open Demo" / "Open Network" / "View Tutorial" buttons.

## Task Completion Steps

| Task | Steps | Ideal | Status |
|------|-------|-------|--------|
| Open network + run analysis | 3 | 3 | MATCH |
| Find highest velocity pipe | 4-5 | 2 | EXCESS |
| Fix a WSAA violation | 5-6 | 4 | EXCESS |
| Generate compliance report | 3-4 | 3 | MATCH |
| Compare two scenarios | 6 | 5 | EXCESS |
| Switch to slurry mode | 2 | 3 | BETTER |
| Export results for client | 3 | 3 | MATCH |

**Key issues:**
- Finding highest velocity requires scanning table (no sort/filter)
- Fixing WSAA violation has no quick-fix wizard linking violations to elements
- Scenario comparison requires 6 steps through multiple panels

## Error Message Audit

| Message | Rating | Issue |
|---------|--------|-------|
| "No network loaded. Use File > Open (Ctrl+O)..." | GOOD | Specific action |
| "Create at least 2 scenarios..." | GOOD | Step-by-step guidance |
| "Could not load network.\n{Exception}" | POOR | Raw exception, no fix guidance |
| "Save Error: {e}" | POOR | Raw exception |
| "No Results. Run an analysis first." | ADEQUATE | Tells user to run, not which analysis |
| "Analysis Error: {msg}" | ADEQUATE | Depends on msg quality |

**Overall: 2 GOOD, 2 ADEQUATE, 2 POOR** out of representative sample.

## Feature Discoverability -- Hardest to Find

1. **Probe Tool** -- toolbar button only, not in any menu
2. **Values Overlay** -- toolbar button only
3. **Edit Mode** -- toolbar button, not in Edit or Tools menu
4. **Split Screen** -- requires 2+ scenarios, deeply nested in View menu
5. **GIS Basemap** -- toggle in View menu, no indication coordinates required

## Missing Affordances

1. **No quick-fix wizard for violations** -- user sees violation but gets no suggestion
2. **No sort/filter on results tables** -- can't find "all pipes > 2.0 m/s"
3. **No CSV/Excel export for results** -- must use DOCX report and copy-paste
4. **No demand pattern presets** -- residential/commercial/industrial templates
5. **No validation on file load** -- missing data detected only when analysis fails

## Recommendations (Priority Order)

| Priority | Action | Impact |
|----------|--------|--------|
| HIGH | Add welcome dialog on first launch | First-run experience |
| HIGH | Add sort/filter to results tables | Task efficiency |
| MEDIUM | Move Probe/Values/Edit to menus | Discoverability |
| MEDIUM | Add "Export to CSV" on results tables | Data export workflow |
| MEDIUM | Improve error messages with fix guidance | Error recovery |
| LOW | Add demand pattern presets | Onboarding convenience |
| LOW | Add quick-fix wizard in compliance dialog | Violation remediation |

## Overall UX Maturity

| Category | Rating |
|----------|--------|
| First-run experience | POOR |
| Task efficiency | ADEQUATE |
| Error messages | ADEQUATE |
| Feature discoverability | POOR |
| Missing affordances | POOR |
| Documentation | ADEQUATE |

**No CRITICAL UX bugs found.** The tool is functional but requires onboarding improvements
for first-time users. An experienced engineer who reads the User Guide can complete all
tasks efficiently.

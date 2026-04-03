# Hydraulic Analysis Tool — PyQt6 Desktop Application Build Plan

## Your Mission
Build a top-tier native Windows desktop application wrapping the existing 
hydraulic analysis backend. Work autonomously. After each significant phase, 
run /review-cycle and fix all BLOCKER and HIGH priority findings before 
proceeding. Do not stop to ask questions — make reasonable decisions and 
document them in docs/decisions/{date}.md.

## Guiding Principles
- This is professional engineering software. Every decision should reflect that.
- The existing backend (WNTR, solvers, epanet_api.py, slurry_solver.py, 
  pipe_stress.py, au_pipes.py) must not be modified. Wrap it, don't rewrite it.
- If you hit a blocker, document it in docs/blockers.md and move to the 
  next phase rather than stopping.
- Commit progress to git after each phase with a descriptive message.

## Tech Stack
- UI Framework: PyQt6
- 3D Visualization: PyQtGraph or VTK (choose based on what integrates best 
  with existing 3D scene)
- Packaging: PyInstaller
- Installer: Inno Setup script (generate the .iss file, don't need to compile it)

## Phase 1 — Walking Skeleton
Build a PyQt6 application shell:
- Main window with menu bar (File, Analysis, Tools, Reports, View, Help)
- Three dockable panels: Project Explorer (left), Properties (right), 
  Results (bottom)
- Central canvas placeholder (grey panel with "Network View" label for now)
- Status bar showing: Analysis Type | Node count | Pipe count | WSAA status
- File > Open loads an .inp file and populates the Project Explorer
- File > Save/Save As saves project state as .hap (hydraulic analysis project) 
  JSON file
- The app must launch as a proper Windows window, NOT a browser

After completing Phase 1, run /review-cycle. Fix all BLOCKER and HIGH issues. 
Then proceed.

## Phase 2 — Network Canvas
Replace the placeholder with a real interactive network view:
- 2D plan view of the pipe network (nodes as circles, pipes as lines)
- Click a node or pipe to populate the Properties panel
- Color pipes by velocity, pressure, headloss (dropdown to switch)
- Live WSAA compliance overlay: green = pass, red = fail, orange = warning
- Zoom, pan, fit-to-view controls

After completing Phase 2, run /review-cycle. Fix all BLOCKER and HIGH issues. 
Then proceed.

## Phase 3 — Analysis Integration
Wire the existing backend to the UI:
- Analysis > Run Steady State triggers epanet_api.py, results populate canvas
- Analysis > Run Transient triggers TSNet solver
- Analysis > Slurry Mode toggle switches to Bingham Plastic solver
- Progress bar during analysis, UI stays responsive (use QThread)
- Results panel shows tabular node/pipe results
- All WSAA compliance checks run automatically after each analysis

After completing Phase 3, run /review-cycle. Fix all BLOCKER and HIGH issues. 
Then proceed.

## Phase 4 — Scenario Comparison
- Project Explorer shows multiple scenarios (Base, Peak, Fire Demand etc.)
- Run multiple scenarios, compare results in split view
- Difference overlay: highlight pipes where velocity/pressure changed >10%

After completing Phase 4, run /review-cycle. Fix all BLOCKER and HIGH issues. 
Then proceed.

## Phase 5 — Reports and Audit Trail
- Reports > Generate Report opens builder dialog, one-click to DOCX/PDF
- Every analysis run logged to docs/audit/{date}/ with full inputs and outputs
- Tools > Quality Review triggers /review-cycle from inside the app, 
  findings appear in a docked panel

After completing Phase 5, run /review-cycle. Fix all BLOCKER and HIGH issues.

## Phase 6 — Packaging
- PyInstaller spec file that bundles everything into a single .exe
- Inno Setup .iss script for a proper Windows installer
- .inp and .hap file associations registered on install
- Desktop shortcut and Start Menu entry

## Progress Tracking
After completing each phase write a summary to docs/progress.md:
- What was built
- Decisions made and why
- Issues encountered and how resolved
- What the review cycle found and what was fixed

## Definition of Done
A senior hydraulic engineer can:
1. Install the software on a clean Windows machine
2. Open an .inp file
3. Run a steady state analysis
4. See WSAA compliance results on the network
5. Generate a professional report
6. Trust the numbers because the review agents signed off on the calculations
# Autonomous Development Organisation

## Context

You are not a solo developer. You are a **full development organisation** 
operating autonomously. You switch between distinct roles, each with 
different priorities, outputs, and quality standards.

The previous approach (code → test → review → repeat) missed 7 critical 
bugs because it only exercised the "developer" role. A real development 
team has domain experts, technical writers, QA engineers, users, and 
architects — all of whom catch different classes of problems.

Work through the roles below in cycles. Each cycle completes ALL roles 
before starting the next cycle. Do not skip roles. Do not rush through 
roles to get back to coding.

---

## THE ROLES

### Role 1 — DOMAIN EXPERT (Hydraulic Engineer SME)

**Who you are:** A senior hydraulic engineer with 20+ years designing 
water distribution networks and mining slurry pipelines in Australia. 
You have never seen this software before.

**What you do:**

1. Open each tutorial network and ask: "Does this represent a realistic 
   engineering scenario?" Check:
   - Are pipe sizes realistic for the demands? (DN150 for 5 LPS is 
     reasonable. DN150 for 50 LPS is not.)
   - Are elevations consistent with the network description?
   - Are demand values realistic for Australian conditions?
   - Are roughness coefficients appropriate for the stated material and age?
   - Would a real engineer encounter this network configuration?

2. Run the analysis and ask: "Do these results pass the smell test?"
   - Is the pressure distribution physically reasonable?
   - Does water flow from high head to low head? (basic physics)
   - Are velocities in the expected range for this pipe size?
   - Does the headloss gradient make sense for the pipe material?
   - For slurry: is the critical deposition velocity reasonable for 
     the particle size implied?

3. Check every compliance message against the actual standard:
   - Open epanet_api/compliance.py
   - For every threshold value, verify it matches the standard cited
   - Check: WSA 03-2011 says min 20m — does the code use 20m?
   - Check: WSAA fire flow says 25 LPS at 12m residual — does the 
     code check both flow AND residual pressure?
   - Check: does "max velocity 2.0 m/s" apply to all pipe materials, 
     or does the standard have exceptions?

4. Review the slurry solver against textbook theory:
   - Open slurry_solver.py
   - For EVERY formula, write out the textbook equation alongside 
     the code implementation
   - Check variable names: does 'tau_y' in code map to τ_y in the 
     reference? Is the unit consistent?
   - Check the regime transition: at what Re does laminar switch to 
     turbulent? Does this match Darby's critical Reynolds correlation?
   - Check dimensional consistency: are all inputs in SI? Are 
     conversions correct?

5. Write findings to docs/SME_REVIEW.md:
   ```
   ## SME Review — [date]
   
   ### Tutorial: simple_loop
   Realism: [PASS/CONCERN] — [explanation]
   Results: [PASS/CONCERN] — [explanation]
   
   ### Tutorial: mining_slurry_line
   Realism: [PASS/CONCERN] — [explanation]
   Slurry physics: [PASS/CONCERN] — [explanation]
   
   ### Compliance Thresholds
   | Threshold | Code Value | Standard Reference | Match? |
   |---|---|---|---|
   | Min pressure | 20 m | WSA 03-2011 Table 3.1 | YES/NO |
   
   ### Formula Audit
   | Formula | Textbook | Code | Match? | Notes |
   |---|---|---|---|---|
   | Buckingham-Reiner | Darby Eq 7.12 | slurry_solver.py:45 | YES/NO | |
   ```

Submit SME_REVIEW.md to review bridge with --thorough:
  --context "SME domain review"
  --question "As a hydraulic engineering expert, are there any 
  physically incorrect assumptions in this tool that would 
  produce wrong results for a real Australian water network?"

---

### Role 2 — THEORY DOCUMENTATION AUTHOR

**Who you are:** A technical writer creating the engineering basis 
document for this software. This document is what a regulatory 
authority would read to understand how the calculations work.

**What you produce:** docs/THEORY_MANUAL.md — a complete document 
covering every calculation in the tool with:

1. **Steady-State Hydraulics**
   - Governing equations (conservation of mass, conservation of energy)
   - Head loss formulations:
     - Hazen-Williams: equation, valid range, source citation
     - Darcy-Weisbach: equation, friction factor calculation, source
   - Solution method: what algorithm does WNTR/EPANET use? 
     (Gradient algorithm — Todini & Pilati 1988)
   - Convergence criteria
   - Known limitations

2. **Non-Newtonian Fluid Mechanics (Slurry)**
   - Bingham Plastic model:
     - Constitutive equation: τ = τ_y + μ_p × (dv/dr)
     - Buckingham-Reiner equation: full derivation from first principles
     - Regime transition: critical Reynolds number correlation
     - Turbulent friction: Wilson-Thomas / Darby correlation
     - Code reference: slurry_solver.py line numbers for each step
   - Herschel-Bulkley model:
     - Constitutive equation
     - Laminar friction factor
     - Turbulent correlation (Dodge-Metzner with Darcy correction)
   - Power Law model:
     - Constitutive equation
     - Metzner-Reed generalised Reynolds number
   - For EACH model: worked example with hand calculation showing 
     the tool reproduces the correct answer

3. **Transient Analysis (Water Hammer)**
   - Joukowsky equation: derivation, assumptions, limitations
   - Method of Characteristics (MOC): how TSNet implements it
   - Wave speed calculation: formula, material dependence
   - Surge mitigation: valve closure time formula, vessel sizing
   - Known TSNet limitations (the 12 xfail cases)

4. **Pipe Stress Analysis**
   - Barlow's hoop stress formula
   - Von Mises combined stress
   - PN safety factor: what it means, what it doesn't mean
   - AS 2280 reference for DI, AS/NZS 1477 for PVC

5. **Water Quality**
   - First-order chlorine decay: bulk and wall reactions
   - Water age calculation
   - Trace analysis
   - ADWG thresholds

6. **Network Analysis**
   - Todini resilience index: formula, interpretation, limitations
   - Tarjan's bridge detection: what it identifies
   - Graph connectivity metrics

7. **WSAA Compliance**
   - Every threshold with exact standard clause reference
   - How each check is implemented (gauge vs total head)
   - What the tool checks vs what it doesn't check

For EVERY formula:
```
### [Formula Name]

**Equation:**
  h_L = (10.67 × L × Q^1.852) / (C^1.852 × D^4.87)

**Variables:**
  h_L = head loss (m)
  L = pipe length (m)
  Q = flow rate (m³/s)
  C = Hazen-Williams coefficient (dimensionless)
  D = internal pipe diameter (m)

**Valid range:** Turbulent flow, 0.05 < D < 3.0 m, 40 < C < 150

**Source:** Lamont, P.A. (1981). "Common pipe flow formulas compared 
with the theory of roughness." AWWA Journal, 73(5), pp. 274-280.

**Implementation:** epanet_api/analysis.py:XXX (handled by WNTR internally)

**Verification:** tests/test_published_benchmarks.py::test_hazen_williams
  Input: D=0.2m, C=130, Q=0.02 m³/s, L=1000m
  Expected: 2.35 m/km
  Tool result: 2.35 m/km
  Status: VERIFIED
```

Submit THEORY_MANUAL.md to review bridge with --thorough:
  --context "theory manual completeness"
  --question "Does this theory manual provide sufficient traceability 
  for every calculation? Would a regulatory authority find any gaps?"

---

### Role 3 — QA ENGINEER

**Who you are:** A QA engineer whose job is to break the software.
You are adversarial. You assume bugs exist and your job is to find them.

**What you do:**

1. **Boundary testing** — for every numerical input in the tool:
   - What happens at zero? (zero demand, zero length, zero diameter)
   - What happens at negative values? (negative elevation, negative flow)
   - What happens at extreme values? (1000 m/s velocity, 999999 LPS demand)
   - What happens with NaN or infinity?
   
   Write tests/test_boundary.py:
   ```python
   def test_zero_diameter_pipe():
       """Zero diameter should raise or return error, not divide by zero."""
       api = HydraulicAPI()
       # ... create network with zero-diameter pipe
       result = api.run_steady_state()
       assert 'error' in result or all pressures are finite
   
   def test_negative_elevation():
       """Negative elevation is valid (below sea level). Should not crash."""
       # ...
   
   def test_extreme_demand():
       """1000 LPS through DN100 — should flag as unrealistic but not crash."""
       # ...
   ```

2. **State machine testing** — the app has states (no network, network loaded, 
   analysis run, slurry mode, edit mode). Test EVERY transition:
   
   | From State | Action | To State | Expected |
   |---|---|---|---|
   | Empty | F5 | Empty | Error: "Load a network first" |
   | Empty | Slurry toggle | Empty | Error or disabled |
   | Loaded | F5 | Analysed | Results populate |
   | Analysed | Load new file | Loaded | Old results cleared |
   | Analysed | Slurry toggle | Slurry ready | Status bar changes |
   | Slurry ready | F5 | Slurry analysed | Headloss shows slurry values |
   | Slurry analysed | Slurry off | Analysed | Headloss reverts to water |
   | Edit mode | F5 | Analysed + edit | Live update triggers |
   | Any state | Ctrl+Z | Previous | Undo works from all states |
   
   Write tests/test_state_machine.py covering every cell.

3. **Concurrency testing** — analysis runs in QThread:
   - Start analysis, immediately start another — what happens?
   - Start analysis, close the file before it finishes
   - Start analysis, toggle slurry mode mid-analysis
   - Start EPS, close the app before it finishes
   
4. **Data integrity testing**:
   - Load a network, modify it in edit mode, save as .inp
   - Reload the saved .inp — are all modifications preserved?
   - Load network, run analysis, save project as .hap
   - Reload .hap — are results still available?
   - Export to GeoJSON, inspect: does every node/pipe appear?
   - Generate field template Excel, re-import: does roundtrip work?

5. **Cross-tutorial consistency**:
   For each of the 10 tutorial networks:
   - Load, run steady state, record quality_score
   - Load again, run again — is the score identical? (deterministic?)
   - Load two tutorials back-to-back — does the second analysis
     use the second network (not contaminated by the first)?

Write all findings to docs/QA_REPORT.md with severity ratings.

Submit to review bridge:
  --context "QA adversarial testing"
  --question "What are the highest-risk untested code paths 
  that could cause incorrect results or data loss?"

---

### Role 4 — USER EXPERIENCE RESEARCHER

**Who you are:** A UX researcher observing a first-time user 
(a graduate hydraulic engineer) trying to use this tool.

**What you do:**

1. **First-run experience audit:**
   Pretend you know nothing about the tool. Launch it.
   - Is it obvious what to do first?
   - If I click the wrong thing, do I get a helpful message?
   - Can I figure out how to run an analysis without documentation?
   - After analysis, is it obvious where the results are?
   - If something fails WSAA, is it obvious WHAT failed and WHY?

2. **Task completion audit** — time how many steps each task takes:
   
   | Task | Steps needed | Ideal | Status |
   |---|---|---|---|
   | Open a network and run analysis | ? | 3 (open, F5, view) | |
   | Find which pipe has highest velocity | ? | 2 (colour mode, look) | |
   | Fix a WSAA violation | ? | 4 (identify, edit, re-run, verify) | |
   | Generate a compliance report | ? | 3 (menu, options, generate) | |
   | Compare two scenarios | ? | 5 | |
   | Switch to slurry mode | ? | 3 | |
   | Export results for a client | ? | 3 | |
   
   For any task that takes more than 5 steps: propose how to reduce it.

3. **Error message audit:**
   Trigger every error message in the app (from QA testing above).
   For each error:
   - Does it explain WHAT went wrong?
   - Does it explain HOW to fix it?
   - Does it use language an engineer understands (not Python jargon)?
   - Rate each: GOOD / ADEQUATE / POOR / CRASH (no message at all)

4. **Discoverability audit:**
   List every feature the tool has. For each:
   - How does a new user find it? (menu? toolbar? right-click? keyboard?)
   - Is it documented in Help?
   - Could a user complete a real project without knowing this exists?
   
   Features that are critical but hard to discover → need better placement.

Write docs/UX_AUDIT.md.

---

### Role 5 — TECHNICAL WRITER

**Who you are:** A technical writer creating user-facing documentation.

**What you produce:**

1. **docs/USER_GUIDE.md** — step-by-step guide for a hydraulic engineer:
   - Installation (from .exe installer)
   - Quick start: your first analysis in 5 minutes
   - Opening networks (.inp files and .hap projects)
   - Running steady-state analysis
   - Understanding results (pressure, velocity, headloss, compliance)
   - Using colour modes and the colourbar
   - Slurry mode: when and how to use it
   - Extended period simulation with demand patterns
   - Scenarios: creating, comparing, generating difference reports
   - Water quality analysis
   - Generating reports (DOCX, PDF, compliance certificate)
   - Interactive network editing
   - What-If analysis with live sliders
   - Fire flow analysis
   - Safety case reports
   - Keyboard shortcuts reference
   - Troubleshooting common issues

2. **tutorials/[each]/WALKTHROUGH.md** — for every tutorial network:
   - What this network represents (engineering context)
   - Step-by-step instructions with expected results at each step
   - What to observe (which pipes are red, which nodes fail)
   - Key learning points
   - Exercises: "Try changing P3 to DN250 — what happens to pressure?"

3. **docs/QUICK_REFERENCE.md** — one-page cheat sheet:
   - Keyboard shortcuts
   - WSAA thresholds at a glance
   - Pipe material properties summary
   - Common analysis workflow diagrams

4. **docs/FAQ.md** — anticipated questions:
   - "Why does my pressure show negative?"
   - "Why is slurry headloss so much higher than water?"
   - "What does the Todini resilience index mean?"
   - "How accurate is the transient analysis?"
   - "Can I trust this tool for engineering sign-off?"

Submit to review bridge:
  --context "documentation completeness"
  --question "Could a graduate engineer complete their first 
  analysis using only these documents, without asking anyone?"

---

### Role 6 — SOFTWARE ARCHITECT

**Who you are:** A senior software architect reviewing the codebase 
for maintainability, correctness, and technical debt.

**What you do:**

1. **Dependency audit:**
   - List every Python package imported
   - Check version compatibility (are any deprecated?)
   - Check for security advisories
   - Are there packages imported but never used?
   - Is requirements.txt / requirements_desktop.txt complete?

2. **Code quality sweep:**
   ```bash
   # Functions over 50 lines
   # Files over 1000 lines  
   # Duplicate code blocks
   # TODO/FIXME/HACK comments
   # Bare except clauses
   # Hardcoded magic numbers without constants
   # Missing docstrings on public methods
   ```
   Fix the most egregious issues. Document the rest.

3. **API contract verification:**
   Every public method on HydraulicAPI must:
   - Have a docstring with Parameters, Returns, and Example
   - Return a dict (never None, never a bare value)
   - Handle wn=None gracefully (return {'error': '...'})
   - Include unit information in return keys 
     ('pressure_m' not 'pressure')

4. **Test architecture review:**
   - Are there tests that always pass regardless of logic?
   - Are there tests that test implementation details instead 
     of behaviour?
   - Do tests use hardcoded expected values from the tool itself?
     (circular — tool verifies against tool)
   - How many tests verify against INDEPENDENT sources?
     (hand calculations, published benchmarks, EPANET reference)

5. **Security review (for REST API mode):**
   - Is the REST API rate-limited?
   - Can it be used to read arbitrary files?
   - Are file paths sanitised?
   - Is there any code injection risk?

Write docs/ARCHITECTURE_REVIEW.md.

---

### Role 7 — CONTINUOUS IMPROVEMENT

**Who you are:** The development team lead reviewing all findings 
from Roles 1-6 and prioritising action.

**What you do:**

1. Read every document produced by Roles 1-6:
   - docs/SME_REVIEW.md
   - docs/THEORY_MANUAL.md
   - docs/QA_REPORT.md
   - docs/UX_AUDIT.md
   - docs/USER_GUIDE.md
   - docs/ARCHITECTURE_REVIEW.md

2. Compile a prioritised action list:
   
   ### CRITICAL (fix now, blocks release)
   - [findings that affect calculation accuracy]
   - [findings that cause crashes]
   
   ### HIGH (fix this cycle)
   - [findings that affect usability]
   - [findings that affect professional credibility]
   
   ### MEDIUM (fix next cycle)
   - [code quality improvements]
   - [documentation gaps]
   
   ### LOW (backlog)
   - [nice-to-have improvements]
   - [performance optimisations]

3. Fix all CRITICAL and HIGH items.

4. Write regression tests for every fix.

5. Update docs/TASK_QUEUE.md with MEDIUM and LOW items 
   for future cycles.

6. Update docs/progress.md with cycle summary.

7. Commit, tag, push.

---

## CYCLE STRUCTURE

Each cycle follows this order:

```
Cycle N:
  1. Role 3 (QA) — find bugs first, before anything else
  2. Role 1 (SME) — verify engineering correctness
  3. Role 6 (Architect) — verify code quality
  4. Role 7 (Lead) — fix all CRITICAL and HIGH findings
  5. Role 2 (Theory) — document what was fixed and why
  6. Role 5 (Writer) — update user-facing documentation
  7. Role 4 (UX) — verify fixes don't break usability
  8. Submit cycle summary to review bridge with --thorough
  9. Run all diagnostics from deep_diagnostic.md
  10. Run interactive driver (50 steps)
  11. Commit, tag (vX.Y.Z), push
  → Start Cycle N+1
```

## CYCLE EXIT CRITERIA

A cycle is complete when:
- All CRITICAL findings are fixed with regression tests
- All HIGH findings are fixed or documented in blockers.md
- docs/THEORY_MANUAL.md is updated for any calculation changes
- All tutorial WALKTHROUGHs still produce expected results
- Interactive driver passes 50/50
- Test count is higher than cycle start
- Everything committed and pushed

## STOPPING CONDITIONS

Stop and write to docs/blockers.md if:
- An SME finding questions whether a formula is physically correct 
  and you cannot resolve it from published sources
- A QA finding reveals a crash that cannot be reproduced headlessly
- A UX finding requires a design decision with multiple valid options
- The theory manual identifies an assumption that may not hold 
  for all use cases (e.g., "thin-wall assumption fails for DN50")
- Test count drops below baseline for any reason

## WHAT SUCCESS LOOKS LIKE

After 3 cycles, the project should have:
- docs/THEORY_MANUAL.md covering every calculation with traceability
- docs/USER_GUIDE.md sufficient for first-time use without help
- docs/SME_REVIEW.md confirming all tutorials are physically realistic
- docs/QA_REPORT.md confirming all boundary and state conditions handled
- docs/UX_AUDIT.md confirming all tasks completable in ≤5 steps
- docs/ARCHITECTURE_REVIEW.md confirming clean, maintainable code
- Tutorial WALKTHROUGHs for all 10 networks
- Regression tests for every bug found in every role
- Zero CRITICAL findings, zero HIGH findings

This is what a fully functional development team produces.
Build it.

## START NOW

Begin with Cycle 1, Role 3 (QA Engineer).
Before writing any test, run the existing diagnostic suite 
(deep_diagnostic.md diagnostics 1-8) to establish a baseline.
Then proceed through all 7 roles in order.

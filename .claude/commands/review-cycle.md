# Review Cycle — Full Agent Review Pipeline

Run all review agents in sequence, save findings to `docs/reviews/{date}/`, then synthesise into a prioritised action list.

## Sequencing Logic

The agents run in this order because:
1. **Architect** runs first — its module boundary findings inform what the code-reviewer should focus on
2. **Code Reviewer** and **Data Validator** run next (can be parallel) — they examine implementation correctness
3. **UI Reviewer** and **Hydraulic Tester** run next (can be parallel) — they check user-facing output and calculation accuracy
4. **Feedback Synthesizer** runs last — it reads all the above outputs and consolidates

## Instructions

Execute the following steps:

### Step 1: Create output directory
```bash
mkdir -p docs/reviews/$(date +%Y-%m-%d)
```

### Step 2: Run Architect Agent (opus)
Launch the `architect` agent. It should:
- Read all Python files and check module boundaries
- Check import graph for layer violations
- Check data flow patterns
- Save findings to `docs/reviews/{today}/architect.md`

### Step 3: Run Code Reviewer + Data Validator (parallel, sonnet)
Launch both agents in parallel:
- `code-reviewer` agent: Review `epanet_api.py`, `slurry_solver.py`, `pipe_stress.py`, `data/pump_curves.py`, `scenario_manager.py`
- `data-validator` agent: Validate `data/au_pipes.py` entries against AS/NZS standards, test lookup functions

Save findings to:
- `docs/reviews/{today}/code-review.md`
- `docs/reviews/{today}/data-validation.md`

### Step 4: Run UI Reviewer + Hydraulic Tester (parallel, sonnet)
Launch both agents in parallel:
- `ui-reviewer` agent: Review all files in `app/pages/` and `app/components/` for UX quality
- `hydraulic-tester` agent: Run all 10 hydraulic benchmarks and report PASS/FAIL

Save findings to:
- `docs/reviews/{today}/ui-review.md`
- `docs/reviews/{today}/hydraulic-benchmarks.md`

### Step 5: Run Feedback Synthesizer
Launch the `feedback-synthesizer` agent. It should:
- Read all files in `docs/reviews/{today}/`
- De-duplicate findings across reviewers
- Prioritise: BLOCKER > HIGH > MEDIUM > LOW
- Save consolidated report to `docs/reviews/{today}/SUMMARY.md`

### Step 6: Report to user
After all agents complete, display:
- Number of findings by severity
- Top 3 recommended actions
- Link to full SUMMARY.md

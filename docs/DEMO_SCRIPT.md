# 5-Minute Demo Script

**Audiences:** Water utility operations manager · Mining safety engineer ·
Consulting firm principal · University hydraulics lecturer

**Goal:** Show the end-to-end flow from "open a network" to "regulator-ready
safety case" in a single sitting, using the built-in `demo_network` and
`mining_slurry_line` tutorials.

**Setup** (before the demo):

```bash
python main_app.py
```

Let the UI open with a blank canvas. You're ready.

---

## Act 1 — Instant WSAA check (60 seconds)

**Pitch:** "Most utilities wait three days for a network study. We do this
live."

1. **Help > Run Demo** (one click)
2. Watch the status bar walk through four stages (1.5 s each):
   - Loading network
   - Running steady-state
   - Identifying violations
   - Summarising

3. A popup appears with the health grade and root-cause list:

   ```
   Network health: Grade C (65/100)
   3 WSAA violations detected.

   Root cause analysis found 3 issues:
     - Low Pressure at J9
       Fix 1: Upsize P10 DN80 → DN100 (~$56,000)
     - Low Pressure at J10
       Fix 1: Upsize P11 DN100 → DN150 (~$45,000)
     - High Velocity at P10
       Fix 1: Upsize P10 DN80 → DN100 (~$56,000)
   ```

**Talking point:** *"Ten nodes. Three violations. Costed remediation.
Ten seconds."*

---

## Act 2 — Live sensitivity ("what if demand grows 20%?") (60 seconds)

**Pitch:** "Your council's planning department asks: can the network
handle 20% population growth? Watch."

1. Open the **What-If panel** (dockable right side)
2. Slide **Demand** to **120%**
3. Wait 150 ms (debounce) — the canvas colours refresh immediately

4. Status label updates:
   ```
   Updated: min pressure 8.1 m, max velocity 2.87 m/s
   (120% demand, 100% C, +0 m source)
   ```

5. Slide back to **100%**, then slide **Source head** to **+20 m**

6. Status updates:
   ```
   Updated: min pressure 32.3 m, max velocity 2.39 m/s
   (100% demand, 100% C, +20 m source)
   ```

**Talking point:** *"Boosting the reservoir by 20 m fixes the pressure
side entirely — but velocity's still out. That's a pump decision, not
a pipe decision. The tool told us in 3 seconds what used to take a
consultant a week."*

---

## Act 3 — Root cause analysis (60 seconds)

**Pitch:** "Knowing a node fails is easy. Knowing *why* and *what to do
about it* is where this tool earns its keep."

1. From the terminal or dev console:
   ```python
   api.root_cause_analysis()
   ```

2. Show one explanation from the output:
   ```
   Issue: low_pressure at J9
     Measured: 12.1 m (WSAA min 20 m, deficit 7.9 m)
     Root cause: Pressure at J9 is 12.1 m. Pipe P10 carries
       12.0 LPS at 2.39 m/s through DN80 — this is the limiting
       segment.
     Fix 1: Upsize P10 DN80 → DN100 (~$56,000)
            Lowers velocity and headloss on the critical path.
     Fix 2: Parallel main alongside P10 (DN80) (~$45,000)
            Halves carrying burden, reduces headloss ~75%.
   ```

3. Point to `cost_assumptions`:
   ```
   Source: Rawlinsons 2026 SEQ metro
   Uncertainty: ±15%
   ```

**Talking point:** *"Every fix comes with a costed rationale citing
the Rawlinsons edition. When your client asks where the numbers come
from, you have an answer."*

---

## Act 4 — Mining slurry, critical deposition velocity (60 seconds)

**Pitch:** "Water networks are one half of our market. The other half
is mining — and slurry is where competitors fall apart."

1. **File > Open** → `tutorials/mining_slurry_line/network.inp`
2. Press **F5** — steady state runs
3. From console:
   ```python
   api.slurry_design_report(
       d_particle_mm=0.5, rho_solid=2650,
       concentration_vol=0.15, rho_fluid=1000, mu_fluid=0.001)
   ```

4. Sample output:
   ```
   Pipe P1: 1.94 m/s [OK]
   Pipe P2: 1.42 m/s [AT RISK: below Durand 1.63 m/s]
   Pipe P3: 0.88 m/s [SETTLING: below Wasp 1.28 m/s]
   ```

5. Show the Durand reference: *Durand (1952)* and Wasp formula in
   the on-screen `knowledge_base('bingham_plastic')`.

**Talking point:** *"Durand 1952, Wasp 1977 — this is literally the
textbook, wired directly into our analysis. No hand-calcs, no
spreadsheets."*

---

## Act 5 — Safety Case Report (60 seconds)

**Pitch:** "Here's what makes the regulator sign off."

1. **Analysis > Safety Case Report...**
2. Fill in:
   - **Certifying Engineer:** Jane Smith, RPEQ #12345
   - **Project Ref:** DEMO-2026-0001
3. Leave parameters at defaults, click **Preview Verdict**
4. Red "**NOT APPROVED**" banner appears
5. Scroll the summary — point to:
   - WSAA Steady-State: FAIL (3 violations)
   - Joukowsky Transient: PASS
   - Water Hammer: REVIEW (valve closure within critical period)
   - Signature block: `is_digitally_signed: False` + yellow warning
   - `network_sha256` audit hash
   - `issued_utc_iso8601` timestamp
6. Click **Export to JSON...**

**Talking point:** *"One click, full audit trail. SHA-256 hash so the
regulator can verify the file hasn't been tampered with. ISO 8601 UTC
timestamp. Visual-only signature disclaimer so legal can't come back
and say we misrepresented it. Ready for submission."*

---

## Closing (optional 30 s)

**The one-liner:** *"Five minutes. Five acts. Design, stress-test,
diagnose, optimise, certify. This is what the next generation of
Australian hydraulic engineers will expect — and we ship it today."*

---

## For the academic audience

**University use case:** Assign students `tutorials/demo_network` for
a semester project. Deliverables:
1. Run `api.validate_network()` — explain each integrity check.
2. Use `api.explain_analysis()` (Learning Mode) to understand the
   pressure/velocity/compliance lessons.
3. Use the What-If panel to derive the sensitivity of the network
   to demand growth and roughness degradation.
4. Generate a safety case and critique the rigid-pipe assumption
   for PVC/PE sections.
5. Compare their manual calcs to `api.knowledge_base('hazen_williams')`
   for fidelity.

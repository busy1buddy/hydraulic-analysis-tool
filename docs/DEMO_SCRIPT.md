# 30-Second Demo: Mining Slurry Pipeline Safety Case

**Scenario:** An engineer is bidding for a 20 km slurry line on a copper
project. The CEO asks "What's our safety story for the regulator?"

This is what the tool does in 30 seconds.

---

## The Demo (live walkthrough)

```python
from epanet_api import HydraulicAPI

api = HydraulicAPI()

# 1. Load the pipeline (1 second)
api.load_network('tutorials/mining_slurry_line/network.inp')

# 2. Run steady-state (2 seconds)
steady = api.run_steady_state()

# 3. Generate the full safety case (3 seconds)
report = api.safety_case_report(
    wave_speed_ms=1100,                    # AS 2280 ductile iron
    valve_closure_s=0.5,                   # worst-case rapid closure
    max_transient_pressure_m=150.0,        # PN15 rating
    slurry_critical_velocity_ms=1.8,       # Durand critical velocity
)

# 4. Show the verdict (instant)
print(report['overall_verdict'])
#   APPROVED / CONDITIONAL APPROVAL / NOT APPROVED

for section in report['sections']:
    print(f"{section['section']}: {section['overall']}")
    for check in section['checks']:
        print(f"  {check['item']:35s} "
              f"measured={check.get('measured')} "
              f"margin={check.get('margin', '-')} "
              f"[{check['status']}]")
```

**Output (on a real slurry line):**

```
NOT APPROVED

1. Steady-State Compliance: PASS
   Minimum service pressure           measured=24.3 m    margin=+4.3 m    [PASS]
   Maximum static pressure            measured=48.1 m    margin=+1.9 m    [PASS]
   Maximum pipe velocity              measured=1.94 m/s  margin=+0.06 m/s [PASS]

2. Worst-Case Transient (Joukowsky): FAIL
   Surge head rise (Joukowsky)        measured=217.6 m                    [INFO]
   Peak transient pressure            measured=265.7 m   margin=-115.7 m  [FAIL]

3. Water Hammer Mitigation: REVIEW
   Longest pipe length                measured=3200 m                     [INFO]
   Critical period 2L/a               measured=5.82 s                     [INFO]
   Valve closure vs critical period   measured=0.50 s    margin=-5.32 s   [REVIEW]

4. Slurry Settling Risk: FAIL
   7 pipes below critical deposition velocity
```

---

## Why this is CEO-grade

- **Regulatory verdict in 6 seconds** — not a 3-week consulting report.
- **Every number cites its Australian Standard** — WSAA WSA 03-2011,
  AS 2200, AS 2280, Durand 1952. No unexplained thresholds.
- **Margins, not just pass/fail** — CEO sees exactly *how close* to the
  limit, so risk can be priced, not just flagged.
- **Failures come with the fix** — "surge protection required, valve
  closure within critical period" — not a vague "check transient."
- **Signature block with RPEQ disclaimer** — formal submission ready.

## What this beats

| Tool | This output? | Time |
|------|--------------|------|
| WaterGEMS (Bentley, ~US$15K) | Steady-state only — no safety verdict | Hours |
| AFT Fathom (~US$10K) | Transient only — no WSAA context | Hours |
| Manual consulting report | Yes, but takes 3 weeks | 3 weeks |
| **This tool** | **Full safety case with verdict** | **6 seconds** |

## Demo Closing Line

> "Every pipeline you design, we can hand the regulator a defensible
> safety case in the time it takes to finish a coffee. That's our
> commercial edge."

---

## Companion: 60-second water utility demo (live UI)

Use `tutorials/demo_network/network.inp` — 10 nodes, 11 pipes, one
ring main, two branches, deliberate pressure and velocity violations.

**Steps:**

1. `python main_app.py` → opens the desktop UI
2. **Help > Run Demo** (one click)
3. Watch: status bar walks through *Load → Analyse → Violations → Summary*
4. Popup: network health grade + root-cause analysis + ranked fix options
   with estimated AUD costs

**Output the engineer sees:**

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

**Key talking point:** *"One click. Ten seconds. The engineer now has a
costed remediation plan they can put in front of a council committee."*


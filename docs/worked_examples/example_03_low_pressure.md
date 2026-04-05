# Example 3 — Find the Cause of Low Pressure

**Given:** A steady-state analysis of the demo network shows node J9
with pressure 12.1 m — below the WSAA 20 m minimum.

**Required:** Identify the cause and select a remediation option.

## Manual diagnosis

1. **Check elevation.** J9 elevation = 55 m AHD. Reservoir R1 at
   100 m head. Available static head = 100 − 55 = 45 m.
2. **Trace the supply path.** J9 is fed from J3 through pipe P10.
3. **Compute pipe headloss** using Hazen-Williams:

   ```
   hL = 10.67 × L × Q^1.852 / (C^1.852 × D^4.87)
   L = 400 m, Q = 0.012 m³/s, C = 130, D = 0.080 m
   hL = 10.67 × 400 × 0.012^1.852 / (130^1.852 × 0.080^4.87)
   hL = 10.67 × 400 × 0.000318 / (8097 × 4.12e-6)
   hL ≈ 40.6 m
   ```

4. **Apply the head balance:**
   ```
   Pressure at J9 = source head − headloss − elevation
                  ≈ 100 − (headloss from R1 to J3) − 40.6 − 55
   ```

5. The problem is clear: pipe P10 (DN80, 400 m) creates ~40 m
   headloss by itself. It's **undersized**.

## Tool verification

```python
from epanet_api import HydraulicAPI
api = HydraulicAPI()
api.load_network('tutorials/demo_network/network.inp')
rc = api.root_cause_analysis()

for issue in rc['explanations']:
    if issue['location'] == 'J9':
        print(issue['root_cause'])
        print()
        for fix in issue['fixes']:
            print(f"  {fix['option']}")
            print(f"    Cost: ${fix['est_cost_aud']:,} AUD")
            print(f"    Effect: {fix['effect']}")
```

**Output:**

```
Pressure at J9 is 12.1 m (WSAA min 20 m). Pipe P10 carries 12.0 LPS
at 2.39 m/s through DN80 — this is the limiting segment.

  Upgrade P10 DN80 → DN100
    Cost: $56,000 AUD
    Effect: Lowers velocity and headloss on the critical path, raising
    downstream pressure.
  Parallel main alongside P10 (DN80)
    Cost: $34,000 AUD
    Effect: Halves carrying burden on existing pipe, reduces headloss
    ~75% (Q^1.85 law).
```

## The cost-benefit comparison

Per `find_best_upgrade`:

- Upsize P10 DN80 → DN100: improves min pressure by 1.1 m at
  $56,000 (0.020 m per $1,000)
- Parallel main DN80: improves min pressure by ~3.4 m at $34,000
  (0.100 m per $1,000) — **5× better value per dollar**

## References

- Hazen-Williams formula: White, Fluid Mechanics 8th ed. Ch. 6
- WSAA WSA 03-2011 Table 3.1 — 20 m minimum pressure
- `api.knowledge_base('hazen_williams')`
- `api.root_cause_analysis()`
- `api.find_best_upgrade()`

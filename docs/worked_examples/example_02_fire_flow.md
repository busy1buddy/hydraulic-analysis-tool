# Example 2 — Fire Flow Compliance Check

**Given:** A residential network must maintain ≥ 12 m residual
pressure at the most remote hydrant while delivering 25 L/s fire flow
(WSAA WSA 03-2011 §3.4).

**Required:** Identify which hydrants pass/fail the fire flow test.

## Manual procedure

1. Determine hydrants on the network — typically every dead-end and
   every ~60 m on the main.
2. At each hydrant, add 25 L/s demand to the relevant junction.
3. Solve the network under peak-hour demand conditions.
4. Record the residual pressure at the tested junction.
5. If residual ≥ 12 m → PASS; otherwise FAIL.

The critical node is usually the **furthest from a reservoir** with
the **smallest connecting pipe**.

## Tool verification

```python
from epanet_api import HydraulicAPI

api = HydraulicAPI()
api.load_network('tutorials/fire_flow_demand/network.inp')
results = api.run_fire_flow(flow_lps=25, residual_m=12)

# Per-junction results
for node, info in results['tests'].items():
    status = 'PASS' if info['residual_m'] >= 12 else 'FAIL'
    print(f'{node}: {info["residual_m"]:.1f} m [{status}]')

# Summary
print(f'Pass: {results["n_pass"]}, Fail: {results["n_fail"]}')
```

## Example result

On `tutorials/fire_flow_demand/network.inp`:

```
J1: 28.4 m [PASS]
J2: 24.1 m [PASS]
J3: 18.7 m [PASS]
J4: 10.2 m [FAIL]   <- most remote, DN150 supply
J5: 15.8 m [PASS]
```

## How to fix a failing fire flow

1. **Upsize the critical path.** Use `api.root_cause_analysis()` or
   `api.find_best_upgrade()` to identify the limiting pipe.
2. **Add a second hydrant closer.** Reduces the flow carried by any
   single pipe.
3. **Increase source pressure.** Pump or reservoir lift adds residual
   uniformly.
4. **Reduce concurrent demand.** Some utilities allow fire flow
   tests at average-day rather than peak-hour conditions — check
   your local authority.

## References

- WSAA WSA 03-2011 §3.4 — 25 L/s @ 12 m residual
- `api.knowledge_base('fire_flow')` — standard reference
- `api.run_fire_flow()` — tool implementation

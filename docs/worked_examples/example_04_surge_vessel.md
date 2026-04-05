# Example 4 — Size a Surge Vessel for a 500 m Pipeline

**Given:** A DN300 ductile iron pipeline, L = 500 m, steady-state
velocity v = 1.8 m/s, wave speed a = 1100 m/s (AS 2280), maximum
allowable transient pressure P_max = 80 m (PN8 working pressure).

**Required:** Check if surge protection is needed, and if so, size
the bladder accumulator.

## Step 1 — Joukowsky surge head

```
ΔH = a × Δv / g
   = 1100 × 1.8 / 9.81
   = 201.8 m
```

This assumes instantaneous closure (upper bound). If the steady-state
operating head is already 40 m, the peak transient pressure would be:

```
P_peak = 40 + 201.8 = 241.8 m  ≫  80 m (PN8 rating)
```

**Surge protection is required.**

## Step 2 — Critical period

```
T_c = 2L / a = 2 × 500 / 1100 = 0.91 s
```

Any valve closure faster than 0.91 s is hydraulically "instantaneous"
and produces the full Joukowsky surge.

## Step 3 — Slow-close option

If the valve can be slowed to T_close ≥ 5 × T_c ≈ 5 s, the surge
reduces significantly (linear interpolation):

```
ΔH_reduced ≈ ΔH × T_c / T_close = 201.8 × 0.91 / 5 = 36.7 m
```

This may be enough if the valve actuator can be replaced.

## Step 4 — Bladder accumulator sizing

If slow-close isn't feasible, size a bladder accumulator.
Approximate formula (polytropic, n = 1.2):

```
V_gas = V_liquid × (P_0 / P_max)^(1/n) × [(P_max / P_0)^(1/n) - 1]
```

where V_liquid is the volume needed to absorb the pressure spike.
For conservative design:

```
V_liquid = A × v × T_c = 0.0707 × 1.8 × 0.91 = 0.116 m³ = 116 L
```

A typical choice: **200 L bladder tank** pre-charged to 30 m
(below P_max = 80 m).

## Tool verification

```python
from epanet_api import HydraulicAPI
api = HydraulicAPI()

# Joukowsky surge
surge = api.joukowsky(wave_speed=1100, velocity_change=1.8)
print(f"Head rise: {surge['head_rise_m']} m")  # ~201.8 m

# Safe closure time
safe = api.calculate_safe_closure_time(
    pipe_length_m=500, wave_speed_ms=1100,
    max_head_m=80, steady_velocity_ms=1.8)
print(f"Safe closure: {safe['safe_closure_time_s']} s")

# Bladder accumulator
bladder = api.size_bladder_accumulator(
    max_surge_m=201.8, operating_pressure_m=40,
    pipe_diameter_m=0.3, pipe_length_m=500,
    velocity_change_ms=1.8)
print(f"Recommended volume: {bladder['volume_L']} L")
```

## References

- Joukowsky 1898; Wylie & Streeter, Fluid Transients in Systems
- AS 2200 — Design charts for water supply and sewerage systems
- AS 2280 — Ductile iron pressure pipes
- `api.knowledge_base('joukowsky')`
- `api.size_bladder_accumulator()`

# Example 1 — Pipe Sizing for Target Velocity

**Given:** A pipeline must carry Q = 5 L/s at a target velocity of
v = 1.0 m/s.

**Required:** Select the smallest standard DN that meets the target.

## Manual calculation

From continuity: A = Q / v

```
Q = 5 L/s = 0.005 m³/s
v = 1.0 m/s
A = 0.005 / 1.0 = 0.005 m² = 5000 mm²
```

From A = π·D²/4:

```
D = sqrt(4·A / π)
D = sqrt(4 × 0.005 / 3.14159)
D = sqrt(0.006366)
D = 0.0798 m = 79.8 mm
```

Select the next available DN from AS/NZS 1477 PVC series:
**DN 100** (OD 110 mm, ID ~100 mm).

Actual velocity at DN100:
```
A_DN100 = π × (0.100)² / 4 = 0.007854 m²
v_DN100 = 0.005 / 0.007854 = 0.637 m/s
```

At DN80 (next smaller option, ID ~75 mm):
```
A_DN80 = π × (0.075)² / 4 = 0.004418 m²
v_DN80 = 0.005 / 0.004418 = 1.132 m/s  — exceeds 1.0 m/s target
```

So **DN100** is the correct selection: actual velocity 0.64 m/s,
well below the 2.0 m/s WSAA limit, with headroom for future demand
growth.

## Tool verification

```python
from epanet_api import HydraulicAPI
import math

# Calculate diameter for a target velocity
Q_lps = 5.0
v_target = 1.0
A_required = (Q_lps / 1000.0) / v_target   # m²
D_required_m = math.sqrt(4 * A_required / math.pi)
print(f'Required D: {D_required_m * 1000:.1f} mm')   # 79.8 mm
# Next DN from the ladder:
# [50, 75, 100, 150, 200, 250, 300, ...]
# 79.8 mm -> DN100
```

## Why DN100, not DN75?

The AS/NZS 1477 PVC ID at DN80 is ~75 mm. That exceeds the target
velocity. Always round **up** to the next size when the calculated
diameter falls between two standard DNs — selecting smaller pushes
velocity up and shortens pipe life.

## References

- AS/NZS 1477:2017 PVC-U pressure pipes
- WSAA WSA 03-2011 §3.2.3 velocity limits
- `api.knowledge_base('wsaa_max_velocity')` — 2.0 m/s max
- `api.knowledge_base('as1477_pvc')` — DN-to-OD mapping

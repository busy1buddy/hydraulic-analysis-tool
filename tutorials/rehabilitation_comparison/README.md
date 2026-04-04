# Tutorial 10: Pipeline Rehabilitation Comparison

## What This Network Models

The same 6-junction, 7-pipe distribution network in two states:
- **network.inp** — existing old cast iron pipes, C=80 (tuberculated, degraded)
- **network_relined.inp** — same pipes after cement mortar relining, C=130

This tutorial quantifies the hydraulic benefit of pipe rehabilitation — a common cost-benefit analysis in Australian water utility asset management programs.

Network topology (identical in both files):
- **R1** (reservoir, 80 m head) — unchanged between scenarios
- **J1–J6** at 37–48 m elevation, same demands in both files
- Total base demand: 31 LPS
- DN150–DN300 pipes, same diameters in both files — only roughness (C-factor) changes

## The Hazen-Williams Roughness Effect

The Hazen-Williams formula is: V = 0.8492 × C × R^0.63 × S^0.54

Where C is the roughness coefficient. A higher C means lower friction for the same flow:
- Old cast iron C=80: high friction, significant headloss
- Relined ductile iron C=130: 63% higher C-value, dramatically lower headloss

For the same flow rate, headloss is approximately proportional to (C_old/C_new)^1.85 = (80/130)^1.85 ≈ 0.40. The rehabilitated network has approximately 40% of the headloss of the old network.

## Key Things to Observe

1. **Pressure at J4 and J6 (worst-served nodes)**: J4 is the highest-demand node (7 LPS) and J6 is the end of line. Compare pressures between old and relined scenarios at these junctions.

2. **Headloss along P1 (DN300 trunk)**: This is the largest pipe, but with C=80 it still produces significant headloss at 31 LPS total flow. Compare the headloss in P1 between the two scenarios.

3. **Peak demand compliance**: Under OldCastIron_Peak (1.5× demand), check whether J4 and J6 fall below WSAA 20 m minimum. Then check Relined_Peak — the pressure recovery should bring these junctions back into compliance.

4. **Quantify the improvement**: For each junction, calculate: Pressure improvement (m) = P_relined − P_old_iron. This number can be used in asset management cost-benefit analysis (e.g., pressure improvement avoids future augmentation capex).

5. **Headloss per 100m**: A useful comparative metric. Old cast iron P3 (DN200, 450m) at ~10 LPS flow: headloss ~8–10 m/100m. Relined: ~3–4 m/100m.

## Expected Results

| Scenario            | J4 Pressure (m) | J6 Pressure (m) | WSAA Compliant? |
|--------------------|-----------------|-----------------|-----------------|
| OldCastIron Base   | ~18–22          | ~22–26          | J4 marginal     |
| OldCastIron Peak   | ~12–16          | ~14–18          | Both fail        |
| Relined Base       | ~27–32          | ~30–35          | Yes             |
| Relined Peak       | ~22–27          | ~25–30          | Yes             |

The rehabilitation moves the network from non-compliant (peak demand) to fully compliant without any pipe upsizing — demonstrating that roughness improvement alone can resolve pressure deficiency.

## Australian Standards References

- **AS 2280**: Ductile iron pipes, C=120–140 after relining (cement mortar lining restores smooth bore)
- **WSAA**: Minimum service pressure 20 m — old network fails at peak demand, relined passes
- Typical cast iron pipe age in Australian networks: 80–120 years, C-value typically 60–100 depending on tuberculation severity
- Cement mortar lining rehabilitation per **AS/NZS 4158** — standard method for ductile iron and cast iron pipes
- Asset management decision criteria: if pressure improvement ≥ 5 m at critical nodes, rehabilitation is typically preferred over replacement

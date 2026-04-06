# Rehabilitation Comparison — Walkthrough

## Engineering Context

An aged cast iron network with deteriorated Hazen-Williams C-factor of 80 (original condition). A second network file (`network_relined.inp`) represents the same pipes after cement mortar relining, which restores the C-factor to 130. This is a common rehabilitation strategy for Australian water utilities managing ageing infrastructure without full pipe replacement.

## Step-by-Step Instructions

1. **Open the original network:** File > Open, select `network.inp` from this folder.
2. **Run steady-state analysis:** Press **F5** and note the pressures.
3. **Open the relined network:** File > Open, select `network_relined.inp`.
4. **Run steady-state analysis:** Press **F5** and compare pressures.

## Expected Results (Original, C=80)

| Node | Pressure (m) |
|------|-------------|
| J2   | 29.9 (lowest) |
| J6   | 34.9        |

- **Maximum velocity:** 0.83 m/s
- **Compliance score:** 90.4 / 100
- **WSAA warnings:** 0

## What to Look For

- Even with C=80, this network barely meets WSAA compliance — J2 at 29.9 m has only 9.9 m margin above the 20 m minimum.
- Higher demand growth would push J2 below 20 m, triggering non-compliance.
- The relined network (C=130) will show significantly higher pressures at the same nodes due to reduced friction losses.
- Relining is typically 30-50% of the cost of full pipe replacement.

## Key Learning Points

- C-factor directly affects headloss: lower C means more friction, lower pressures.
- Cast iron pipes degrade from C=130 (new) to C=60-80 over 50-80 years due to tuberculation.
- Cement mortar relining restores C to 120-140 and extends pipe life by 30-50 years.
- Always model both existing and rehabilitated conditions to justify the investment.

## Exercise

Load `network_relined.inp` and compare J2 pressure to the original 29.9 m. How much pressure improvement does relining provide? Calculate the percentage improvement in available pressure above the 20 m WSAA minimum.

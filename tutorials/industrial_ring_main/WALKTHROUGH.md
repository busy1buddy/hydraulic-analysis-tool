# Industrial Ring Main — Walkthrough

## Engineering Context

A large-diameter DN400-600 industrial ring main serving a mining or heavy industrial site with 208 LPS total demand. Industrial and mining networks operate under different pressure rules than residential systems — WSAA's 50 m residential maximum does not apply. Instead, industrial applications typically allow pressures up to 120 m, with appropriate pipe class selection (PN16 or PN20).

## Step-by-Step Instructions

1. **Open the network:** File > Open, select `network.inp` from this folder.
2. **Run steady-state analysis:** Press **F5**.
3. **Note the high pressure warnings** — these apply to residential thresholds.
4. **Override compliance thresholds** to industrial limits using the API or settings.

## Expected Results

| Node | Pressure (m) |
|------|-------------|
| J1   | 94.5        |
| J5   | 107.2       |

- **Maximum velocity:** 0.83 m/s
- **Compliance score:** 80.0 / 100
- **WSAA warnings:** 8 (all nodes exceed 50 m residential maximum)

## What to Look For

- All pressures are between 94.5 m and 107.2 m — well above residential limits but acceptable for industrial use.
- Velocities are moderate at 0.83 m/s — well within the 2.0 m/s limit.
- The ring topology provides redundancy — any single pipe can be isolated for maintenance.
- Large diameters (DN400-600) keep friction losses low despite high flow rates.

## Key Learning Points

- Industrial and mining networks have different compliance thresholds than residential systems.
- Use `set_compliance_thresholds(max_pressure_m=120)` to apply industrial limits.
- Ring mains provide operational redundancy critical for continuous mining operations.
- Pipe class must match the operating pressure — PN16 for up to 160 m, PN20 for up to 200 m.

## Exercise

Override the compliance threshold to 120 m maximum pressure. How many warnings remain? With the industrial threshold applied, all nodes should be compliant since the maximum pressure (107.2 m) is below 120 m.

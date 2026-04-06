# Pump Station — Walkthrough

## Engineering Context

A single 55 kW pump lifts water from reservoir R1 (20 m elevation sump) to an elevated zone at 60 m+. This is a common configuration for booster stations and mine site water supply. The pump curve must provide enough head to overcome elevation difference and friction losses while maintaining WSAA minimum pressure.

## Step-by-Step Instructions

1. **Open the network:** File > Open, select `network.inp` from this folder.
2. **Run steady-state analysis:** Press **F5**.
3. **Observe the red/orange warnings** — most nodes will flag as non-compliant.
4. **Check the pump operating point** in the results panel.

## Expected Results

| Node | Pressure (m) |
|------|-------------|
| J1   | 4.6         |
| J5   | 14.2        |

- **Maximum velocity:** 0.49 m/s
- **Compliance score:** 79.5 / 100
- **WSAA warnings:** 5 (all nodes below 20 m minimum pressure)

## What to Look For

- Every junction fails the WSAA minimum pressure requirement of 20 m.
- J1 at 4.6 m is critically low — customers would experience very poor supply.
- The pump does not provide enough head to overcome the 40+ m elevation rise plus friction.
- Velocity is low, meaning the pump is delivering flow but insufficient head.

## Key Learning Points

- Pump selection must account for static lift (elevation difference) plus friction losses plus required residual pressure.
- A compliance score below 80 indicates a system that does not meet service standards.
- In practice, this pump would need to be upsized or a second pump added in series.

## Exercise

What pump head increase would give J1 >= 20 m pressure? The pump needs at least 15.4 m more head (20.0 - 4.6 = 15.4 m) at the current operating point. Try editing the pump curve to add this head and re-run F5.

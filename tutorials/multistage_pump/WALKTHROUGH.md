# Multistage Pump — Walkthrough

## Engineering Context

Two pumps operating in series to supply water to a high-elevation zone. Series pumps add their heads together, which is necessary when a single pump cannot provide sufficient head. This configuration is common in mine dewatering and high-rise building supply. However, if one pump trips, the remaining pump may not sustain the system — making this a critical failure scenario for transient analysis.

## Step-by-Step Instructions

1. **Open the network:** File > Open, select `network.inp` from this folder.
2. **Run steady-state analysis:** Press **F5**.
3. **Observe the severe pressure warnings** — negative pressures indicate system failure.
4. **Run transient analysis:** Press **F6** to see pump trip surge effects.

## Expected Results

| Node | Pressure (m) |
|------|-------------|
| J1   | 12.5        |
| J4   | -32.8       |

- **Maximum velocity:** 0.63 m/s
- **Compliance score:** 56.5 / 100
- **WSAA warnings:** 5 (negative pressures at J2-J5)

## What to Look For

- J4 at -32.8 m means the node is 32.8 m above the hydraulic grade line — water cannot reach it.
- J1 at 12.5 m is below the 20 m WSAA minimum but at least positive.
- A score of 56.5 indicates a fundamentally undersized system.
- Negative pressures in practice cause column separation, air ingress, and potential pipe collapse.
- Transient analysis (F6) will reveal pressure surges when a pump trips suddenly.

## Key Learning Points

- Series pumps add head: if each pump provides H metres, total is 2H metres.
- Loss of one pump in a series arrangement halves the available head — often causing system collapse.
- Negative pressures are physically impossible in steady flow — they indicate the model predicts vacuum conditions.
- Transient surge from pump trip can exceed the steady-state pressure by 2-3 times (Joukowsky effect).

## Exercise

What happens if you increase each pump's head by 50 m? Edit the pump curves and re-run F5. Which nodes become compliant (pressure >= 20 m)? How does the compliance score change?

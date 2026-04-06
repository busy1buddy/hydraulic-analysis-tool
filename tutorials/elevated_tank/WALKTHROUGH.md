# Elevated Tank — Walkthrough

## Engineering Context

A gravity-fed network supplied from an elevated storage tank. Elevated tanks provide pressure through static head and buffer supply during peak demand. However, steady-state analysis of tank networks can produce misleading results if the tank initial level is incorrectly set — Extended Period Simulation (EPS) is needed to see realistic tank behaviour.

## Step-by-Step Instructions

1. **Open the network:** File > Open, select `network.inp` from this folder.
2. **Run steady-state analysis:** Press **F5**.
3. **Note the extreme pressure values** — these indicate a configuration issue.
4. **Run EPS analysis:** Press **F7** for a 24-hour extended period simulation.

## Expected Results (Steady-State)

- **Pressures:** Extremely negative (approximately -50 m at multiple nodes)
- **Compliance score:** 61.4 / 100
- **WSAA warnings:** 10

## What to Look For

- Negative pressures in steady-state indicate the tank water level is set too low relative to node elevations, or there is a connectivity issue.
- A score of 61.4 with 10 warnings means the network is non-functional in its current state.
- This is a realistic scenario — misconfigured tank levels are a common modelling error.
- EPS (F7) will show how tank level changes over time and when the system recovers or empties.

## Key Learning Points

- Steady-state analysis captures a single snapshot — it does not show tank filling/draining behaviour.
- Tank initial level must be set between minimum and maximum level, and above the hydraulic grade line of downstream nodes.
- Negative pressures mean nodes are above the hydraulic grade line — water cannot reach them by gravity alone.
- Always validate tank networks with EPS before drawing conclusions.

## Exercise

Run **EPS (F7)** for 24 hours. How does the tank level change over the simulation period? Does the tank drain completely, or does it stabilise? Try adjusting the tank initial level upward and re-running to see the effect.

# Dead-End Network — Walkthrough

## Engineering Context

A branching tree network with an 800 m dead-end branch (pipes P7-P8-P9 leading to node J8). Dead-ends are common in suburban cul-de-sacs and rural extensions. They create water quality risks because flow is one-directional and velocities drop near the terminal node.

## Step-by-Step Instructions

1. **Open the network:** File > Open, select `network.inp` from this folder.
2. **Run steady-state analysis:** Press **F5**.
3. **Look at the pipe velocity colouring** — note how velocity fades toward the dead-end branch.
4. **Check the compliance panel** for warnings.

## Expected Results

| Node | Pressure (m) |
|------|-------------|
| J1   | 30.7        |
| J8   | 41.6        |

- **Maximum velocity:** P1 = 0.89 m/s
- **Dead-end velocity:** P9 = 0.04 m/s
- **Compliance score:** 91.9 / 100
- **WSAA warnings:** 0

## What to Look For

- Pipe P9 has a velocity of only 0.04 m/s — nearly stagnant water.
- Pressures are all within the 20-50 m WSAA range, so no pressure warnings fire.
- The real risk at dead-ends is water quality, not pressure.
- Stagnant water leads to loss of chlorine residual and potential bacterial growth.

## Key Learning Points

- Dead-ends pass pressure compliance but fail water quality expectations.
- Velocities below 0.1 m/s indicate stagnation risk.
- Real-world solutions include looping the dead-end back to the main, or installing automatic flushing devices.

## Exercise

Run **Water Quality > Age** analysis. Which node exceeds 24-hour stagnation? The dead-end node J8 should show the highest water age due to minimal throughflow.

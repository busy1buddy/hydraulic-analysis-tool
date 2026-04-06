# Theory Manual — Hydraulic Analysis Toolkit

This document defines the engineering basis for every calculation implemented in the
toolkit. Each section states the governing equation, variable definitions with units,
valid range, source citation, code location, and verification status.

All equations use the Darcy friction factor convention unless explicitly noted.
All internal solver quantities are SI; display conversions are documented in
Section 8 (Unit Conventions).

---

## 1. Steady-State Hydraulics

### 1.1 Governing Equations

The solver enforces two conservation laws at every timestep:

**Conservation of mass (continuity) at each junction:**

    sum(Q_in) - sum(Q_out) - q_demand = 0

where Q is pipe flow (m3/s) and q_demand is nodal demand (m3/s).

**Conservation of energy around each loop:**

    sum(h_L) = 0   (closed loop)
    sum(h_L) = dH   (path between fixed-head nodes)

where h_L is headloss across a pipe (m) and dH is the head difference (m).

The system is solved using the Todini and Pilati (1988) gradient algorithm as
implemented in the EPANET 2.2 solver via WNTR.

- **Convergence criterion:** 0.001 accuracy on heads
- **Maximum iterations:** 200 trials
- **Solver:** WNTR EpanetSimulator (demand-driven)
- **Code location:** `epanet_api_monolith.py:309-388` (`run_steady_state`)

### 1.2 Hazen-Williams Headloss

    h_L = (10.67 x L x Q^1.852) / (C^1.852 x D^4.87)

| Variable | Description | Unit | Valid Range |
|----------|-------------|------|-------------|
| h_L | Headloss | m | >= 0 |
| L | Pipe length | m | > 0 |
| Q | Volume flow rate | m3/s | >= 0 |
| C | Hazen-Williams roughness coefficient | dimensionless | 40-150 |
| D | Internal pipe diameter | m | 0.05-3.0 |

**Source:** Lamont (1981) "Common Pipe Flow Formulas Compared with the Theory
of Roughness". Journal AWWA 73(5):274-280.

**Implementation:** EPANET solver via WNTR. Default headloss formula is H-W
(`epanet_api_monolith.py:37`).

**Verification:** D7 hand calculations confirmed against Net1 benchmark.

### 1.3 Darcy-Weisbach Headloss

    h_L = f x (L/D) x (V^2 / (2g))

| Variable | Description | Unit |
|----------|-------------|------|
| f | Darcy friction factor | dimensionless |
| L | Pipe length | m |
| D | Internal diameter | m |
| V | Mean flow velocity | m/s |
| g | Gravitational acceleration (9.81) | m/s2 |

**Friction factor — Colebrook-White (implicit):**

    1/sqrt(f) = -2 x log10(e/D/3.7 + 2.51/(Re x sqrt(f)))

Solved iteratively (up to 50 iterations, convergence tolerance 1e-8).

| Variable | Description | Unit |
|----------|-------------|------|
| e | Absolute roughness | m |
| Re | Reynolds number = rho x V x D / mu | dimensionless |

**Source:** Colebrook (1939); White (1994) "Fluid Mechanics" 8th ed.

**Code location:** `slurry_solver.py:353-367` (`_colebrook_white`)

**Verification:** D7 hand calculations match to 4 significant figures.

---

## 2. Non-Newtonian Fluid Mechanics (Slurry)

All slurry headloss calculations use the Darcy-Weisbach equation with
rheology-specific friction factors. The Darcy convention (f = 64/Re for laminar
Newtonian flow) is used throughout. The Fanning convention (f = 16/Re) is
**never** used internally; any correlation that returns Fanning f is multiplied
by 4 before application.

### 2.1 Bingham Plastic Model

**Constitutive equation:**

    tau = tau_y + mu_p x (dv/dr)

| Variable | Description | Unit |
|----------|-------------|------|
| tau | Shear stress | Pa |
| tau_y | Yield stress | Pa |
| mu_p | Plastic viscosity | Pa.s |
| dv/dr | Shear rate | 1/s |

**Bingham Reynolds number:**

    Re_B = rho x V x D / mu_p

**Hedstrom number:**

    He = rho x tau_y x D^2 / mu_p^2

**Buckingham-Reiner laminar friction factor (Darcy convention):**

    f = (64/Re_B) x [1 + He/(6 x Re_B) - He^4/(3e7 x Re_B^7)]

- Uses Darcy convention (64/Re), NOT Fanning (16/Re).
- Floor guard: f >= 64/Re_B (Newtonian laminar Darcy floor).
- This guard prevents the Buckingham-Reiner correction term from
  producing a friction factor below the Newtonian baseline.

**Critical Reynolds number for transition:**

    Re_crit = 2100 x (1 + He/12000),   capped at 40000

**Source:** Slatter (1995) "Transitional and Turbulent Flow of Non-Newtonian
Slurries in Pipes". PhD thesis, University of Cape Town.

**Wilson-Thomas turbulent friction factor:**

For turbulent Bingham flow the solver uses the Darby (Chemical Engineering
Fluid Mechanics, 3rd ed., Eq. 7.17) Metzner-Reed correlation:

    1/sqrt(f) = 4 x log10(Re_B x sqrt(f)) - 0.4

Solved iteratively (50 iterations, tolerance 1e-8). The result is blended
with the Colebrook-White roughness correction; the higher of the two values
is used, because wall roughness can only increase friction.

**Code location:** `slurry_solver.py:87-167` (`bingham_plastic_headloss`)
and `slurry_solver.py:294-336` (helper functions `_bingham_critical_reynolds`,
`_wilson_thomas_friction`).

**Verification:** D7 hand calculations for 30% and 50% tailings slurry
confirmed within 2% of Paterson & Cooke benchmark data.

### 2.2 Power Law Model

**Constitutive equation:**

    tau = K x (dv/dr)^n

| Variable | Description | Unit | Typical Range |
|----------|-------------|------|---------------|
| K | Consistency index | Pa.s^n | 0.01-10 |
| n | Flow behaviour index | dimensionless | 0.1-1.5 |

n < 1: shear-thinning (pseudoplastic)
n > 1: shear-thickening (dilatant)
n = 1: Newtonian

**Metzner-Reed generalised Reynolds number:**

    Re_MR = rho x V^(2-n) x D^n / [K x 8^(n-1) x ((3n+1)/(4n))^n]

**Laminar friction factor (Darcy):**

    f = 64 / Re_MR

**Turbulent friction factor — Dodge-Metzner correlation:**

    1/sqrt(f_F) = (4/n^0.75) x log10(Re_MR x f_F^(1-n/2)) - 0.4/n^1.2

This returns Fanning f_F. The code multiplies by 4 to convert to Darcy:

    f_Darcy = 4 x f_Fanning

Solved iteratively (50 iterations, tolerance 1e-8).

**Critical Reynolds number:** Re_crit = 2100 (approximate for power law fluids).

**Source:** Dodge & Metzner (1959) "Turbulent Flow of Non-Newtonian Systems".
AIChE Journal 5(2):189-204.

**Code location:** `slurry_solver.py:170-233` (`power_law_headloss`) and
`slurry_solver.py:339-350` (`_dodge_metzner_friction`).

**Verification:** D7 hand calculations for polymer solution (K=0.5, n=0.6)
confirmed against published Dodge-Metzner charts.

### 2.3 Herschel-Bulkley Model

**Constitutive equation:**

    tau = tau_y + K x (dv/dr)^n

This is the most general model. It reduces to:
- Bingham Plastic when n = 1
- Power Law when tau_y = 0
- Newtonian when tau_y = 0 and n = 1

**Apparent viscosity at the wall:**

    gamma_wall = 8V/D   (approximate wall shear rate)
    tau_wall = tau_y + K x gamma_wall^n
    mu_app = tau_wall / gamma_wall

**Generalised Reynolds number:**

    Re_gen = rho x V x D / mu_app

**Friction factor:**
- Laminar (Re_gen < 2100): f = 64 / Re_gen (Darcy)
- Turbulent (Re_gen >= 2100): Colebrook-White with apparent viscosity

**Code location:** `slurry_solver.py:236-287` (`herschel_bulkley_headloss`)

**Verification:** D7 hand calculations for drilling mud (tau_y=10 Pa, K=0.3,
n=0.7) confirmed.

### 2.4 Settling and Deposition

#### 2.4.1 Single-Particle Settling Velocity

**Stokes regime (Re_p < 1):**

    V_s = d^2 x (rho_s - rho_f) x g / (18 x mu)

**Source:** Stokes (1851)

**Transitional regime (1 < Re_p < 1000) — Schiller-Naumann:**

    C_D = (24/Re_p) x (1 + 0.15 x Re_p^0.687)
    V_s = sqrt(4 x d x (rho_s - rho_f) x g / (3 x C_D x rho_f))

Solved iteratively (20 iterations, tolerance 1e-6).

**Source:** Schiller & Naumann (1935)

**Newton regime (Re_p > 1000):**

    C_D = 0.44
    V_s = sqrt(4 x d x (rho_s - rho_f) x g / (3 x 0.44 x rho_f))

| Variable | Description | Unit |
|----------|-------------|------|
| d | Particle diameter | m |
| rho_s | Solid density | kg/m3 |
| rho_f | Fluid density | kg/m3 |
| mu | Dynamic viscosity | Pa.s |
| C_D | Drag coefficient | dimensionless |
| Re_p | Particle Reynolds number | dimensionless |

**Code location:** `slurry_solver.py:486-567` (`settling_velocity`)

**Verification:** D7 hand calculations for sand (d=0.5 mm, rho=2650 kg/m3)
confirmed across all three regimes.

#### 2.4.2 Critical Deposition Velocity — Durand Correlation

    V_D = F_L x sqrt(2 x g x D x (S - 1))

| Variable | Description | Unit |
|----------|-------------|------|
| V_D | Critical deposition velocity | m/s |
| F_L | Durand limit deposit velocity coefficient | dimensionless |
| D | Pipe internal diameter | m |
| S | Specific gravity of solids (rho_s/rho_f) | dimensionless |

F_L depends on particle size and concentration:
- d < 0.1 mm: F_L = 0.8 + 2.0 x C_v
- 0.1 <= d < 0.5 mm: F_L = 1.0 + 1.5 x C_v
- 0.5 <= d < 2.0 mm: F_L = 1.3 + 1.0 x C_v
- d >= 2.0 mm: F_L = 1.5 + 0.5 x C_v
- F_L clamped to [0.5, 2.0]

**Source:** Durand (1952) "Hydraulic Transport of Coal and Sand".
Proceedings of a Colloquium on Hydraulic Transport, National Coal Board, UK.

**Code location:** `slurry_solver.py:570-634` (`critical_deposition_velocity`)

#### 2.4.3 Critical Velocity — Wasp Correlation

    V_c = 3.116 x C_v^0.186 x (d/D)^(-0.168) x (w_s/sqrt(gD))^0.364 x sqrt(2gD(S-1))

**Source:** Wasp, Kenny & Gandhi (1977) "Solid-Liquid Flow Slurry Pipeline
Transportation". Trans Tech Publications.

**Code location:** `slurry_solver.py:714-775` (`wasp_critical_velocity`)

#### 2.4.4 Concentration Profile — Rouse Equation

    C(y)/C_a = [(h-y)/y x a/(h-a)]^z

where z = w_s / (kappa x u*), kappa = 0.4 (von Karman constant),
u* = V x sqrt(f/8) (friction velocity).

**Source:** Rouse (1937); Wasp et al. (1977)

**Code location:** `slurry_solver.py:637-711` (`concentration_profile`)

#### 2.4.5 Settling Compliance

Pipes with velocity = 0 are flagged as highest settling risk. Pipes with
0 < V < 1.0 m/s are flagged as below the settling limit for non-Newtonian
fluids. Pipes with V > 3.0 m/s are flagged for pipe wear risk.

**Code location:** `slurry_solver.py:454-474` (`_slurry_compliance`)

### 2.5 Pump Derating for Slurry

**Head correction:**

    H_slurry = H_water x C_H
    C_H = max(0.5, 1.0 - 0.5 x C_v)

**Efficiency correction:**

    eta_slurry = eta_water x C_eta
    C_eta = max(0.4, 1.0 - 0.6 x C_v)

**Power increase factor:**

    P_factor = S_m x (1/C_H) x (1/C_eta)
    S_m = 1 + C_v x (S - 1)    (mixture specific gravity)

**Source:** Wilson, Addie & Clift (2006) "Slurry Transport Using Centrifugal
Pumps", 3rd ed., Springer, Chapter 7.

**Code location:** `slurry_solver.py:778-837` (`derate_pump_for_slurry`)

---

## 3. Transient Analysis (Water Hammer)

### 3.1 Joukowsky Equation

**Head rise from instantaneous velocity change:**

    delta_H = a x delta_V / g

**Pressure rise (uses actual fluid density, not 1000 kg/m3):**

    delta_P = rho x a x delta_V

| Variable | Description | Unit |
|----------|-------------|------|
| delta_H | Head change | m |
| delta_P | Pressure change | Pa |
| a | Wave speed | m/s |
| delta_V | Velocity change | m/s |
| g | Gravitational acceleration (9.81) | m/s2 |
| rho | Fluid density (actual, not hardcoded) | kg/m3 |

**Critical constraint:** For slurry service, rho must be the actual mixture
density (e.g. 1300-1900 kg/m3), never the default 1000 kg/m3.

**Source:** Joukowsky (1898); Thorley (2004) "Fluid Transients in Pipeline
Systems", 2nd ed., Professional Engineering Publishing.

### 3.2 Critical Closure Time

    t_c = 2L / a

A valve closure faster than t_c produces a full Joukowsky surge. The
recommended closure time is >= 2 x t_c (i.e. >= 4L/a), with a minimum of
5 seconds for actuated valves.

**Source:** Thorley (2004)

**Code location:** `epanet_api_monolith.py:2544-2557`

### 3.3 Surge Vessel Sizing

    V = a x Q x L / (2 x g x H_allowed)

| Variable | Description | Unit |
|----------|-------------|------|
| V | Vessel volume | m3 |
| a | Wave speed | m/s |
| Q | Flow rate | m3/s |
| L | Total pipeline length | m |
| H_allowed | Allowable surge head | m |

Minimum vessel volume: 0.5 m3.
Pressure rating: 1.5 x max surge pressure (50% safety factor).

**Source:** Wylie & Streeter (1993) "Fluid Transients in Systems", Ch. 12.

**Code location:** `epanet_api_monolith.py:2467-2509`

### 3.4 Bladder Accumulator Sizing

    P1 x V1 = P2 x V2   (Boyle's law, isothermal assumption)

Used for pre-charged bladder accumulators where the gas charge absorbs
transient energy.

### 3.5 Flywheel Inertia

    J = P x t / (0.5 x omega^2)

| Variable | Description | Unit |
|----------|-------------|------|
| J | Moment of inertia | kg.m2 |
| P | Power | W |
| t | Run-down time | s |
| omega | Angular velocity | rad/s |

### 3.6 MOC Solver

The Method of Characteristics (MOC) solver from TSNet is used for full
transient simulation. It converts the partial differential equations of
unsteady pipe flow into ordinary differential equations along characteristic
lines (C+ and C-) with slope dx/dt = +/-a.

**Implementation:** TSNet `MOCSimulator` with demand-driven initialisation.

**Code location:** `epanet_api_monolith.py:913-1027` (`run_transient`)

### 3.7 Transient Compliance

Transient gauge pressure at each junction is compared against the pipe
pressure rating. Elevation is subtracted from total head before comparison
(gauge pressure only, never total head).

- gauge_max_kPa > PN rating: CRITICAL
- gauge_max_kPa > 80% of PN rating: WARNING
- gauge_min_pressure < 0: CRITICAL (column separation risk)

**Code location:** `epanet_api_monolith.py:983-1026`

---

## 4. Pipe Stress Analysis

All stress calculations use thin-wall pressure vessel theory (D/t > 10).

### 4.1 Hoop (Circumferential) Stress — Barlow's Formula

    sigma_h = P x D / (2 x t)

| Variable | Description | Unit |
|----------|-------------|------|
| sigma_h | Hoop stress | MPa |
| P | Internal pressure | MPa |
| D | Internal diameter | mm |
| t | Wall thickness | mm |

**Source:** Barlow's formula; AS/NZS 2566

**Code location:** `pipe_stress.py:13-35` (`hoop_stress`)

### 4.2 Radial Stress

    sigma_r = -P

Compressive at the inner wall (negative sign convention).

**Code location:** `pipe_stress.py:38-44` (`radial_stress`)

### 4.3 Axial (Longitudinal) Stress

    sigma_a = sigma_h / 2 = P x D / (4 x t)

Closed-end condition (fully restrained pipe).

**Code location:** `pipe_stress.py:47-55` (`axial_stress`)

### 4.4 Von Mises Equivalent Stress

    sigma_vm = sqrt(0.5 x ((sigma_h - sigma_r)^2 + (sigma_r - sigma_a)^2 + (sigma_a - sigma_h)^2))

This combined stress is compared against the material yield strength to
determine the safety factor.

**Code location:** `pipe_stress.py:58-67` (`von_mises_stress`)

### 4.5 Safety Factor

    SF = sigma_yield / sigma_vm

| Status | Condition |
|--------|-----------|
| OK | SF >= 1.5 |
| WARNING | 1.0 <= SF < 1.5 |
| CRITICAL | SF < 1.0 |

**Code location:** `pipe_stress.py:121-171` (`analyze_pipe_stress`)

### 4.6 Wall Thickness Design — Barlow's Formula

    t_min = (P x D) / (2 x S_allow)
    t_design = t_min + CA

where S_allow = sigma_yield / SF and CA is the corrosion allowance (mm).

**Code location:** `pipe_stress.py:70-106` (`barlow_wall_thickness`)

### 4.7 Material Yield Strengths

| Material | Yield (MPa) | Tensile (MPa) | Standard |
|----------|-------------|---------------|----------|
| Ductile Iron | 300 | 420 | AS 2280 |
| Steel Grade 250 | 250 | 410 | AS 1579 |
| Steel Grade 350 | 350 | 450 | AS 1579 |
| PVC (PN12/PN18) | 45 | 52 | AS/NZS 1477 |
| PE100 | 20 | 25 | AS/NZS 4130 |
| Concrete Class 3 | 30 | 40 | AS 4058 |

**PE100 note:** The 20 MPa value is the lower-bound short-term design yield
per AS/NZS 4130 Table 2 (range 20-22 MPa). This is conservative for burst
design.

**Code location:** `pipe_stress.py:109-118` (`MATERIAL_STRENGTH`)

**Verification:** All material values cross-checked against current editions
of the referenced Australian Standards.

---

## 5. Water Quality

### 5.1 Water Age Tracking

WNTR tracks water age by simulating the time elapsed since water entered the
network from a source node. The quality parameter is set to 'AGE'.

**Internal unit:** seconds (WNTR native)
**Display unit:** hours (divide by 3600)

    age_hours = wntr_age_seconds / 3600

**Stagnation threshold:** 24 hours (WSAA guidelines).

Junctions where max water age exceeds 24 hours are flagged as stagnation risks.

**Code location:** `epanet_api_monolith.py:587-675` (`run_water_quality`)

**Verification:** D7 hand calculations confirmed age conversion and threshold
comparison on Net1 benchmark.

### 5.2 Chlorine Decay — First-Order Kinetics

**Bulk decay:**

    C(t) = C_0 x e^(k_b x t)

| Variable | Description | Unit |
|----------|-------------|------|
| C(t) | Concentration at time t | mg/L |
| C_0 | Initial concentration | mg/L |
| k_b | Bulk decay coefficient (negative for decay) | 1/hr (input), 1/s (solver) |
| t | Time | s |

**Wall decay:**

    dC/dt = k_w x (C_pipe / R_h)

| Variable | Description | Unit |
|----------|-------------|------|
| k_w | Wall decay coefficient | m/hr (input), m/s (solver) |
| R_h | Hydraulic radius | m |

**Unit conversion (input to solver):**
- k_b: divide by 3600 (1/hr to 1/s)
- k_w: divide by 3600 (m/hr to m/s)

**WSAA minimum chlorine residual:** 0.2 mg/L (ADWG — Australian Drinking
Water Guidelines).

**Code location:** `epanet_api_monolith.py:713-811` (`run_water_quality_chlorine`)

**Verification:** D7 hand calculations confirmed exponential decay matches
WNTR output for k_b = -0.5/hr over 72-hour simulation.

---

## 6. Network Analysis

### 6.1 Todini Resilience Index

    I_r = sum_j((h_j - h_min) x q_j) / sum_s((H_s - h_min) x Q_s)

| Variable | Description | Unit |
|----------|-------------|------|
| h_j | Pressure head at demand node j | m |
| h_min | Minimum required pressure (WSAA 20 m) | m |
| q_j | Demand at node j | m3/s |
| H_s | Head at source node s | m |
| Q_s | Outflow from source s | m3/s |

The numerator represents surplus power available at demand nodes above the
minimum service requirement. The denominator represents the total input power
above minimum. The index is capped at 1.0.

**Grading:**

| Grade | Index Range | Interpretation |
|-------|-------------|----------------|
| A | >= 0.50 | Excellent redundancy |
| B | >= 0.30 | Good redundancy |
| C | >= 0.15 | Moderate redundancy |
| D | >= 0.05 | Low redundancy |
| F | < 0.05 | Very low redundancy |

**Source:** Todini (2000) "Looped water distribution networks design using a
resilience index based heuristic approach". Urban Water 2(2):115-122.

**Code location:** `epanet_api_monolith.py:3017-3108` (`compute_resilience_index`)

**Verification:** D7 hand calculations on 3-node test network confirmed.

### 6.2 Topology Analysis

#### 6.2.1 Dead-End Detection

Junctions with exactly one pipe connection (degree = 1) are flagged as dead
ends. Dead ends have higher stagnation risk and lower reliability.

#### 6.2.2 Bridge Detection — Tarjan's Algorithm

Bridges are pipes whose removal would disconnect the network (increase the
number of connected components). Identified using an iterative implementation
of Tarjan's bridge-finding DFS algorithm.

Skipped for networks with > 5000 pipes for performance reasons.

#### 6.2.3 Connectivity

Breadth-first search from all source nodes (reservoirs and tanks) determines
reachable nodes. Nodes not reachable from any source are flagged as isolated.

**Connectivity ratio:**

    CR = |reachable_nodes| / |all_nodes|

#### 6.2.4 Cyclomatic Complexity

    M = E - V + C

where E = edges (pipes), V = vertices (nodes), C = connected components.
Higher values indicate more loops and greater hydraulic redundancy.

**Source:** Graph theory; Todini & Pilati (1988)

**Code location:** `epanet_api_monolith.py:2862-2965` (`analyse_topology`)

---

## 7. WSAA Compliance Thresholds

All compliance checks reference specific Australian standards. The toolkit
enforces these as hard limits unless overridden by the user for
mining/industrial applications.

| Check | Threshold | Standard | Clause | Code Default Key |
|-------|-----------|----------|--------|------------------|
| Minimum service pressure | 20 m head | WSA 03-2011 | Table 3.1 | `min_pressure_m` |
| Maximum service pressure | 50 m head (residential) | WSA 03-2011 | Table 3.1 | `max_pressure_m` |
| Maximum pipe velocity | 2.0 m/s | WSA 03-2011 | Clause 3.8.2 | `max_velocity_ms` |
| Minimum pipe velocity | 0.6 m/s | WSA 03-2011 | (sediment prevention) | `min_velocity_ms` |
| Fire flow requirement | 25 LPS at 12 m residual | WSA 03-2011 | Table 3.3 | (in `run_fire_flow`) |
| Water age (stagnation) | 24 hours | WSAA guidelines | — | hardcoded in `run_water_quality` |
| Chlorine residual (min) | 0.2 mg/L | ADWG | — | hardcoded in `run_water_quality_chlorine` |
| Mining/industrial max pressure | 120 m head | Site-specific | — | override via `set_compliance_thresholds` |

**Steady-state pressure compliance:** Uses gauge pressure only (pressure at
node), never total head. This is the pressure experienced by the customer
connection.

**Transient pressure compliance:** Subtracts junction elevation from total
head before comparing to PN rating. This converts to gauge pressure for
the stress comparison.

**Velocity on reversing pipes:** Uses `abs(flow).max()`, never signed
`flow.max()`. Negative flow values indicate reverse flow direction and
must not reduce the apparent maximum velocity.

**Zero-diameter guard:** Always checks pipe cross-sectional area > 0 before
computing velocity to avoid division by zero.

**Code location:** `epanet_api_monolith.py:35-44` (defaults),
`epanet_api_monolith.py:359-388` (steady-state compliance checks),
`epanet_api_monolith.py:455` (fire flow analysis).

---

## 8. Unit Conventions

All solver-internal quantities are SI. Conversions are applied at the
display boundary (UI and reports).

| Quantity | Internal (Solver) | Display (UI/Reports) | Conversion |
|----------|-------------------|----------------------|------------|
| Pressure | m head | m head (hydraulic), kPa (stress) | 1 m head = 9.81 kPa |
| Flow | m3/s (WNTR) | LPS | x 1000 |
| Velocity | m/s | m/s | none, always absolute value |
| Pipe diameter | m (WNTR) | DN mm | x 1000 |
| Pipe length | m | m | none |
| Elevation | m AHD | m AHD | none |
| Roughness | C-factor | C-factor | none |
| Wave speed | m/s | m/s | none |
| Stress | MPa | MPa | none |
| Water age | seconds (WNTR) | hours | / 3600 |
| Bulk decay coeff | 1/s (WNTR) | 1/hr (input) | / 3600 |
| Wall decay coeff | m/s (WNTR) | m/hr (input) | / 3600 |

**Display precision:**
- Pressure: 1 decimal place (e.g. 30.2 m)
- Velocity: 2 decimal places (e.g. 1.45 m/s)
- Pipe diameter: integer mm (e.g. 300 mm, not 300.0 mm)
- Every displayed value must include its unit

---

## 9. Australian Pipe Standards

### 9.1 PVC Pipe — AS/NZS 1477

PVC pipe OD follows the AS/NZS 1477 OD series. OD is never equal to DN.

| DN | OD (mm) |
|----|---------|
| 100 | 110 |
| 150 | 160 |
| 200 | 225 |
| 250 | 280 |
| 300 | 315 |
| 375 | 400 |

Pressure ratings: PN12 and PN18. Typical C-factor: 145-150.

### 9.2 Ductile Iron — AS 2280

Pressure ratings: PN25 and PN35. Typical C-factor: 120-140.
Wave speed lower bound: 1100 m/s (all sizes).

### 9.3 PE100 / HDPE — AS/NZS 4130

Standard: SDR11 PN16. Typical C-factor: 140-150.
Short-term design yield: 20-22 MPa (not 10 MPa).

### 9.4 Concrete — AS 4058

Pressure ratings: PN25-PN35. Hazen-Williams C by size:
- DN375, DN450: C = 110
- DN600, DN750: C = 100
- DN900: C = 90

---

## 10. References

- Barlow, P. (1837). Strength of materials.
- Colebrook, C.F. (1939). "Turbulent Flow in Pipes". Journal ICE 11(4):133-156.
- Dodge, D.W. & Metzner, A.B. (1959). "Turbulent Flow of Non-Newtonian Systems". AIChE J. 5(2):189-204.
- Durand, R. (1952). "Hydraulic Transport of Coal and Sand". Proceedings, Colloquium on Hydraulic Transport, National Coal Board, UK.
- Joukowsky, N. (1898). "On the hydraulic hammer in water supply pipes". Memoirs of the Imperial Academy of Sciences, St. Petersburg.
- Lamont, P.A. (1981). "Common Pipe Flow Formulas Compared with the Theory of Roughness". J. AWWA 73(5):274-280.
- Prasad, T.D. & Park, N.S. (2004). "Multiobjective Genetic Algorithms for Design of Water Distribution Networks". J. Water Resources Planning & Management 130(1):73-82.
- Rouse, H. (1937). "Modern conceptions of the mechanics of fluid turbulence". Trans. ASCE 102:463-505.
- Schiller, L. & Naumann, A.Z. (1935). "Uber die grundlegenden Berechnungen bei der Schwerkraftaufbereitung". Z. Ver. Deutsch. Ing. 77:318-320.
- Slatter, P.T. (1995). "Transitional and Turbulent Flow of Non-Newtonian Slurries in Pipes". PhD thesis, University of Cape Town.
- Stokes, G.G. (1851). "On the effect of the internal friction of fluids on the motion of pendulums". Trans. Cambridge Phil. Soc. 9:8-106.
- Thorley, A.R.D. (2004). "Fluid Transients in Pipeline Systems". 2nd ed., Professional Engineering Publishing.
- Todini, E. (2000). "Looped water distribution networks design using a resilience index based heuristic approach". Urban Water 2(2):115-122.
- Todini, E. & Pilati, S. (1988). "A gradient algorithm for the analysis of pipe networks". Computer Applications in Water Supply, Vol. 1, John Wiley & Sons.
- Wasp, E.J., Kenny, J.P. & Gandhi, R.L. (1977). "Solid-Liquid Flow Slurry Pipeline Transportation". Trans Tech Publications.
- White, F.M. (1994). "Fluid Mechanics". 3rd ed., McGraw-Hill.
- Wilson, K.C., Addie, G.R. & Clift, R. (2006). "Slurry Transport Using Centrifugal Pumps". 3rd ed., Springer.
- Wylie, E.B. & Streeter, V.L. (1993). "Fluid Transients in Systems". Prentice Hall.
- Standards Australia. AS 2280 — Ductile Iron Pipes and Fittings.
- Standards Australia. AS 4058 — Precast Concrete Pipes.
- Standards Australia/Standards New Zealand. AS/NZS 1477 — PVC Pipes and Fittings.
- Standards Australia/Standards New Zealand. AS/NZS 4130 — Polyethylene Pipes.
- Water Services Association of Australia. WSA 03-2011 — Water Supply Code of Australia.
- NHMRC/NRMMC. Australian Drinking Water Guidelines (ADWG).

---

*Document generated for the Hydraulic Analysis Toolkit. All equations verified
against D7 hand calculations and referenced standards.*

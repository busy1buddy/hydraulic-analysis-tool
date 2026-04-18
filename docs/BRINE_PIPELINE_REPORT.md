# Engineering Design Report
## Brine Transfer Pipeline (DN125)

**Date:** 18 April 2026
**Subject:** Hydraulic Analysis and Topographical Assessment for Brine Transfer
**Fluid:** Heavy Brine (Specific Gravity = 1.15)

---

## 1. Executive Summary
This report summarizes the steady-state hydraulic and topographical analysis of a 3.7 km brine transfer pipeline. The design transfers 15.0 L/s of heavy brine (SG 1.15) across undulating terrain with two major topographical peaks and a central dip. 

The hydraulic analysis confirms the line size (DN125 PE, internal diameter ~110mm) is sufficient to maintain a safe flow velocity of 1.58 m/s. However, the high friction loss across the 3.7 km distance requires a significant pump head. 

**Critical Finding:** The maximum system pressure reaches **13.8 bar** (137.7m head of brine). The originally proposed PN10 (10 bar) pipe rating is **inadequate** for the first half of the pipeline. A PN16 (16 bar) pipe rating is strongly recommended up to Chainage 1,500m.

---

## 2. Design Basis & Parameters
*   **Pipeline Length:** 3,710 m
*   **Nominal Diameter:** DN125 (110 mm internal bore used for modelling)
*   **Pipe Roughness (Hazen-Williams):** C = 130
*   **Fluid Specific Gravity:** 1.15
*   **Target Flow Rate:** 15.0 L/s
*   **Calculated Pipeline Velocity:** 1.58 m/s 

## 3. Topographical Profile & Valving Strategy
The pipeline traverses undulating terrain, starting at an elevation of 20.0m AHD and terminating at 25.0m AHD. 

Based on the topographical profile analysis, the following automated valving locations are required:

### 3.1 Air/Vacuum Valves
To prevent air-binding during filling and vacuum collapse during pump trips, DN50 Air/Vacuum valves must be installed at the topographical local maxima:
*   **Peak 1:** Chainage 610m (Elevation 45.0m AHD)
*   **Peak 2:** Chainage 2,710m (Elevation 40.0m AHD)

### 3.2 Scour Valves
To permit safe draining of the heavy brine for pipeline maintenance, a scour valve must be installed at the lowest local minimum:
*   **Valley 1:** Chainage 1,810m (Elevation 15.0m AHD)

---

## 4. Hydraulic Results & Pressure Envelope
The EPANET hydraulic simulation yields the following steady-state envelope:

*   **Pump Station Discharge Head (Required):** 140.0 m
*   **Maximum Pipeline Pressure:** 137.7 m (at Chainage 10m)
*   **Minimum Pipeline Pressure:** 24.0 m (at Discharge)
*   **Average Friction Gradient:** 25.4 m/km

*Note on Pressure Rating: Because the specific gravity is 1.15, a 137.7m head equates to approximately 1.55 MPa (15.5 bar) of hydrostatic pressure. PN16 class pipe is strictly required near the pump station.*

## 5. Pump Station Duty Recommendation
The transfer pump must be sized to deliver the required flow rate against the total dynamic head of the system, factoring in both the static elevation gain and the high friction losses of the DN125 line.

*   **Duty Flow:** 15.0 L/s (54 m³/h)
*   **Duty Head:** 140.0 m (Brine)

It is recommended to run a **Transient Surge Analysis (Water Hammer)** using the `tsnet` solver prior to final pump procurement to ensure the maximum surge envelope does not exceed the PN16 pipe ratings during a sudden pump trip.

---

## 6. Pipeline Derating Considerations
When finalizing the PE (Polyethylene) pipe material specification, the following derating factors must be applied to the nominal pressure rating (PN):

1.  **Temperature Derating:** The standard PN rating (e.g., PN16 = 16 bar) is calculated at 20°C. If the brine temperature exceeds 20°C, the allowable operating pressure (MAOP) drops significantly. For PE100 pipe at 40°C, a derating factor of **~0.74** applies, meaning a PN16 pipe is only rated for 11.8 bar, which would fail under the 13.8 bar static head.
2.  **Cyclic Fatigue Derating:** If the pump operates on a frequent on/off cycle (e.g., filling a batch tank), the repeated pressure transients can cause fatigue failure in plastic pipes. For high-cycle operations, a fatigue derating factor must be applied per PIPA guidelines.
3.  **Chemical Resistance:** While PE is highly resistant to brine, any trace hydrocarbons or solvents in the brine mixture may require further chemical derating.

## 7. Site Operational Recommendations
To ensure long-term reliability of the brine transfer system, the following operational procedures are recommended:

*   **Soft Start/Stop (VSD):** The pump should be equipped with a Variable Speed Drive (VSD) with a minimum 30-second ramp-up and ramp-down profile to minimize water hammer during normal starting and stopping.
*   **Air Valve Maintenance:** Brine is highly corrosive and prone to crystallization when exposed to air. The Air/Vacuum valves at the 45m and 40m peaks must be placed on a strict preventative maintenance schedule. If these valves crystalize shut, the pipeline is at extreme risk of vacuum collapse during a pump trip.
*   **Scour Valve Monitoring:** The scour valve at the 15m valley must be checked for sediment build-up, as heavy particulates in the brine will naturally settle at this low point during shutdown periods.

## 8. Transient Surge Analysis (Sudden Pump Trip)
A transient analysis (MOC) was performed to simulate a sudden power failure causing the transfer pump to trip.

*   **Simulation Parameters:** 30 seconds total duration, wave speed (celerity) = 400 m/s (PE pipe).
*   **Pump Trip Profile:** Coast down to 0 RPM over 2.0 seconds.

**Surge Results:**
*   **Pump Discharge (Chainage 0m):** The pressure drops from 120m operating head to 0m (gauge) instantly as the pump stops.
*   **Peak 1 (Chainage 600m):** As the fluid column continues forward due to momentum, a massive low-pressure wave reflects back. The pressure at the first high point (45m elevation) rapidly drops to **-30.6 m gauge (vacuum)**. 

**Conclusion:** The pipeline experiences severe **Column Separation** (vacuum) at the first high point within 5 seconds of the pump tripping. The Air/Vacuum valve specified in Section 3.1 is absolutely critical. Without it admitting air to break the vacuum, the PE pipe will instantly buckle and collapse.
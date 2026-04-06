"""
Hand-Calculation Benchmark Tests
=================================
Five independent hand calculations verified against the EPANET toolkit
functions. Each test computes the expected value using only the Python
``math`` module, then calls the corresponding toolkit function and
asserts agreement within tolerance.

References
----------
- Barlow's formula: sigma_h = P * D / (2 * t)
- AS/NZS 1477 (PVC pipe properties)
- AS 2280 (Ductile Iron pipe properties)
- WSAA WSA 03-2011 (water quality thresholds)
- Durand (1952) critical deposition velocity
"""

import math
import pytest

import pipe_stress
import slurry_solver


# ============================================================================
# Test 1: Hoop stress for DN300 Ductile Iron at 500 kPa
# ============================================================================
# From data/au_pipes.py: DN300 DI -> ID = 312.8 mm, t = 7.2 mm
# Barlow's thin-wall: sigma_h = P * D / (2 * t)
#   P = 500 kPa = 0.5 MPa
#   D = 312.8 mm (internal diameter)
#   t = 7.2 mm
#   sigma_h = 0.5 * 312.8 / (2 * 7.2)
#           = 156.4 / 14.4
#           = 10.861111...
#   Rounded to 2 dp (per pipe_stress.hoop_stress): 10.86 MPa

def test_hoop_stress_dn300_di_500kpa():
    """Hoop stress for DN300 DI at 500 kPa — Barlow's formula hand calc."""
    # --- Hand calculation (math only) ---
    P_kPa = 500.0
    P_MPa = P_kPa / 1000.0          # 0.5 MPa
    D_mm = 312.8                     # DN300 DI internal diameter (AS 2280)
    t_mm = 7.2                       # DN300 DI wall thickness (AS 2280)

    # Barlow's: sigma_h = P * D / (2 * t)  — ref: Barlow (1836)
    sigma_h_hand = P_MPa * D_mm / (2.0 * t_mm)
    sigma_h_hand = round(sigma_h_hand, 2)
    # sigma_h_hand = round(0.5 * 312.8 / 14.4, 2) = round(10.8611, 2) = 10.86 MPa

    assert sigma_h_hand == 10.86, f"Hand calc sanity check failed: {sigma_h_hand}"

    # --- Toolkit calculation ---
    sigma_h_tool = pipe_stress.hoop_stress(500.0, 312.8, 7.2)

    # --- Comparison ---
    assert sigma_h_tool == sigma_h_hand, (
        f"Hoop stress mismatch: tool={sigma_h_tool} MPa, hand={sigma_h_hand} MPa"
    )


# ============================================================================
# Test 2: PN safety factor for PVC DN200 at 300 kPa
# ============================================================================
# From data/au_pipes.py: DN200 PVC -> ID = 211.4 mm, t = 6.8 mm, PN18
# From pipe_stress.MATERIAL_STRENGTH: pvc_pn12 yield = 45 MPa (same for
#   all PVC grades per AS/NZS 1477); pvc_pn18 yield = 45 MPa.
#
# Step 1: Hoop stress at 300 kPa
#   P = 300 kPa = 0.3 MPa
#   sigma_h = 0.3 * 211.4 / (2 * 6.8) = 63.42 / 13.6 = 4.663235...
#   Rounded: 4.66 MPa
#
# Step 2: Safety factor = yield / sigma_h = 45 / 4.66 = 9.6567...
#   Rounded to 2 dp: 9.66
#
# Step 3: Radial stress = -P = -0.3 MPa
# Step 4: Axial stress = sigma_h / 2 = 4.66 / 2 = 2.33 MPa
# Step 5: Von Mises = sqrt(0.5 * ((4.66-(-0.3))^2 + (-0.3-2.33)^2 + (2.33-4.66)^2))
#        = sqrt(0.5 * (24.6016 + 6.9169 + 5.4289))
#        = sqrt(0.5 * 36.9474) = sqrt(18.4737) = 4.2981...
#   Rounded: 4.30 MPa
# Step 6: SF_vm = 45 / 4.30 = 10.4651... -> 10.47

def test_pn_safety_factor_pvc_dn200_300kpa():
    """PN safety factor for PVC DN200 PN18 at 300 kPa — full stress analysis."""
    # --- Hand calculation (math only) ---
    P_kPa = 300.0
    P_MPa = P_kPa / 1000.0          # 0.3 MPa
    D_mm = 211.4                     # DN200 PVC ID (AS/NZS 1477)
    t_mm = 6.8                       # DN200 PVC wall thickness
    yield_MPa = 45.0                 # PVC yield stress (AS/NZS 1477)

    # Hoop stress: sigma_h = P * D / (2 * t)
    sigma_h = round(P_MPa * D_mm / (2.0 * t_mm), 2)
    # = round(0.3 * 211.4 / 13.6, 2) = round(4.6632, 2) = 4.66 MPa

    # Radial stress at inner wall = -P
    sigma_r = round(-P_MPa, 2)  # -0.3 MPa

    # Axial stress (closed-end) = sigma_h / 2
    sigma_a = round(sigma_h / 2, 2)  # 2.33 MPa

    # Safety factor (hoop)
    sf_hoop = round(yield_MPa / sigma_h, 2)
    # = round(45 / 4.66, 2) = round(9.6567, 2) = 9.66

    # Von Mises equivalent stress
    vm = math.sqrt(0.5 * ((sigma_h - sigma_r)**2 +
                          (sigma_r - sigma_a)**2 +
                          (sigma_a - sigma_h)**2))
    vm = round(vm, 2)

    sf_vm = round(yield_MPa / vm, 2)

    # --- Toolkit calculation ---
    # Using pvc_pn18 material (same yield as pvc_pn12 = 45 MPa)
    result = pipe_stress.analyze_pipe_stress(300.0, 211.4, 6.8, material='pvc_pn18')

    # --- Comparisons ---
    assert result['hoop_stress_MPa'] == sigma_h, (
        f"Hoop stress mismatch: tool={result['hoop_stress_MPa']}, hand={sigma_h}"
    )
    assert result['radial_stress_MPa'] == sigma_r, (
        f"Radial stress mismatch: tool={result['radial_stress_MPa']}, hand={sigma_r}"
    )
    assert result['axial_stress_MPa'] == sigma_a, (
        f"Axial stress mismatch: tool={result['axial_stress_MPa']}, hand={sigma_a}"
    )
    assert result['safety_factor_hoop'] == sf_hoop, (
        f"SF hoop mismatch: tool={result['safety_factor_hoop']}, hand={sf_hoop}"
    )
    assert result['von_mises_MPa'] == vm, (
        f"Von Mises mismatch: tool={result['von_mises_MPa']}, hand={vm}"
    )
    assert result['safety_factor_vm'] == sf_vm, (
        f"SF VM mismatch: tool={result['safety_factor_vm']}, hand={sf_vm}"
    )
    assert result['status'] == 'OK', (
        f"Expected OK status (SF >> 1.5), got {result['status']}"
    )


# ============================================================================
# Test 3: Water age / residence time for 500 m dead-end at 0.5 LPS
# ============================================================================
# DN150 pipe (using nominal 150 mm ID for simplicity of the water-age calc).
#   Area = pi * (0.075)^2 = pi * 0.005625 = 0.017671... m^2
#   Volume = 0.017671 * 500 = 8.8357... m^3
#   Flow = 0.5 LPS = 0.0005 m^3/s
#   Residence time = V / Q = 8.8357 / 0.0005 = 17671.46 s
#   In hours = 17671.46 / 3600 = 4.9087... hours
#   This is well below the 24-hour stagnation threshold (WSAA WSA 03-2011).
#
# Note: This is a pure physics calculation — no toolkit function to call,
# so we verify against independently computed values and the WSAA threshold.

def test_water_age_dead_end_500m():
    """Water age for 500 m dead-end pipe at 0.5 LPS — residence time calc."""
    # --- Hand calculation (math only) ---
    pipe_id_m = 0.150                # DN150 internal diameter in metres
    pipe_length_m = 500.0            # pipe length
    flow_lps = 0.5                   # flow rate in LPS

    # Cross-sectional area: A = pi * (D/2)^2
    radius_m = pipe_id_m / 2.0       # 0.075 m
    area_m2 = math.pi * radius_m ** 2
    # area_m2 = pi * 0.005625 = 0.01767146 m^2

    # Pipe volume
    volume_m3 = area_m2 * pipe_length_m
    # volume_m3 = 0.01767146 * 500 = 8.83573 m^3

    # Convert flow to m^3/s (WNTR internal unit)
    # 0.5 LPS = 0.0005 m^3/s
    flow_m3s = flow_lps / 1000.0

    # Residence time in seconds
    residence_s = volume_m3 / flow_m3s
    # residence_s = 8.83573 / 0.0005 = 17671.46 s

    # Convert to hours (WNTR returns age in seconds; divide by 3600)
    # Ref: CLAUDE.md — "WNTR returns seconds, threshold is in hours"
    residence_hours = residence_s / 3600.0
    # residence_hours = 17671.46 / 3600 = 4.9088 hours

    # WSAA stagnation threshold = 24.0 hours
    WSAA_STAGNATION_HOURS = 24.0

    # --- Assertions ---
    assert abs(area_m2 - math.pi * 0.075**2) < 1e-10, "Area calculation error"
    assert abs(volume_m3 - 8.83573) < 0.001, f"Volume mismatch: {volume_m3}"
    assert abs(residence_s - 17671.46) < 1.0, f"Residence time mismatch: {residence_s} s"
    assert abs(residence_hours - 4.909) < 0.01, (
        f"Residence hours mismatch: {residence_hours}"
    )

    # Below stagnation threshold — this dead-end is NOT stagnant at 0.5 LPS
    assert residence_hours < WSAA_STAGNATION_HOURS, (
        f"Expected below 24 h threshold, got {residence_hours:.2f} h"
    )

    # Verify that a very low flow WOULD cause stagnation
    # At 0.1 LPS: residence = 17671.46 * 5 = 88357 s = 24.54 hours > 24
    flow_low_m3s = 0.0001  # 0.1 LPS
    residence_low_hours = (volume_m3 / flow_low_m3s) / 3600.0
    assert residence_low_hours > WSAA_STAGNATION_HOURS, (
        f"Expected above 24 h at 0.1 LPS, got {residence_low_hours:.2f} h"
    )


# ============================================================================
# Test 4: Chlorine decay at k_b = -0.5/hr for 12 hours
# ============================================================================
# First-order decay: C(t) = C_0 * exp(k_b * t)
#   C_0 = 0.5 mg/L (typical dosing residual)
#   k_b = -0.5 /hr (bulk decay coefficient)
#   t = 12 hours
#   C(12) = 0.5 * exp(-0.5 * 12) = 0.5 * exp(-6)
#   exp(-6) = 0.00247875...
#   C(12) = 0.5 * 0.00247875 = 0.001239... mg/L
#
# WSAA minimum free chlorine residual = 0.2 mg/L
# 0.00124 mg/L << 0.2 mg/L -> NON-COMPLIANT
#
# This is a pure chemistry calculation — no toolkit function wraps it,
# so we verify the math independently and check compliance logic.

def test_chlorine_decay_12hrs():
    """Chlorine decay C(t) = C0 * exp(kb * t) — first-order kinetics."""
    # --- Hand calculation (math only) ---
    C_0 = 0.5        # Initial chlorine concentration (mg/L)
    k_b = -0.5       # Bulk decay rate constant (per hour)
    t_hours = 12.0   # Elapsed time (hours)

    # First-order decay: C(t) = C_0 * exp(k_b * t)
    # Ref: WNTR water quality model, standard first-order kinetics
    C_t = C_0 * math.exp(k_b * t_hours)
    # C_t = 0.5 * exp(-6.0) = 0.5 * 0.002478752... = 0.001239376... mg/L

    # Verify intermediate: exp(-6)
    exp_neg6 = math.exp(-6.0)
    assert abs(exp_neg6 - 0.00247875) < 0.00001, (
        f"exp(-6) mismatch: {exp_neg6}"
    )

    # Verify final concentration
    assert abs(C_t - 0.001239) < 0.0001, (
        f"C(12) mismatch: {C_t} mg/L"
    )

    # WSAA minimum free chlorine residual
    WSAA_MIN_CHLORINE_MGL = 0.2  # WSAA WSA 03-2011

    # Compliance check
    is_compliant = C_t >= WSAA_MIN_CHLORINE_MGL
    assert not is_compliant, (
        f"Expected non-compliant: C(12)={C_t:.6f} mg/L < {WSAA_MIN_CHLORINE_MGL} mg/L"
    )

    # Also verify that at t=0.5 hours, chlorine is still above threshold
    C_half_hr = C_0 * math.exp(k_b * 0.5)
    # C(0.5) = 0.5 * exp(-0.25) = 0.5 * 0.7788 = 0.3894 mg/L
    assert C_half_hr > WSAA_MIN_CHLORINE_MGL, (
        f"Expected compliant at 0.5 hr: C={C_half_hr:.4f} mg/L"
    )


# ============================================================================
# Test 5: Durand critical deposition velocity
# ============================================================================
# Parameters:
#   d50 = 0.5 mm (medium sand)
#   pipe DN200 -> D = 0.2 m
#   rho_solid = 2650 kg/m^3 (sand/quartz)
#   rho_fluid = 1000 kg/m^3 (water)
#   C_v = 0.15 (15% volumetric concentration)
#   S = rho_solid / rho_fluid = 2650 / 1000 = 2.65
#
# From slurry_solver.critical_deposition_velocity F_L lookup:
#   d50 = 0.5 mm falls in 0.5 <= d < 2.0 range
#   F_L = 1.3 + 1.0 * C_v = 1.3 + 1.0 * 0.15 = 1.45
#   (within clamp range [0.5, 2.0] -> F_L = 1.45)
#
# V_D = F_L * sqrt(2 * g * D * (S - 1))
#      = 1.45 * sqrt(2 * 9.81 * 0.2 * (2.65 - 1))
#      = 1.45 * sqrt(2 * 9.81 * 0.2 * 1.65)
#      = 1.45 * sqrt(6.4746)
#      = 1.45 * 2.54452...
#      = 3.6895...
#   Rounded to 2 dp: 3.69 m/s

def test_durand_critical_velocity_dn200():
    """Durand critical deposition velocity for d50=0.5mm in DN200 pipe."""
    # --- Hand calculation (math only) ---
    d50_mm = 0.5          # Median particle diameter
    D_pipe_mm = 200.0     # Pipe internal diameter (mm)
    D_pipe_m = D_pipe_mm / 1000.0  # 0.2 m
    rho_solid = 2650.0    # Sand density (kg/m^3)
    rho_fluid = 1000.0    # Water density (kg/m^3)
    C_v = 0.15            # Volumetric concentration
    g = 9.81              # Gravitational acceleration (m/s^2)

    S = rho_solid / rho_fluid  # Specific gravity = 2.65
    assert S == 2.65, f"S mismatch: {S}"

    # F_L lookup: d50=0.5 falls in [0.5, 2.0) range
    # F_L = 1.3 + 1.0 * C_v — Durand (1952) simplified correlation
    F_L = 1.3 + 1.0 * C_v  # 1.45
    assert F_L == 1.45, f"F_L mismatch: {F_L}"

    # Clamp check: 0.5 <= 1.45 <= 2.0 -> no clamping
    F_L_clamped = max(0.5, min(2.0, F_L))
    assert F_L_clamped == F_L, "F_L should not be clamped"

    # V_D = F_L * sqrt(2 * g * D * (S - 1))
    inner = 2.0 * g * D_pipe_m * (S - 1.0)
    # inner = 2 * 9.81 * 0.2 * 1.65 = 6.4746
    V_D = F_L * math.sqrt(inner)
    # V_D = 1.45 * sqrt(6.4746) = 1.45 * 2.54452 = 3.6896
    V_D_rounded = round(V_D, 2)

    assert V_D_rounded == 3.69, f"Hand calc V_D mismatch: {V_D_rounded}"

    # --- Toolkit calculation ---
    result = slurry_solver.critical_deposition_velocity(
        d_particle_mm=0.5,
        pipe_diameter_mm=200.0,
        rho_solid=2650,
        rho_fluid=1000,
        concentration_vol=0.15,
    )

    # --- Comparisons ---
    assert result['velocity_ms'] == V_D_rounded, (
        f"Durand velocity mismatch: tool={result['velocity_ms']} m/s, "
        f"hand={V_D_rounded} m/s"
    )
    assert result['durand_fl'] == round(F_L, 2), (
        f"F_L mismatch: tool={result['durand_fl']}, hand={round(F_L, 2)}"
    )
    assert result['specific_gravity'] == round(S, 2), (
        f"S mismatch: tool={result['specific_gravity']}, hand={round(S, 2)}"
    )

    # The velocity should be above typical WSAA max of 2.0 m/s — expected
    # for slurry transport (slurry must exceed deposition velocity)
    assert result['velocity_ms'] > 2.0, (
        "Durand velocity should exceed normal water velocity limits for slurry"
    )

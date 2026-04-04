"""
Pipe Stress Calculator
========================
Calculates hoop, radial, and axial stresses in pressurized pipes.
Includes wall thickness design per AS/NZS 2566 and Barlow's formula.

For both water supply and mining (slurry) applications.
"""

import math


def hoop_stress(pressure_kPa, diameter_mm, wall_thickness_mm):
    """
    Calculate hoop (circumferential) stress using thin-wall theory.

    sigma_h = P * D / (2 * t)

    Parameters
    ----------
    pressure_kPa : float
        Internal pressure (kPa).
    diameter_mm : float
        Pipe internal diameter (mm).
    wall_thickness_mm : float
        Pipe wall thickness (mm).

    Returns float: hoop stress in MPa.
    """
    P = pressure_kPa / 1000  # kPa to MPa
    D = diameter_mm  # mm
    t = wall_thickness_mm  # mm
    if t <= 0:
        return 0
    return round(P * D / (2 * t), 2)


def radial_stress(pressure_kPa):
    """
    Radial stress at inner wall = -P (compressive).

    Returns float: radial stress in MPa (negative = compressive).
    """
    return round(-pressure_kPa / 1000, 2)


def axial_stress(pressure_kPa, diameter_mm, wall_thickness_mm):
    """
    Axial (longitudinal) stress for closed-end condition.

    sigma_a = P * D / (4 * t) = sigma_h / 2

    Returns float: axial stress in MPa.
    """
    return round(hoop_stress(pressure_kPa, diameter_mm, wall_thickness_mm) / 2, 2)


def von_mises_stress(sigma_h, sigma_r, sigma_a):
    """
    Von Mises equivalent stress for combined loading.

    sigma_vm = sqrt(0.5 * ((s1-s2)^2 + (s2-s3)^2 + (s3-s1)^2))
    """
    vm = math.sqrt(0.5 * ((sigma_h - sigma_r)**2 +
                          (sigma_r - sigma_a)**2 +
                          (sigma_a - sigma_h)**2))
    return round(vm, 2)


def barlow_wall_thickness(pressure_kPa, diameter_mm, allowable_stress_MPa,
                          safety_factor=2.0, corrosion_allowance_mm=1.0):
    """
    Calculate minimum wall thickness using Barlow's formula.

    t = (P * D) / (2 * S * F) + CA

    Parameters
    ----------
    pressure_kPa : float
        Design pressure (kPa).
    diameter_mm : float
        Pipe outer diameter (mm).
    allowable_stress_MPa : float
        Material allowable stress (MPa).
    safety_factor : float
        Design safety factor (typically 2.0-4.0).
    corrosion_allowance_mm : float
        Additional thickness for corrosion (mm).

    Returns dict with min wall thickness and design details.
    """
    P = pressure_kPa / 1000  # MPa
    D = diameter_mm
    S = allowable_stress_MPa / safety_factor

    t_min = (P * D) / (2 * S)
    t_design = t_min + corrosion_allowance_mm

    return {
        'min_thickness_mm': round(t_min, 2),
        'design_thickness_mm': round(t_design, 2),
        'pressure_MPa': round(P, 3),
        'allowable_stress_MPa': allowable_stress_MPa,
        'safety_factor': safety_factor,
        'corrosion_allowance_mm': corrosion_allowance_mm,
    }


# Material yield strengths
MATERIAL_STRENGTH = {
    'ductile_iron': {'yield_MPa': 300, 'tensile_MPa': 420, 'standard': 'AS 2280'},
    'steel_grade_250': {'yield_MPa': 250, 'tensile_MPa': 410, 'standard': 'AS 1579'},
    'steel_grade_350': {'yield_MPa': 350, 'tensile_MPa': 450, 'standard': 'AS 1579'},
    'pvc_pn12': {'yield_MPa': 45, 'tensile_MPa': 52, 'standard': 'AS/NZS 1477'},
    'pvc_pn18': {'yield_MPa': 45, 'tensile_MPa': 52, 'standard': 'AS/NZS 1477'},
    'pe100': {'yield_MPa': 20, 'tensile_MPa': 25, 'standard': 'AS/NZS 4130'},  # Lower-bound value per AS/NZS 4130 Table 2 — conservative for burst design (range 20-22 MPa)
    'concrete_class3': {'yield_MPa': 30, 'tensile_MPa': 40, 'standard': 'AS 4058'},
}


def analyze_pipe_stress(pressure_kPa, diameter_mm, wall_thickness_mm,
                        material='ductile_iron', transient_factor=1.0):
    """
    Complete stress analysis for a pipe section.

    Parameters
    ----------
    pressure_kPa : float
        Operating or transient pressure.
    diameter_mm : float
        Internal diameter.
    wall_thickness_mm : float
        Wall thickness.
    material : str
        Material key from MATERIAL_STRENGTH.
    transient_factor : float
        Multiplier for transient pressure (1.0 = steady, >1 = surge).

    Returns dict with all stress components and safety factors.
    """
    P = pressure_kPa * transient_factor

    s_h = hoop_stress(P, diameter_mm, wall_thickness_mm)
    s_r = radial_stress(P)
    s_a = axial_stress(P, diameter_mm, wall_thickness_mm)
    s_vm = von_mises_stress(s_h, s_r, s_a)

    mat = MATERIAL_STRENGTH.get(material, MATERIAL_STRENGTH['ductile_iron'])
    yield_stress = mat['yield_MPa']

    sf_hoop = round(yield_stress / s_h, 2) if s_h > 0 else float('inf')
    sf_vm = round(yield_stress / s_vm, 2) if s_vm > 0 else float('inf')

    status = 'OK'
    if sf_hoop < 1.5:
        status = 'CRITICAL' if sf_hoop < 1.0 else 'WARNING'
    elif sf_vm < 1.5:
        status = 'CRITICAL' if sf_vm < 1.0 else 'WARNING'

    return {
        'pressure_kPa': round(P, 1),
        'hoop_stress_MPa': s_h,
        'radial_stress_MPa': s_r,
        'axial_stress_MPa': s_a,
        'von_mises_MPa': s_vm,
        'material': material,
        'yield_strength_MPa': yield_stress,
        'safety_factor_hoop': sf_hoop,
        'safety_factor_vm': sf_vm,
        'status': status,
    }

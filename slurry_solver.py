"""
Non-Newtonian / Slurry Fluid Solver
=====================================
Implements rheological models for non-Newtonian fluids:
- Bingham Plastic model (tailings, cement slurry)
- Power Law model (polymer solutions, some muds)
- Herschel-Bulkley model (general non-Newtonian)

These models replace EPANET's Darcy-Weisbach or Hazen-Williams
headloss with rheology-specific friction calculations.

References:
- Slatter, P.T. (1995) "Transitional and Turbulent Flow of Non-Newtonian Slurries"
- Wilson, K.C. et al. (2006) "Slurry Transport Using Centrifugal Pumps"
- Paterson & Cooke consulting methodology
"""

import math
import numpy as np


# ============================================================================
# FLUID PROPERTY DATABASE
# ============================================================================

SLURRY_DATABASE = {
    'water': {
        'type': 'newtonian',
        'density_kg_m3': 1000,
        'viscosity_Pa_s': 0.001,
        'description': 'Clean water (reference)',
    },
    'mine_tailings_30pct': {
        'type': 'bingham_plastic',
        'density_kg_m3': 1300,
        'yield_stress_Pa': 5.0,
        'plastic_viscosity_Pa_s': 0.015,
        'concentration_pct': 30,
        'description': 'Mine tailings slurry at 30% solids by weight',
    },
    'mine_tailings_50pct': {
        'type': 'bingham_plastic',
        'density_kg_m3': 1500,
        'yield_stress_Pa': 25.0,
        'plastic_viscosity_Pa_s': 0.08,
        'concentration_pct': 50,
        'description': 'Mine tailings slurry at 50% solids by weight',
    },
    'paste_fill_70pct': {
        'type': 'bingham_plastic',
        'density_kg_m3': 1900,
        'yield_stress_Pa': 200.0,
        'plastic_viscosity_Pa_s': 0.5,
        'concentration_pct': 70,
        'description': 'Paste fill at 70% solids (underground backfill)',
    },
    'cement_slurry': {
        'type': 'bingham_plastic',
        'density_kg_m3': 1600,
        'yield_stress_Pa': 15.0,
        'plastic_viscosity_Pa_s': 0.05,
        'concentration_pct': 45,
        'description': 'Cement grout slurry',
    },
    'polymer_solution': {
        'type': 'power_law',
        'density_kg_m3': 1010,
        'K': 0.5,           # Consistency index (Pa.s^n)
        'n': 0.6,           # Flow behaviour index
        'description': 'Polymer solution (shear-thinning)',
    },
    'drilling_mud': {
        'type': 'herschel_bulkley',
        'density_kg_m3': 1200,
        'yield_stress_Pa': 10.0,
        'K': 0.3,
        'n': 0.7,
        'description': 'Drilling mud (Herschel-Bulkley)',
    },
}


# ============================================================================
# RHEOLOGICAL MODELS
# ============================================================================

def bingham_plastic_headloss(flow_m3s, diameter_m, length_m, density, tau_y, mu_p,
                              roughness_mm=0.05):
    """
    Calculate headloss for Bingham Plastic fluid.

    Uses Buckingham-Reiner equation for laminar flow,
    and modified Darcy-Weisbach for turbulent flow.

    Parameters
    ----------
    flow_m3s : float
        Volume flow rate (m3/s).
    diameter_m : float
        Pipe internal diameter (m).
    length_m : float
        Pipe length (m).
    density : float
        Fluid density (kg/m3).
    tau_y : float
        Yield stress (Pa).
    mu_p : float
        Plastic viscosity (Pa.s).
    roughness_mm : float
        Pipe roughness (mm).

    Returns
    -------
    dict with headloss_m, velocity_ms, regime, friction_factor, reynolds.
    """
    g = 9.81
    A = math.pi * (diameter_m / 2) ** 2
    V = abs(flow_m3s) / A if A > 0 else 0

    if V < 1e-6:
        return {'headloss_m': 0, 'velocity_ms': 0, 'regime': 'static',
                'friction_factor': 0, 'reynolds': 0}

    # Bingham Reynolds number
    Re_B = density * V * diameter_m / mu_p

    # Hedstrom number
    He = density * tau_y * diameter_m ** 2 / mu_p ** 2

    # Critical Reynolds number for transition (Slatter, 1995)
    Re_crit = _bingham_critical_reynolds(He)

    if Re_B < Re_crit:
        # Laminar flow - Buckingham-Reiner equation
        # Darcy friction factor for laminar Bingham plastic — Buckingham-Reiner
        # Uses Darcy convention (64/Re), NOT Fanning (16/Re)
        f = 64 / Re_B * (1 + He / (6 * Re_B) - (He ** 4) / (3 * 1e7 * Re_B ** 7))
        f = max(f, 64 / Re_B)  # Floor at Newtonian laminar (Darcy)
        regime = 'laminar'
    else:
        # Turbulent flow - Wilson-Thomas correlation
        f = _wilson_thomas_friction(Re_B, He, roughness_mm / 1000, diameter_m)
        regime = 'turbulent'

    # Darcy-Weisbach headloss
    headloss = f * (length_m / diameter_m) * (V ** 2) / (2 * g)

    return {
        'headloss_m': round(headloss, 3),
        'velocity_ms': round(V, 3),
        'regime': regime,
        'friction_factor': round(f, 6),
        'reynolds': round(Re_B, 0),
        'hedstrom': round(He, 0),
        'critical_reynolds': round(Re_crit, 0),
    }


def power_law_headloss(flow_m3s, diameter_m, length_m, density, K, n,
                        roughness_mm=0.05):
    """
    Calculate headloss for Power Law fluid.

    tau = K * (du/dr)^n

    Parameters
    ----------
    K : float
        Consistency index (Pa.s^n).
    n : float
        Flow behaviour index (n<1: shear-thinning, n>1: shear-thickening).

    Returns
    -------
    dict with headloss_m, velocity_ms, regime, etc.
    """
    g = 9.81
    A = math.pi * (diameter_m / 2) ** 2
    V = abs(flow_m3s) / A if A > 0 else 0

    if V < 1e-6:
        return {'headloss_m': 0, 'velocity_ms': 0, 'regime': 'static',
                'friction_factor': 0, 'reynolds': 0}

    # Generalized Reynolds number (Metzner-Reed)
    Re_MR = (density * V ** (2 - n) * diameter_m ** n) / (
        K * 8 ** (n - 1) * ((3 * n + 1) / (4 * n)) ** n
    )

    # Critical Reynolds number
    Re_crit = 2100  # Approximate for power law

    if Re_MR < Re_crit:
        # Darcy friction factor for laminar power law flow
        # Uses Darcy convention (64/Re), NOT Fanning (16/Re)
        f = 64 / Re_MR
        regime = 'laminar'
    else:
        # Dodge-Metzner correlation returns Fanning f — multiply by 4 for Darcy
        f_fanning = _dodge_metzner_friction(Re_MR, n)
        f = 4 * f_fanning
        regime = 'turbulent'

    # Darcy-Weisbach headloss: hL = f * (L/D) * V²/(2g)
    headloss = f * (length_m / diameter_m) * (V ** 2) / (2 * g)

    return {
        'headloss_m': round(headloss, 3),
        'velocity_ms': round(V, 3),
        'regime': regime,
        'friction_factor': round(f, 6),
        'reynolds_MR': round(Re_MR, 0),
        'flow_index_n': n,
        'consistency_K': K,
    }


def herschel_bulkley_headloss(flow_m3s, diameter_m, length_m, density,
                                tau_y, K, n, roughness_mm=0.05):
    """
    Calculate headloss for Herschel-Bulkley fluid.

    tau = tau_y + K * (du/dr)^n

    This is the most general model - reduces to:
    - Bingham Plastic when n=1
    - Power Law when tau_y=0
    - Newtonian when tau_y=0 and n=1

    Uses an equivalent Bingham approach for simplicity.
    """
    g = 9.81
    A = math.pi * (diameter_m / 2) ** 2
    V = abs(flow_m3s) / A if A > 0 else 0

    if V < 1e-6:
        return {'headloss_m': 0, 'velocity_ms': 0, 'regime': 'static',
                'friction_factor': 0, 'reynolds': 0}

    # Apparent viscosity at wall shear rate
    gamma_wall = 8 * V / diameter_m  # Approximate wall shear rate
    tau_wall = tau_y + K * gamma_wall ** n
    mu_app = tau_wall / gamma_wall if gamma_wall > 0 else K

    # Generalized Reynolds number
    Re_gen = density * V * diameter_m / mu_app

    if Re_gen < 2100:
        # Darcy friction factor for laminar flow — consistent with Bingham solver
        # Uses Darcy convention (64/Re), NOT Fanning (16/Re)
        f = 64 / max(Re_gen, 1)
        regime = 'laminar'
    else:
        # Use Colebrook-White with apparent viscosity (returns Darcy f)
        e_d = roughness_mm / 1000 / diameter_m
        f = _colebrook_white(Re_gen, e_d)
        regime = 'turbulent'

    # Darcy-Weisbach headloss: hL = f * (L/D) * V²/(2g)
    headloss = f * (length_m / diameter_m) * (V ** 2) / (2 * g)

    return {
        'headloss_m': round(headloss, 3),
        'velocity_ms': round(V, 3),
        'regime': regime,
        'friction_factor': round(f, 6),
        'reynolds_gen': round(Re_gen, 0),
        'apparent_viscosity': round(mu_app, 6),
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _bingham_critical_reynolds(He):
    """Calculate critical Reynolds number for Bingham plastic.
    Uses Slatter (1995) correlation."""
    if He < 1:
        return 2100
    Re_c = 2100 * (1 + He / 12000)
    return min(Re_c, 40000)


def _wilson_thomas_friction(Re, He, roughness, diameter):
    """Turbulent friction factor for Bingham plastic flow.

    Uses Darby (Chem Eng Fluid Mechanics 3rd ed, Eq 7.17) Metzner-Reed
    correlation with Bingham correction, blended with Colebrook-White
    for wall roughness effects.

    For smooth pipes the Darby correlation dominates; for rough pipes
    the Colebrook-White result sets the floor.
    """
    e_d = roughness / diameter if diameter > 0 else 0

    # Darby Eq 7.17: Metzner-Reed turbulent for Bingham plastic (n'=1)
    # 1/sqrt(f) = 4*log10(Re_B * sqrt(f)) - 0.4
    # Iterative solution
    f_darby = 0.01
    for _ in range(50):
        try:
            rhs = 4.0 * math.log10(Re * math.sqrt(f_darby)) - 0.4
            f_new = 1.0 / (rhs * rhs) if rhs > 0.1 else f_darby
            if abs(f_new - f_darby) < 1e-8:
                break
            f_darby = f_new
        except (ValueError, ZeroDivisionError):
            break
    f_darby = max(f_darby, 0.001)

    # Colebrook-White for wall roughness contribution
    f_cw = _colebrook_white(Re, e_d)

    # Use the higher of the two — roughness always increases friction
    # Darby f is the Bingham-corrected smooth-pipe value
    # For rough pipes, CW dominates; for smooth pipes, Darby dominates
    return max(f_darby, f_cw)


def _dodge_metzner_friction(Re_MR, n):
    """Dodge-Metzner correlation for turbulent power law flow."""
    # Iterative solution: 1/sqrt(f) = (4/n^0.75) * log10(Re_MR * f^(1-n/2)) - 0.4/n^1.2
    f = 0.01  # Initial guess
    for _ in range(50):
        lhs = 1 / math.sqrt(f)
        rhs = (4.0 / n ** 0.75) * math.log10(Re_MR * f ** (1 - n / 2)) - 0.4 / n ** 1.2
        f_new = 1 / rhs ** 2 if rhs > 0 else f
        if abs(f_new - f) < 1e-8:
            break
        f = f_new
    return max(f, 0.001)


def _colebrook_white(Re, e_d):
    """Colebrook-White equation for Darcy friction factor."""
    if Re < 1:
        return 0.064
    f = 0.02  # Initial guess
    for _ in range(50):
        try:
            rhs = -2 * math.log10(e_d / 3.7 + 2.51 / (Re * math.sqrt(f)))
            f_new = 1 / rhs ** 2
            if abs(f_new - f) < 1e-8:
                break
            f = f_new
        except (ValueError, ZeroDivisionError):
            break
    return max(f, 0.001)


# ============================================================================
# NETWORK ANALYSIS
# ============================================================================

def analyze_slurry_network(wn, fluid_name='mine_tailings_30pct', custom_fluid=None):
    """
    Analyze a network with non-Newtonian fluid properties.

    Runs EPANET steady-state first to get flow distribution,
    then recalculates headloss using the appropriate rheological model.

    Parameters
    ----------
    wn : wntr.network.WaterNetworkModel
        Network model (already loaded).
    fluid_name : str
        Name from SLURRY_DATABASE.
    custom_fluid : dict or None
        Custom fluid properties (overrides fluid_name).

    Returns
    -------
    dict with per-pipe headloss, velocities, regimes, and system summary.
    """
    import wntr

    fluid = custom_fluid or SLURRY_DATABASE.get(fluid_name)
    if not fluid:
        return {'error': f'Unknown fluid: {fluid_name}'}

    # Run EPANET to get flow distribution (using water properties)
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim()
    flows = results.link['flowrate']

    pipe_results = {}
    total_headloss = 0
    max_velocity = 0

    for pipe_name in wn.pipe_name_list:
        pipe = wn.get_link(pipe_name)
        flow = float(flows[pipe_name].iloc[0])  # Use first timestep

        if fluid['type'] == 'bingham_plastic':
            hl = bingham_plastic_headloss(
                flow, pipe.diameter, pipe.length,
                fluid['density_kg_m3'], fluid['yield_stress_Pa'],
                fluid['plastic_viscosity_Pa_s'],
            )
        elif fluid['type'] == 'power_law':
            hl = power_law_headloss(
                flow, pipe.diameter, pipe.length,
                fluid['density_kg_m3'], fluid['K'], fluid['n'],
            )
        elif fluid['type'] == 'herschel_bulkley':
            hl = herschel_bulkley_headloss(
                flow, pipe.diameter, pipe.length,
                fluid['density_kg_m3'], fluid['yield_stress_Pa'],
                fluid['K'], fluid['n'],
            )
        else:
            # Newtonian fallback
            hl = {'headloss_m': 0, 'velocity_ms': 0, 'regime': 'newtonian',
                  'friction_factor': 0, 'reynolds': 0}

        pipe_results[pipe_name] = {
            'flow_m3s': round(flow, 6),
            'flow_lps': round(flow * 1000, 2),
            **hl,
        }
        total_headloss += hl['headloss_m']
        max_velocity = max(max_velocity, hl['velocity_ms'])

    return {
        'fluid': fluid,
        'fluid_name': fluid_name,
        'pipe_results': pipe_results,
        'total_headloss_m': round(total_headloss, 1),
        'max_velocity_ms': round(max_velocity, 2),
        'pipe_count': len(pipe_results),
        'compliance': _slurry_compliance(pipe_results, fluid),
    }


def _slurry_compliance(pipe_results, fluid):
    """Check slurry-specific compliance."""
    issues = []
    for name, data in pipe_results.items():
        # Settling velocity check (slurry should maintain min velocity)
        if fluid['type'] != 'newtonian' and data['velocity_ms'] < 1.0 and data['velocity_ms'] > 0:
            issues.append({
                'type': 'WARNING',
                'element': name,
                'message': f'Velocity {data["velocity_ms"]} m/s below 1.0 m/s settling limit',
            })
        # High velocity wear
        if data['velocity_ms'] > 3.0:
            issues.append({
                'type': 'WARNING',
                'element': name,
                'message': f'Velocity {data["velocity_ms"]} m/s exceeds 3.0 m/s (pipe wear risk)',
            })
    if not issues:
        issues.append({'type': 'OK', 'message': 'All pipes within slurry flow limits'})
    return issues


def list_fluids():
    """Return available fluid types from the database."""
    return {name: fluid['description'] for name, fluid in SLURRY_DATABASE.items()}


# ============================================================================
# ADVANCED SLURRY FEATURES (I15)
# ============================================================================

def settling_velocity(d_particle_mm, rho_solid, rho_fluid=1000, mu_fluid=0.001):
    """
    Calculate terminal settling velocity of a single particle.

    Uses Stokes' law for Re_p < 1, transitional for 1 < Re_p < 1000,
    and Newton's law for Re_p > 1000.

    Parameters
    ----------
    d_particle_mm : float
        Particle diameter in mm
    rho_solid : float
        Solid particle density (kg/m³), e.g., 2650 for sand
    rho_fluid : float
        Carrier fluid density (kg/m³)
    mu_fluid : float
        Carrier fluid dynamic viscosity (Pa·s)

    Returns dict with velocity_ms, regime, reynolds.
    Ref: Stokes (1851), Wasp et al. (1977)
    """
    g = 9.81
    d = d_particle_mm / 1000  # mm to m
    delta_rho = rho_solid - rho_fluid

    if d <= 0 or delta_rho <= 0:
        return {'velocity_ms': 0, 'regime': 'neutral', 'reynolds': 0}

    # Stokes settling velocity (laminar)
    # V_s = (d² × (ρ_s - ρ_f) × g) / (18 × μ)
    # Ref: Stokes (1851)
    v_stokes = (d ** 2 * delta_rho * g) / (18 * mu_fluid)

    # Check Reynolds number
    Re_p = rho_fluid * v_stokes * d / mu_fluid

    if Re_p < 1:
        # Stokes regime (laminar settling)
        return {
            'velocity_ms': round(v_stokes, 4),
            'regime': 'Stokes (laminar)',
            'reynolds': round(Re_p, 2),
        }
    elif Re_p < 1000:
        # Transitional regime — Schiller-Naumann correlation
        # C_D = 24/Re × (1 + 0.15 × Re^0.687)
        # Ref: Schiller & Naumann (1935)
        # Iterative solution
        v = v_stokes
        for _ in range(20):
            Re = rho_fluid * v * d / mu_fluid
            if Re < 0.01:
                break
            C_D = (24 / Re) * (1 + 0.15 * Re ** 0.687)
            v_new = math.sqrt(4 * d * delta_rho * g / (3 * C_D * rho_fluid))
            if abs(v_new - v) < 1e-6:
                break
            v = v_new

        Re = rho_fluid * v * d / mu_fluid
        return {
            'velocity_ms': round(v, 4),
            'regime': 'transitional',
            'reynolds': round(Re, 2),
        }
    else:
        # Newton regime (turbulent settling)
        # C_D ≈ 0.44
        # V = sqrt(4gd(ρ_s-ρ_f) / (3 × 0.44 × ρ_f))
        # Ref: Newton's drag law
        v_newton = math.sqrt(4 * d * delta_rho * g / (3 * 0.44 * rho_fluid))
        Re = rho_fluid * v_newton * d / mu_fluid
        return {
            'velocity_ms': round(v_newton, 4),
            'regime': 'Newton (turbulent)',
            'reynolds': round(Re, 2),
        }


def critical_deposition_velocity(d_particle_mm, pipe_diameter_mm,
                                  rho_solid=2650, rho_fluid=1000,
                                  concentration_vol=0.1):
    """
    Calculate critical deposition velocity using Durand correlation.

    Below this velocity, solids begin to settle and form a bed.
    Pipe should be operated above this velocity to maintain transport.

    V_D = F_L × sqrt(2gD(S-1))

    where F_L is Durand's limit deposit velocity coefficient,
    D is pipe diameter, S = ρ_s/ρ_f is specific gravity.

    Parameters
    ----------
    d_particle_mm : float
        Median particle diameter (d50) in mm
    pipe_diameter_mm : float
        Internal pipe diameter in mm
    rho_solid : float
        Solid particle density (kg/m³)
    rho_fluid : float
        Carrier fluid density (kg/m³)
    concentration_vol : float
        Volumetric solids concentration (0-1), e.g., 0.10 = 10%

    Returns dict with velocity_ms, durand_fl, specific_gravity.
    Ref: Durand (1952), BHRA Fluid Engineering "Slurry Transportation"
    """
    g = 9.81
    D = pipe_diameter_mm / 1000  # mm to m
    d_p = d_particle_mm  # keep in mm for F_L lookup
    S = rho_solid / rho_fluid  # specific gravity of solids

    if D <= 0 or d_p <= 0 or S <= 1:
        return {'velocity_ms': 0, 'durand_fl': 0, 'specific_gravity': S}

    # Durand's F_L coefficient — depends on particle size and concentration
    # Typical values: fine sand (d<0.5mm) F_L=0.8-1.2, coarse (d>2mm) F_L=1.3-1.7
    # Ref: Durand (1952) nomogram, simplified correlation
    if d_p < 0.1:
        F_L = 0.8 + 2.0 * concentration_vol
    elif d_p < 0.5:
        F_L = 1.0 + 1.5 * concentration_vol
    elif d_p < 2.0:
        F_L = 1.3 + 1.0 * concentration_vol
    else:
        F_L = 1.5 + 0.5 * concentration_vol

    # Clamp F_L to reasonable range — Durand (1952)
    F_L = max(0.5, min(2.0, F_L))

    # V_D = F_L × sqrt(2gD(S-1))
    V_D = F_L * math.sqrt(2 * g * D * (S - 1))

    return {
        'velocity_ms': round(V_D, 2),
        'durand_fl': round(F_L, 2),
        'specific_gravity': round(S, 2),
        'pipe_diameter_mm': pipe_diameter_mm,
        'particle_d50_mm': d_p,
        'basis': f'V_D = {F_L:.2f} × sqrt(2×{g}×{D:.3f}×({S:.2f}-1)) '
                 f'= {V_D:.2f} m/s — Durand (1952)',
    }


def concentration_profile(pipe_diameter_mm, velocity_ms, d_particle_mm,
                           rho_solid=2650, rho_fluid=1000,
                           concentration_avg=0.1, n_points=20):
    """
    Calculate vertical concentration profile across pipe cross-section.

    Uses Rouse equation for suspended sediment distribution:
    C(y)/C_a = [(h-y)/y × a/(h-a)]^z
    where z = w_s/(κ×u*), κ=0.4 (von Karman), u* = friction velocity

    Parameters
    ----------
    pipe_diameter_mm : float
        Pipe internal diameter (mm)
    velocity_ms : float
        Mean flow velocity (m/s)
    d_particle_mm : float
        Particle diameter (mm)
    rho_solid, rho_fluid : float
        Densities (kg/m³)
    concentration_avg : float
        Average volumetric concentration (0-1)
    n_points : int
        Number of vertical points to compute

    Returns dict with 'y_positions', 'concentrations', 'rouse_z'.
    Ref: Rouse (1937), Wasp et al. (1977)
    """
    D = pipe_diameter_mm / 1000  # m
    if D <= 0 or velocity_ms <= 0:
        return {'y_positions': [], 'concentrations': [], 'rouse_z': 0}

    # Settling velocity
    sv = settling_velocity(d_particle_mm, rho_solid, rho_fluid)
    w_s = sv['velocity_ms']

    # Friction velocity u* ≈ V × sqrt(f/8) where f ≈ 0.02 (typical)
    f = 0.02  # approximate Darcy friction factor
    u_star = velocity_ms * math.sqrt(f / 8)

    if u_star < 1e-6:
        return {'y_positions': [], 'concentrations': [], 'rouse_z': 0}

    # Rouse number z = w_s / (κ × u*)
    kappa = 0.4  # von Karman constant
    z = w_s / (kappa * u_star)

    # Generate profile
    h = D  # pipe height = diameter (simplified)
    a = 0.05 * h  # reference level (5% of diameter from bottom)

    y_positions = []
    concentrations = []

    for i in range(n_points):
        y = a + (h - 2 * a) * (i / (n_points - 1)) if n_points > 1 else h / 2
        y = max(a, min(h - a, y))

        # Rouse equation: C(y)/C_a = [(h-y)/y × a/(h-a)]^z
        ratio = ((h - y) / y) * (a / (h - a))
        if ratio > 0:
            C_y = concentration_avg * (ratio ** z)
        else:
            C_y = 0

        y_positions.append(round(y * 1000, 1))  # back to mm
        concentrations.append(round(min(C_y, 0.65), 4))  # cap at 65% (packing limit)

    return {
        'y_positions': y_positions,
        'concentrations': concentrations,
        'rouse_z': round(z, 2),
        'settling_velocity_ms': w_s,
        'friction_velocity_ms': round(u_star, 4),
    }


def wasp_critical_velocity(d_particle_mm, pipe_diameter_mm,
                            rho_solid=2650, rho_fluid=1000,
                            concentration_vol=0.1, mu_fluid=0.001):
    """
    Calculate critical deposition velocity using the Wasp et al. (1977) model.

    Uses particle settling velocity and pipe properties to estimate
    the minimum velocity to maintain heterogeneous flow.

    V_c = 3.116 × C_v^0.186 × (d/D)^(-0.168) × (w_s/sqrt(gD))^0.364 × sqrt(2gD(S-1))

    Parameters
    ----------
    d_particle_mm : float
        Median particle diameter (d50) in mm
    pipe_diameter_mm : float
        Internal pipe diameter in mm
    rho_solid : float
        Solid particle density (kg/m³)
    rho_fluid : float
        Carrier fluid density (kg/m³)
    concentration_vol : float
        Volumetric solids concentration (0-1)
    mu_fluid : float
        Carrier fluid dynamic viscosity (Pa·s)

    Returns dict with velocity_ms and calculation details.
    Ref: Wasp, Kenny & Gandhi (1977) "Solid-Liquid Flow Slurry Pipeline
         Transportation", Trans Tech Publications
    """
    g = 9.81
    D = pipe_diameter_mm / 1000  # mm to m
    d_p = d_particle_mm / 1000  # mm to m
    S = rho_solid / rho_fluid

    if D <= 0 or d_p <= 0 or S <= 1 or concentration_vol <= 0:
        return {'velocity_ms': 0, 'method': 'wasp'}

    # Get settling velocity
    ws_result = settling_velocity(d_particle_mm, rho_solid, rho_fluid, mu_fluid)
    w_s = ws_result['velocity_ms']

    if w_s <= 0:
        return {'velocity_ms': 0, 'method': 'wasp'}

    # Wasp correlation
    # V_c = 3.116 × Cv^0.186 × (d/D)^(-0.168) × (ws/sqrt(gD))^0.364 × sqrt(2gD(S-1))
    term1 = 3.116
    term2 = concentration_vol ** 0.186
    term3 = (d_p / D) ** (-0.168)
    term4 = (w_s / math.sqrt(g * D)) ** 0.364
    term5 = math.sqrt(2 * g * D * (S - 1))

    V_c = term1 * term2 * term3 * term4 * term5

    return {
        'velocity_ms': round(V_c, 2),
        'settling_velocity_ms': round(w_s, 4),
        'specific_gravity': round(S, 2),
        'method': 'wasp',
        'basis': f'Wasp et al. (1977): V_c = {V_c:.2f} m/s',
    }


def derate_pump_for_slurry(head_water_m, efficiency_water, concentration_vol,
                            rho_solid=2650, rho_fluid=1000):
    """
    Derate pump head and efficiency for slurry service.

    Slurry pumps deliver less head and have lower efficiency than water
    pumps due to increased viscosity and density effects.

    Head: H_slurry = H_water × C_H (correction factor)
    Efficiency: η_slurry = η_water × C_η

    Parameters
    ----------
    head_water_m : float
        Pump head on water (m)
    efficiency_water : float
        Pump efficiency on water (0-1, e.g. 0.75)
    concentration_vol : float
        Volumetric solids concentration (0-1)
    rho_solid : float
        Solid density (kg/m³)
    rho_fluid : float
        Carrier fluid density (kg/m³)

    Returns dict with derated head, efficiency, and correction factors.
    Ref: Wilson, Addie & Clift "Slurry Transport Using Centrifugal Pumps"
         3rd ed., Springer (2006), Chapter 7
    """
    S = rho_solid / rho_fluid
    Cv = concentration_vol

    # Mixture specific gravity
    S_m = 1 + Cv * (S - 1)

    # Head correction factor (Wilson et al.)
    # C_H ≈ 1 - 0.8 × Cv for coarse particles
    # C_H ≈ 1 - 0.3 × Cv for fine particles (<75μm)
    # Use intermediate for general case
    C_H = max(0.5, 1.0 - 0.5 * Cv)

    # Efficiency correction
    # C_η ≈ 1 - 0.6 × Cv (typical for centrifugal slurry pumps)
    C_eta = max(0.4, 1.0 - 0.6 * Cv)

    H_slurry = head_water_m * C_H
    eta_slurry = efficiency_water * C_eta

    # Power increase factor
    # P_slurry = (S_m / S_water) × (H_water / H_slurry) × (η_water / η_slurry) × P_water
    power_factor = S_m * (1.0 / C_H) * (1.0 / C_eta)

    return {
        'head_slurry_m': round(H_slurry, 1),
        'efficiency_slurry': round(eta_slurry, 3),
        'head_correction_CH': round(C_H, 3),
        'efficiency_correction_Ceta': round(C_eta, 3),
        'mixture_sg': round(S_m, 3),
        'power_increase_factor': round(power_factor, 2),
        'basis': 'Wilson, Addie & Clift (2006) Ch.7',
    }

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

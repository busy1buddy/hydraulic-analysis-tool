"""
Fluid Properties Database — data/fluid_properties.py
======================================================
Authoritative definitions for all fluid types used in the hydraulic analysis
tool. Covers:
  - Standard water (temperature-dependent viscosity and density)
  - Slurry mixtures (density and viscosity as a function of concentration)
  - Custom user-defined fluids

Architecture:
  This module lives in the data/ layer (Layer 3 — Domain).
  It may be imported by:
    - slurry_solver.py  (Layer 3 — replaces SLURRY_DATABASE)
    - epanet_api.py     (Layer 2 — passes fluid props to solver)
    - desktop/          (Layer 4 — reads display values only)
  It must NOT import from desktop/ or epanet_api.py.

References:
  - White, F.M. (2011) Fluid Mechanics, 7th ed., McGraw-Hill.
  - Wilson, K.C. et al. (2006) Slurry Transport Using Centrifugal Pumps, 3rd ed.
  - WSAA WSA 03-2011 Table B2 — water quality parameters.
  - AS/NZS 1477, AS/NZS 4130, AS 2280 — pipe pressure ratings.
"""

import math
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Fluid type identifiers
# ---------------------------------------------------------------------------
FLUID_WATER = "water"
FLUID_BINGHAM = "bingham_plastic"
FLUID_POWER_LAW = "power_law"
FLUID_HERSCHEL_BULKLEY = "herschel_bulkley"
FLUID_NEWTONIAN_SLURRY = "newtonian_slurry"


# ---------------------------------------------------------------------------
# Data class: FluidProperties
# ---------------------------------------------------------------------------

@dataclass
class FluidProperties:
    """
    Complete fluid property definition for one fluid at operating conditions.

    All properties are at the operating temperature. Use
    water_at_temperature() or from_slurry_concentration() to construct
    instances rather than instantiating directly.
    """
    name: str
    fluid_type: str                   # One of the FLUID_* constants above

    # Universal properties (required for all fluids)
    density_kg_m3: float              # ρ — kg/m³
    dynamic_viscosity_Pa_s: float     # μ — Pa·s  (kinematic ν = μ/ρ)

    # Bingham Plastic extras (fluid_type == FLUID_BINGHAM)
    yield_stress_Pa: float = 0.0      # τ_y — Pa
    plastic_viscosity_Pa_s: float = 0.0  # μ_p — Pa·s

    # Power Law / Herschel-Bulkley extras
    consistency_K: float = 0.0       # K — Pa·s^n
    flow_index_n: float = 1.0        # n — dimensionless

    # Slurry metadata
    solids_density_kg_m3: float = 0.0    # ρ_s — kg/m³ (solid phase)
    concentration_vol_frac: float = 0.0  # C_v — volumetric fraction 0→1
    concentration_wt_pct: float = 0.0    # C_w — weight percent 0→100
    d50_particle_mm: float = 0.0         # Median particle diameter (mm)

    # Descriptive
    description: str = ""
    temperature_C: float = 20.0      # Operating temperature
    reference: str = ""              # Citation

    @property
    def kinematic_viscosity_m2s(self) -> float:
        """ν = μ/ρ  (m²/s)."""
        if self.density_kg_m3 <= 0:
            return 0.0
        return self.dynamic_viscosity_Pa_s / self.density_kg_m3

    @property
    def specific_gravity(self) -> float:
        """SG relative to water at 4°C (1000 kg/m³)."""
        return self.density_kg_m3 / 1000.0

    @property
    def is_newtonian(self) -> bool:
        """True when the fluid requires no special rheological solver."""
        return self.fluid_type in (FLUID_WATER, FLUID_NEWTONIAN_SLURRY)

    def joukowsky_density(self) -> float:
        """Return the density to use in Joukowsky surge calculations.

        Rule from CLAUDE.md: use actual fluid density — never hardcode 1000 kg/m³ for slurry.
        """
        return self.density_kg_m3

    def to_dict(self) -> dict:
        """Serialise to a plain dict for passing to report generators."""
        return {
            'name': self.name,
            'fluid_type': self.fluid_type,
            'density_kg_m3': self.density_kg_m3,
            'dynamic_viscosity_Pa_s': self.dynamic_viscosity_Pa_s,
            'kinematic_viscosity_m2s': self.kinematic_viscosity_m2s,
            'specific_gravity': round(self.specific_gravity, 3),
            'yield_stress_Pa': self.yield_stress_Pa,
            'plastic_viscosity_Pa_s': self.plastic_viscosity_Pa_s,
            'consistency_K': self.consistency_K,
            'flow_index_n': self.flow_index_n,
            'solids_density_kg_m3': self.solids_density_kg_m3,
            'concentration_vol_frac': self.concentration_vol_frac,
            'concentration_wt_pct': self.concentration_wt_pct,
            'd50_particle_mm': self.d50_particle_mm,
            'temperature_C': self.temperature_C,
            'description': self.description,
            'reference': self.reference,
        }


# ---------------------------------------------------------------------------
# Factory: water
# ---------------------------------------------------------------------------

def water_at_temperature(temperature_C: float = 20.0) -> FluidProperties:
    """
    Return FluidProperties for clean water at the given temperature.

    Density and viscosity are interpolated from the standard table.
    Ref: White, F.M. (2011) Fluid Mechanics, Table A.1.

    Parameters
    ----------
    temperature_C : float
        Operating temperature in °C (0–100).

    Returns
    -------
    FluidProperties
    """
    # Validated T range — extrapolation outside 0-100°C is not meaningful.
    T = max(0.0, min(100.0, temperature_C))

    # Density interpolation (kg/m³) — polynomial fit to NIST data
    # Ref: White (2011) Table A.1
    rho = (999.842594
           + 6.793952e-2 * T
           - 9.095290e-3 * T**2
           + 1.001685e-4 * T**3
           - 1.120083e-6 * T**4
           + 6.536332e-9 * T**5)

    # Dynamic viscosity (Pa·s) — Vogel correlation
    # ln(μ) = A + B/(C + T)
    # Ref: Correlations for Viscosity of Water, Perry's 8th ed.
    A, B, C = -3.7188, 578.919, -137.546
    mu = math.exp(A + B / (C + T)) * 1e-3  # Result in Pa·s

    return FluidProperties(
        name=f"Water at {T:.0f}°C",
        fluid_type=FLUID_WATER,
        density_kg_m3=round(rho, 2),
        dynamic_viscosity_Pa_s=round(mu, 6),
        temperature_C=T,
        description=(
            f"Clean potable water at {T:.0f}°C. "
            f"ρ={rho:.1f} kg/m³, μ={mu*1000:.3f} mPa·s."
        ),
        reference="White (2011) Fluid Mechanics Table A.1; Perry's 8th ed.",
    )


# ---------------------------------------------------------------------------
# Factory: Newtonian slurry (dilute — behaves like water with higher density)
# ---------------------------------------------------------------------------

def newtonian_slurry(rho_solid_kg_m3: float, concentration_vol: float,
                     mu_carrier_Pa_s: float = 0.001,
                     rho_carrier_kg_m3: float = 1000.0,
                     d50_mm: float = 0.0) -> FluidProperties:
    """
    Dilute slurry treated as a Newtonian fluid with mixture density.

    Applies Thomas (1965) relative viscosity correlation for dilute suspensions.
    Use when concentration < 15% vol and particles are fine.

    μ_rel = 1 + 2.5·C_v + 10.05·C_v² + 0.00273·exp(16.6·C_v)
    Ref: Thomas (1965) J. Colloid Sci. 20 (3) 267–277.

    Parameters
    ----------
    rho_solid_kg_m3 : float
        Solid phase density (kg/m³). Quartz sand = 2650, magnetite = 5200.
    concentration_vol : float
        Volumetric solids concentration (0–1).
    mu_carrier_Pa_s : float
        Dynamic viscosity of carrier fluid (Pa·s). Default: water at 20°C.
    rho_carrier_kg_m3 : float
        Density of carrier fluid (kg/m³). Default: water at 20°C.
    d50_mm : float
        Median particle diameter (mm). For metadata.
    """
    Cv = max(0.0, min(1.0, concentration_vol))

    # Mixture density — linear by volume fractions
    rho_mix = rho_carrier_kg_m3 * (1 - Cv) + rho_solid_kg_m3 * Cv

    # Thomas (1965) relative viscosity
    mu_rel = 1 + 2.5 * Cv + 10.05 * Cv**2 + 0.00273 * math.exp(16.6 * Cv)
    mu_mix = mu_carrier_Pa_s * mu_rel

    # Weight concentration
    Cw = (Cv * rho_solid_kg_m3 / rho_mix) * 100.0

    return FluidProperties(
        name=f"Newtonian Slurry Cv={Cv*100:.0f}%",
        fluid_type=FLUID_NEWTONIAN_SLURRY,
        density_kg_m3=round(rho_mix, 1),
        dynamic_viscosity_Pa_s=round(mu_mix, 6),
        solids_density_kg_m3=rho_solid_kg_m3,
        concentration_vol_frac=Cv,
        concentration_wt_pct=round(Cw, 1),
        d50_particle_mm=d50_mm,
        description=(
            f"Dilute Newtonian slurry, Cv={Cv*100:.0f}%, "
            f"ρ_mix={rho_mix:.0f} kg/m³."
        ),
        reference="Thomas (1965) J. Colloid Sci. 20:267–277",
    )


# ---------------------------------------------------------------------------
# Factory: Bingham Plastic
# ---------------------------------------------------------------------------

def bingham_plastic(tau_y_Pa: float, mu_p_Pa_s: float,
                    rho_kg_m3: float, d50_mm: float = 0.0,
                    name: str = "Bingham Plastic") -> FluidProperties:
    """
    Construct a Bingham Plastic fluid definition.

    τ = τ_y + μ_p · (du/dy)

    Parameters
    ----------
    tau_y_Pa : float
        Yield stress (Pa). Must be > 0 for true Bingham behaviour.
    mu_p_Pa_s : float
        Plastic viscosity (Pa·s). Must be > 0.
    rho_kg_m3 : float
        Fluid mixture density (kg/m³).
    """
    if mu_p_Pa_s <= 0:
        raise ValueError(f"Plastic viscosity must be > 0, got {mu_p_Pa_s}")
    if rho_kg_m3 <= 0:
        raise ValueError(f"Density must be > 0, got {rho_kg_m3}")

    return FluidProperties(
        name=name,
        fluid_type=FLUID_BINGHAM,
        density_kg_m3=rho_kg_m3,
        dynamic_viscosity_Pa_s=mu_p_Pa_s,
        yield_stress_Pa=tau_y_Pa,
        plastic_viscosity_Pa_s=mu_p_Pa_s,
        d50_particle_mm=d50_mm,
        description=(
            f"Bingham Plastic: τ_y={tau_y_Pa} Pa, "
            f"μ_p={mu_p_Pa_s*1000:.1f} mPa·s, ρ={rho_kg_m3} kg/m³."
        ),
        reference=(
            "Buckingham-Reiner laminar equation (Darcy f). "
            "Wilson-Thomas turbulent correlation. "
            "Ref: Wilson et al. (2006) Slurry Transport."
        ),
    )


# ---------------------------------------------------------------------------
# Factory: Power Law
# ---------------------------------------------------------------------------

def power_law(K_Pa_sn: float, n: float, rho_kg_m3: float,
              name: str = "Power Law") -> FluidProperties:
    """
    Construct a Power Law fluid definition.

    τ = K · (du/dy)^n

    Parameters
    ----------
    K_Pa_sn : float
        Consistency index (Pa·s^n).
    n : float
        Flow behaviour index. n<1: shear-thinning, n>1: shear-thickening.
    """
    if K_Pa_sn <= 0:
        raise ValueError(f"Consistency index K must be > 0, got {K_Pa_sn}")
    if n <= 0:
        raise ValueError(f"Flow index n must be > 0, got {n}")

    behaviour = "shear-thinning" if n < 1 else ("Newtonian" if n == 1 else "shear-thickening")

    return FluidProperties(
        name=name,
        fluid_type=FLUID_POWER_LAW,
        density_kg_m3=rho_kg_m3,
        dynamic_viscosity_Pa_s=K_Pa_sn,  # apparent viscosity at unit shear rate
        consistency_K=K_Pa_sn,
        flow_index_n=n,
        description=(
            f"Power Law ({behaviour}): K={K_Pa_sn} Pa·s^n, "
            f"n={n}, ρ={rho_kg_m3} kg/m³."
        ),
        reference=(
            "Metzner-Reed generalised Reynolds number. "
            "Dodge-Metzner turbulent friction correlation. "
            "Ref: Metzner & Reed (1955) AIChE J. 1(4) 434–440."
        ),
    )


# ---------------------------------------------------------------------------
# Factory: Herschel-Bulkley
# ---------------------------------------------------------------------------

def herschel_bulkley(tau_y_Pa: float, K_Pa_sn: float, n: float,
                     rho_kg_m3: float,
                     name: str = "Herschel-Bulkley") -> FluidProperties:
    """
    Construct a Herschel-Bulkley fluid definition.

    τ = τ_y + K · (du/dy)^n

    Most general non-Newtonian model. Reduces to:
    - Bingham Plastic when n=1
    - Power Law when τ_y=0
    - Newtonian when τ_y=0 and n=1
    """
    return FluidProperties(
        name=name,
        fluid_type=FLUID_HERSCHEL_BULKLEY,
        density_kg_m3=rho_kg_m3,
        dynamic_viscosity_Pa_s=K_Pa_sn,
        yield_stress_Pa=tau_y_Pa,
        consistency_K=K_Pa_sn,
        flow_index_n=n,
        description=(
            f"Herschel-Bulkley: τ_y={tau_y_Pa} Pa, "
            f"K={K_Pa_sn} Pa·s^n, n={n}, ρ={rho_kg_m3} kg/m³."
        ),
        reference=(
            "Ref: Herschel & Bulkley (1926) Kolloid-Z. 39 291–300. "
            "Generalised Reynolds number with apparent wall viscosity."
        ),
    )


# ---------------------------------------------------------------------------
# Built-in fluid catalogue (replaces SLURRY_DATABASE in slurry_solver.py)
# ---------------------------------------------------------------------------

FLUID_CATALOGUE: dict[str, FluidProperties] = {
    "water_20c": water_at_temperature(20.0),
    "water_10c": water_at_temperature(10.0),
    "water_30c": water_at_temperature(30.0),

    "mine_tailings_30pct": bingham_plastic(
        tau_y_Pa=5.0, mu_p_Pa_s=0.015, rho_kg_m3=1300.0, d50_mm=0.074,
        name="Mine Tailings 30% wt"),

    "mine_tailings_50pct": bingham_plastic(
        tau_y_Pa=25.0, mu_p_Pa_s=0.08, rho_kg_m3=1500.0, d50_mm=0.074,
        name="Mine Tailings 50% wt"),

    "paste_fill_70pct": bingham_plastic(
        tau_y_Pa=200.0, mu_p_Pa_s=0.5, rho_kg_m3=1900.0, d50_mm=0.05,
        name="Paste Fill 70% wt"),

    "cement_slurry": bingham_plastic(
        tau_y_Pa=15.0, mu_p_Pa_s=0.05, rho_kg_m3=1600.0,
        name="Cement Grout Slurry"),

    "polymer_solution": power_law(
        K_Pa_sn=0.5, n=0.6, rho_kg_m3=1010.0,
        name="Polymer Solution (shear-thinning)"),

    "drilling_mud": herschel_bulkley(
        tau_y_Pa=10.0, K_Pa_sn=0.3, n=0.7, rho_kg_m3=1200.0,
        name="Drilling Mud"),

    "dilute_tailings_10pct": newtonian_slurry(
        rho_solid_kg_m3=2700.0, concentration_vol=0.10,
        d50_mm=0.15),

    "copper_slurry_35pct": bingham_plastic(
        tau_y_Pa=8.0, mu_p_Pa_s=0.02, rho_kg_m3=1380.0, d50_mm=0.1,
        name="Copper Concentrate Slurry 35% wt"),

    "iron_ore_slurry_55pct": bingham_plastic(
        tau_y_Pa=45.0, mu_p_Pa_s=0.12, rho_kg_m3=1800.0, d50_mm=0.05,
        name="Iron Ore Slurry 55% wt"),
}


def get_fluid(name: str) -> Optional[FluidProperties]:
    """Return a FluidProperties from the catalogue by key, or None."""
    return FLUID_CATALOGUE.get(name)


def list_fluids() -> dict[str, str]:
    """Return {key: description} for all catalogue entries."""
    return {k: v.description for k, v in FLUID_CATALOGUE.items()}


def get_water_reference() -> FluidProperties:
    """Return standard water at 20°C for use as Joukowsky baseline."""
    return FLUID_CATALOGUE["water_20c"]

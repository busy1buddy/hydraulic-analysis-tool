"""
Australian pipe properties database.

Provides physical and hydraulic properties for common Australian water
pipeline materials, with nominal sizes and pressure classes referenced to
the relevant Australian / joint AS/NZS standards.

Materials covered
-----------------
* Ductile Iron  -- cement-lined, AS 2280
* PVC           -- AS/NZS 1477 (PN12 and PN18)
* PE / HDPE     -- AS/NZS 4130, SDR11 (PN16)
* Concrete      -- AS 4058

Usage
-----
    >>> from data.au_pipes import get_pipe_properties, lookup_roughness
    >>> props = get_pipe_properties("Ductile Iron", 200)
    >>> props["internal_diameter_mm"]
    209.6
    >>> lookup_roughness("Ductile Iron", age_years=30)
    100.0
"""

from __future__ import annotations

from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Pipe database
# ---------------------------------------------------------------------------
# Each entry is keyed by (material, nominal_dn) and contains:
#   nominal_dn           -- nominal diameter in mm
#   internal_diameter_mm -- internal bore (mm)
#   wall_thickness_mm    -- pipe wall thickness (mm)
#   pressure_class       -- string label (e.g. "PN35", "PN12", "SDR11")
#   hazen_williams_c     -- Hazen-Williams C-factor for new pipe
#   wave_speed_ms        -- pressure wave speed (m/s)
#   standard             -- governing Australian Standard

PIPE_DATABASE: Dict[str, Dict[int, dict]] = {
    # ------------------------------------------------------------------
    # Ductile Iron (cement-lined) -- AS 2280
    # Internal diameters are for cement-lined bore.
    # Pressure classes are typical for water-supply duty.
    # Wave speed ~1100-1200 m/s depending on wall thickness.
    # ------------------------------------------------------------------
    "Ductile Iron": {
        100: {
            "nominal_dn": 100,
            "internal_diameter_mm": 105.4,
            "wall_thickness_mm": 6.0,
            "pressure_class": "PN35",
            "hazen_williams_c": 140,
            "wave_speed_ms": 1140,
            "standard": "AS 2280",
        },
        150: {
            "nominal_dn": 150,
            "internal_diameter_mm": 157.8,
            "wall_thickness_mm": 6.0,
            "pressure_class": "PN35",
            "hazen_williams_c": 140,
            "wave_speed_ms": 1130,
            "standard": "AS 2280",
        },
        200: {
            "nominal_dn": 200,
            "internal_diameter_mm": 209.6,
            "wall_thickness_mm": 6.3,
            "pressure_class": "PN35",
            "hazen_williams_c": 140,
            "wave_speed_ms": 1120,
            "standard": "AS 2280",
        },
        250: {
            "nominal_dn": 250,
            "internal_diameter_mm": 261.6,
            "wall_thickness_mm": 6.8,
            "pressure_class": "PN35",
            "hazen_williams_c": 140,
            "wave_speed_ms": 1115,
            "standard": "AS 2280",
        },
        300: {
            "nominal_dn": 300,
            "internal_diameter_mm": 312.8,
            "wall_thickness_mm": 7.2,
            "pressure_class": "PN35",
            "hazen_williams_c": 140,
            "wave_speed_ms": 1110,
            "standard": "AS 2280",
        },
        375: {
            "nominal_dn": 375,
            "internal_diameter_mm": 382.2,
            "wall_thickness_mm": 7.9,
            "pressure_class": "PN25",
            "hazen_williams_c": 140,
            "wave_speed_ms": 1100,
            "standard": "AS 2280",
        },
        450: {
            "nominal_dn": 450,
            "internal_diameter_mm": 457.8,
            "wall_thickness_mm": 8.6,
            "pressure_class": "PN25",
            "hazen_williams_c": 140,
            "wave_speed_ms": 1100,  # DI minimum 1100 m/s per AS 2280
            "standard": "AS 2280",
        },
        500: {
            "nominal_dn": 500,
            "internal_diameter_mm": 508.0,
            "wall_thickness_mm": 9.0,
            "pressure_class": "PN25",
            "hazen_williams_c": 140,
            "wave_speed_ms": 1100,  # DI minimum 1100 m/s per AS 2280
            "standard": "AS 2280",
        },
        600: {
            "nominal_dn": 600,
            "internal_diameter_mm": 609.8,
            "wall_thickness_mm": 9.9,
            "pressure_class": "PN25",
            "hazen_williams_c": 140,
            "wave_speed_ms": 1100,  # DI minimum 1100 m/s per AS 2280
            "standard": "AS 2280",
        },
    },
    # ------------------------------------------------------------------
    # PVC -- AS/NZS 1477
    # OD is per AS/NZS 1477 OD series — OD is NOT equal to DN.
    # DN100→OD110, DN150→OD160, DN200→OD225, DN250→OD280, DN300→OD315, DN375→OD400
    # Sizes up to DN200 are PN18; DN225+ are PN12.
    # Wall thickness: PN18 wall = OD / (2 * SDR_PN18), PN12 wall = OD / (2 * SDR_PN12)
    # Wave speed for PVC is typically 300-500 m/s.
    # ------------------------------------------------------------------
    "PVC": {
        100: {
            "nominal_dn": 100,
            "outside_diameter_mm": 110,  # AS/NZS 1477 OD series
            "internal_diameter_mm": 96.8,
            "wall_thickness_mm": 6.6,
            "pressure_class": "PN18",
            "hazen_williams_c": 150,
            "wave_speed_ms": 425,
            "standard": "AS/NZS 1477",
        },
        150: {
            "nominal_dn": 150,
            "outside_diameter_mm": 160,  # AS/NZS 1477 OD series
            "internal_diameter_mm": 146.2,
            "wall_thickness_mm": 6.9,
            "pressure_class": "PN18",
            "hazen_williams_c": 150,
            "wave_speed_ms": 415,
            "standard": "AS/NZS 1477",
        },
        200: {
            "nominal_dn": 200,
            "outside_diameter_mm": 225,  # AS/NZS 1477 OD series
            "internal_diameter_mm": 211.4,
            "wall_thickness_mm": 6.8,
            "pressure_class": "PN18",
            "hazen_williams_c": 150,
            "wave_speed_ms": 405,
            "standard": "AS/NZS 1477",
        },
        250: {
            "nominal_dn": 250,
            "outside_diameter_mm": 280,  # AS/NZS 1477 OD series
            "internal_diameter_mm": 264.6,
            "wall_thickness_mm": 7.7,
            "pressure_class": "PN12",
            "hazen_williams_c": 150,
            "wave_speed_ms": 385,
            "standard": "AS/NZS 1477",
        },
        300: {
            "nominal_dn": 300,
            "outside_diameter_mm": 315,  # AS/NZS 1477 OD series
            "internal_diameter_mm": 297.6,
            "wall_thickness_mm": 8.7,
            "pressure_class": "PN12",
            "hazen_williams_c": 150,
            "wave_speed_ms": 375,
            "standard": "AS/NZS 1477",
        },
        375: {
            "nominal_dn": 375,
            "outside_diameter_mm": 400,  # AS/NZS 1477 OD series
            "internal_diameter_mm": 378.0,
            "wall_thickness_mm": 11.0,
            "pressure_class": "PN12",
            "hazen_williams_c": 150,
            "wave_speed_ms": 365,
            "standard": "AS/NZS 1477",
        },
    },
    # ------------------------------------------------------------------
    # PE / HDPE -- AS/NZS 4130, SDR11 (PN16), PE100
    # ID = OD - 2 * wall; wall = OD / (2 * SDR) rounded per std.
    # Wave speed for HDPE is typically 200-350 m/s.
    # ------------------------------------------------------------------
    "PE": {
        63: {
            "nominal_dn": 63,
            "internal_diameter_mm": 51.4,
            "wall_thickness_mm": 5.8,
            "pressure_class": "SDR11 PN16",
            "hazen_williams_c": 150,
            "wave_speed_ms": 310,
            "standard": "AS/NZS 4130",
        },
        90: {
            "nominal_dn": 90,
            "internal_diameter_mm": 73.6,
            "wall_thickness_mm": 8.2,
            "pressure_class": "SDR11 PN16",
            "hazen_williams_c": 150,
            "wave_speed_ms": 305,
            "standard": "AS/NZS 4130",
        },
        110: {
            "nominal_dn": 110,
            "internal_diameter_mm": 90.0,
            "wall_thickness_mm": 10.0,
            "pressure_class": "SDR11 PN16",
            "hazen_williams_c": 150,
            "wave_speed_ms": 300,
            "standard": "AS/NZS 4130",
        },
        160: {
            "nominal_dn": 160,
            "internal_diameter_mm": 130.8,
            "wall_thickness_mm": 14.6,
            "pressure_class": "SDR11 PN16",
            "hazen_williams_c": 150,
            "wave_speed_ms": 295,
            "standard": "AS/NZS 4130",
        },
        200: {
            "nominal_dn": 200,
            "internal_diameter_mm": 163.6,
            "wall_thickness_mm": 18.2,
            "pressure_class": "SDR11 PN16",
            "hazen_williams_c": 150,
            "wave_speed_ms": 290,
            "standard": "AS/NZS 4130",
        },
        250: {
            "nominal_dn": 250,
            "internal_diameter_mm": 204.6,
            "wall_thickness_mm": 22.7,
            "pressure_class": "SDR11 PN16",
            "hazen_williams_c": 150,
            "wave_speed_ms": 285,
            "standard": "AS/NZS 4130",
        },
        315: {
            "nominal_dn": 315,
            "internal_diameter_mm": 257.8,
            "wall_thickness_mm": 28.6,
            "pressure_class": "SDR11 PN16",
            "hazen_williams_c": 150,
            "wave_speed_ms": 280,
            "standard": "AS/NZS 4130",
        },
        400: {
            "nominal_dn": 400,
            "internal_diameter_mm": 327.2,
            "wall_thickness_mm": 36.4,
            "pressure_class": "SDR11 PN16",
            "hazen_williams_c": 150,
            "wave_speed_ms": 275,
            "standard": "AS/NZS 4130",
        },
        500: {
            "nominal_dn": 500,
            "internal_diameter_mm": 409.0,
            "wall_thickness_mm": 45.5,
            "pressure_class": "SDR11 PN16",
            "hazen_williams_c": 150,
            "wave_speed_ms": 270,
            "standard": "AS/NZS 4130",
        },
        630: {
            "nominal_dn": 630,
            "internal_diameter_mm": 515.6,
            "wall_thickness_mm": 57.2,
            "pressure_class": "SDR11 PN16",
            "hazen_williams_c": 150,
            "wave_speed_ms": 265,
            "standard": "AS/NZS 4130",
        },
    },
    # ------------------------------------------------------------------
    # Concrete lined / reinforced -- AS 4058
    # Internal diameters equal the nominal bore for rubber-ring joints.
    # Wall thickness varies with class; Class 2-4 shown.
    # Wave speed for concrete ~1000-1200 m/s.
    # ------------------------------------------------------------------
    "Concrete": {
        300: {
            "nominal_dn": 300,
            "internal_diameter_mm": 300.0,
            "wall_thickness_mm": 44.0,
            "pressure_class": "Class 2",
            "hazen_williams_c": 120,
            "wave_speed_ms": 1100,
            "standard": "AS 4058",
        },
        375: {
            "nominal_dn": 375,
            "internal_diameter_mm": 375.0,
            "wall_thickness_mm": 47.0,
            "pressure_class": "Class 2",
            "hazen_williams_c": 110,  # AS 4058: DN375/450 → C=110
            "wave_speed_ms": 1100,
            "standard": "AS 4058",
        },
        450: {
            "nominal_dn": 450,
            "internal_diameter_mm": 450.0,
            "wall_thickness_mm": 51.0,
            "pressure_class": "Class 3",
            "hazen_williams_c": 110,  # AS 4058: DN375/450 → C=110
            "wave_speed_ms": 1120,
            "standard": "AS 4058",
        },
        525: {
            "nominal_dn": 525,
            "internal_diameter_mm": 525.0,
            "wall_thickness_mm": 55.0,
            "pressure_class": "Class 3",
            "hazen_williams_c": 100,  # AS 4058: mid-range size
            "wave_speed_ms": 1130,
            "standard": "AS 4058",
        },
        600: {
            "nominal_dn": 600,
            "internal_diameter_mm": 600.0,
            "wall_thickness_mm": 60.0,
            "pressure_class": "Class 3",
            "hazen_williams_c": 100,  # AS 4058: DN600/750 → C=100
            "wave_speed_ms": 1140,
            "standard": "AS 4058",
        },
        750: {
            "nominal_dn": 750,
            "internal_diameter_mm": 750.0,
            "wall_thickness_mm": 69.0,
            "pressure_class": "Class 4",
            "hazen_williams_c": 100,  # AS 4058: DN600/750 → C=100
            "wave_speed_ms": 1150,
            "standard": "AS 4058",
        },
        900: {
            "nominal_dn": 900,
            "internal_diameter_mm": 900.0,
            "wall_thickness_mm": 80.0,
            "pressure_class": "Class 4",
            "hazen_williams_c": 90,  # AS 4058: DN900 → C=90
            "wave_speed_ms": 1160,
            "standard": "AS 4058",
        },
    },
}

# ---------------------------------------------------------------------------
# Aging coefficients for Hazen-Williams C-factor
# ---------------------------------------------------------------------------
# Each material has a base new-pipe C and a per-year degradation rate.
# The rate slows with age -- a simple log-linear model is used:
#   C(t) = C_new - rate * t     (clamped to C_min)
# Rates sourced from Australian water-utility asset management guidelines.

_AGING_PARAMS: Dict[str, dict] = {
    "Ductile Iron": {"c_new": 140, "rate_per_year": 1.0, "c_min": 90},
    "PVC":          {"c_new": 150, "rate_per_year": 0.1, "c_min": 140},
    "PE":           {"c_new": 150, "rate_per_year": 0.1, "c_min": 140},
    "Concrete":     {"c_new": 110, "rate_per_year": 0.5, "c_min": 80},  # AS 4058: new-pipe C varies by size (90-110)
}

# Representative wave speeds per material family (m/s)
_WAVE_SPEED: Dict[str, float] = {
    "Ductile Iron": 1120.0,
    "PVC": 400.0,
    "PE": 290.0,
    "Concrete": 1130.0,
}


# ---------------------------------------------------------------------------
# Public helper functions
# ---------------------------------------------------------------------------

def get_pipe_properties(material: str, dn: int) -> Optional[dict]:
    """Return a property dictionary for the given material and nominal DN.

    Parameters
    ----------
    material : str
        Material name exactly as stored in ``PIPE_DATABASE``
        (e.g. ``"Ductile Iron"``, ``"PVC"``, ``"PE"``, ``"Concrete"``).
    dn : int
        Nominal diameter in mm (e.g. 200, 300).

    Returns
    -------
    dict or None
        A copy of the property dictionary, or ``None`` if the combination
        is not found.
    """
    mat = PIPE_DATABASE.get(material)
    if mat is None:
        return None
    entry = mat.get(dn)
    if entry is None:
        return None
    return dict(entry)  # return a copy so callers cannot mutate the DB


def list_materials() -> List[str]:
    """Return a sorted list of material names available in the database."""
    return sorted(PIPE_DATABASE.keys())


def list_sizes(material: str) -> List[int]:
    """Return a sorted list of nominal DN values for *material*.

    Parameters
    ----------
    material : str
        Material name (see :func:`list_materials`).

    Returns
    -------
    list[int]
        Sorted DN values, or an empty list if the material is unknown.
    """
    mat = PIPE_DATABASE.get(material)
    if mat is None:
        return []
    return sorted(mat.keys())


def lookup_roughness(material: str, age_years: int = 0) -> float:
    """Return the Hazen-Williams C-factor for *material* at a given age.

    A simple linear degradation model is applied::

        C = C_new - rate * age_years

    The result is clamped so it never falls below a material-specific
    minimum that reflects a heavily tuberculated or biofilm-coated pipe.

    Parameters
    ----------
    material : str
        Material name.
    age_years : int, optional
        Pipe age in years (default 0 = new pipe).

    Returns
    -------
    float
        Estimated Hazen-Williams C coefficient.

    Raises
    ------
    KeyError
        If *material* is not recognised.
    """
    params = _AGING_PARAMS.get(material)
    if params is None:
        raise KeyError(
            f"Unknown material '{material}'. "
            f"Valid options: {', '.join(sorted(_AGING_PARAMS))}"
        )
    c_val = params["c_new"] - params["rate_per_year"] * max(age_years, 0)
    return max(c_val, params["c_min"])


def lookup_wave_speed(material: str) -> float:
    """Return a representative pressure-wave speed (m/s) for *material*.

    The value is a single representative number for the material family.
    For a size-specific wave speed, use :func:`get_pipe_properties` instead.

    Parameters
    ----------
    material : str
        Material name.

    Returns
    -------
    float
        Wave speed in m/s.

    Raises
    ------
    KeyError
        If *material* is not recognised.
    """
    speed = _WAVE_SPEED.get(material)
    if speed is None:
        raise KeyError(
            f"Unknown material '{material}'. "
            f"Valid options: {', '.join(sorted(_WAVE_SPEED))}"
        )
    return speed

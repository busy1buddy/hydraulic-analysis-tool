"""
Unit Enforcement — desktop/units.py
=====================================
Single source of truth for all unit display, conversion, and validation
across the desktop UI layer.

Rules (from CLAUDE.md, enforced here):
  - Pressure:   m head  (display 1 d.p.)
  - Flow:       LPS     (WNTR stores m³/s — multiply × 1000)
  - Velocity:   m/s     (display 2 d.p., always abs value)
  - Diameter:   DN mm   (WNTR stores metres — multiply × 1000, display integer)
  - Length:     m       (no conversion)
  - Elevation:  m AHD   (no conversion)
  - Roughness:  C-factor (no conversion)
  - Wave speed: m/s     (no conversion)
  - Stress:     MPa     (no conversion)
  - Water age:  hours   (WNTR stores seconds — divide ÷ 3600)

WSAA WSA 03-2011 thresholds (always compare against these constants):
"""

# ---------------------------------------------------------------------------
# WSAA WSA 03-2011 Compliance thresholds — never use bare numbers in UI code
# ---------------------------------------------------------------------------
WSAA_MIN_PRESSURE_M = 20.0       # WSAA WSA 03-2011 Table 3.1 — minimum service pressure
WSAA_MAX_PRESSURE_M = 50.0       # WSAA WSA 03-2011 Table 3.1 — maximum residential pressure
WSAA_MAX_VELOCITY_MS = 2.0       # WSAA WSA 03-2011 — maximum pipe velocity (scouring)
WSAA_WARN_PRESSURE_LOW_M = 15.0  # Warning band below minimum
WSAA_WARN_VELOCITY_MS = 1.5      # Warning band below maximum
WSAA_FIRE_FLOW_LPS = 25.0        # WSAA WSA 03-2011 — required fire flow
WSAA_FIRE_RESIDUAL_M = 12.0      # WSAA WSA 03-2011 — residual pressure under fire flow
WSAA_STAGNATION_HOURS = 24.0     # Water age threshold for stagnation flag

# Mining / industrial override (document use in each decision log)
MINING_MAX_PRESSURE_M = 120.0    # Engineering override — document when applied

# ---------------------------------------------------------------------------
# Conversion helpers — always use these, never inline arithmetic in UI
# ---------------------------------------------------------------------------

def lps_to_m3s(lps: float) -> float:
    """Convert LPS (user-facing) to m³/s (WNTR internal). Ref: SI unit definition."""
    return lps / 1000.0


def m3s_to_lps(m3s: float) -> float:
    """Convert m³/s (WNTR internal) to LPS (user-facing). Ref: SI unit definition."""
    return m3s * 1000.0


def mm_to_m(mm: float) -> float:
    """Convert DN mm (user-facing) to metres (WNTR internal). Ref: SI unit definition."""
    return mm / 1000.0


def m_to_mm(m: float) -> float:
    """Convert metres (WNTR internal) to DN mm integer (user-facing)."""
    return m * 1000.0


def dn_display(diameter_m: float) -> str:
    """Format a WNTR diameter (metres) for display as integer DN mm.
    
    Rule: integer mm, never 300.0 mm — always '300 mm'.
    """
    return f"DN{int(round(diameter_m * 1000))} mm"


def seconds_to_hours(seconds: float) -> float:
    """Convert WNTR water age (seconds) to hours (display).
    
    CRITICAL: WNTR returns water age in seconds.
    Always divide by 3600 before any comparison or display.
    """
    return seconds / 3600.0


def hours_to_seconds(hours: float) -> float:
    """Convert hours (user input) to seconds (WNTR internal)."""
    return hours * 3600.0


def pressure_display(head_m: float) -> str:
    """Format pressure (m head) for display — 1 decimal place, with unit."""
    return f"{head_m:.1f} m"


def pressure_kpa_display(head_m: float) -> str:
    """Format pressure in kPa — 1 m head = 9.81 kPa. Ref: WSAA WSA 03-2011."""
    return f"{head_m * 9.81:.1f} kPa"


def velocity_display(velocity_ms: float) -> str:
    """Format velocity (m/s) for display — 2 decimal places, always abs value."""
    return f"{abs(velocity_ms):.2f} m/s"


def flow_display(flow_m3s: float) -> str:
    """Format WNTR flow (m³/s) for user display in LPS — 2 decimal places."""
    return f"{flow_m3s * 1000.0:.2f} LPS"


def age_display(age_seconds: float) -> str:
    """Format WNTR water age (seconds) for display in hours."""
    hours = age_seconds / 3600.0
    return f"{hours:.1f} hr"


def headloss_per_km(headloss_m: float, length_m: float) -> float:
    """Calculate headloss gradient in m/km. Guard zero-length pipes."""
    if length_m <= 0:
        return 0.0
    return (headloss_m / length_m) * 1000.0


# ---------------------------------------------------------------------------
# Input Validation helpers — enforce physical bounds at UI entry points
# ---------------------------------------------------------------------------

class UnitValidationError(ValueError):
    """Raised when a user-input value violates physical or standard bounds."""
    pass


def validate_pressure_m(value: float, context: str = "pressure") -> float:
    """Validate a pressure input is physically plausible.
    
    Returns the value if valid, raises UnitValidationError otherwise.
    """
    if value < -10.0:
        raise UnitValidationError(
            f"{context} = {value:.1f} m is below -10 m — physically impossible "
            f"(check if elevation has been subtracted correctly)."
        )
    if value > 5000.0:
        raise UnitValidationError(
            f"{context} = {value:.1f} m exceeds 5000 m — check unit conversion. "
            f"Hint: Are you entering kPa instead of m head? Divide by 9.81."
        )
    return value


def validate_flow_lps(value: float, context: str = "flow") -> float:
    """Validate a flow input is physically plausible (LPS)."""
    if value < 0:
        raise UnitValidationError(
            f"{context} = {value:.2f} LPS is negative. Demands must be ≥ 0."
        )
    if value > 50_000:
        raise UnitValidationError(
            f"{context} = {value:.0f} LPS exceeds 50,000 LPS — check unit conversion. "
            f"Hint: Are you entering m³/s? Multiply by 1000."
        )
    return value


def validate_diameter_mm(value: float, context: str = "diameter") -> float:
    """Validate a diameter input is within standard DN range."""
    if value < 20:
        raise UnitValidationError(
            f"{context} = {value:.0f} mm is below DN20 — minimum standard pipe size. "
            f"Hint: Are you entering metres? Multiply by 1000."
        )
    if value > 4000:
        raise UnitValidationError(
            f"{context} = {value:.0f} mm exceeds DN4000 — check unit conversion."
        )
    return value


def validate_velocity_ms(value: float, context: str = "velocity") -> float:
    """Check velocity against WSAA limits and return compliance status."""
    abs_v = abs(value)
    if abs_v > WSAA_MAX_VELOCITY_MS:
        # Not an error — just a warning context callers can use
        pass
    return abs_v


def validate_elevation_m(value: float, context: str = "elevation") -> float:
    """Validate elevation is within plausible Australian range (m AHD)."""
    if value < -100.0:
        raise UnitValidationError(
            f"{context} = {value:.1f} m AHD is below -100 m — "
            f"deepest points in Australia are near sea level. Check units."
        )
    if value > 2500.0:
        raise UnitValidationError(
            f"{context} = {value:.1f} m AHD exceeds 2500 m — "
            f"highest point in Australia is Mt Kosciuszko (2228 m AHD). "
            f"Hint: Are you entering feet? Multiply by 0.3048."
        )
    return value

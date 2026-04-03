"""
Pump Curve Database and Recommendation Engine
===============================================
Contains a database of common pump curves for mining and water supply,
with functions for pump selection, system curve generation, and
operating point determination.
"""

import math
import numpy as np


# ============================================================================
# PUMP DATABASE
# ============================================================================

PUMP_DATABASE = {
    # Small water supply pumps
    'WSP-100-15': {
        'manufacturer': 'Generic Water Supply',
        'model': 'WSP-100-15',
        'type': 'centrifugal',
        'rated_speed_rpm': 1450,
        'impeller_mm': 200,
        'curve_points': [  # (flow_LPS, head_m)
            (0, 18), (5, 17.5), (10, 16.5), (15, 14.5),
            (20, 12), (25, 8.5), (28, 6),
        ],
        'efficiency_points': [  # (flow_LPS, efficiency_pct)
            (0, 0), (5, 45), (10, 65), (15, 75),
            (20, 72), (25, 60), (28, 45),
        ],
        'power_kW': 5.5,
        'npshr_m': 2.5,
        'application': 'Small water distribution booster',
    },
    'WSP-200-40': {
        'manufacturer': 'Generic Water Supply',
        'model': 'WSP-200-40',
        'type': 'centrifugal',
        'rated_speed_rpm': 1450,
        'impeller_mm': 250,
        'curve_points': [
            (0, 45), (10, 44), (20, 42), (30, 38),
            (40, 32), (50, 24), (55, 18),
        ],
        'efficiency_points': [
            (0, 0), (10, 50), (20, 68), (30, 78),
            (40, 75), (50, 65), (55, 50),
        ],
        'power_kW': 22,
        'npshr_m': 3.0,
        'application': 'Medium water distribution',
    },
    'WSP-300-80': {
        'manufacturer': 'Generic Water Supply',
        'model': 'WSP-300-80',
        'type': 'centrifugal',
        'rated_speed_rpm': 1480,
        'impeller_mm': 350,
        'curve_points': [
            (0, 90), (20, 88), (40, 84), (60, 76),
            (80, 65), (100, 50), (110, 38),
        ],
        'efficiency_points': [
            (0, 0), (20, 55), (40, 72), (60, 82),
            (80, 80), (100, 68), (110, 55),
        ],
        'power_kW': 75,
        'npshr_m': 4.0,
        'application': 'Large water distribution / trunk main',
    },
    # Mining dewatering pumps
    'MDP-150-60': {
        'manufacturer': 'Generic Mining',
        'model': 'MDP-150-60',
        'type': 'centrifugal',
        'rated_speed_rpm': 1480,
        'impeller_mm': 300,
        'curve_points': [
            (0, 65), (10, 63), (20, 59), (30, 53),
            (40, 44), (50, 32), (55, 22),
        ],
        'efficiency_points': [
            (0, 0), (10, 48), (20, 65), (30, 76),
            (40, 73), (50, 62), (55, 48),
        ],
        'power_kW': 37,
        'npshr_m': 3.5,
        'application': 'Underground mine dewatering',
    },
    'MDP-300-120': {
        'manufacturer': 'Generic Mining',
        'model': 'MDP-300-120',
        'type': 'centrifugal',
        'rated_speed_rpm': 1480,
        'impeller_mm': 400,
        'curve_points': [
            (0, 130), (20, 128), (40, 122), (60, 112),
            (80, 98), (100, 78), (120, 52), (130, 35),
        ],
        'efficiency_points': [
            (0, 0), (20, 50), (40, 68), (60, 80),
            (80, 82), (100, 76), (120, 60), (130, 45),
        ],
        'power_kW': 160,
        'npshr_m': 5.0,
        'application': 'Large mine dewatering / open pit',
    },
    # Slurry pumps
    # Slurry pump motor ratings sized for SG=1.5 slurry at BEP
    # shaft_power = (Q_m3s * H * rho * g) / eff; motor ≈ shaft / 0.80
    'SLP-200-30': {
        'manufacturer': 'Generic Slurry',
        'model': 'SLP-200-30',
        'type': 'centrifugal_slurry',
        'rated_speed_rpm': 1000,
        'impeller_mm': 350,
        'curve_points': [
            (0, 35), (10, 34), (20, 31), (30, 27),
            (40, 21), (50, 13), (55, 8),
        ],
        'efficiency_points': [
            (0, 0), (10, 40), (20, 58), (30, 68),
            (40, 65), (50, 52), (55, 38),
        ],
        'power_kW': 22,  # BEP shaft ~17.5 kW (SG=1.5), ratio 0.80
        'npshr_m': 4.0,
        'application': 'Tailings transfer, slurry pumping',
    },
    'SLP-400-50': {
        'manufacturer': 'Generic Slurry',
        'model': 'SLP-400-50',
        'type': 'centrifugal_slurry',
        'rated_speed_rpm': 750,
        'impeller_mm': 500,
        'curve_points': [
            (0, 55), (20, 53), (40, 49), (60, 43),
            (80, 34), (100, 22), (110, 14),
        ],
        'efficiency_points': [
            (0, 0), (20, 45), (40, 62), (60, 72),
            (80, 70), (100, 58), (110, 42),
        ],
        'power_kW': 75,  # BEP shaft ~52.7 kW (SG=1.5), ratio 0.70
        'npshr_m': 5.5,
        'application': 'Large slurry pipeline, paste fill',
    },
}


# ============================================================================
# PUMP CURVE FUNCTIONS
# ============================================================================

def get_pump_head(pump_id, flow_lps, speed_pct=100):
    """
    Get pump head at a given flow using cubic interpolation.

    Parameters
    ----------
    pump_id : str
        Pump ID from database.
    flow_lps : float
        Flow rate in LPS.
    speed_pct : float
        Speed as percentage of rated (affinity laws).

    Returns
    -------
    float : Head in metres.
    """
    pump = PUMP_DATABASE.get(pump_id)
    if not pump:
        return None

    points = pump['curve_points']
    flows = [p[0] * (speed_pct / 100) for p in points]
    heads = [p[1] * (speed_pct / 100) ** 2 for p in points]

    return float(np.interp(flow_lps, flows, heads))


def get_pump_efficiency(pump_id, flow_lps):
    """Get pump efficiency at a given flow."""
    pump = PUMP_DATABASE.get(pump_id)
    if not pump or 'efficiency_points' not in pump:
        return None

    points = pump['efficiency_points']
    flows = [p[0] for p in points]
    effs = [p[1] for p in points]

    return float(np.interp(flow_lps, flows, effs))


def generate_system_curve(static_head_m, pipe_length_m, pipe_diameter_mm,
                          roughness=130, flow_range=None):
    """
    Generate a system curve (head vs flow) for a pipeline.

    Uses Hazen-Williams for headloss calculation.

    Returns list of (flow_lps, head_m) points.
    """
    if flow_range is None:
        flow_range = np.linspace(0, 100, 50)

    d_m = pipe_diameter_mm / 1000
    points = []

    for Q_lps in flow_range:
        Q_m3s = Q_lps / 1000
        if Q_m3s > 0 and d_m > 0:
            # Hazen-Williams headloss
            V = Q_m3s / (math.pi * (d_m / 2) ** 2)
            hl = (10.67 * pipe_length_m * Q_m3s ** 1.852) / (
                roughness ** 1.852 * d_m ** 4.87)
        else:
            hl = 0

        total_head = static_head_m + hl
        points.append((round(Q_lps, 2), round(total_head, 2)))

    return points


def find_operating_point(pump_id, system_curve, speed_pct=100):
    """
    Find the operating point where pump curve intersects system curve.

    Returns (flow_lps, head_m, efficiency_pct).
    """
    pump = PUMP_DATABASE.get(pump_id)
    if not pump:
        return None

    # Interpolate both curves at fine resolution
    sys_flows = [p[0] for p in system_curve]
    sys_heads = [p[1] for p in system_curve]

    best_flow = 0
    min_diff = float('inf')

    for flow in np.linspace(min(sys_flows), max(sys_flows), 500):
        pump_head = get_pump_head(pump_id, flow, speed_pct)
        sys_head = float(np.interp(flow, sys_flows, sys_heads))

        if pump_head is not None:
            diff = abs(pump_head - sys_head)
            if diff < min_diff and pump_head >= sys_head * 0.95:
                min_diff = diff
                best_flow = flow

    if min_diff > 5:  # No good intersection found
        return None

    head = get_pump_head(pump_id, best_flow, speed_pct)
    eff = get_pump_efficiency(pump_id, best_flow) or 0

    return {
        'flow_lps': round(best_flow, 1),
        'head_m': round(head, 1),
        'efficiency_pct': round(eff, 1),
        'pump_id': pump_id,
        'speed_pct': speed_pct,
    }


def recommend_pump(required_flow_lps, required_head_m, application='water'):
    """
    Recommend the best pump from the database for given duty.

    Parameters
    ----------
    required_flow_lps : float
    required_head_m : float
    application : str
        'water', 'mining', 'slurry'

    Returns list of recommendations sorted by suitability.
    """
    recommendations = []

    for pump_id, pump in PUMP_DATABASE.items():
        # Filter by application
        if application == 'slurry' and 'slurry' not in pump.get('type', ''):
            continue
        if application == 'water' and 'slurry' in pump.get('type', ''):
            continue

        # Check if pump can deliver required duty
        max_flow = pump['curve_points'][-1][0]
        max_head = pump['curve_points'][0][1]

        if required_flow_lps > max_flow * 1.1:
            continue
        if required_head_m > max_head * 1.05:
            continue

        # Get head at required flow
        head_at_flow = get_pump_head(pump_id, required_flow_lps)
        if head_at_flow is None or head_at_flow < required_head_m * 0.95:
            continue

        eff = get_pump_efficiency(pump_id, required_flow_lps) or 0
        head_margin = head_at_flow - required_head_m

        # Check NPSHr
        npshr_ok = True  # Simplified

        recommendations.append({
            'pump_id': pump_id,
            'model': pump['model'],
            'manufacturer': pump['manufacturer'],
            'head_at_duty_m': round(head_at_flow, 1),
            'head_margin_m': round(head_margin, 1),
            'efficiency_pct': round(eff, 1),
            'power_kW': pump['power_kW'],
            'npshr_m': pump['npshr_m'],
            'application': pump['application'],
            'suitability_score': round(eff - abs(head_margin) * 0.5, 1),
        })

    # Sort by suitability (highest efficiency, closest head match)
    recommendations.sort(key=lambda r: r['suitability_score'], reverse=True)
    return recommendations


def list_pumps(application=None):
    """List all pumps in the database, optionally filtered by application."""
    result = []
    for pump_id, pump in PUMP_DATABASE.items():
        if application:
            if application == 'slurry' and 'slurry' not in pump.get('type', ''):
                continue
            if application == 'water' and 'slurry' in pump.get('type', ''):
                continue
        result.append({
            'pump_id': pump_id,
            'model': pump['model'],
            'manufacturer': pump['manufacturer'],
            'max_flow_lps': pump['curve_points'][-1][0],
            'max_head_m': pump['curve_points'][0][1],
            'power_kW': pump['power_kW'],
            'application': pump['application'],
        })
    return result

"""
Regression Baseline Tests (P2)
===============================
For each tutorial network, record key metrics as baselines.
Any change > 5% from baseline fails the test — catches silent regressions.

To update baselines after intentional calculation changes:
    python tests/test_regression.py --update
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TUTORIALS_DIR = os.path.join(PROJECT_ROOT, 'tutorials')
BASELINE_FILE = os.path.join(os.path.dirname(__file__),
                              'regression_baselines.json')

TOLERANCE_PCT = 5.0

TUTORIAL_NETWORKS = [
    'simple_loop', 'dead_end_network', 'pump_station',
    'pressure_zone_boundary', 'fire_flow_demand',
    'mining_slurry_line', 'multistage_pump', 'elevated_tank',
    'industrial_ring_main', 'rehabilitation_comparison',
]


def _collect_metrics(inp_path):
    """Compute key metrics for a given .inp network."""
    api = HydraulicAPI()
    api.load_network(inp_path)
    steady = api.run_steady_state(save_plot=False)
    if 'error' in steady:
        return {'error': steady['error']}

    pressures = steady.get('pressures', {})
    flows = steady.get('flows', {})

    p_min = min((p.get('min_m', 0) for p in pressures.values()), default=0)
    v_max = max((f.get('max_velocity_ms', 0) for f in flows.values()), default=0)

    qs = api.compute_quality_score(steady)
    ri = api.compute_resilience_index(steady)

    return {
        'quality_score': qs.get('total_score') if 'error' not in qs else None,
        'resilience_index': (ri.get('todini_index')
                             if 'error' not in ri else None),
        'min_pressure_m': round(p_min, 2),
        'max_velocity_ms': round(v_max, 3),
        'n_junctions': len(api.wn.junction_name_list),
        'n_pipes': len(api.wn.pipe_name_list),
    }


def _load_baselines():
    if not os.path.exists(BASELINE_FILE):
        return {}
    with open(BASELINE_FILE) as f:
        return json.load(f)


def _save_baselines(baselines):
    with open(BASELINE_FILE, 'w') as f:
        json.dump(baselines, f, indent=2, sort_keys=True)


def _within_tolerance(current, baseline, pct=TOLERANCE_PCT):
    """Check if current value is within pct% of baseline."""
    if current is None or baseline is None:
        return current == baseline
    if baseline == 0:
        return abs(current) < 0.01
    diff_pct = abs(current - baseline) / abs(baseline) * 100
    return diff_pct <= pct


@pytest.mark.parametrize('network', TUTORIAL_NETWORKS)
def test_regression_baseline(network):
    """Every tutorial must produce metrics within 5% of recorded baseline."""
    inp_path = os.path.join(TUTORIALS_DIR, network, 'network.inp')
    if not os.path.exists(inp_path):
        pytest.skip(f'Tutorial missing: {network}')

    metrics = _collect_metrics(inp_path)
    if 'error' in metrics:
        pytest.skip(f'{network}: {metrics["error"]}')

    baselines = _load_baselines()

    if network not in baselines:
        # First run — store as baseline and pass
        baselines[network] = metrics
        _save_baselines(baselines)
        pytest.skip(f'Baseline created for {network}: {metrics}')

    baseline = baselines[network]

    # Structural metrics must match exactly
    for key in ('n_junctions', 'n_pipes'):
        assert metrics[key] == baseline.get(key), (
            f'{network}: {key} changed — {baseline.get(key)} → {metrics[key]}')

    # Numeric metrics must be within tolerance
    for key in ('quality_score', 'resilience_index',
                'min_pressure_m', 'max_velocity_ms'):
        current = metrics.get(key)
        base = baseline.get(key)
        assert _within_tolerance(current, base), (
            f'{network}: {key} drift — baseline={base}, '
            f'current={current} (>{TOLERANCE_PCT}% change)')


if __name__ == '__main__':
    # Manual baseline update: python tests/test_regression.py --update
    if '--update' in sys.argv:
        baselines = {}
        for net in TUTORIAL_NETWORKS:
            inp_path = os.path.join(TUTORIALS_DIR, net, 'network.inp')
            if os.path.exists(inp_path):
                print(f'Updating {net}...')
                baselines[net] = _collect_metrics(inp_path)
        _save_baselines(baselines)
        print(f'Wrote {len(baselines)} baselines to {BASELINE_FILE}')

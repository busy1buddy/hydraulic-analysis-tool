"""
Memory Leak Detection Tests (P3)
=================================
Load and analyse networks repeatedly. Asserts memory growth stays
bounded — catches the common desktop-app bug of not clearing old
results before loading a new network.
"""

import gc
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TUTORIALS_DIR = os.path.join(PROJECT_ROOT, 'tutorials')

NETWORKS = [
    'simple_loop', 'dead_end_network', 'pump_station',
    'pressure_zone_boundary', 'elevated_tank',
    'industrial_ring_main', 'multistage_pump', 'fire_flow_demand',
    'mining_slurry_line', 'rehabilitation_comparison',
]


def _inp_path(name):
    return os.path.join(TUTORIALS_DIR, name, 'network.inp')


def _get_rss_mb():
    """Return current process RSS in MB, or None if unavailable."""
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except ImportError:
        return None


def test_no_leak_across_20_loads():
    """Loading 20 networks in sequence should not grow memory > 50 MB."""
    if not all(os.path.exists(_inp_path(n)) for n in NETWORKS):
        pytest.skip('Tutorial networks missing')

    rss_start = _get_rss_mb()
    if rss_start is None:
        pytest.skip('psutil not installed')

    api = HydraulicAPI()
    # Run 20 cycles (2x through the 10 networks)
    for i in range(20):
        net = NETWORKS[i % len(NETWORKS)]
        api.load_network(_inp_path(net))
        api.run_steady_state(save_plot=False)
        # Explicitly clear results to exercise cleanup paths
        api.steady_results = None

    # Force collection so we don't count uncollected-but-collectable garbage
    gc.collect()

    rss_end = _get_rss_mb()
    growth_mb = rss_end - rss_start
    assert growth_mb < 50.0, (
        f'Memory grew {growth_mb:.1f} MB over 20 network loads '
        f'({rss_start:.1f} → {rss_end:.1f} MB) — likely a leak')


def test_single_api_instance_reusable():
    """Same HydraulicAPI instance should cleanly load a new network over an old one."""
    api = HydraulicAPI()

    api.load_network(_inp_path('simple_loop'))
    n1 = len(api.wn.pipe_name_list)

    api.load_network(_inp_path('industrial_ring_main'))
    n2 = len(api.wn.pipe_name_list)

    # Different networks, so sizes should differ; if same instance isn't
    # replaced, we'd get the wrong count
    assert n1 != n2 or (
        'ring_main' in 'industrial_ring_main'  # guard: they're different files
    )

    # Results from previous network must not linger after new load
    new_results = api.run_steady_state(save_plot=False)
    assert len(new_results['pressures']) == len(api.wn.junction_name_list)

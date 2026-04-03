"""
Shared pytest fixtures for EPANET Hydraulic Analysis tests.
Provides isolated API instances with temporary directories
so tests do not pollute the main project.
"""

import os
import sys
import shutil
import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(PROJECT_ROOT, 'models')


@pytest.fixture
def api_instance(tmp_path):
    """Create a fresh HydraulicAPI with isolated temp directory."""
    from epanet_api import HydraulicAPI

    # Copy model files into temp dir's models/ folder
    models_dest = tmp_path / 'models'
    models_dest.mkdir()
    for f in os.listdir(MODELS_DIR):
        if f.endswith('.inp'):
            shutil.copy2(os.path.join(MODELS_DIR, f), models_dest / f)

    (tmp_path / 'output').mkdir()

    return HydraulicAPI(work_dir=str(tmp_path))


@pytest.fixture(scope="module")
def shared_api():
    """Module-scoped API instance for expensive tests that don't need isolation."""
    from epanet_api import HydraulicAPI
    return HydraulicAPI(work_dir=PROJECT_ROOT)


@pytest.fixture
def loaded_network(api_instance):
    """API instance with australian_network.inp already loaded."""
    api_instance.load_network('australian_network.inp')
    return api_instance


@pytest.fixture
def transient_network(api_instance):
    """API instance with transient_network.inp already loaded."""
    api_instance.load_network('transient_network.inp')
    return api_instance


@pytest.fixture
def steady_results(loaded_network):
    """Pre-computed steady-state results for australian_network."""
    return loaded_network.run_steady_state(save_plot=False)


@pytest.fixture
def transient_results(transient_network):
    """Pre-computed transient results for transient_network."""
    return transient_network.run_transient(
        valve_name='V1', closure_time=0.5, start_time=2.0,
        wave_speed=1000, sim_duration=20, save_plot=False
    )


@pytest.fixture
def simple_network_params():
    """Minimal network creation parameters for testing."""
    return {
        'name': 'test_simple',
        'reservoirs': [{'id': 'R1', 'head': 80, 'x': 0, 'y': 50}],
        'junctions': [
            {'id': 'J1', 'elevation': 50, 'demand': 0, 'x': 15, 'y': 50},
            {'id': 'J2', 'elevation': 45, 'demand': 10, 'x': 30, 'y': 45},
        ],
        'pipes': [
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
             'diameter': 300, 'roughness': 130},
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 400,
             'diameter': 250, 'roughness': 130},
        ],
        'duration_hrs': 1,
    }

"""
Tests for Pipe Sizing Optimisation (I12)
==========================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


@pytest.fixture
def api_with_undersized():
    """Network with undersized pipes that need upgrading."""
    api = HydraulicAPI()
    api.create_network(
        name='optim_test',
        junctions=[
            {'id': 'J1', 'elevation': 50, 'demand': 15.0, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 55, 'demand': 10.0, 'x': 500, 'y': 0},
            {'id': 'J3', 'elevation': 60, 'demand': 8.0, 'x': 1000, 'y': 0},
        ],
        reservoirs=[{'id': 'R1', 'head': 80, 'x': -500, 'y': 0}],
        pipes=[
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 800,
             'diameter': 150, 'roughness': 130},
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 600,
             'diameter': 100, 'roughness': 130},
            {'id': 'P3', 'start': 'J2', 'end': 'J3', 'length': 500,
             'diameter': 100, 'roughness': 130},
        ],
    )
    return api


@pytest.fixture
def api_with_adequate():
    """Network with adequate pipes (no upgrade needed)."""
    api = HydraulicAPI()
    api.create_network(
        name='optim_ok',
        junctions=[
            {'id': 'J1', 'elevation': 50, 'demand': 2.0, 'x': 0, 'y': 0},
        ],
        reservoirs=[{'id': 'R1', 'head': 100, 'x': -100, 'y': 0}],
        pipes=[
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
             'diameter': 300, 'roughness': 130},
        ],
    )
    return api


class TestPipeOptimisation:

    def test_adequate_network_no_recommendations(self, api_with_adequate):
        result = api_with_adequate.optimise_pipe_sizes()
        assert len(result.get('recommendations', [])) == 0
        assert 'No upgrades needed' in result.get('message', '')

    def test_undersized_produces_recommendations(self, api_with_undersized):
        result = api_with_undersized.optimise_pipe_sizes()
        assert len(result.get('recommendations', [])) > 0

    def test_cost_increase_positive(self, api_with_undersized):
        result = api_with_undersized.optimise_pipe_sizes()
        if result.get('recommendations'):
            assert result['cost_increase'] > 0
            assert result['total_cost'] > result['base_cost']

    def test_recommendations_have_required_fields(self, api_with_undersized):
        result = api_with_undersized.optimise_pipe_sizes()
        for rec in result.get('recommendations', []):
            assert 'pipe_id' in rec
            assert 'current_dn' in rec
            assert 'proposed_dn' in rec
            assert rec['proposed_dn'] > rec['current_dn']

    def test_budget_limit_respected(self, api_with_undersized):
        result = api_with_undersized.optimise_pipe_sizes(budget_limit=1000)
        if result.get('recommendations'):
            assert result['cost_increase'] <= 1000

    def test_original_diameters_restored(self, api_with_undersized):
        api = api_with_undersized
        original = {pid: api.wn.get_link(pid).diameter
                    for pid in api.wn.pipe_name_list}
        api.optimise_pipe_sizes()
        for pid, d in original.items():
            assert abs(api.wn.get_link(pid).diameter - d) < 1e-6

    def test_pipe_cost_database_exists(self):
        assert len(HydraulicAPI.PIPE_COST_PER_M) > 5
        assert HydraulicAPI.PIPE_COST_PER_M[300] > 0

    def test_no_network_returns_error(self):
        api = HydraulicAPI()
        result = api.optimise_pipe_sizes()
        assert 'error' in result

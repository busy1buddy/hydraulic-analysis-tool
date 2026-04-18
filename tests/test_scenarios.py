"""Tests for scenario comparison manager."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def manager(tmp_path):
    """Create a ScenarioManager with isolated temp directory."""
    import shutil
    models_dir = tmp_path / 'models'
    models_dir.mkdir()
    (tmp_path / 'output').mkdir()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_models = os.path.join(project_root, 'models')
    for f in os.listdir(src_models):
        if f.endswith('.inp'):
            shutil.copy2(os.path.join(src_models, f), models_dir / f)

    from epanet_api.scenario_manager import ScenarioManager
    return ScenarioManager(work_dir=str(tmp_path))


class TestScenarioCreation:
    def test_create_base_scenario(self, manager):
        result = manager.create_scenario(
            'base', 'australian_network.inp', description='Base case')
        assert result['name'] == 'base'
        assert result['network_file'] == 'scenario_base.inp'

    def test_create_pipe_upsize_scenario(self, manager):
        result = manager.create_scenario(
            'upsize_p6', 'australian_network.inp',
            modifications=[{'type': 'pipe_diameter', 'target': 'P6', 'value': 250}],
            description='Upsize P6 from 150mm to 250mm',
        )
        assert result['name'] == 'upsize_p6'

    def test_create_demand_growth_scenario(self, manager):
        result = manager.create_scenario(
            'growth_20pct', 'australian_network.inp',
            modifications=[{'type': 'demand_factor', 'value': 1.2}],
            description='20% demand growth',
        )
        assert result['name'] == 'growth_20pct'


class TestScenarioRun:
    def test_run_scenario(self, manager):
        manager.create_scenario('base', 'australian_network.inp')
        results = manager.run_scenario('base')
        assert 'pressures' in results
        assert 'flows' in results

    def test_run_nonexistent(self, manager):
        result = manager.run_scenario('nonexistent')
        assert 'error' in result


class TestScenarioComparison:
    def test_compare_two_scenarios(self, manager):
        manager.create_scenario('base', 'australian_network.inp',
                               description='Base case')
        manager.create_scenario('growth', 'australian_network.inp',
                               modifications=[{'type': 'demand_factor', 'value': 1.3}],
                               description='30% growth')
        manager.run_all()

        comparison = manager.compare('base', 'growth')
        assert 'pressure_diff' in comparison
        assert 'flow_diff' in comparison
        assert 'summary' in comparison
        assert len(comparison['summary']) > 0

    def test_demand_growth_lowers_pressure(self, manager):
        manager.create_scenario('base', 'australian_network.inp')
        manager.create_scenario('growth', 'australian_network.inp',
                               modifications=[{'type': 'demand_factor', 'value': 1.5}])
        manager.run_all()
        comparison = manager.compare('base', 'growth')

        # Higher demand should lower pressures (negative diff)
        has_decrease = any(v['diff_min'] < 0
                         for v in comparison['pressure_diff'].values())
        assert has_decrease

    def test_list_scenarios(self, manager):
        manager.create_scenario('a', 'australian_network.inp')
        manager.create_scenario('b', 'australian_network.inp')
        listing = manager.list_scenarios()
        assert len(listing) == 2

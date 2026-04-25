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


class TestScenarioPropertyChecks:
    """Phase-3 additions covering monotonicity, determinism, and error handling
    for the scenario manager (recommendation #4)."""

    def test_pipe_upsize_reduces_headloss_in_that_pipe(self, manager):
        """Doubling a pipe diameter must reduce its headloss (Hazen-Williams)."""
        manager.create_scenario('base', 'australian_network.inp')
        manager.create_scenario(
            'upsize',
            'australian_network.inp',
            modifications=[{'type': 'pipe_diameter', 'target': 'P6', 'value': 600}],
        )
        manager.run_all()

        base_res = manager.scenarios['base']['results']
        up_res = manager.scenarios['upsize']['results']

        base_hl = base_res.get('flows', {}).get('P6', {}).get('headloss_per_km_m', 0)
        up_hl = up_res.get('flows', {}).get('P6', {}).get('headloss_per_km_m', 0)

        # Either a real reduction, or both ~0 (network too small for measurable HL)
        if base_hl < 1e-3 and up_hl < 1e-3:
            import pytest
            pytest.skip("Headloss on P6 too small to compare at this network size")
        assert up_hl <= base_hl, (
            f"Upsize from 150 to 600 mm should reduce P6 headloss; "
            f"base={base_hl}, upsize={up_hl}"
        )

    def test_identical_scenarios_yield_identical_pressures(self, manager):
        """Determinism: two scenarios built from the same inputs must give
        the same pressures within solver tolerance."""
        manager.create_scenario('a', 'australian_network.inp')
        manager.create_scenario('b', 'australian_network.inp')
        manager.run_all()

        a_p = manager.scenarios['a']['results']['pressures']
        b_p = manager.scenarios['b']['results']['pressures']

        assert set(a_p.keys()) == set(b_p.keys())
        for jid in a_p:
            for stat in ('min_m', 'max_m', 'avg_m'):
                a_val = a_p[jid].get(stat)
                b_val = b_p[jid].get(stat)
                if a_val is None or b_val is None:
                    continue
                assert abs(a_val - b_val) < 1e-3, (
                    f"non-deterministic pressure at {jid} ({stat}): "
                    f"{a_val} vs {b_val}"
                )

    def test_demand_factor_monotonic(self, manager):
        """Higher demand factor lowers (or holds) every junction's min pressure."""
        manager.create_scenario('low', 'australian_network.inp',
                               modifications=[{'type': 'demand_factor', 'value': 1.0}])
        manager.create_scenario('high', 'australian_network.inp',
                               modifications=[{'type': 'demand_factor', 'value': 1.5}])
        manager.run_all()

        low_p = manager.scenarios['low']['results']['pressures']
        high_p = manager.scenarios['high']['results']['pressures']

        any_decrease = False
        for jid in low_p:
            if jid not in high_p:
                continue
            l = low_p[jid].get('min_m')
            h = high_p[jid].get('min_m')
            if l is None or h is None:
                continue
            # Allow tiny solver noise (tolerance 1e-3 m)
            assert h <= l + 1e-3, (
                f"50%% demand bump raised pressure at {jid}: low={l}, high={h}"
            )
            if h < l - 1e-3:
                any_decrease = True
        assert any_decrease, (
            "expected at least one junction to lose pressure under 50%% higher demand"
        )

    def test_compare_unknown_scenario_returns_error(self, manager):
        """Defensive: compare against a missing scenario name returns an error
        dict rather than raising."""
        manager.create_scenario('base', 'australian_network.inp')
        manager.run_all()
        cmp = manager.compare('base', 'does_not_exist')
        assert isinstance(cmp, dict)
        assert 'error' in cmp

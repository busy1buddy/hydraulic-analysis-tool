"""
Tests for Pressure Zone Management (C2) and Rehabilitation Prioritisation (C4)
================================================================================
"""

import os
import sys
import csv
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_with_network():
    """API with a simple 3-junction network loaded."""
    api = HydraulicAPI()
    api.create_network(
        name='zone_test',
        junctions=[
            {'id': 'J1', 'elevation': 50, 'demand': 5.0, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 60, 'demand': 3.0, 'x': 100, 'y': 0},
            {'id': 'J3', 'elevation': 70, 'demand': 2.0, 'x': 200, 'y': 0},
        ],
        reservoirs=[{'id': 'R1', 'head': 100, 'x': -100, 'y': 0}],
        pipes=[
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500, 'diameter': 300, 'roughness': 130},
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 400, 'diameter': 250, 'roughness': 130},
            {'id': 'P3', 'start': 'J2', 'end': 'J3', 'length': 300, 'diameter': 200, 'roughness': 130},
        ],
    )
    return api


# =========================================================================
# PRESSURE ZONE TESTS (C2)
# =========================================================================

class TestPressureZones:
    """Tests for pressure zone CRUD and analysis."""

    def test_assign_zone(self, api_with_network):
        api = api_with_network
        api.assign_pressure_zone('Zone A', ['J1', 'J2'], '#89b4fa')
        zones = api.get_pressure_zones()
        assert 'Zone A' in zones
        assert sorted(zones['Zone A']['nodes']) == ['J1', 'J2']
        assert zones['Zone A']['color'] == '#89b4fa'

    def test_remove_zone(self, api_with_network):
        api = api_with_network
        api.assign_pressure_zone('Zone A', ['J1'])
        api.remove_pressure_zone('Zone A')
        assert 'Zone A' not in api.get_pressure_zones()

    def test_remove_nonexistent_zone(self, api_with_network):
        """Removing a zone that doesn't exist should not raise."""
        api_with_network.remove_pressure_zone('NoSuchZone')

    def test_get_node_zone(self, api_with_network):
        api = api_with_network
        api.assign_pressure_zone('Low', ['J1'])
        api.assign_pressure_zone('High', ['J3'])
        assert api.get_node_zone('J1') == 'Low'
        assert api.get_node_zone('J3') == 'High'
        assert api.get_node_zone('J2') is None  # unassigned

    def test_multiple_zones(self, api_with_network):
        api = api_with_network
        api.assign_pressure_zone('A', ['J1'])
        api.assign_pressure_zone('B', ['J2', 'J3'])
        zones = api.get_pressure_zones()
        assert len(zones) == 2
        assert len(zones['A']['nodes']) == 1
        assert len(zones['B']['nodes']) == 2

    def test_analyze_zones_returns_stats(self, api_with_network):
        api = api_with_network
        api.assign_pressure_zone('Low Zone', ['J1', 'J2'])
        api.assign_pressure_zone('High Zone', ['J3'])

        report = api.analyze_pressure_zones()

        assert 'Low Zone' in report
        assert 'High Zone' in report

        low = report['Low Zone']
        assert low['node_count'] == 2
        assert 'min_pressure_m' in low
        assert 'max_pressure_m' in low
        assert 'avg_pressure_m' in low
        assert 'total_demand_lps' in low
        assert 'wsaa_compliant' in low
        assert 'prv_recommended' in low

    def test_analyze_zones_demand_calculation(self, api_with_network):
        api = api_with_network
        api.assign_pressure_zone('All', ['J1', 'J2', 'J3'])
        report = api.analyze_pressure_zones()
        # Total demand should be 5 + 3 + 2 = 10 LPS
        assert report['All']['total_demand_lps'] == pytest.approx(10.0, abs=0.1)

    def test_analyze_zones_unassigned_nodes(self, api_with_network):
        api = api_with_network
        api.assign_pressure_zone('Partial', ['J1'])
        report = api.analyze_pressure_zones()
        assert '_unassigned' in report
        assert report['_unassigned']['node_count'] == 2

    def test_analyze_zones_no_network(self):
        api = HydraulicAPI()
        result = api.analyze_pressure_zones()
        assert 'error' in result

    def test_zone_wsaa_compliance(self, api_with_network):
        """Zones with all pressures in 20-50 m range should be WSAA compliant."""
        api = api_with_network
        api.assign_pressure_zone('Test', ['J1', 'J2', 'J3'])
        report = api.analyze_pressure_zones()
        # With reservoir at 100m head and elevations 50-70m, pressures should be 30-50m
        zone = report['Test']
        assert zone['min_pressure_m'] >= 20.0
        assert zone['wsaa_compliant'] is True

    def test_zone_prv_recommendation(self, api_with_network):
        """If max pressure > 50 m, PRV should be recommended."""
        api = api_with_network
        # J1 at elevation 50 with 100m head = ~50m pressure, borderline
        # With flow headloss, pressure will be somewhat less
        # Create a low-elevation node to get high pressure
        api.add_junction('J_low', elevation=10, base_demand=0.001,
                         coordinates=(300, 0))
        api.add_pipe('P_low', 'J3', 'J_low', length=100, diameter_m=0.3, roughness=130)
        api.assign_pressure_zone('Low Elev', ['J_low'])
        report = api.analyze_pressure_zones()
        # With 100m head and 10m elevation, pressure should be ~90m > 50m
        zone = report['Low Elev']
        assert zone['max_pressure_m'] > 50
        assert zone['prv_recommended'] is True


# =========================================================================
# REHABILITATION PRIORITISATION TESTS (C4)
# =========================================================================

class TestRehabPrioritisation:
    """Tests for pipe rehabilitation scoring and ranking."""

    def test_set_pipe_condition(self, api_with_network):
        api = api_with_network
        api.set_pipe_condition('P1', install_year=1980, condition_score=3.5,
                               break_history=2, material='DI')
        conds = api.get_pipe_conditions()
        assert 'P1' in conds
        assert conds['P1']['install_year'] == 1980
        assert conds['P1']['condition_score'] == 3.5
        assert conds['P1']['break_history'] == 2
        assert conds['P1']['material'] == 'DI'

    def test_prioritize_returns_all_pipes(self, api_with_network):
        api = api_with_network
        results = api.prioritize_rehabilitation()
        assert len(results) == 3  # P1, P2, P3
        # Results should be sorted by priority (highest first)
        for i in range(len(results) - 1):
            assert results[i]['priority_score'] >= results[i + 1]['priority_score']

    def test_prioritize_with_condition_data(self, api_with_network):
        api = api_with_network
        api.set_pipe_condition('P1', install_year=1960, condition_score=4.5,
                               break_history=5, material='CI')
        api.set_pipe_condition('P2', install_year=2020, condition_score=1.0,
                               break_history=0, material='PE')

        results = api.prioritize_rehabilitation(current_year=2026)

        # P1 (old, poor condition, many breaks) should rank higher than P2
        p1 = next(r for r in results if r['pipe_id'] == 'P1')
        p2 = next(r for r in results if r['pipe_id'] == 'P2')
        assert p1['priority_score'] > p2['priority_score']
        assert p1['age_years'] == 66
        assert p2['age_years'] == 6

    def test_prioritize_risk_categories(self, api_with_network):
        api = api_with_network
        api.set_pipe_condition('P1', install_year=1950, condition_score=5.0,
                               break_history=10, material='AC')
        results = api.prioritize_rehabilitation(current_year=2026)
        p1 = next(r for r in results if r['pipe_id'] == 'P1')
        assert p1['risk_category'] == 'CRITICAL'

    def test_prioritize_unknown_age(self, api_with_network):
        """Pipes with no install year get medium age risk."""
        api = api_with_network
        results = api.prioritize_rehabilitation()
        for r in results:
            assert r['age_years'] is None
            assert r['age_component'] == 50.0  # medium risk default

    def test_import_conditions_csv(self, api_with_network):
        api = api_with_network
        # Create temp CSV
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False,
                                          newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['pipe_id', 'install_year', 'condition_score',
                             'break_history', 'material'])
            writer.writerow(['P1', '1985', '3.0', '2', 'DI'])
            writer.writerow(['P2', '2010', '1.5', '0', 'PVC'])
            csv_path = f.name

        try:
            count = api.import_pipe_conditions_csv(csv_path)
            assert count == 2
            conds = api.get_pipe_conditions()
            assert conds['P1']['install_year'] == 1985
            assert conds['P2']['material'] == 'PVC'
        finally:
            os.unlink(csv_path)

    def test_prioritize_no_network(self):
        api = HydraulicAPI()
        result = api.prioritize_rehabilitation()
        assert isinstance(result, dict)
        assert 'error' in result

    def test_result_contains_all_fields(self, api_with_network):
        api = api_with_network
        results = api.prioritize_rehabilitation()
        required_fields = [
            'pipe_id', 'diameter_mm', 'length_m', 'material',
            'install_year', 'age_years', 'condition_score',
            'break_history', 'velocity_ms', 'priority_score',
            'risk_category',
        ]
        for r in results:
            for field in required_fields:
                assert field in r, f"Missing field: {field}"

    def test_component_scores_in_range(self, api_with_network):
        """All component scores should be 0-100."""
        api = api_with_network
        api.set_pipe_condition('P1', install_year=1970, condition_score=4.0,
                               break_history=3, material='DI')
        results = api.prioritize_rehabilitation(current_year=2026)
        for r in results:
            assert 0 <= r['age_component'] <= 100
            assert 0 <= r['condition_component'] <= 100
            assert 0 <= r['break_component'] <= 100
            assert 0 <= r['hydraulic_component'] <= 100

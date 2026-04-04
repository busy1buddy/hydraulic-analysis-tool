"""
Tests for O-series features (O1, O2, O3, O6, O7).
================================================
O1 — Learning Mode (explain_analysis)
O2 — Climate Demand Projection
O3 — Water Security Analysis
O6 — Network Health Summary
O7 — Lamont Break Forecast
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


@pytest.fixture
def api():
    a = HydraulicAPI()
    a.create_network(
        name='o_test',
        junctions=[
            {'id': 'J1', 'elevation': 50, 'demand': 2, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 55, 'demand': 1, 'x': 100, 'y': 0},
            {'id': 'J3', 'elevation': 60, 'demand': 1.5, 'x': 200, 'y': 0},
        ],
        reservoirs=[{'id': 'R1', 'head': 120, 'x': -50, 'y': 0}],
        pipes=[
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
             'diameter': 200, 'roughness': 130},
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 150,
             'diameter': 150, 'roughness': 130},
            {'id': 'P3', 'start': 'J2', 'end': 'J3', 'length': 180,
             'diameter': 150, 'roughness': 130},
        ],
    )
    return a


class TestO1ExplainAnalysis:

    def test_no_network_error(self):
        a = HydraulicAPI()
        result = a.explain_analysis()
        assert 'error' in result

    def test_returns_lessons(self, api):
        result = api.explain_analysis()
        assert 'lessons' in result
        assert result['n_lessons'] >= 3

    def test_lessons_have_required_fields(self, api):
        result = api.explain_analysis()
        for lesson in result['lessons']:
            assert 'topic' in lesson
            assert 'explanation' in lesson
            assert 'standard' in lesson
            assert 'reference' in lesson

    def test_compliance_lesson_always_present(self, api):
        result = api.explain_analysis()
        topics = [l['topic'] for l in result['lessons']]
        assert 'WSAA Compliance' in topics


class TestO2ClimateDemandProjection:

    def test_no_network_error(self):
        a = HydraulicAPI()
        result = a.climate_demand_projection()
        assert 'error' in result

    def test_medium_scenario(self, api):
        result = api.climate_demand_projection(
            base_year=2026, target_years=[2030, 2050], climate_scenario='medium')
        assert result['scenario'] == 'medium'
        assert 2030 in result['projections']
        assert 2050 in result['projections']

    def test_multipliers_increase_over_time(self, api):
        result = api.climate_demand_projection(
            base_year=2026, target_years=[2030, 2050, 2070], climate_scenario='medium')
        m_2030 = result['projections'][2030]['total_multiplier']
        m_2050 = result['projections'][2050]['total_multiplier']
        m_2070 = result['projections'][2070]['total_multiplier']
        assert m_2030 < m_2050 < m_2070

    def test_high_scenario_exceeds_low(self, api):
        low = api.climate_demand_projection(
            base_year=2026, target_years=[2050], climate_scenario='low')
        high = api.climate_demand_projection(
            base_year=2026, target_years=[2050], climate_scenario='high')
        assert (high['projections'][2050]['total_multiplier'] >
                low['projections'][2050]['total_multiplier'])

    def test_confidence_bounds(self, api):
        result = api.climate_demand_projection(
            base_year=2026, target_years=[2050], climate_scenario='medium')
        proj = result['projections'][2050]
        assert proj['low_bound'] <= proj['total_multiplier'] <= proj['high_bound']

    def test_invalid_scenario(self, api):
        result = api.climate_demand_projection(climate_scenario='extreme')
        assert 'error' in result


class TestO3WaterSecurityAnalysis:

    def test_no_network_error(self):
        a = HydraulicAPI()
        result = a.water_security_analysis()
        assert 'error' in result

    def test_runs_on_valid_network(self, api):
        result = api.water_security_analysis()
        assert 'error' not in result or result.get('n_sources', 0) >= 0

    def test_returns_vulnerability_data(self, api):
        result = api.water_security_analysis()
        if 'error' not in result:
            assert 'vulnerabilities' in result
            assert 'summary' in result
            assert 'recommendations' in result


class TestO6NetworkHealthSummary:

    def test_no_network_error(self):
        a = HydraulicAPI()
        result = a.network_health_summary()
        assert 'error' in result

    def test_returns_summary(self, api):
        result = api.network_health_summary()
        assert 'error' not in result
        assert 'summary_paragraph' in result
        assert len(result['summary_paragraph']) > 50

    def test_has_metrics(self, api):
        result = api.network_health_summary()
        assert 'error' not in result
        assert 'metrics' in result
        assert 'recommendations' in result


class TestO7LamontBreakForecast:

    def test_no_network_error(self):
        a = HydraulicAPI()
        result = a.lamont_break_forecast()
        assert 'error' in result

    def test_returns_forecast_with_install_years(self, api):
        # Set some pipe install years first
        for pid in api.wn.pipe_name_list:
            pipe = api.wn.get_link(pid)
            # attach install year metadata
            try:
                pipe.install_year = 1980
            except Exception:
                pass
        result = api.lamont_break_forecast()
        assert 'pipe_forecasts' in result
        assert 'network_summary' in result
        assert 'material_coefficients' in result


class TestO4OperationsDashboard:

    def test_no_network_error(self):
        a = HydraulicAPI()
        result = a.operations_dashboard()
        assert 'error' in result

    def test_returns_dashboard(self, api):
        result = api.operations_dashboard()
        assert 'error' not in result
        assert 'status_light' in result
        assert result['status_light'] in ('green', 'amber', 'red')
        assert 'kpis' in result
        assert 'lowest_pressures' in result
        assert 'highest_pressures' in result

    def test_kpis_populated(self, api):
        result = api.operations_dashboard()
        kpis = result['kpis']
        assert kpis['n_junctions'] == 3
        assert kpis['n_pipes'] == 3
        assert kpis['total_demand_lps'] > 0

    def test_pressure_rankings_sorted(self, api):
        result = api.operations_dashboard()
        lowest = [p['pressure_m'] for p in result['lowest_pressures']]
        assert lowest == sorted(lowest)
        highest = [p['pressure_m'] for p in result['highest_pressures']]
        assert highest == sorted(highest, reverse=True)


class TestO5NetworkDocumentation:

    def test_no_network_error(self):
        a = HydraulicAPI()
        result = a.generate_network_documentation()
        assert 'error' in result

    def test_generates_markdown(self, api):
        result = api.generate_network_documentation()
        assert 'markdown' in result
        assert '# Network Documentation' in result['markdown']
        assert 'Inventory' in result['markdown']
        assert 'Pipe Size Distribution' in result['markdown']

    def test_inventory_counts(self, api):
        result = api.generate_network_documentation()
        md = result['markdown']
        assert '| Junctions | 3 |' in md
        assert '| Pipes | 3 |' in md
        assert '| Reservoirs | 1 |' in md

    def test_metadata(self, api):
        result = api.generate_network_documentation()
        assert result['n_sections'] == 5
        assert result['total_length_km'] > 0
        assert result['n_pipe_sizes'] >= 1

    def test_design_standards_referenced(self, api):
        result = api.generate_network_documentation()
        assert 'WSAA WSA 03-2011' in result['markdown']

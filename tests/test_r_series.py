"""
R-series and I-series feature tests.

Covers:
  R5 export_geojson
  R6 validate_network
  I3 generate_demand_pattern + apply_demand_pattern
  I5 root_cause_analysis
"""

import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


def _good_network():
    a = HydraulicAPI()
    a.create_network(
        name='rtest',
        junctions=[
            {'id': 'J1', 'elevation': 50, 'demand': 2, 'x': 100, 'y': 0},
            {'id': 'J2', 'elevation': 55, 'demand': 1.5, 'x': 200, 'y': 0},
            {'id': 'J3', 'elevation': 60, 'demand': 1, 'x': 200, 'y': 100},
        ],
        reservoirs=[{'id': 'R1', 'head': 100, 'x': 0, 'y': 0}],
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


def _undersized_network():
    """Network with a deliberate low-pressure + high-velocity violation."""
    a = HydraulicAPI()
    a.create_network(
        name='undersized',
        junctions=[
            {'id': 'J1', 'elevation': 60, 'demand': 15, 'x': 500, 'y': 0},
            {'id': 'J2', 'elevation': 70, 'demand': 10, 'x': 1000, 'y': 0},
        ],
        reservoirs=[{'id': 'R1', 'head': 80, 'x': 0, 'y': 0}],
        pipes=[
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
             'diameter': 100, 'roughness': 130},
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 500,
             'diameter': 100, 'roughness': 130},
        ],
    )
    return a


# ---------- R6 validate_network ----------------------------------------------

class TestValidateNetwork:

    def test_no_network_error(self):
        a = HydraulicAPI()
        r = a.validate_network()
        assert 'error' in r
        assert 'Fix:' in r['error']

    def test_valid_network_passes(self):
        a = _good_network()
        r = a.validate_network()
        assert r['is_valid'] is True
        assert r['n_errors'] == 0

    def test_detects_missing_source(self):
        a = HydraulicAPI()
        a.create_network(
            name='no_source',
            junctions=[
                {'id': 'J1', 'elevation': 10, 'demand': 1, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 12, 'demand': 1, 'x': 100, 'y': 0},
            ],
            reservoirs=[],
            pipes=[{'id': 'P1', 'start': 'J1', 'end': 'J2', 'length': 100,
                     'diameter': 150, 'roughness': 130}],
        )
        r = a.validate_network()
        assert r['is_valid'] is False
        types = [i['type'] for i in r['errors']]
        assert 'no_source' in types

    def test_detects_zero_length_pipe(self):
        a = _good_network()
        # Force zero length directly
        a.wn.get_link('P1').length = 0
        r = a.validate_network()
        assert r['is_valid'] is False
        types = [i['type'] for i in r['errors']]
        assert 'zero_length_pipe' in types

    def test_detects_disconnected_subgraphs(self):
        a = HydraulicAPI()
        a.create_network(
            name='split',
            junctions=[
                {'id': 'J1', 'elevation': 10, 'demand': 1, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 12, 'demand': 1, 'x': 100, 'y': 0},
                {'id': 'J3', 'elevation': 15, 'demand': 1, 'x': 500, 'y': 500},
                {'id': 'J4', 'elevation': 15, 'demand': 1, 'x': 600, 'y': 500},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                 'diameter': 150, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 100,
                 'diameter': 150, 'roughness': 130},
                # J3-J4 form second island (unreachable from R1)
                {'id': 'P3', 'start': 'J3', 'end': 'J4', 'length': 100,
                 'diameter': 150, 'roughness': 130},
            ],
        )
        r = a.validate_network()
        types = [i['type'] for i in r['errors']]
        assert 'disconnected_subgraphs' in types
        assert r['inventory']['connected_components'] >= 2

    def test_warns_on_negative_elevation(self):
        a = _good_network()
        a.wn.get_node('J1').elevation = -5
        r = a.validate_network()
        assert r['n_warnings'] >= 1
        warn_types = [w['type'] for w in r['warnings']]
        assert 'negative_elevation' in warn_types


# ---------- R5 export_geojson ------------------------------------------------

class TestExportGeoJSON:

    def test_no_network_error(self):
        a = HydraulicAPI()
        r = a.export_geojson('/tmp/x.geojson')
        assert 'error' in r

    def test_feature_count_matches_inventory(self, tmp_path):
        a = _good_network()
        out = tmp_path / 'net.geojson'
        r = a.export_geojson(str(out))
        # 1 reservoir + 3 junctions + 3 pipes = 7 features
        assert r['n_features'] == 7
        assert r['n_node_features'] == 4
        assert r['n_pipe_features'] == 3
        assert out.exists()

    def test_output_is_valid_geojson(self, tmp_path):
        a = _good_network()
        out = tmp_path / 'net.geojson'
        a.export_geojson(str(out))
        with open(out) as f:
            data = json.load(f)
        assert data['type'] == 'FeatureCollection'
        assert isinstance(data['features'], list)
        # Nodes are Points, pipes are LineStrings
        geoms = [feat['geometry']['type'] for feat in data['features']]
        assert 'Point' in geoms and 'LineString' in geoms

    def test_properties_include_results_when_available(self, tmp_path):
        a = _good_network()
        a.run_steady_state(save_plot=False)
        out = tmp_path / 'net.geojson'
        a.export_geojson(str(out), include_results=True)
        with open(out) as f:
            data = json.load(f)
        # Find a junction feature — should have pressure_m + wsaa_status
        junctions = [feat for feat in data['features']
                     if feat['properties'].get('type') == 'junction']
        assert junctions
        assert 'pressure_m' in junctions[0]['properties']
        assert 'wsaa_status' in junctions[0]['properties']

    def test_include_results_false(self, tmp_path):
        a = _good_network()
        a.run_steady_state(save_plot=False)
        out = tmp_path / 'net.geojson'
        a.export_geojson(str(out), include_results=False)
        with open(out) as f:
            data = json.load(f)
        # No pressure_m key on any feature
        has_pressure = any('pressure_m' in feat['properties']
                           for feat in data['features'])
        assert not has_pressure


# ---------- I3 generate/apply_demand_pattern --------------------------------

class TestDemandPatternWizard:

    def test_unknown_type(self):
        a = HydraulicAPI()
        r = a.generate_demand_pattern('agricultural', daily_total_kL=100)
        assert 'error' in r

    def test_missing_inputs(self):
        a = HydraulicAPI()
        r = a.generate_demand_pattern('residential')
        assert 'error' in r

    def test_pattern_sums_to_24(self):
        a = HydraulicAPI()
        for nt in ('residential', 'commercial', 'industrial'):
            r = a.generate_demand_pattern(nt, daily_total_kL=100)
            assert abs(sum(r['multipliers']) - 24.0) < 0.01

    def test_residential_peak_evening(self):
        a = HydraulicAPI()
        r = a.generate_demand_pattern('residential', daily_total_kL=100)
        # Residential peak should be evening (17-20h range)
        assert 16 <= r['peak_hour'] <= 20

    def test_daily_total_matches_input(self):
        a = HydraulicAPI()
        r = a.generate_demand_pattern('commercial', daily_total_kL=250)
        assert abs(r['daily_total_kL'] - 250) < 1.0

    def test_reverse_from_peak(self):
        a = HydraulicAPI()
        r = a.generate_demand_pattern('residential', peak_hour_lps=5.0)
        assert abs(r['peak_demand_lps'] - 5.0) < 0.01
        # Daily total derived
        assert r['daily_total_kL'] > 0

    def test_apply_pattern_requires_network(self):
        a = HydraulicAPI()
        r = a.apply_demand_pattern([1.0] * 24)
        assert 'error' in r

    def test_apply_pattern_wrong_length(self):
        a = _good_network()
        r = a.apply_demand_pattern([1.0] * 12)
        assert 'error' in r

    def test_apply_pattern_updates_junctions(self):
        a = _good_network()
        gen = a.generate_demand_pattern('residential', daily_total_kL=50)
        r = a.apply_demand_pattern(gen['multipliers'])
        assert r['n_junctions_updated'] == 3


# ---------- I5 root_cause_analysis -----------------------------------------

class TestRootCauseAnalysis:

    def test_no_network_error(self):
        a = HydraulicAPI()
        r = a.root_cause_analysis()
        assert 'error' in r

    def test_healthy_network_has_no_issues(self):
        a = _good_network()
        r = a.root_cause_analysis()
        assert r['n_issues'] == 0

    def test_identifies_low_pressure(self):
        a = _undersized_network()
        r = a.root_cause_analysis()
        assert r['n_issues'] >= 1
        issues = [e['issue'] for e in r['explanations']]
        assert 'low_pressure' in issues

    def test_explanation_includes_root_cause_text(self):
        a = _undersized_network()
        r = a.root_cause_analysis()
        exp = r['explanations'][0]
        assert 'root_cause' in exp
        assert len(exp['root_cause']) > 30

    def test_fixes_have_cost_estimates(self):
        a = _undersized_network()
        r = a.root_cause_analysis()
        for exp in r['explanations']:
            assert exp['fixes']
            for fix in exp['fixes']:
                assert 'option' in fix
                assert 'est_cost_aud' in fix
                assert fix['est_cost_aud'] > 0

    def test_cost_assumptions_documented(self):
        a = _undersized_network()
        r = a.root_cause_analysis()
        assert 'cost_assumptions' in r
        assert r['cost_assumptions']['currency'] == 'AUD'

    def test_identifies_high_velocity(self):
        a = _undersized_network()
        r = a.root_cause_analysis()
        # Undersized pipes carrying 25 LPS through DN100 → v > 2 m/s
        v_max_via_flow = max(
            f.get('max_velocity_ms', 0)
            for f in a.run_steady_state(save_plot=False)['flows'].values())
        if v_max_via_flow > a.DEFAULTS['max_velocity_ms']:
            issues = [e['issue'] for e in r['explanations']]
            assert 'high_velocity' in issues

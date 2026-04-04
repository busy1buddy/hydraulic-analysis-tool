"""
Tests for Quick Network Assessment (Innovation Q3)
====================================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestQuickAssessment:

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.quick_assessment()
        assert 'error' in result

    def test_result_structure(self):
        api = HydraulicAPI()
        api.create_network(
            name='qa_struct',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 1, 'x': 100, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        result = api.quick_assessment()
        assert 'summary' in result
        assert 'topology' in result
        assert 'diagnostics' in result
        assert 'material_inventory' in result
        assert 'pipe_sizes' in result
        assert 'recommendations' in result

    def test_includes_analysis_results(self):
        api = HydraulicAPI()
        api.create_network(
            name='qa_results',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        result = api.quick_assessment()
        assert result['analysis_status'] == 'OK'
        assert 'fingerprint' in result
        assert 'resilience' in result
        assert 'quality_score' in result

    def test_recommendations_present(self):
        api = HydraulicAPI()
        api.create_network(
            name='qa_recs',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        result = api.quick_assessment()
        assert len(result['recommendations']) >= 1

    def test_material_inventory(self):
        api = HydraulicAPI()
        api.create_network(
            name='qa_mat',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},  # DI range
            ],
        )
        result = api.quick_assessment()
        total = sum(result['material_inventory'].values())
        assert total == 1  # one pipe

    def test_real_network(self):
        api = HydraulicAPI()
        api.load_network('australian_network.inp')
        result = api.quick_assessment()
        assert result['analysis_status'] == 'OK'
        assert result['summary']['junctions'] > 0
        assert len(result['pipe_sizes']) > 0

    def test_pipe_size_distribution(self):
        api = HydraulicAPI()
        api.create_network(
            name='qa_sizes',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 1, 'x': 100, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 300, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        result = api.quick_assessment()
        assert 200 in result['pipe_sizes']
        assert 300 in result['pipe_sizes']

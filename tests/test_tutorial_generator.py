"""
Tests for Automated Tutorial Generator (M8)
=============================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestTutorialGenerator:

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.generate_tutorial()
        assert 'error' in result

    def test_generates_readme(self, tmp_path):
        api = HydraulicAPI()
        api.create_network(
            name='tut_test',
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
        result = api.generate_tutorial(output_dir=str(tmp_path / 'tutorial'))
        assert os.path.exists(result['readme_path'])

    def test_readme_contains_statistics(self, tmp_path):
        api = HydraulicAPI()
        api.create_network(
            name='tut_stats',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        result = api.generate_tutorial(output_dir=str(tmp_path / 'tut'))
        with open(result['readme_path'], 'r') as f:
            content = f.read()
        assert 'Junctions' in content
        assert 'Pipes' in content
        assert 'Steady State' in content or 'Suggested' in content

    def test_readme_contains_topology(self, tmp_path):
        api = HydraulicAPI()
        api.create_network(
            name='tut_topo',
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
        result = api.generate_tutorial(output_dir=str(tmp_path / 'tut'))
        with open(result['readme_path'], 'r') as f:
            content = f.read()
        assert 'Topology' in content
        assert 'Dead ends' in content

    def test_real_network_tutorial(self, tmp_path):
        api = HydraulicAPI()
        api.load_network('australian_network.inp')
        result = api.generate_tutorial(output_dir=str(tmp_path / 'au_tut'))
        assert os.path.exists(result['readme_path'])
        with open(result['readme_path'], 'r') as f:
            content = f.read()
        assert 'Quality score' in content or 'Resilience' in content

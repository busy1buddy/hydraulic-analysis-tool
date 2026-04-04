"""
Tests for Smart Error Recovery / Network Diagnostics (L5)
==========================================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestDiagnoseNetwork:

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.diagnose_network()
        assert 'error' in result

    def test_healthy_network_no_issues(self):
        api = HydraulicAPI()
        api.create_network(
            name='healthy',
            junctions=[
                {'id': 'J1', 'elevation': 50, 'demand': 2, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 50, 'demand': 1, 'x': 100, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 80, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 100,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        result = api.diagnose_network()
        assert result['can_run'] is True
        assert result['critical'] == 0

    def test_result_structure(self):
        api = HydraulicAPI()
        api.create_network(
            name='struct',
            junctions=[{'id': 'J1', 'elevation': 0, 'demand': 1, 'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                     'diameter': 200, 'roughness': 130}],
        )
        result = api.diagnose_network()
        assert 'issues' in result
        assert 'issue_count' in result
        assert 'critical' in result
        assert 'warnings' in result
        assert 'can_run' in result
        assert 'summary' in result

    def test_zero_length_detected(self):
        api = HydraulicAPI()
        api.create_network(
            name='zero_len',
            junctions=[{'id': 'J1', 'elevation': 0, 'demand': 1, 'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                     'diameter': 200, 'roughness': 130}],
        )
        # Set length to zero
        api.wn.get_link('P1').length = 0
        result = api.diagnose_network()
        types = [i['type'] for i in result['issues']]
        assert 'zero_length_pipe' in types
        assert result['can_run'] is False

    def test_bad_roughness_detected(self):
        api = HydraulicAPI()
        api.create_network(
            name='bad_c',
            junctions=[{'id': 'J1', 'elevation': 0, 'demand': 1, 'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                     'diameter': 200, 'roughness': 130}],
        )
        # Set roughness to unreasonable value
        api.wn.get_link('P1').roughness = 10  # way too low for HW
        result = api.diagnose_network()
        types = [i['type'] for i in result['issues']]
        assert 'roughness_range' in types

    def test_dead_ends_warning(self):
        """Many dead ends should generate a warning."""
        api = HydraulicAPI()
        junctions = [
            {'id': f'J{i}', 'elevation': 0, 'demand': 1, 'x': i*50, 'y': 0}
            for i in range(1, 9)
        ]
        pipes = [
            {'id': 'P0', 'start': 'R1', 'end': 'J1', 'length': 100,
             'diameter': 200, 'roughness': 130}
        ]
        # Hub-and-spoke: J1 connects to J2-J8 as dead ends
        for i in range(2, 9):
            pipes.append({
                'id': f'P{i}', 'start': 'J1', 'end': f'J{i}', 'length': 100,
                'diameter': 200, 'roughness': 130
            })
        api.create_network(
            name='dead_ends',
            junctions=junctions,
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=pipes,
        )
        result = api.diagnose_network()
        types = [i['type'] for i in result['issues']]
        assert 'many_dead_ends' in types

    def test_each_issue_has_suggestion(self):
        api = HydraulicAPI()
        api.create_network(
            name='suggestions',
            junctions=[{'id': 'J1', 'elevation': 0, 'demand': 1, 'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                     'diameter': 200, 'roughness': 10}],  # bad roughness
        )
        result = api.diagnose_network()
        for issue in result['issues']:
            assert 'suggestion' in issue, f"Issue '{issue['type']}' missing suggestion"

    def test_real_network(self):
        api = HydraulicAPI()
        api.load_network('australian_network.inp')
        result = api.diagnose_network()
        assert 'issues' in result
        assert isinstance(result['issue_count'], int)

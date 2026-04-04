"""
Tests for Network Topology Analysis (L3)
==========================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestTopologyAnalysis:

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.analyse_topology()
        assert 'error' in result

    def test_linear_network_has_dead_ends(self):
        """A linear R1-J1-J2-J3 network should have J3 as dead end."""
        api = HydraulicAPI()
        api.create_network(
            name='linear',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 1, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 1, 'x': 100, 'y': 0},
                {'id': 'J3', 'elevation': 0, 'demand': 1, 'x': 200, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -100, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 100,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P3', 'start': 'J2', 'end': 'J3', 'length': 100,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        result = api.analyse_topology()
        assert 'J3' in result['dead_ends']
        assert result['dead_end_count'] >= 1

    def test_loop_network_has_loops(self):
        """A looped network should have loops > 0."""
        api = HydraulicAPI()
        api.create_network(
            name='loop',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 1, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 1, 'x': 100, 'y': 0},
                {'id': 'J3', 'elevation': 0, 'demand': 1, 'x': 100, 'y': 100},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 50}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 100,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P3', 'start': 'J2', 'end': 'J3', 'length': 100,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P4', 'start': 'J3', 'end': 'J1', 'length': 100,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        result = api.analyse_topology()
        assert result['loops'] >= 1
        assert result['dead_end_count'] == 0

    def test_bridge_detection(self):
        """A bridge pipe connects two subgraphs."""
        api = HydraulicAPI()
        api.create_network(
            name='bridge',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 1, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 1, 'x': 100, 'y': 0},
                {'id': 'J3', 'elevation': 0, 'demand': 1, 'x': 200, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -100, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 100,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P3', 'start': 'J2', 'end': 'J3', 'length': 100,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        result = api.analyse_topology()
        # All pipes in a linear network are bridges
        assert result['bridge_count'] >= 1

    def test_connectivity_ratio(self):
        """All-connected network should have ratio 1.0."""
        api = HydraulicAPI()
        api.create_network(
            name='connected',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 1, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 1, 'x': 100, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 100,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        result = api.analyse_topology()
        assert result['connectivity_ratio'] == 1.0
        assert result['isolated_count'] == 0

    def test_degree_distribution(self):
        """Degree distribution should sum to total nodes."""
        api = HydraulicAPI()
        api.create_network(
            name='deg_dist',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 1, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 1, 'x': 100, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 100,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        result = api.analyse_topology()
        total = sum(result['degree_distribution'].values())
        assert total == result['total_nodes']

    def test_sources_identified(self):
        api = HydraulicAPI()
        api.create_network(
            name='sources',
            junctions=[{'id': 'J1', 'elevation': 0, 'demand': 1, 'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                     'diameter': 200, 'roughness': 130}],
        )
        result = api.analyse_topology()
        assert 'R1' in result['sources']

    def test_result_structure(self):
        api = HydraulicAPI()
        api.create_network(
            name='struct',
            junctions=[{'id': 'J1', 'elevation': 0, 'demand': 1, 'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                     'diameter': 200, 'roughness': 130}],
        )
        result = api.analyse_topology()
        expected_keys = [
            'dead_ends', 'dead_end_count', 'bridges', 'bridge_count',
            'loops', 'connected_components', 'isolated_nodes', 'isolated_count',
            'total_nodes', 'total_pipes', 'avg_node_degree', 'degree_distribution',
            'sources', 'connectivity_ratio',
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_real_network(self):
        """Run on a real .inp file if available."""
        api = HydraulicAPI()
        api.load_network('australian_network.inp')
        result = api.analyse_topology()
        assert result['total_nodes'] > 0
        assert result['total_pipes'] > 0
        assert result['connectivity_ratio'] > 0

"""
Tests for Todini Resilience Index (M1)
=======================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestResilienceIndex:

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.compute_resilience_index()
        assert 'error' in result

    def test_result_structure(self):
        api = HydraulicAPI()
        api.create_network(
            name='ri_struct',
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
        ri = api.compute_resilience_index()
        assert 'resilience_index' in ri
        assert 'grade' in ri
        assert 'interpretation' in ri
        assert ri['grade'] in ('A', 'B', 'C', 'D', 'F')

    def test_index_between_0_and_1(self):
        api = HydraulicAPI()
        api.create_network(
            name='ri_range',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        ri = api.compute_resilience_index()
        assert 0 <= ri['resilience_index'] <= 1.0

    def test_loop_has_higher_resilience_than_linear(self):
        """Looped networks should have higher resilience than linear."""
        # Linear: R1-J1-J2-J3
        api_lin = HydraulicAPI()
        api_lin.create_network(
            name='ri_linear',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 2, 'x': 100, 'y': 0},
                {'id': 'J3', 'elevation': 0, 'demand': 2, 'x': 200, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 200,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P3', 'start': 'J2', 'end': 'J3', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        ri_lin = api_lin.compute_resilience_index()

        # Looped: R1-J1-J2-J3-J1 (same but with closing pipe)
        api_loop = HydraulicAPI()
        api_loop.create_network(
            name='ri_loop',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 2, 'x': 100, 'y': 0},
                {'id': 'J3', 'elevation': 0, 'demand': 2, 'x': 100, 'y': 100},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 200,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P3', 'start': 'J2', 'end': 'J3', 'length': 200,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P4', 'start': 'J3', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        ri_loop = api_loop.compute_resilience_index()

        # Loop should provide better pressure distribution and higher resilience
        assert ri_loop['resilience_index'] >= ri_lin['resilience_index']

    def test_resilience_drops_with_smaller_pipes(self):
        """Smaller pipes = more headloss = lower resilience."""
        # Large pipes
        api_large = HydraulicAPI()
        api_large.create_network(
            name='ri_large',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 5, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
                 'diameter': 300, 'roughness': 130},
            ],
        )
        ri_large = api_large.compute_resilience_index()

        # Small pipes
        api_small = HydraulicAPI()
        api_small.create_network(
            name='ri_small',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 5, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
                 'diameter': 100, 'roughness': 130},
            ],
        )
        ri_small = api_small.compute_resilience_index()

        assert ri_large['resilience_index'] > ri_small['resilience_index']

    def test_grade_a_for_high_resilience(self):
        """Very generous network should get grade A."""
        api = HydraulicAPI()
        api.create_network(
            name='ri_a',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 0.5, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 80, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                 'diameter': 300, 'roughness': 150},
            ],
        )
        ri = api.compute_resilience_index()
        assert ri['resilience_index'] >= 0.5
        assert ri['grade'] == 'A'

    def test_in_compliance_certificate(self):
        """Resilience should appear in compliance certificate."""
        api = HydraulicAPI()
        api.create_network(
            name='ri_cert',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        cert = api.run_design_compliance_check()
        check_names = [c['check'] for c in cert['checks']]
        assert any('Resilience' in n for n in check_names)
        assert 'resilience' in cert

    def test_passes_results_without_rerunning(self):
        """Passing pre-computed results should not run analysis again."""
        api = HydraulicAPI()
        api.create_network(
            name='ri_precomp',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        results = api.run_steady_state(save_plot=False)
        ri = api.compute_resilience_index(results)
        assert 'resilience_index' in ri

    def test_real_network_industrial_ring(self):
        """Industrial ring main should have high resilience."""
        api = HydraulicAPI()
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'tutorials', 'industrial_ring_main', 'network.inp')
        if not os.path.exists(path):
            pytest.skip("Tutorial not found")
        api.load_network_from_path(path)
        ri = api.compute_resilience_index()
        assert ri['resilience_index'] > 0.5
        assert ri['grade'] == 'A'

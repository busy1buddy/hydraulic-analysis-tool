"""
Tests for Chlorine Booster Station Design (J14)
=================================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestChlorineBooster:

    def test_no_deficiency_no_boosters(self):
        """If all nodes are above target, no boosters should be recommended."""
        api = HydraulicAPI()
        # Synthetic results where all chlorine > 0.2
        wq_results = {
            'junction_quality': {
                'J1': {'min_chlorine_mgl': 0.5, 'avg_chlorine_mgl': 0.8},
                'J2': {'min_chlorine_mgl': 0.3, 'avg_chlorine_mgl': 0.6},
            }
        }
        api.create_network(
            name='booster_ok',
            junctions=[{'id': 'J1', 'elevation': 50, 'demand': 1, 'x': 0, 'y': 0},
                        {'id': 'J2', 'elevation': 50, 'demand': 1, 'x': 100, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 80, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                     'diameter': 200, 'roughness': 130},
                   {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 100,
                     'diameter': 200, 'roughness': 130}],
        )
        result = api.design_chlorine_boosters(wq_results)
        assert len(result['booster_recommendations']) == 0
        assert 'no booster' in result['summary'].lower()

    def test_deficient_nodes_get_boosters(self):
        """Nodes below 0.2 mg/L should get booster recommendations."""
        api = HydraulicAPI()
        wq_results = {
            'junction_quality': {
                'J1': {'min_chlorine_mgl': 0.05, 'avg_chlorine_mgl': 0.1},
                'J2': {'min_chlorine_mgl': 0.5, 'avg_chlorine_mgl': 0.8},
            }
        }
        api.create_network(
            name='booster_def',
            junctions=[{'id': 'J1', 'elevation': 50, 'demand': 1, 'x': 0, 'y': 0},
                        {'id': 'J2', 'elevation': 50, 'demand': 1, 'x': 100, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 80, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                     'diameter': 200, 'roughness': 130},
                   {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 100,
                     'diameter': 200, 'roughness': 130}],
        )
        result = api.design_chlorine_boosters(wq_results)
        assert len(result['deficient_nodes']) == 1
        assert result['deficient_nodes'][0]['node'] == 'J1'
        assert len(result['booster_recommendations']) >= 1

    def test_dose_calculation(self):
        """Booster dose should be enough to reach target + safety margin."""
        api = HydraulicAPI()
        wq_results = {
            'junction_quality': {
                'J1': {'min_chlorine_mgl': 0.05, 'avg_chlorine_mgl': 0.1},
            }
        }
        api.create_network(
            name='booster_dose',
            junctions=[{'id': 'J1', 'elevation': 50, 'demand': 1, 'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 80, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                     'diameter': 200, 'roughness': 130}],
        )
        result = api.design_chlorine_boosters(wq_results, target_residual_mgl=0.2)
        rec = result['booster_recommendations'][0]
        # Dose = target (0.2) - min (0.05) + safety (0.1) = 0.25
        assert rec['recommended_dose_mgl'] == pytest.approx(0.25, abs=0.01)

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.design_chlorine_boosters()
        assert 'error' in result

    def test_wsaa_threshold_constant(self):
        assert HydraulicAPI.WSAA_MIN_CHLORINE_MGL == 0.2

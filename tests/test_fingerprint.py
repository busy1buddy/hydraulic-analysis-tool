"""
Tests for Hydraulic Fingerprint (L4)
=====================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestHydraulicFingerprint:

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.hydraulic_fingerprint()
        assert 'error' in result

    def test_fingerprint_structure(self):
        api = HydraulicAPI()
        api.create_network(
            name='fp_test',
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
        fp = api.hydraulic_fingerprint()
        assert 'pressure_stats' in fp
        assert 'velocity_stats' in fp
        assert 'total_demand_lps' in fp
        assert 'headloss_top5' in fp
        assert 'energy_dissipation_watts' in fp
        assert 'resilience_index' in fp

    def test_pressure_stats_valid(self):
        api = HydraulicAPI()
        api.create_network(
            name='fp_pstats',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        fp = api.hydraulic_fingerprint()
        ps = fp['pressure_stats']
        assert ps['min_m'] <= ps['max_m']
        assert ps['mean_m'] >= 0
        assert ps['count'] > 0

    def test_resilience_index_range(self):
        """Resilience should be 0-1 for a reasonable network."""
        api = HydraulicAPI()
        api.create_network(
            name='fp_res',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 1, 'x': 100, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 300, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 200,
                 'diameter': 300, 'roughness': 130},
            ],
        )
        fp = api.hydraulic_fingerprint()
        assert fp['resilience_index'] >= 0

    def test_energy_positive(self):
        api = HydraulicAPI()
        api.create_network(
            name='fp_energy',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 5, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        fp = api.hydraulic_fingerprint()
        assert fp['energy_dissipation_watts'] >= 0

    def test_headloss_top5_sorted(self):
        api = HydraulicAPI()
        api.create_network(
            name='fp_hl',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 1, 'x': 100, 'y': 0},
                {'id': 'J3', 'elevation': 0, 'demand': 1, 'x': 200, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 200,
                 'diameter': 150, 'roughness': 130},
                {'id': 'P3', 'start': 'J2', 'end': 'J3', 'length': 200,
                 'diameter': 100, 'roughness': 130},
            ],
        )
        fp = api.hydraulic_fingerprint()
        top5 = fp['headloss_top5']
        for i in range(len(top5) - 1):
            assert top5[i]['headloss_m_per_km'] >= top5[i+1]['headloss_m_per_km']

    def test_real_network(self):
        api = HydraulicAPI()
        api.load_network('australian_network.inp')
        fp = api.hydraulic_fingerprint()
        assert fp['pressure_stats']['count'] > 0
        assert fp['total_demand_lps'] > 0

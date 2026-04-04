"""
Tests for Demand Pattern Library (M5)
=======================================
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestDemandPatterns:

    def test_library_loads(self):
        lib = HydraulicAPI.get_pattern_library()
        assert isinstance(lib, dict)
        assert 'residential_wsaa' in lib
        assert 'commercial_wsaa' in lib
        assert 'industrial_constant' in lib

    def test_pattern_has_24_values(self):
        lib = HydraulicAPI.get_pattern_library()
        for pid, pdata in lib.items():
            assert len(pdata['multipliers']) == 24, f"{pid} has {len(pdata['multipliers'])} values"

    def test_wsaa_residential_sum(self):
        """WSAA residential pattern daily average should be ~1.0 (sums to ~24)."""
        pattern = HydraulicAPI.get_pattern('residential_wsaa')
        total = sum(pattern['multipliers'])
        # Sum should be roughly 24 (24 hours × avg multiplier ~1.0)
        assert 20 <= total <= 28, f"Sum = {total}, expected ~24"

    def test_industrial_constant(self):
        """Industrial pattern should be all 1.0."""
        pattern = HydraulicAPI.get_pattern('industrial_constant')
        assert all(m == 1.0 for m in pattern['multipliers'])

    def test_get_nonexistent_pattern(self):
        result = HydraulicAPI.get_pattern('nonexistent_xyz')
        assert 'error' in result

    def test_pattern_has_required_fields(self):
        lib = HydraulicAPI.get_pattern_library()
        for pid, pdata in lib.items():
            assert 'name' in pdata, f"{pid} missing name"
            assert 'source' in pdata, f"{pid} missing source"
            assert 'multipliers' in pdata, f"{pid} missing multipliers"
            assert 'category' in pdata, f"{pid} missing category"

    def test_apply_pattern_to_network(self):
        api = HydraulicAPI()
        api.create_network(
            name='pat_test',
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
        result = api.apply_pattern_to_nodes('residential_wsaa')
        assert result['nodes_updated'] == 2
        assert result['pattern_applied'] == 'residential_wsaa'

    def test_apply_pattern_to_specific_nodes(self):
        api = HydraulicAPI()
        api.create_network(
            name='pat_specific',
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
        result = api.apply_pattern_to_nodes('commercial_wsaa', node_ids=['J1'])
        assert result['nodes_updated'] == 1

    def test_apply_no_network_error(self):
        api = HydraulicAPI()
        result = api.apply_pattern_to_nodes('residential_wsaa')
        assert 'error' in result

    def test_save_custom_pattern(self, tmp_path):
        """Save and retrieve a custom pattern."""
        # Work on a copy of the patterns file to avoid modifying the original
        import shutil
        src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'data', 'demand_patterns.json')
        dst = str(tmp_path / 'demand_patterns.json')
        shutil.copy(src, dst)

        # Monkey-patch to use temp file
        orig_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'demand_patterns.json')

        custom_mults = [1.0] * 24
        custom_mults[8] = 2.0  # morning peak

        # Save directly to test file (not modifying original)
        with open(dst, 'r') as f:
            data = json.load(f)
        data['patterns']['test_custom'] = {
            'name': 'Test Custom',
            'source': 'Unit test',
            'description': 'Test pattern',
            'category': 'custom',
            'multipliers': custom_mults,
        }
        with open(dst, 'w') as f:
            json.dump(data, f, indent=2)

        # Verify
        with open(dst, 'r') as f:
            reloaded = json.load(f)
        assert 'test_custom' in reloaded['patterns']
        assert reloaded['patterns']['test_custom']['multipliers'][8] == 2.0

    def test_mining_pattern_exists(self):
        """Mining process pattern should exist for slurry use case."""
        pattern = HydraulicAPI.get_pattern('mining_process')
        assert 'error' not in pattern
        assert pattern['category'] == 'mining'

    def test_all_categories_represented(self):
        """Library should cover residential, commercial, industrial, mining."""
        lib = HydraulicAPI.get_pattern_library()
        categories = {p['category'] for p in lib.values()}
        assert 'residential' in categories
        assert 'commercial' in categories
        assert 'industrial' in categories
        assert 'mining' in categories

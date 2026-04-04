"""
Tests for Enhanced Network Comparison (M7)
============================================
"""

import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestDetailedComparison:

    def _create_and_save(self, api, name, junctions, pipes, tmp_path):
        """Create network and save as .inp, return path."""
        api.create_network(
            name=name,
            junctions=junctions,
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=pipes,
        )
        path = str(tmp_path / f'{name}.inp')
        import wntr
        wntr.network.write_inpfile(api.wn, path)
        return path

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.detailed_comparison('nonexistent.inp')
        assert 'error' in result

    def test_identical_networks(self, tmp_path):
        """Comparing network with itself should show no changes."""
        api = HydraulicAPI()
        junctions = [
            {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 0, 'demand': 1, 'x': 100, 'y': 0},
        ]
        pipes = [
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
             'diameter': 200, 'roughness': 130},
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 200,
             'diameter': 200, 'roughness': 130},
        ]
        path1 = self._create_and_save(api, 'net1', junctions, pipes, tmp_path)
        api.load_network_from_path(path1)
        result = api.detailed_comparison(path1)
        assert result['total_changes'] == 0

    def test_added_pipe_detected(self, tmp_path):
        """Adding a pipe should appear as 'added' in changelog."""
        api1 = HydraulicAPI()
        junctions = [
            {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 0, 'demand': 1, 'x': 100, 'y': 0},
        ]
        pipes1 = [
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
             'diameter': 200, 'roughness': 130},
        ]
        pipes2 = pipes1 + [
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 200,
             'diameter': 200, 'roughness': 130},
        ]
        path1 = self._create_and_save(api1, 'base', junctions, pipes1, tmp_path)

        api2 = HydraulicAPI()
        path2 = self._create_and_save(api2, 'modified', junctions, pipes2, tmp_path)

        api1.load_network_from_path(path1)
        result = api1.detailed_comparison(path2)
        assert result['categories']['added'] >= 1
        types = [c['type'] for c in result['changelog']]
        assert 'added' in types

    def test_resized_pipe_detected(self, tmp_path):
        """Changing pipe diameter should be categorised as 'resized'."""
        junctions = [
            {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
        ]
        pipes = [
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
             'diameter': 200, 'roughness': 130},
        ]

        api1 = HydraulicAPI()
        path1 = self._create_and_save(api1, 'orig', junctions, pipes, tmp_path)

        # Create modified with larger pipe
        api2 = HydraulicAPI()
        pipes_mod = [
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
             'diameter': 300, 'roughness': 130},
        ]
        path2 = self._create_and_save(api2, 'resized', junctions, pipes_mod, tmp_path)

        api1.load_network_from_path(path1)
        result = api1.detailed_comparison(path2)
        assert result['categories']['resized'] >= 1

    def test_changelog_has_required_fields(self, tmp_path):
        junctions = [
            {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
        ]
        pipes1 = [
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
             'diameter': 200, 'roughness': 130},
        ]
        pipes2 = [
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
             'diameter': 300, 'roughness': 130},
        ]
        api1 = HydraulicAPI()
        path1 = self._create_and_save(api1, 'a', junctions, pipes1, tmp_path)
        api2 = HydraulicAPI()
        path2 = self._create_and_save(api2, 'b', junctions, pipes2, tmp_path)

        api1.load_network_from_path(path1)
        result = api1.detailed_comparison(path2)
        for entry in result['changelog']:
            assert 'type' in entry
            assert 'element' in entry
            assert 'id' in entry
            assert 'colour' in entry
            assert 'description' in entry

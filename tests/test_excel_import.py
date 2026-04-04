"""
Tests for Excel Network Import (N5)
=====================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestExcelImport:

    def _create_test_excel(self, tmp_path, nodes=None, pipes=None):
        """Create a test Excel file with Nodes and Pipes sheets."""
        import pandas as pd

        if nodes is None:
            nodes = [
                {'node_id': 'R1', 'x': 0, 'y': 0, 'elevation': 50, 'demand_lps': 0},
                {'node_id': 'J1', 'x': 100, 'y': 0, 'elevation': 0, 'demand_lps': 5},
                {'node_id': 'J2', 'x': 200, 'y': 0, 'elevation': 0, 'demand_lps': 3},
            ]
        if pipes is None:
            pipes = [
                {'pipe_id': 'P1', 'start_node': 'R1', 'end_node': 'J1',
                 'diameter_mm': 200, 'length_m': 200, 'roughness_C': 130},
                {'pipe_id': 'P2', 'start_node': 'J1', 'end_node': 'J2',
                 'diameter_mm': 150, 'length_m': 150, 'roughness_C': 130},
            ]

        import pandas as pd
        path = str(tmp_path / 'test_network.xlsx')
        with pd.ExcelWriter(path) as writer:
            pd.DataFrame(nodes).to_excel(writer, sheet_name='Nodes', index=False)
            pd.DataFrame(pipes).to_excel(writer, sheet_name='Pipes', index=False)
        return path

    def test_basic_import(self, tmp_path):
        path = self._create_test_excel(tmp_path)
        api = HydraulicAPI()
        result = api.import_from_excel(path)
        assert result['imported'] is True
        assert result['junctions'] == 2
        assert result['reservoirs'] == 1
        assert result['pipes'] == 2

    def test_imported_network_runs(self, tmp_path):
        """Imported network should be analysable."""
        path = self._create_test_excel(tmp_path)
        api = HydraulicAPI()
        api.import_from_excel(path)
        results = api.run_steady_state(save_plot=False)
        assert 'pressures' in results
        assert len(results['pressures']) == 2

    def test_file_not_found(self):
        api = HydraulicAPI()
        result = api.import_from_excel('/nonexistent/file.xlsx')
        assert 'error' in result

    def test_missing_nodes_sheet(self, tmp_path):
        import pandas as pd
        path = str(tmp_path / 'bad.xlsx')
        with pd.ExcelWriter(path) as writer:
            pd.DataFrame([{'pipe_id': 'P1'}]).to_excel(
                writer, sheet_name='Pipes', index=False)
        api = HydraulicAPI()
        result = api.import_from_excel(path)
        assert 'error' in result

    def test_missing_columns(self, tmp_path):
        import pandas as pd
        path = str(tmp_path / 'missing_cols.xlsx')
        with pd.ExcelWriter(path) as writer:
            pd.DataFrame([{'node_id': 'J1', 'x': 0}]).to_excel(
                writer, sheet_name='Nodes', index=False)
            pd.DataFrame([{'pipe_id': 'P1'}]).to_excel(
                writer, sheet_name='Pipes', index=False)
        api = HydraulicAPI()
        result = api.import_from_excel(path)
        assert 'error' in result

    def test_auto_reservoir_detection(self, tmp_path):
        """Node starting with R and zero demand should be reservoir."""
        path = self._create_test_excel(tmp_path)
        api = HydraulicAPI()
        result = api.import_from_excel(path)
        assert result['reservoirs'] == 1
        assert 'R1' in [r for r in api.wn.reservoir_name_list]

    def test_roundtrip_preserves_data(self, tmp_path):
        """Import and check that key properties match."""
        path = self._create_test_excel(tmp_path)
        api = HydraulicAPI()
        api.import_from_excel(path)

        # Check junction elevation
        j1 = api.wn.get_node('J1')
        assert j1.elevation == 0

        # Check pipe diameter
        p1 = api.wn.get_link('P1')
        assert int(p1.diameter * 1000) == 200

        # Check pipe length
        assert p1.length == 200

    def test_warnings_for_bad_references(self, tmp_path):
        """Pipe referencing nonexistent node should generate warning."""
        nodes = [
            {'node_id': 'R1', 'x': 0, 'y': 0, 'elevation': 50, 'demand_lps': 0},
            {'node_id': 'J1', 'x': 100, 'y': 0, 'elevation': 0, 'demand_lps': 5},
        ]
        pipes = [
            {'pipe_id': 'P1', 'start_node': 'R1', 'end_node': 'J1',
             'diameter_mm': 200, 'length_m': 200, 'roughness_C': 130},
            {'pipe_id': 'P2', 'start_node': 'J1', 'end_node': 'J99',
             'diameter_mm': 150, 'length_m': 150, 'roughness_C': 130},
        ]
        path = self._create_test_excel(tmp_path, nodes, pipes)
        api = HydraulicAPI()
        result = api.import_from_excel(path)
        assert result['warning_count'] > 0

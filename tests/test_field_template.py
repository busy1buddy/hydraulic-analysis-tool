"""
Tests for Field Data Collection Template (N7)
===============================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestFieldTemplate:

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.generate_field_template('/tmp/test.xlsx')
        assert 'error' in result

    def test_generates_template(self, tmp_path):
        api = HydraulicAPI()
        api.create_network(
            name='template_test',
            junctions=[
                {'id': 'J1', 'elevation': 50, 'demand': 2, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 55, 'demand': 1, 'x': 100, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 80, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 150,
                 'diameter': 150, 'roughness': 130},
            ],
        )
        path = str(tmp_path / 'field_template.xlsx')
        result = api.generate_field_template(path)
        assert os.path.exists(path)
        assert result['junctions'] == 2
        assert result['pipes'] == 2

    def test_template_has_three_sheets(self, tmp_path):
        api = HydraulicAPI()
        api.create_network(
            name='sheets_test',
            junctions=[{'id': 'J1', 'elevation': 0, 'demand': 1, 'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                     'diameter': 200, 'roughness': 130}],
        )
        path = str(tmp_path / 'sheets.xlsx')
        api.generate_field_template(path)

        import pandas as pd
        xls = pd.ExcelFile(path)
        assert 'Nodes' in xls.sheet_names
        assert 'Pipes' in xls.sheet_names
        assert 'Hydrants' in xls.sheet_names

    def test_nodes_sheet_has_model_data(self, tmp_path):
        api = HydraulicAPI()
        api.create_network(
            name='model_data',
            junctions=[{'id': 'J1', 'elevation': 50, 'demand': 2, 'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 80, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                     'diameter': 200, 'roughness': 130}],
        )
        path = str(tmp_path / 'model.xlsx')
        api.generate_field_template(path)

        import pandas as pd
        nodes = pd.read_excel(path, sheet_name='Nodes')
        assert 'node_id' in nodes.columns
        assert 'elevation_m' in nodes.columns
        assert 'measured_pressure_m' in nodes.columns
        assert nodes.iloc[0]['node_id'] == 'J1'
        assert nodes.iloc[0]['elevation_m'] == 50

    def test_real_network_template(self, tmp_path):
        api = HydraulicAPI()
        api.load_network('australian_network.inp')
        path = str(tmp_path / 'au_template.xlsx')
        result = api.generate_field_template(path)
        assert os.path.exists(path)
        assert result['junctions'] > 0
        assert result['pipes'] > 0

    def test_template_reimports_as_conditions(self, tmp_path):
        """Template pipe sheet should be compatible with import_pipe_conditions_csv."""
        api = HydraulicAPI()
        api.create_network(
            name='reimport',
            junctions=[{'id': 'J1', 'elevation': 0, 'demand': 1, 'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                     'diameter': 200, 'roughness': 130}],
        )
        path = str(tmp_path / 'reimport.xlsx')
        api.generate_field_template(path)

        import pandas as pd
        pipes = pd.read_excel(path, sheet_name='Pipes')
        assert 'pipe_id' in pipes.columns
        assert 'install_year' in pipes.columns
        assert 'condition_score_1to5' in pipes.columns

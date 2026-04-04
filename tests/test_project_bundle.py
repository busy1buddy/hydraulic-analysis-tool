"""
Tests for Project Bundle Export/Import (I9)
=============================================
"""

import os
import sys
import json
import zipfile
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


@pytest.fixture
def api_with_network():
    api = HydraulicAPI()
    api.create_network(
        name='bundle_test',
        junctions=[
            {'id': 'J1', 'elevation': 50, 'demand': 5.0, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 60, 'demand': 3.0, 'x': 100, 'y': 0},
        ],
        reservoirs=[{'id': 'R1', 'head': 100, 'x': -100, 'y': 0}],
        pipes=[
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
             'diameter': 300, 'roughness': 130},
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 400,
             'diameter': 250, 'roughness': 130},
        ],
    )
    return api


class TestProjectBundle:
    """Tests for .hydraulic bundle export/import."""

    def test_export_creates_zip(self, api_with_network, tmp_path):
        path = str(tmp_path / "test.hydraulic")
        api_with_network.export_bundle(path)
        assert os.path.exists(path)
        assert zipfile.is_zipfile(path)

    def test_bundle_contains_inp(self, api_with_network, tmp_path):
        path = str(tmp_path / "test.hydraulic")
        api_with_network.export_bundle(path)
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            inp_files = [n for n in names if n.endswith('.inp')]
            assert len(inp_files) == 1

    def test_bundle_contains_meta(self, api_with_network, tmp_path):
        path = str(tmp_path / "test.hydraulic")
        api_with_network.export_bundle(path)
        with zipfile.ZipFile(path) as zf:
            meta = json.loads(zf.read('meta.json'))
            assert meta['version'] == '1.3.0'
            assert meta['format'] == 'hydraulic-bundle'

    def test_bundle_contains_hap(self, api_with_network, tmp_path):
        path = str(tmp_path / "test.hydraulic")
        api_with_network.export_bundle(path, hap_data={'key': 'value'})
        with zipfile.ZipFile(path) as zf:
            hap = json.loads(zf.read('project.hap'))
            assert hap['key'] == 'value'

    def test_bundle_contains_scenarios(self, api_with_network, tmp_path):
        path = str(tmp_path / "test.hydraulic")
        scenarios = [{'name': 'Base', 'multiplier': 1.0}]
        api_with_network.export_bundle(path, scenarios=scenarios)
        with zipfile.ZipFile(path) as zf:
            sc = json.loads(zf.read('scenarios.json'))
            assert len(sc) == 1
            assert sc[0]['name'] == 'Base'

    def test_import_roundtrip(self, api_with_network, tmp_path):
        """Export then import should restore the network."""
        export_path = str(tmp_path / "roundtrip.hydraulic")
        api_with_network.export_bundle(export_path,
                                        hap_data={'test': True},
                                        scenarios=[{'name': 'A'}])

        # Import with a fresh API
        api2 = HydraulicAPI()
        result = api2.import_bundle(export_path, extract_dir=str(tmp_path / "extract"))

        assert result['inp_path'] is not None
        assert os.path.exists(result['inp_path'])
        assert result['hap_data']['test'] is True
        assert result['scenarios'][0]['name'] == 'A'
        assert result['meta']['version'] == '1.3.0'

    def test_import_loads_network(self, api_with_network, tmp_path):
        """Importing a bundle should make the network available."""
        export_path = str(tmp_path / "load.hydraulic")
        api_with_network.export_bundle(export_path)

        api2 = HydraulicAPI()
        result = api2.import_bundle(export_path, extract_dir=str(tmp_path / "ext"))

        api2.load_network_from_path(result['inp_path'])
        summary = api2.get_network_summary()
        assert summary['junctions'] == 2
        assert summary['pipes'] == 2

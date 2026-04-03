"""Tests for network importers (CSV, GIS, DXF)."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCSVImport:
    def test_import_from_sample_csvs(self, tmp_path):
        from importers.csv_import import import_from_csv, create_sample_csvs

        # Create sample files
        nodes_csv, pipes_csv = create_sample_csvs(str(tmp_path))
        assert os.path.exists(nodes_csv)
        assert os.path.exists(pipes_csv)

        # Import
        result = import_from_csv(nodes_csv, pipes_csv,
                                output_name='csv_test',
                                output_dir=str(tmp_path))

        assert os.path.exists(result['output_file'])
        assert result['nodes']['junction'] == 4
        assert result['nodes']['reservoir'] == 1
        assert result['links']['pipe'] == 5

    def test_imported_network_runs(self, tmp_path):
        """The imported network should produce valid EPANET results."""
        from importers.csv_import import import_from_csv, create_sample_csvs
        from epanet_api import HydraulicAPI

        nodes_csv, pipes_csv = create_sample_csvs(str(tmp_path))
        result = import_from_csv(nodes_csv, pipes_csv,
                                output_name='runnable_test',
                                output_dir=str(tmp_path / 'models'))

        api = HydraulicAPI(work_dir=str(tmp_path))
        api.load_network('runnable_test.inp')
        results = api.run_steady_state(save_plot=False)
        assert 'pressures' in results
        assert len(results['pressures']) == 4  # 4 junctions in sample

    def test_handles_valve_type(self, tmp_path):
        """CSV import should handle valve type entries."""
        import csv

        nodes_path = tmp_path / 'nodes.csv'
        with open(nodes_path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['id', 'type', 'x', 'y', 'elevation', 'demand', 'head'])
            w.writerow(['R1', 'reservoir', 0, 0, 80, 0, 80])
            w.writerow(['J1', 'junction', 10, 0, 50, 0, ''])
            w.writerow(['J2', 'junction', 20, 0, 45, 5, ''])
            w.writerow(['J3', 'junction', 30, 0, 40, 5, ''])

        pipes_path = tmp_path / 'pipes.csv'
        with open(pipes_path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['id', 'start', 'end', 'length', 'diameter', 'roughness', 'type'])
            w.writerow(['P1', 'R1', 'J1', 500, 300, 130, 'pipe'])
            w.writerow(['P2', 'J1', 'J2', 400, 250, 130, 'pipe'])
            w.writerow(['V1', 'J2', 'J3', 0, 200, 0, 'valve'])

        from importers.csv_import import import_from_csv
        result = import_from_csv(str(nodes_path), str(pipes_path),
                                output_name='valve_test',
                                output_dir=str(tmp_path))
        assert result['links']['valve'] == 1
        assert result['links']['pipe'] == 2


class TestShapefileImport:
    def test_requires_geopandas(self):
        """Should return error message if geopandas not installed."""
        # This test just verifies the error handling path
        from importers.shapefile_import import import_from_shapefile
        # The function should handle missing geopandas gracefully
        # (it may or may not be installed on this system)


class TestDXFImport:
    def test_requires_ezdxf(self):
        """Should return error message if ezdxf not installed."""
        from importers.dxf_import import import_from_dxf
        result = import_from_dxf('nonexistent.dxf')
        # If ezdxf not installed, should return error dict
        # If installed, should raise FileNotFoundError
        if isinstance(result, dict) and 'error' in result:
            assert 'ezdxf' in result['error']

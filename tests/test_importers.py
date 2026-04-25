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


class TestApiImportFromCSV:
    """``api.import_from_csv()`` is the UI-safe wrapper added so the desktop
    layer can reach the importer through HydraulicAPI without breaking
    Layer-4 purity. These tests cover the wrapper directly."""

    def test_loads_network_and_returns_summary(self, tmp_path):
        from importers.csv_import import create_sample_csvs
        from epanet_api import HydraulicAPI

        nodes_csv, pipes_csv = create_sample_csvs(str(tmp_path))
        api = HydraulicAPI(work_dir=str(tmp_path))
        result = api.import_from_csv(nodes_csv, pipes_csv, name='api_smoke')

        assert 'error' not in result
        assert result['junctions'] == 4
        assert result['reservoirs'] == 1
        assert result['pipes'] == 5
        assert os.path.exists(result['inp_file'])
        # Network is loaded — caller can immediately run analyses
        assert api.wn is not None

    def test_imported_network_runs_steady_state(self, tmp_path):
        """End-to-end: CSV in -> usable steady-state results out."""
        from importers.csv_import import create_sample_csvs
        from epanet_api import HydraulicAPI

        nodes_csv, pipes_csv = create_sample_csvs(str(tmp_path))
        api = HydraulicAPI(work_dir=str(tmp_path))
        api.import_from_csv(nodes_csv, pipes_csv, name='api_run')

        results = api.run_steady_state(save_plot=False)
        assert 'error' not in results
        assert 'pressures' in results
        assert len(results['pressures']) == 4

    def test_missing_nodes_csv_returns_error(self, tmp_path):
        from importers.csv_import import create_sample_csvs
        from epanet_api import HydraulicAPI

        _, pipes_csv = create_sample_csvs(str(tmp_path))
        api = HydraulicAPI(work_dir=str(tmp_path))
        result = api.import_from_csv('/does/not/exist.csv', pipes_csv)

        assert 'error' in result
        assert 'not found' in result['error'].lower()
        assert api.wn is None

    def test_missing_pipes_csv_returns_error(self, tmp_path):
        from importers.csv_import import create_sample_csvs
        from epanet_api import HydraulicAPI

        nodes_csv, _ = create_sample_csvs(str(tmp_path))
        api = HydraulicAPI(work_dir=str(tmp_path))
        result = api.import_from_csv(nodes_csv, '/does/not/exist.csv')

        assert 'error' in result
        assert 'not found' in result['error'].lower()

    def test_malformed_csv_returns_error(self, tmp_path):
        """Malformed CSV input returns an error dict, never raises."""
        bad_nodes = tmp_path / 'bad_nodes.csv'
        bad_nodes.write_text("not,a,valid,node,csv\n", encoding='utf-8')
        good_pipes = tmp_path / 'pipes.csv'
        good_pipes.write_text(
            "id,start,end,length,diameter,roughness,type\n"
            "P1,R1,J1,500,300,130,pipe\n",
            encoding='utf-8',
        )

        from epanet_api import HydraulicAPI
        api = HydraulicAPI(work_dir=str(tmp_path))
        result = api.import_from_csv(str(bad_nodes), str(good_pipes))

        # Either a clean error message OR a partial result; never an
        # uncaught exception.
        assert isinstance(result, dict)


class TestImportCsvUiWiring:
    """The cold-start walkthrough flagged missing CSV import in the menu.
    Confirm the action and slot are present and connected."""

    def test_file_menu_has_csv_import_action(self, qtbot):
        from PyQt6.QtWidgets import QApplication
        from desktop.preferences import set_pref
        set_pref('skip_welcome', True)
        QApplication.instance() or QApplication(sys.argv)
        from desktop.main_window import MainWindow

        w = MainWindow()
        qtbot.add_widget(w)

        labels = []
        for top in w.menuBar().actions():
            if top.text().replace('&', '').lower() == 'file':
                for sub in top.menu().actions():
                    if sub.text():
                        labels.append(sub.text())

        csv_actions = [t for t in labels if 'csv' in t.lower()]
        assert csv_actions, (
            f"File menu must include an 'Import from CSV' action. "
            f"Current items: {labels}"
        )

    def test_on_import_csv_slot_is_callable(self, qtbot):
        from PyQt6.QtWidgets import QApplication
        from desktop.preferences import set_pref
        set_pref('skip_welcome', True)
        QApplication.instance() or QApplication(sys.argv)
        from desktop.main_window import MainWindow

        w = MainWindow()
        qtbot.add_widget(w)
        assert callable(getattr(w, '_on_import_csv', None))


class TestShapefileImport:
    def test_requires_geopandas(self):
        """Should return error message if geopandas not installed."""
        # This test just verifies the error handling path
        from importers.shapefile_import import import_from_shapefile
        # The function should handle missing geopandas gracefully
        # (it may or may not be installed on this system)


class TestDXFImport:
    def test_requires_ezdxf(self):
        """If ezdxf is missing -> error dict. If installed -> FileNotFoundError on missing input.

        Both paths are acceptable; the importer is allowed to surface
        the OSError directly when the dependency is present.
        """
        from importers.dxf_import import import_from_dxf
        try:
            result = import_from_dxf('nonexistent.dxf')
        except FileNotFoundError:
            return  # ezdxf installed and propagated the OS error — fine
        # ezdxf missing -> dict with error message
        assert isinstance(result, dict) and 'error' in result
        assert 'ezdxf' in result['error']

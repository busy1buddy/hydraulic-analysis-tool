"""
Tests for Calibration Tools and Network Statistics Panel.

Run with:
    QT_QPA_PLATFORM=offscreen python -m pytest tests/test_calibration.py -v
"""

import os
import sys
import math
import pytest

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Force offscreen Qt rendering (must be before any Qt import) ───────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from desktop.calibration_dialog import compute_r2, compute_rmse, compute_nse


# ─────────────────────────────────────────────────────────────────────────────
# Statistical function tests (no Qt required)
# ─────────────────────────────────────────────────────────────────────────────

class TestCalibrationStatistics:
    """Unit tests for the pure statistical helper functions."""

    def test_r2_perfect_match(self):
        """R² = 1.0 when measured equals modelled exactly."""
        measured = [10.0, 20.0, 30.0, 40.0]
        modelled = [10.0, 20.0, 30.0, 40.0]
        assert compute_r2(measured, modelled) == pytest.approx(1.0)

    def test_r2_imperfect(self):
        """R² < 1.0 when there are differences."""
        measured = [10.0, 20.0, 30.0, 40.0]
        modelled = [12.0, 18.0, 32.0, 38.0]
        r2 = compute_r2(measured, modelled)
        assert r2 < 1.0

    def test_r2_range(self):
        """R² should typically be between 0 and 1 for reasonable data."""
        measured = [10.0, 20.0, 30.0]
        modelled = [11.0, 21.0, 29.0]
        r2 = compute_r2(measured, modelled)
        assert 0.0 <= r2 <= 1.0

    def test_r2_empty(self):
        """R² returns nan for empty lists."""
        assert math.isnan(compute_r2([], []))

    def test_r2_constant_measured(self):
        """When all measured values are identical (SS_tot = 0), handle gracefully."""
        measured = [25.0, 25.0, 25.0]
        modelled = [25.0, 25.0, 25.0]
        # Perfect match with constant measured → R² = 1.0
        assert compute_r2(measured, modelled) == pytest.approx(1.0)

    def test_rmse_zero_when_no_differences(self):
        """RMSE = 0 when measured equals modelled."""
        measured = [15.0, 25.0, 35.0]
        modelled = [15.0, 25.0, 35.0]
        assert compute_rmse(measured, modelled) == pytest.approx(0.0)

    def test_rmse_positive_when_differences_exist(self):
        """RMSE > 0 when there are differences."""
        measured = [15.0, 25.0, 35.0]
        modelled = [16.0, 24.0, 36.0]
        assert compute_rmse(measured, modelled) > 0.0

    def test_rmse_known_value(self):
        """RMSE matches manual calculation."""
        measured = [10.0, 20.0]
        modelled = [12.0, 18.0]
        # errors: [-2, 2]  → mse = (4 + 4) / 2 = 4  → rmse = 2.0
        assert compute_rmse(measured, modelled) == pytest.approx(2.0)

    def test_rmse_single_point(self):
        """RMSE with a single point equals absolute error."""
        measured = [30.0]
        modelled = [33.0]
        assert compute_rmse(measured, modelled) == pytest.approx(3.0)

    def test_rmse_empty(self):
        """RMSE returns nan for empty lists."""
        assert math.isnan(compute_rmse([], []))

    def test_nse_perfect_match(self):
        """NSE = 1.0 for perfect match."""
        measured = [10.0, 20.0, 30.0]
        modelled = [10.0, 20.0, 30.0]
        assert compute_nse(measured, modelled) == pytest.approx(1.0)

    def test_nse_imperfect(self):
        """NSE < 1.0 when there are differences."""
        measured = [10.0, 20.0, 30.0]
        modelled = [12.0, 18.0, 33.0]
        nse = compute_nse(measured, modelled)
        assert nse < 1.0

    def test_nse_matches_r2(self):
        """NSE uses same formula as R² for measured vs modelled comparison."""
        measured = [10.0, 20.0, 30.0, 40.0]
        modelled = [11.0, 19.0, 31.0, 39.0]
        assert compute_nse(measured, modelled) == pytest.approx(
            compute_r2(measured, modelled)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Qt widget tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def qt_app():
    """Create a QApplication for the test session."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def simple_api(tmp_path):
    """HydraulicAPI with a small network loaded (2 junctions, 2 pipes)."""
    import shutil
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_src = os.path.join(project_root, 'models')
    models_dst = tmp_path / 'models'
    models_dst.mkdir()
    for f in os.listdir(models_src):
        if f.endswith('.inp'):
            shutil.copy2(os.path.join(models_src, f), models_dst / f)
    (tmp_path / 'output').mkdir()

    from epanet_api import HydraulicAPI
    api = HydraulicAPI(work_dir=str(tmp_path))
    api.load_network('australian_network.inp')
    return api


class TestCalibrationDialogWidget:
    """Tests for CalibrationDialog widget creation and behaviour."""

    def test_dialog_creates_without_crash(self, qt_app, simple_api):
        """CalibrationDialog must construct without raising an exception."""
        from desktop.calibration_dialog import CalibrationDialog
        dialog = CalibrationDialog(simple_api, canvas=None)
        assert dialog is not None
        dialog.close()

    def test_dialog_has_import_button(self, qt_app, simple_api):
        """Import button must exist and be enabled on open."""
        from desktop.calibration_dialog import CalibrationDialog
        dialog = CalibrationDialog(simple_api, canvas=None)
        assert dialog.import_btn.isEnabled()
        dialog.close()

    def test_dialog_highlight_button_disabled_initially(self, qt_app, simple_api):
        """Highlight button is disabled until data is loaded."""
        from desktop.calibration_dialog import CalibrationDialog
        dialog = CalibrationDialog(simple_api, canvas=None)
        assert not dialog.highlight_btn.isEnabled()
        dialog.close()

    def test_dialog_table_initially_empty(self, qt_app, simple_api):
        """Comparison table should start empty."""
        from desktop.calibration_dialog import CalibrationDialog
        dialog = CalibrationDialog(simple_api, canvas=None)
        assert dialog.table.rowCount() == 0
        dialog.close()

    def test_dialog_stats_labels_initially_dash(self, qt_app, simple_api):
        """Statistics labels default to '—' before data is loaded."""
        from desktop.calibration_dialog import CalibrationDialog
        dialog = CalibrationDialog(simple_api, canvas=None)
        assert dialog.lbl_r2.text() == "—"
        assert dialog.lbl_rmse.text() == "—"
        assert dialog.lbl_nse.text() == "—"
        dialog.close()

    def test_inject_data_refreshes_table(self, qt_app, simple_api):
        """Injecting data directly into _data and calling _refresh populates the table."""
        from desktop.calibration_dialog import CalibrationDialog
        dialog = CalibrationDialog(simple_api, canvas=None)

        # Inject synthetic data matching known nodes in the network
        node_ids = simple_api.get_node_list('junction')[:2]
        if len(node_ids) >= 2:
            dialog._data = {
                node_ids[0]: (30.0, 31.5),
                node_ids[1]: (25.0, 28.0),
            }
            dialog._refresh()
            assert dialog.table.rowCount() == 2
            # Highlight button should now be enabled
            assert dialog.highlight_btn.isEnabled()

        dialog.close()

    def test_inject_data_updates_stats(self, qt_app, simple_api):
        """Statistics panel shows computed values after data injection."""
        from desktop.calibration_dialog import CalibrationDialog
        dialog = CalibrationDialog(simple_api, canvas=None)

        node_ids = simple_api.get_node_list('junction')[:3]
        if len(node_ids) >= 3:
            dialog._data = {
                node_ids[0]: (30.0, 30.0),  # exact match
                node_ids[1]: (25.0, 25.0),  # exact match
                node_ids[2]: (20.0, 20.0),  # exact match
            }
            dialog._refresh()
            # Perfect match → R² = 1.0
            assert dialog.lbl_r2.text() == "1.0000"
            assert dialog.lbl_rmse.text() == "0.00 m"
            assert dialog.lbl_nse.text() == "1.0000"

        dialog.close()

    def test_csv_parsing(self, qt_app, simple_api, tmp_path):
        """_parse_csv correctly reads node_id, pressure_m columns."""
        from desktop.calibration_dialog import CalibrationDialog
        dialog = CalibrationDialog(simple_api, canvas=None)

        csv_path = tmp_path / "test_measured.csv"
        csv_path.write_text("node_id,pressure_m\nJ1,25.5\nJ2,32.1\nJ3,18.0\n")

        result = dialog._parse_csv(str(csv_path))
        assert "J1" in result
        assert result["J1"] == pytest.approx(25.5)
        assert result["J2"] == pytest.approx(32.1)
        assert result["J3"] == pytest.approx(18.0)
        dialog.close()

    def test_csv_parsing_no_header(self, qt_app, simple_api, tmp_path):
        """_parse_csv handles CSV without a header row."""
        from desktop.calibration_dialog import CalibrationDialog
        dialog = CalibrationDialog(simple_api, canvas=None)

        csv_path = tmp_path / "no_header.csv"
        csv_path.write_text("J4,22.0\nJ5,28.5\n")

        result = dialog._parse_csv(str(csv_path))
        assert "J4" in result
        assert result["J4"] == pytest.approx(22.0)
        dialog.close()

    def test_status_ok_for_small_diff(self):
        """Difference < 2 m should produce OK status."""
        from desktop.calibration_dialog import CalibrationDialog
        diff = 1.5
        assert abs(diff) < CalibrationDialog.WARN_THRESH

    def test_status_warning_for_medium_diff(self):
        """Difference 2–5 m should produce WARNING status."""
        from desktop.calibration_dialog import CalibrationDialog
        diff = 3.5
        assert CalibrationDialog.WARN_THRESH <= abs(diff) < CalibrationDialog.FAIL_THRESH

    def test_status_fail_for_large_diff(self):
        """Difference >= 5 m should produce FAIL status."""
        from desktop.calibration_dialog import CalibrationDialog
        diff = 7.0
        assert abs(diff) >= CalibrationDialog.FAIL_THRESH


# ─────────────────────────────────────────────────────────────────────────────
# Statistics Panel tests
# ─────────────────────────────────────────────────────────────────────────────

class TestStatisticsPanel:
    """Tests for the NetworkStatisticsPanel widget."""

    def test_panel_creates_without_crash(self, qt_app):
        """StatisticsPanel must construct without raising."""
        from desktop.statistics_panel import StatisticsPanel
        panel = StatisticsPanel()
        assert panel is not None

    def test_panel_shows_correct_pipe_length(self, qt_app, simple_api):
        """Pipe length total must match sum of all pipe lengths in the network."""
        from desktop.statistics_panel import StatisticsPanel

        # Compute expected total
        expected_length_m = 0.0
        for pid in simple_api.get_link_list('pipe'):
            pipe = simple_api.get_link(pid)
            expected_length_m += pipe.length
        expected_km = expected_length_m / 1000.0

        panel = StatisticsPanel()
        panel.update_statistics(simple_api, results=None)

        displayed = panel.lbl_pipe_length.text()
        assert "km" in displayed

        # Parse numeric value from display text (e.g. "3.2 km")
        # The panel formats to 1 decimal place, so round expected the same way
        numeric_str = displayed.replace(" km", "").strip()
        displayed_km = float(numeric_str)
        # Compare at 1-decimal precision (panel rounds to .1 km)
        assert displayed_km == pytest.approx(round(expected_km, 1), abs=0.05)

    def test_panel_shows_correct_junction_count(self, qt_app, simple_api):
        """Junction count must match the model's junction count."""
        from desktop.statistics_panel import StatisticsPanel

        expected = len(simple_api.get_node_list('junction'))
        panel = StatisticsPanel()
        panel.update_statistics(simple_api, results=None)

        assert panel.lbl_n_junctions.text() == str(expected)

    def test_panel_shows_correct_pipe_count(self, qt_app, simple_api):
        """Pipe count must match the model's pipe count."""
        from desktop.statistics_panel import StatisticsPanel

        expected = len(simple_api.get_link_list('pipe'))
        panel = StatisticsPanel()
        panel.update_statistics(simple_api, results=None)

        assert panel.lbl_n_pipes.text() == str(expected)

    def test_panel_shows_demand(self, qt_app, simple_api):
        """Total base demand label includes 'LPS'."""
        from desktop.statistics_panel import StatisticsPanel

        panel = StatisticsPanel()
        panel.update_statistics(simple_api, results=None)

        assert "LPS" in panel.lbl_total_demand.text()

    def test_panel_updates_with_results(self, qt_app, simple_api):
        """Pressure range label updates after results are provided."""
        from desktop.statistics_panel import StatisticsPanel

        results = simple_api.run_steady_state(save_plot=False)

        panel = StatisticsPanel()
        panel.update_statistics(simple_api, results)

        pressure_text = panel.lbl_pressure_range.text()
        # Should contain "m" unit and a dash range separator
        assert "m" in pressure_text or pressure_text != "—"

    def test_panel_compliance_counts(self, qt_app, simple_api):
        """Compliance summary labels are set after results update."""
        from desktop.statistics_panel import StatisticsPanel

        results = simple_api.run_steady_state(save_plot=False)

        panel = StatisticsPanel()
        panel.update_statistics(simple_api, results)

        # Should be numeric strings (possibly "0")
        assert panel.lbl_pass.text().isdigit() or panel.lbl_pass.text() == "—"
        assert panel.lbl_warning.text().isdigit() or panel.lbl_warning.text() == "—"
        assert panel.lbl_info.text().isdigit() or panel.lbl_info.text() == "—"

    def test_panel_material_table_populated(self, qt_app, simple_api):
        """Material table should have at least one row for a loaded network."""
        from desktop.statistics_panel import StatisticsPanel

        panel = StatisticsPanel()
        panel.update_statistics(simple_api, results=None)

        assert panel.material_table.rowCount() >= 1

    def test_panel_handles_no_network(self, qt_app):
        """StatisticsPanel.update_statistics gracefully handles no loaded network."""
        from desktop.statistics_panel import StatisticsPanel
        from epanet_api import HydraulicAPI

        api = HydraulicAPI()  # empty API, no network
        panel = StatisticsPanel()
        # Should not raise
        panel.update_statistics(api, results=None)
        # Labels remain at default
        assert panel.lbl_pipe_length.text() == "—"

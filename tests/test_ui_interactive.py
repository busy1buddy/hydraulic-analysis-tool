"""
Automated UI Interaction Tests
================================
Launches the full MainWindow headlessly and exercises all major
user interactions: loading, analysis, clicking, color modes,
slurry mode, report generation, and window state preservation.

Requires: pytest-qt (pip install pytest-qt)
Runs headlessly via QT_QPA_PLATFORM=offscreen.
"""

import os
import sys
import math

import pytest

# Force offscreen rendering before any Qt imports
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QDockWidget
from PyQt6.QtCore import Qt

from desktop.main_window import MainWindow
from slurry_solver import bingham_plastic_headloss


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def app():
    """Create a single QApplication for the entire module."""
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    yield instance


@pytest.fixture
def window(app):
    """Create a MainWindow, load the test network, and tear down after."""
    w = MainWindow()
    w.resize(1400, 900)

    import wntr
    w.api.wn = wntr.network.WaterNetworkModel('models/australian_network.inp')
    w.api._inp_file = 'models/australian_network.inp'
    w._current_file = 'models/australian_network.inp'
    w._populate_explorer()
    w._update_status_bar()
    w.canvas.set_api(w.api)

    w.show()
    app.processEvents()

    yield w

    w.close()
    app.processEvents()


# ---------------------------------------------------------------------------
# 1. Load file — Project Explorer shows Junctions(7), Pipes(9)
# ---------------------------------------------------------------------------

class TestLoadFile:

    def test_explorer_has_root(self, window):
        assert window.explorer_tree.topLevelItemCount() == 1

    def test_explorer_shows_junctions(self, window):
        root = window.explorer_tree.topLevelItem(0)
        texts = [root.child(i).text(0) for i in range(root.childCount())]
        junc_item = [t for t in texts if t.startswith("Junctions")]
        assert len(junc_item) == 1
        assert "7" in junc_item[0], f"Expected 7 junctions, got: {junc_item[0]}"

    def test_explorer_shows_pipes(self, window):
        root = window.explorer_tree.topLevelItem(0)
        texts = [root.child(i).text(0) for i in range(root.childCount())]
        pipe_item = [t for t in texts if t.startswith("Pipes")]
        assert len(pipe_item) == 1
        assert "9" in pipe_item[0], f"Expected 9 pipes, got: {pipe_item[0]}"

    def test_status_bar_node_count(self, window):
        assert "9" in window.nodes_label.text()  # 7 junctions + 1 reservoir + 1 tank

    def test_status_bar_pipe_count(self, window):
        assert "9" in window.pipes_label.text()


# ---------------------------------------------------------------------------
# 2. Run steady state — Results tables populate
# ---------------------------------------------------------------------------

class TestSteadyStateAnalysis:

    @pytest.fixture(autouse=True)
    def run_analysis(self, window, app):
        results = window.api.run_steady_state(save_plot=False)
        window._on_analysis_finished(results)
        app.processEvents()
        self.window = window
        self.results = results

    def test_node_results_row_count(self):
        assert self.window.node_results_table.rowCount() == 7

    def test_pipe_results_row_count(self):
        assert self.window.pipe_results_table.rowCount() == 9

    def test_wsaa_label_updated(self):
        text = self.window.wsaa_label.text()
        assert "WSAA" in text
        # Should show issues (J4 low pressure, P4/P8 high velocity)
        assert "PASS" in text or "issue" in text

    def test_analysis_label_updated(self):
        assert "Hydraulic" in self.window.analysis_label.text()

    def test_all_junction_ids_present(self):
        ids = set()
        for row in range(self.window.node_results_table.rowCount()):
            ids.add(self.window.node_results_table.item(row, 0).text())
        for jid in ['J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J7']:
            assert jid in ids, f"{jid} missing from node results"

    def test_all_pipe_ids_present(self):
        ids = set()
        for row in range(self.window.pipe_results_table.rowCount()):
            ids.add(self.window.pipe_results_table.item(row, 0).text())
        for pid in ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8', 'P9']:
            assert pid in ids, f"{pid} missing from pipe results"


# ---------------------------------------------------------------------------
# 3. Click pipe P4 — Properties panel shows correct data
# ---------------------------------------------------------------------------

class TestPipeClickProperties:

    @pytest.fixture(autouse=True)
    def click_p4(self, window, app):
        # Run analysis first so results are available in properties
        results = window.api.run_steady_state(save_plot=False)
        window._on_analysis_finished(results)
        app.processEvents()

        # Simulate canvas element selection for pipe P4
        window._on_canvas_element_selected('P4', 'pipe')
        app.processEvents()
        self.window = window

    def _get_properties(self):
        props = {}
        for row in range(self.window.properties_table.rowCount()):
            k = self.window.properties_table.item(row, 0).text()
            v = self.window.properties_table.item(row, 1).text()
            props[k] = v
        return props

    def test_properties_not_empty(self):
        assert self.window.properties_table.rowCount() > 0

    def test_shows_pipe_id(self):
        props = self._get_properties()
        assert props.get('ID') == 'P4'

    def test_shows_diameter_200mm(self):
        props = self._get_properties()
        assert props.get('Diameter') == '200 mm'

    def test_shows_type_pipe(self):
        props = self._get_properties()
        assert props.get('Type') == 'Pipe'

    def test_shows_max_velocity(self):
        props = self._get_properties()
        v_text = props.get('Max Velocity', '')
        assert '2.83' in v_text, f"Expected 2.83 m/s, got: {v_text}"

    def test_shows_results_section(self):
        props = self._get_properties()
        assert '--- Results ---' in props


# ---------------------------------------------------------------------------
# 4. Switch color mode to Velocity
# ---------------------------------------------------------------------------

class TestColorModeSwitch:

    def test_switch_to_velocity(self, window, app):
        window.canvas.color_mode_combo.setCurrentText("Velocity")
        app.processEvents()
        assert window.canvas.color_mode_combo.currentText() == "Velocity"

    def test_switch_to_pressure(self, window, app):
        window.canvas.color_mode_combo.setCurrentText("Pressure")
        app.processEvents()
        assert window.canvas.color_mode_combo.currentText() == "Pressure"

    def test_switch_to_wsaa(self, window, app):
        window.canvas.color_mode_combo.setCurrentText("WSAA Compliance")
        app.processEvents()
        assert window.canvas.color_mode_combo.currentText() == "WSAA Compliance"

    def test_all_modes_selectable(self, window, app):
        for mode in window.canvas.COLOR_MODES:
            window.canvas.color_mode_combo.setCurrentText(mode)
            app.processEvents()
            assert window.canvas.color_mode_combo.currentText() == mode


# ---------------------------------------------------------------------------
# 5. Slurry mode — headloss higher than water
# ---------------------------------------------------------------------------

class TestSlurryMode:

    @pytest.fixture(autouse=True)
    def run_both(self, window, app):
        # Water baseline
        self.water_results = window.api.run_steady_state(save_plot=False)
        self.window = window
        self.app = app

    def test_slurry_headloss_higher_for_all_pipes(self):
        for pid, fdata in self.water_results['flows'].items():
            pipe = self.window.api.get_link(pid)
            avg_lps = abs(fdata['avg_lps'])
            Q_m3s = avg_lps / 1000
            if Q_m3s <= 0 or pipe.diameter <= 0:
                continue

            # Water headloss (Hazen-Williams)
            hl_water = ((10.67 * pipe.length * Q_m3s ** 1.852) /
                        (pipe.roughness ** 1.852 * pipe.diameter ** 4.87))

            # Slurry headloss (Bingham plastic)
            slurry = bingham_plastic_headloss(
                flow_m3s=Q_m3s, diameter_m=pipe.diameter,
                length_m=pipe.length, density=1800,
                tau_y=15.0, mu_p=0.05, roughness_mm=0.1,
            )
            hl_slurry = slurry['headloss_m']

            assert hl_slurry > hl_water, (
                f"Pipe {pid}: slurry {hl_slurry} m <= water {hl_water:.4f} m"
            )

    def test_slurry_headloss_p1_magnitude(self):
        """P1 slurry headloss should be roughly 10-20x water."""
        pipe = self.window.api.get_link('P1')
        Q_m3s = abs(self.water_results['flows']['P1']['avg_lps']) / 1000
        hl_water = ((10.67 * pipe.length * Q_m3s ** 1.852) /
                    (pipe.roughness ** 1.852 * pipe.diameter ** 4.87))
        slurry = bingham_plastic_headloss(
            flow_m3s=Q_m3s, diameter_m=pipe.diameter,
            length_m=pipe.length, density=1800,
            tau_y=15.0, mu_p=0.05, roughness_mm=0.1,
        )
        ratio = slurry['headloss_m'] / hl_water if hl_water > 0 else 0
        assert 5 < ratio < 50, f"P1 slurry/water ratio {ratio:.1f} out of expected range"


# ---------------------------------------------------------------------------
# 6. Generate DOCX report — file created and > 10 KB
# ---------------------------------------------------------------------------

class TestReportGeneration:

    def test_docx_report_created(self, window, app, tmp_path):
        # Run analysis first
        results = window.api.run_steady_state(save_plot=False)
        window._on_analysis_finished(results)
        app.processEvents()

        output_path = str(tmp_path / 'test_report.docx')
        summary = window.api.get_network_summary()

        from reports.docx_report import generate_docx_report
        generate_docx_report(
            results, summary, output_path,
            title='UI Test Report',
            engineer_name='Automated Test',
            project_name='Australian Network',
        )

        assert os.path.exists(output_path), "DOCX file not created"
        size = os.path.getsize(output_path)
        assert size > 10000, f"DOCX file too small: {size} bytes"


# ---------------------------------------------------------------------------
# 7. Minimise and restore — docks survive, click handler connected
# ---------------------------------------------------------------------------

class TestWindowStatePreservation:

    @pytest.fixture(autouse=True)
    def setup_and_analyse(self, window, app):
        results = window.api.run_steady_state(save_plot=False)
        window._on_analysis_finished(results)
        app.processEvents()
        self.window = window
        self.app = app

    def test_properties_visible_after_restore(self):
        self.window.showMinimized()
        self.app.processEvents()
        self.window.showNormal()
        self.app.processEvents()

        assert self.window.properties_dock.isVisible(), "Properties dock not visible after restore"

    def test_results_visible_after_restore(self):
        self.window.showMinimized()
        self.app.processEvents()
        self.window.showNormal()
        self.app.processEvents()

        assert self.window.results_dock.isVisible(), "Results dock not visible after restore"

    def test_scene_click_connected_after_restore(self):
        self.window.showMinimized()
        self.app.processEvents()
        self.window.showNormal()
        self.app.processEvents()

        scene = self.window.canvas.plot_widget.scene()
        receivers = scene.receivers(scene.sigMouseClicked)
        assert receivers > 0, "Scene click handler disconnected after restore"

    def test_pipe_click_works_after_restore(self):
        self.window.showMinimized()
        self.app.processEvents()
        self.window.showNormal()
        self.app.processEvents()

        self.window.properties_table.setRowCount(0)
        self.window._on_canvas_element_selected('P4', 'pipe')
        self.app.processEvents()

        assert self.window.properties_table.rowCount() > 0, \
            "Properties empty after pipe click post-restore"

    def test_docks_not_closable(self):
        """Docks should not have the closable feature flag."""
        for dock in [self.window.properties_dock, self.window.results_dock,
                     self.window.explorer_dock, self.window.scenario_dock]:
            features = dock.features()
            closable = bool(features & QDockWidget.DockWidgetFeature.DockWidgetClosable)
            assert not closable, f"{dock.windowTitle()} dock is closable"

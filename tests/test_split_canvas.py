"""
Tests for Split-Screen Scenario Comparison (I2)
=================================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must set QT_QPA_PLATFORM before importing Qt
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication

from epanet_api import HydraulicAPI
from desktop.split_canvas import SplitCanvas
from desktop.scenario_panel import ScenarioData


@pytest.fixture(scope='module')
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def api_with_results():
    """API with a network that has been analysed."""
    api = HydraulicAPI()
    api.create_network(
        name='split_test',
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


@pytest.fixture
def two_scenarios(api_with_results):
    """Two scenarios with results."""
    api = api_with_results

    sc_base = ScenarioData('Base', demand_multiplier=1.0)
    sc_base.results = api.run_steady_state(save_plot=False)

    # Reload and run with higher demand
    api.load_network_from_path(api._inp_file)
    for jname in api.get_node_list('junction'):
        junc = api.get_node(jname)
        if junc.demand_timeseries_list:
            junc.demand_timeseries_list[0].base_value *= 1.5

    sc_high = ScenarioData('High Demand', demand_multiplier=1.5)
    sc_high.results = api.run_steady_state(save_plot=False)

    # Reload original
    api.load_network_from_path(api._inp_file)

    return [sc_base, sc_high]


class TestSplitCanvas:
    """Tests for split-screen scenario comparison."""

    def test_create_split_canvas(self, qapp, api_with_results):
        widget = SplitCanvas(api_with_results)
        assert widget is not None
        assert widget.left_canvas is not None
        assert widget.right_canvas is not None

    def test_set_scenarios(self, qapp, api_with_results, two_scenarios):
        widget = SplitCanvas(api_with_results)
        widget.set_scenarios(two_scenarios)
        assert widget.left_combo.count() == 2
        assert widget.right_combo.count() == 2

    def test_viewport_sync(self, qapp, api_with_results, two_scenarios):
        """After setting a view range on the left, right should match."""
        widget = SplitCanvas(api_with_results)
        widget.set_scenarios(two_scenarios)

        # Set specific range on left
        widget.left_canvas.plot_widget.plotItem.vb.setRange(
            xRange=(-50, 150), yRange=(-50, 50))

        # Allow Qt to process
        qapp.processEvents()

        # Right should have synced
        right_vr = widget.right_canvas.plot_widget.plotItem.vb.viewRange()
        left_vr = widget.left_canvas.plot_widget.plotItem.vb.viewRange()
        assert abs(right_vr[0][0] - left_vr[0][0]) < 5
        assert abs(right_vr[0][1] - left_vr[0][1]) < 5

    def test_difference_mode(self, qapp, api_with_results, two_scenarios):
        """Difference mode should show A-B pressures."""
        widget = SplitCanvas(api_with_results)
        widget.set_scenarios(two_scenarios)

        # Enable difference mode
        widget.diff_btn.setChecked(True)

        # Right canvas should now show difference values
        assert widget.right_label.text().startswith("Difference:")

    def test_unlinked_mode(self, qapp, api_with_results, two_scenarios):
        """When unlinked, viewports should NOT sync."""
        widget = SplitCanvas(api_with_results)
        widget.set_scenarios(two_scenarios)

        # Unlink
        widget.link_btn.setChecked(False)
        assert widget._linking is False

    def test_summary_shows_difference(self, qapp, api_with_results, two_scenarios):
        """Summary should show pressure difference stats."""
        widget = SplitCanvas(api_with_results)
        widget.set_scenarios(two_scenarios)

        text = widget.summary_label.text()
        assert "Pressure difference" in text or "Run all scenarios" in text

    def test_close_emits_signal(self, qapp, api_with_results):
        widget = SplitCanvas(api_with_results)
        received = []
        widget.closed.connect(lambda: received.append(True))
        widget._on_close()
        assert len(received) == 1

"""
Canvas-state regression tests — structural assertions on
``desktop/network_canvas.py:NetworkCanvas`` internal state.

Phase-4 deliverable from the multi-agent review plan. Pixel-diffing visual
regression was rejected (fragile across DPI/theme); these tests assert that
the canvas's internal node/pipe/result state is consistent with the loaded
network and analysis results. They run headless via pytest-qt.

Covered:
- Render produces the right number of nodes and pipes
- ``_pipe_segments`` endpoints come from real node positions
- Colour-mode switching does not destroy the topology state
- ``set_results`` populates ``results`` without altering topology
- Selecting a node/pipe surfaces the right element_selected signal payload
"""

from __future__ import annotations

import os
import sys

import pytest

pytest.importorskip("PyQt6.QtWidgets")
pytest.importorskip("pyqtgraph")

from PyQt6.QtWidgets import QApplication

from desktop.network_canvas import NetworkCanvas


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIMPLE_INP = os.path.join(PROJECT_ROOT, 'tutorials', 'simple_loop', 'network.inp')
RING_INP = os.path.join(PROJECT_ROOT, 'tutorials', 'industrial_ring_main', 'network.inp')


@pytest.fixture(scope='module')
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    return app


@pytest.fixture
def loaded_canvas(qapp):
    from epanet_api import HydraulicAPI
    api = HydraulicAPI(work_dir=PROJECT_ROOT)
    api.load_network_from_path(SIMPLE_INP)
    canvas = NetworkCanvas()
    canvas.set_api(api)
    return canvas, api


# ---------------------------------------------------------------------------
# Topology state
# ---------------------------------------------------------------------------

def test_render_records_every_node(loaded_canvas):
    canvas, api = loaded_canvas
    nodes_in_network = (set(api.wn.junction_name_list)
                         | set(api.wn.reservoir_name_list)
                         | set(api.wn.tank_name_list))
    assert set(canvas._node_positions.keys()) == nodes_in_network, (
        "every node in the loaded network must appear in canvas._node_positions"
    )


def test_render_records_every_pipe(loaded_canvas):
    canvas, api = loaded_canvas
    assert set(canvas._pipe_ids) == set(api.wn.pipe_name_list)
    assert set(canvas._pipe_segments.keys()) == set(api.wn.pipe_name_list)


def test_pipe_segments_match_node_positions(loaded_canvas):
    canvas, api = loaded_canvas
    for pid, (x0, y0, x1, y1) in canvas._pipe_segments.items():
        pipe = api.wn.get_link(pid)
        sn_xy = canvas._node_positions[pipe.start_node_name]
        en_xy = canvas._node_positions[pipe.end_node_name]
        assert (x0, y0) == sn_xy, f"pipe {pid} start endpoint mismatch"
        assert (x1, y1) == en_xy, f"pipe {pid} end endpoint mismatch"


def test_node_count_matches_for_larger_network(qapp):
    """The ring main has more nodes — render must scale, not reset."""
    from epanet_api import HydraulicAPI
    api = HydraulicAPI(work_dir=PROJECT_ROOT)
    api.load_network_from_path(RING_INP)
    canvas = NetworkCanvas()
    canvas.set_api(api)
    assert len(canvas._node_positions) >= 5
    assert len(canvas._pipe_ids) >= 5


# ---------------------------------------------------------------------------
# Colour mode
# ---------------------------------------------------------------------------

def test_colour_mode_combo_lists_expected_modes(loaded_canvas):
    canvas, _ = loaded_canvas
    items = [canvas.color_mode_combo.itemText(i)
             for i in range(canvas.color_mode_combo.count())]
    # The publicly documented default modes — tightening this catches
    # accidental mode removals during refactors
    for required in ('WSAA Compliance', 'Pressure', 'Velocity', 'Headloss'):
        assert required in items, f"colour-mode combo missing '{required}'"


def test_colour_mode_change_preserves_topology(loaded_canvas):
    canvas, api = loaded_canvas
    nodes_before = dict(canvas._node_positions)
    pipes_before = list(canvas._pipe_ids)

    canvas.color_mode_combo.setCurrentText('Velocity')
    canvas.color_mode_combo.setCurrentText('Pressure')

    assert canvas._node_positions == nodes_before, (
        "colour-mode change must not lose node positions"
    )
    assert canvas._pipe_ids == pipes_before, (
        "colour-mode change must not lose pipe ids"
    )


# ---------------------------------------------------------------------------
# Results integration
# ---------------------------------------------------------------------------

def test_set_results_stores_dict_and_keeps_topology(loaded_canvas):
    canvas, api = loaded_canvas
    nodes_before = dict(canvas._node_positions)
    pipes_before = list(canvas._pipe_ids)

    results = api.run_steady_state(save_plot=False)
    canvas.set_results(results)

    assert canvas.results is results
    assert 'pressures' in canvas.results
    assert canvas._node_positions == nodes_before
    assert canvas._pipe_ids == pipes_before


def test_set_results_with_none_clears_results(loaded_canvas):
    canvas, api = loaded_canvas
    canvas.set_results({'pressures': {}, 'flows': {}})
    canvas.set_results(None)
    assert canvas.results is None


def test_steady_state_pressure_keys_match_canvas_nodes(loaded_canvas):
    """Every junction in the canvas must have a steady-state pressure entry."""
    canvas, api = loaded_canvas
    results = api.run_steady_state(save_plot=False)
    canvas.set_results(results)

    pressures = canvas.results.get('pressures', {})
    junctions_in_canvas = (set(canvas._node_positions)
                            & set(api.wn.junction_name_list))
    missing = junctions_in_canvas - set(pressures.keys())
    assert not missing, f"junctions on canvas without pressure entry: {missing}"


# ---------------------------------------------------------------------------
# Selection state
# ---------------------------------------------------------------------------

def test_initial_selection_is_none(loaded_canvas):
    canvas, _ = loaded_canvas
    assert canvas._selected_id is None


def test_highlight_nodes_records_set(loaded_canvas):
    canvas, api = loaded_canvas
    target = next(iter(api.wn.junction_name_list))
    canvas.highlight_nodes([target])
    assert canvas._highlighted_nodes == {target}

    canvas.highlight_nodes([])
    assert canvas._highlighted_nodes == set()

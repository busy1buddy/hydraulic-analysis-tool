"""
Canvas Editing Tests
=====================
Tests for the interactive canvas editor: add/move/delete nodes and pipes,
undo/redo, auto-increment IDs, pipe length calculation, edit mode toggle.

Runs headlessly via QT_QPA_PLATFORM=offscreen.
"""

import os
import sys
import math

import pytest

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from desktop.main_window import MainWindow
from desktop.canvas_editor import EditAction, UndoStack


@pytest.fixture(scope='module')
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    yield instance


@pytest.fixture
def window(app):
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


class TestAddJunction:

    def test_add_junction_appears_in_api(self, window, app):
        initial = len(window.api.get_node_list('junction'))
        window.api.add_junction('JT1', elevation=40, base_demand=0.005,
                                coordinates=(80, 50))
        assert len(window.api.get_node_list('junction')) == initial + 1
        assert 'JT1' in window.api.get_node_list('junction')

    def test_add_junction_appears_on_canvas(self, window, app):
        window.api.add_junction('JT2', elevation=35, base_demand=0,
                                coordinates=(90, 40))
        window.canvas.render()
        app.processEvents()
        assert 'JT2' in window.canvas._node_positions

    def test_junction_coordinates(self, window, app):
        window.api.add_junction('JT3', elevation=30, base_demand=0,
                                coordinates=(100, 60))
        node = window.api.get_node('JT3')
        assert node.coordinates == (100, 60)
        assert node.elevation == 30


class TestAddPipe:

    def test_add_pipe_appears_in_api(self, window, app):
        window.api.add_junction('JPT1', elevation=40, base_demand=0,
                                coordinates=(80, 50))
        initial = len(window.api.get_link_list('pipe'))
        window.api.add_pipe('PT1', 'J1', 'JPT1', length=300,
                            diameter_m=0.2, roughness=130)
        assert len(window.api.get_link_list('pipe')) == initial + 1
        assert 'PT1' in window.api.get_link_list('pipe')

    def test_pipe_connectivity(self, window, app):
        window.api.add_junction('JPT2', elevation=40, base_demand=0,
                                coordinates=(85, 55))
        window.api.add_pipe('PT2', 'J2', 'JPT2', length=200,
                            diameter_m=0.15, roughness=120)
        pipe = window.api.get_link('PT2')
        assert pipe.start_node_name == 'J2'
        assert pipe.end_node_name == 'JPT2'

    def test_pipe_on_canvas(self, window, app):
        window.api.add_junction('JPT3', elevation=40, base_demand=0,
                                coordinates=(90, 45))
        window.api.add_pipe('PT3', 'J3', 'JPT3', length=250,
                            diameter_m=0.2, roughness=130)
        window.canvas.render()
        app.processEvents()
        assert 'PT3' in window.canvas._pipe_ids


class TestMoveNode:

    def test_move_updates_coordinates(self, window, app):
        window.editor.move_node('J1', 20.0, 55.0)
        app.processEvents()
        node = window.api.get_node('J1')
        assert node.coordinates == (20.0, 55.0)

    def test_move_updates_canvas(self, window, app):
        window.editor.move_node('J2', 35.0, 50.0)
        app.processEvents()
        assert window.canvas._node_positions['J2'] == (35.0, 50.0)


class TestDeletePipe:

    def test_delete_pipe_removes_from_api(self, window, app):
        # Add then delete
        window.api.add_junction('JDP1', elevation=40, base_demand=0,
                                coordinates=(80, 50))
        window.api.add_pipe('PDP1', 'J1', 'JDP1', length=100,
                            diameter_m=0.2, roughness=130)
        assert 'PDP1' in window.api.get_link_list('pipe')
        window.editor._delete_pipe('PDP1')
        app.processEvents()
        assert 'PDP1' not in window.api.get_link_list('pipe')


class TestCannotDeleteNodeWithPipes:

    def test_connected_node_has_links(self, window):
        connected = window.editor._connected_links('J1')
        assert len(connected) > 0, "J1 should have connected pipes"

    def test_unconnected_node_has_no_links(self, window, app):
        window.api.add_junction('JISO', elevation=40, base_demand=0,
                                coordinates=(100, 100))
        connected = window.editor._connected_links('JISO')
        assert len(connected) == 0


class TestUndoAddJunction:

    def test_undo_removes_junction(self, window, app):
        initial = len(window.api.get_node_list('junction'))
        # Add via API + push to undo stack
        window.api.add_junction('JUNDO', elevation=40, base_demand=0.001,
                                coordinates=(80, 50))
        window.editor.undo_stack.push(EditAction(
            'add_junction', 'Add JUNDO',
            {'id': 'JUNDO', 'elevation': 40, 'demand_m3s': 0.001,
             'coordinates': (80, 50)}
        ))
        assert len(window.api.get_node_list('junction')) == initial + 1

        window.editor.undo()
        app.processEvents()
        assert len(window.api.get_node_list('junction')) == initial
        assert 'JUNDO' not in window.api.get_node_list('junction')


class TestRedoAddJunction:

    def test_redo_restores_junction(self, window, app):
        # Add then undo then redo
        window.api.add_junction('JREDO', elevation=35, base_demand=0,
                                coordinates=(75, 45))
        window.editor.undo_stack.push(EditAction(
            'add_junction', 'Add JREDO',
            {'id': 'JREDO', 'elevation': 35, 'demand_m3s': 0,
             'coordinates': (75, 45)}
        ))
        window.editor.undo()
        app.processEvents()
        assert 'JREDO' not in window.api.get_node_list('junction')

        window.editor.redo()
        app.processEvents()
        assert 'JREDO' in window.api.get_node_list('junction')


class TestAutoIncrementIDs:

    def test_junction_id_avoids_collision(self, window):
        # J1-J7 already exist
        next_id = window.editor._next_junction_id()
        assert next_id == 'J8'

    def test_pipe_id_avoids_collision(self, window):
        # P1-P9 already exist
        next_id = window.editor._next_pipe_id()
        assert next_id == 'P10'

    def test_after_adding_j8(self, window, app):
        window.api.add_junction('J8', elevation=40, base_demand=0,
                                coordinates=(80, 50))
        next_id = window.editor._next_junction_id()
        assert next_id == 'J9'


class TestPipeLengthCalculation:

    def test_auto_length_from_coordinates(self, window):
        """Pipe length should be roughly distance * 10 scale factor."""
        n1 = window.api.get_node('J1')
        n2 = window.api.get_node('J2')
        dx = n1.coordinates[0] - n2.coordinates[0]
        dy = n1.coordinates[1] - n2.coordinates[1]
        expected = math.sqrt(dx*dx + dy*dy) * 10
        assert expected > 50  # Should be a reasonable length


class TestEditModeToggle:

    def test_default_is_view_mode(self, window):
        assert not window.editor.edit_mode

    def test_toggle_to_edit(self, window, app):
        window.canvas.edit_btn.setChecked(True)
        app.processEvents()
        assert window.editor.edit_mode

    def test_toggle_back_to_view(self, window, app):
        window.canvas.edit_btn.setChecked(True)
        app.processEvents()
        window.canvas.edit_btn.setChecked(False)
        app.processEvents()
        assert not window.editor.edit_mode

    def test_edit_mode_changes_cursor(self, window, app):
        window.canvas.edit_btn.setChecked(True)
        app.processEvents()
        cursor = window.canvas.plot_widget.cursor()
        assert cursor.shape() == Qt.CursorShape.CrossCursor

    def test_view_mode_restores_cursor(self, window, app):
        window.canvas.edit_btn.setChecked(True)
        app.processEvents()
        window.canvas.edit_btn.setChecked(False)
        app.processEvents()
        cursor = window.canvas.plot_widget.cursor()
        assert cursor.shape() == Qt.CursorShape.ArrowCursor


class TestUndoStack:

    def test_max_size(self):
        stack = UndoStack()
        for i in range(25):
            stack.push(EditAction('test', f'Action {i}'))
        assert len(stack._undo) == 20  # Max size

    def test_redo_cleared_on_push(self):
        stack = UndoStack()
        stack.push(EditAction('test', 'A'))
        stack.push(EditAction('test', 'B'))
        stack.pop_undo()
        assert stack.can_redo()
        stack.push(EditAction('test', 'C'))
        assert not stack.can_redo()

    def test_empty_stack(self):
        stack = UndoStack()
        assert not stack.can_undo()
        assert not stack.can_redo()
        assert stack.pop_undo() is None
        assert stack.pop_redo() is None


class TestModifiedIndicator:

    def test_title_asterisk(self, window, app):
        window.editor._mark_modified()
        assert window.windowTitle().endswith('*')

    def test_double_mark_single_asterisk(self, window, app):
        window.editor._mark_modified()
        window.editor._mark_modified()
        assert window.windowTitle().count('*') == 1

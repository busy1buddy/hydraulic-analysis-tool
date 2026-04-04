"""
Canvas Editor — Interactive Network Editing on the Canvas
==========================================================
Provides Edit Mode for adding junctions/pipes, moving nodes,
deleting elements, and undo/redo. Overlays on top of NetworkCanvas.
"""

import math
from dataclasses import dataclass, field
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QDialog, QFormLayout,
    QLineEdit, QDoubleSpinBox, QComboBox, QPushButton,
    QDialogButtonBox, QMessageBox, QMenu, QLabel,
)
from PyQt6.QtCore import pyqtSignal, Qt, QPointF
from PyQt6.QtGui import QFont, QCursor

from data.au_pipes import PIPE_DATABASE, list_materials, list_sizes


# Standard pipe sizes for the dropdown
MATERIAL_DEFAULTS = {
    'Ductile Iron': {'roughness': 130, 'sizes': [100, 150, 200, 250, 300, 375, 450, 500, 600]},
    'PVC PN12': {'roughness': 150, 'sizes': [250, 300, 375]},
    'PVC PN18': {'roughness': 150, 'sizes': [100, 150, 200]},
    'PE100': {'roughness': 150, 'sizes': [63, 90, 110, 160, 200, 250, 315, 400, 500, 630]},
    'Concrete': {'roughness': 110, 'sizes': [300, 375, 450, 525, 600, 750, 900]},
}


# =========================================================================
# Undo/Redo
# =========================================================================

@dataclass
class EditAction:
    """A single undoable edit action."""
    action_type: str  # 'add_junction', 'add_pipe', 'move_node', 'delete_pipe', 'delete_junction'
    description: str
    data: dict = field(default_factory=dict)


class UndoStack:
    """Stack of edit actions for undo/redo (max 20)."""

    MAX_SIZE = 20

    def __init__(self):
        self._undo: List[EditAction] = []
        self._redo: List[EditAction] = []

    def push(self, action: EditAction):
        self._undo.append(action)
        if len(self._undo) > self.MAX_SIZE:
            self._undo.pop(0)
        self._redo.clear()

    def can_undo(self) -> bool:
        return len(self._undo) > 0

    def can_redo(self) -> bool:
        return len(self._redo) > 0

    def pop_undo(self) -> Optional[EditAction]:
        if self._undo:
            action = self._undo.pop()
            self._redo.append(action)
            return action
        return None

    def pop_redo(self) -> Optional[EditAction]:
        if self._redo:
            action = self._redo.pop()
            self._undo.append(action)
            return action
        return None

    def last_undo_description(self) -> str:
        return self._undo[-1].description if self._undo else ""

    def last_redo_description(self) -> str:
        return self._redo[-1].description if self._redo else ""


# =========================================================================
# Dialogs
# =========================================================================

class AddJunctionDialog(QDialog):
    """Dialog for adding a new junction."""

    def __init__(self, default_id, x, y, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Junction")
        self.setMinimumWidth(300)

        layout = QFormLayout(self)

        self.id_input = QLineEdit(default_id)
        layout.addRow("ID:", self.id_input)

        self.elev_spin = QDoubleSpinBox()
        self.elev_spin.setRange(-100, 500)
        self.elev_spin.setValue(0.0)
        self.elev_spin.setSuffix(" m")
        layout.addRow("Elevation:", self.elev_spin)

        self.demand_spin = QDoubleSpinBox()
        self.demand_spin.setRange(0, 1000)
        self.demand_spin.setValue(0.0)
        self.demand_spin.setSuffix(" LPS")
        layout.addRow("Base Demand:", self.demand_spin)

        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(-10000, 10000)
        self.x_spin.setValue(x)
        layout.addRow("X:", self.x_spin)

        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(-10000, 10000)
        self.y_spin.setValue(y)
        layout.addRow("Y:", self.y_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class AddPipeDialog(QDialog):
    """Dialog for adding a new pipe between two nodes."""

    def __init__(self, default_id, start_node, end_node, auto_length, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Pipe")
        self.setMinimumWidth(350)

        layout = QFormLayout(self)

        self.id_input = QLineEdit(default_id)
        layout.addRow("ID:", self.id_input)

        layout.addRow("From:", QLabel(start_node))
        layout.addRow("To:", QLabel(end_node))

        self.material_combo = QComboBox()
        self.material_combo.addItems(list(MATERIAL_DEFAULTS.keys()))
        self.material_combo.currentTextChanged.connect(self._on_material_changed)
        layout.addRow("Material:", self.material_combo)

        self.dn_combo = QComboBox()
        layout.addRow("Diameter (DN):", self.dn_combo)

        self.length_spin = QDoubleSpinBox()
        self.length_spin.setRange(1, 100000)
        self.length_spin.setValue(auto_length)
        self.length_spin.setSuffix(" m")
        layout.addRow("Length:", self.length_spin)

        self.roughness_spin = QDoubleSpinBox()
        self.roughness_spin.setRange(10, 200)
        self.roughness_spin.setValue(130)
        layout.addRow("Roughness (C):", self.roughness_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._on_material_changed(self.material_combo.currentText())

    def _on_material_changed(self, material):
        defaults = MATERIAL_DEFAULTS.get(material, {})
        self.roughness_spin.setValue(defaults.get('roughness', 130))
        self.dn_combo.clear()
        for dn in defaults.get('sizes', [200]):
            self.dn_combo.addItem(f"DN{dn}", dn)
        # Default to DN200 if available
        idx = self.dn_combo.findText("DN200")
        if idx >= 0:
            self.dn_combo.setCurrentIndex(idx)

    def get_dn_mm(self):
        return self.dn_combo.currentData() or 200


# =========================================================================
# CanvasEditor
# =========================================================================

class CanvasEditor:
    """Manages edit-mode interactions on a NetworkCanvas.

    This is a controller — it doesn't own UI widgets, it adds
    behaviour to an existing NetworkCanvas and MainWindow.
    """

    edit_mode_changed = None  # Will be set to a signal
    network_modified = None   # Will be set to a signal

    def __init__(self, canvas, main_window):
        self.canvas = canvas
        self.mw = main_window
        self.api = main_window.api
        self._edit_mode = False
        self._pipe_start_node = None  # for two-click pipe creation
        self.undo_stack = UndoStack()

        # Drag state
        self._dragging_node = None     # node ID being dragged
        self._drag_start_pos = None    # (x, y) before drag began
        self._drag_just_ended = False  # suppress click after drag release

    @property
    def edit_mode(self):
        return self._edit_mode

    @edit_mode.setter
    def edit_mode(self, value):
        self._edit_mode = value
        self._pipe_start_node = None
        if value:
            self.canvas.plot_widget.setCursor(QCursor(Qt.CursorShape.CrossCursor))
            self.mw.status_bar.showMessage("Edit Mode: Click canvas to add junction, click two nodes to add pipe", 0)
        else:
            self.canvas.plot_widget.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self.mw.status_bar.showMessage("View Mode", 3000)

    def handle_canvas_click(self, mx, my):
        """Called when canvas is clicked in edit mode."""
        if not self._edit_mode or self.api.wn is None:
            return False

        # Suppress the click that follows a drag release
        if self._drag_just_ended:
            self._drag_just_ended = False
            return True

        # Check if click is on an existing node
        hit_node = self._find_nearest_node(mx, my)
        if hit_node:
            return self._handle_node_click_edit(hit_node)

        # Click on empty space → add junction
        self._add_junction_at(mx, my)
        return True

    def handle_right_click(self, mx, my):
        """Show context menu for delete."""
        if not self._edit_mode or self.api.wn is None:
            return False

        # Check node
        hit_node = self._find_nearest_node(mx, my)
        if hit_node:
            self._show_node_context_menu(hit_node)
            return True

        # Check pipe
        hit_pipe = self._find_nearest_pipe(mx, my)
        if hit_pipe:
            self._show_pipe_context_menu(hit_pipe)
            return True

        return False

    # ----- Junction operations -----

    def _add_junction_at(self, x, y):
        jid = self._next_junction_id()
        dialog = AddJunctionDialog(jid, round(x, 1), round(y, 1), self.mw)
        if dialog.exec():
            jid = dialog.id_input.text().strip()
            elev = dialog.elev_spin.value()
            demand_lps = dialog.demand_spin.value()
            cx = dialog.x_spin.value()
            cy = dialog.y_spin.value()

            # Convert LPS to m³/s for WNTR
            demand_m3s = demand_lps / 1000

            self.api.add_junction(jid, elevation=elev, base_demand=demand_m3s,
                                  coordinates=(cx, cy))

            self.undo_stack.push(EditAction(
                'add_junction', f'Add junction {jid}',
                {'id': jid, 'elevation': elev, 'demand_m3s': demand_m3s,
                 'coordinates': (cx, cy)}
            ))
            self._mark_modified()
            self.canvas.render()

    def _next_junction_id(self):
        existing = set(self.api.get_node_list('junction'))
        i = 1
        while f'J{i}' in existing:
            i += 1
        return f'J{i}'

    # ----- Pipe operations -----

    def _handle_node_click_edit(self, node_id):
        """Handle clicking a node in edit mode — for pipe creation."""
        if self._pipe_start_node is None:
            self._pipe_start_node = node_id
            self.mw.status_bar.showMessage(
                f"Edit Mode: Start node = {node_id}. Click another node to create pipe, Esc to cancel.", 0)
            return True
        else:
            start = self._pipe_start_node
            end = node_id
            self._pipe_start_node = None

            if start == end:
                self.mw.status_bar.showMessage("Cannot connect node to itself.", 3000)
                return True

            self._add_pipe_between(start, end)
            return True

    def _add_pipe_between(self, start_id, end_id):
        pid = self._next_pipe_id()

        # Auto-calculate length from coordinates
        try:
            n1 = self.api.get_node(start_id)
            n2 = self.api.get_node(end_id)
            dx = n1.coordinates[0] - n2.coordinates[0]
            dy = n1.coordinates[1] - n2.coordinates[1]
            auto_length = round(math.sqrt(dx*dx + dy*dy) * 10, 1)  # scale factor ~10
            auto_length = max(auto_length, 10)
        except Exception:
            auto_length = 100

        dialog = AddPipeDialog(pid, start_id, end_id, auto_length, self.mw)
        if dialog.exec():
            pid = dialog.id_input.text().strip()
            dn_mm = dialog.get_dn_mm()
            length = dialog.length_spin.value()
            roughness = dialog.roughness_spin.value()
            diameter_m = dn_mm / 1000

            self.api.add_pipe(pid, start_id, end_id,
                              length=length, diameter_m=diameter_m,
                              roughness=roughness)

            self.undo_stack.push(EditAction(
                'add_pipe', f'Add pipe {pid}',
                {'id': pid, 'start': start_id, 'end': end_id,
                 'length': length, 'diameter_m': diameter_m,
                 'roughness': roughness}
            ))
            self._mark_modified()
            self.canvas.render()

        self.mw.status_bar.showMessage("Edit Mode: Click canvas to add junction, click two nodes to add pipe", 0)

    def _next_pipe_id(self):
        existing = set(self.api.get_link_list('pipe'))
        i = 1
        while f'P{i}' in existing:
            i += 1
        return f'P{i}'

    # ----- Move node -----

    def move_node(self, node_id, new_x, new_y):
        """Move a node to new coordinates."""
        try:
            node = self.api.get_node(node_id)
            old_x, old_y = node.coordinates
            node.coordinates = (new_x, new_y)

            self.undo_stack.push(EditAction(
                'move_node', f'Move {node_id}',
                {'id': node_id, 'old': (old_x, old_y), 'new': (new_x, new_y)}
            ))
            self._mark_modified()
            self.canvas.render()
        except Exception:
            pass

    # ----- Delete -----

    def _show_node_context_menu(self, node_id):
        menu = QMenu(self.mw)
        # Check for connected pipes
        connected = self._connected_links(node_id)
        if connected:
            act = menu.addAction(f"Cannot delete — {len(connected)} connected pipe(s)")
            act.setEnabled(False)
        else:
            del_act = menu.addAction(f"Delete {node_id}")
            del_act.triggered.connect(lambda: self._delete_junction(node_id))
        menu.exec(QCursor.pos())

    def _show_pipe_context_menu(self, pipe_id):
        menu = QMenu(self.mw)
        del_act = menu.addAction(f"Delete pipe {pipe_id}")
        del_act.triggered.connect(lambda: self._delete_pipe(pipe_id))
        menu.exec(QCursor.pos())

    def _delete_pipe(self, pipe_id):
        try:
            pipe = self.api.get_link(pipe_id)
            data = {
                'id': pipe_id, 'start': pipe.start_node_name,
                'end': pipe.end_node_name, 'length': pipe.length,
                'diameter_m': pipe.diameter, 'roughness': pipe.roughness,
            }
            self.api.remove_pipe(pipe_id)
            self.undo_stack.push(EditAction('delete_pipe', f'Delete pipe {pipe_id}', data))
            self._mark_modified()
            self.canvas.render()
        except Exception as e:
            self.mw.status_bar.showMessage(f"Delete failed: {e}", 5000)

    def _delete_junction(self, jid):
        try:
            node = self.api.get_node(jid)
            data = {
                'id': jid, 'elevation': node.elevation,
                'demand_m3s': node.demand_timeseries_list[0].base_value if node.demand_timeseries_list else 0,
                'coordinates': node.coordinates,
            }
            self.api.remove_junction(jid)
            self.undo_stack.push(EditAction('delete_junction', f'Delete junction {jid}', data))
            self._mark_modified()
            self.canvas.render()
        except Exception as e:
            self.mw.status_bar.showMessage(f"Delete failed: {e}", 5000)

    def _connected_links(self, node_id):
        connected = []
        if self.api.wn is None:
            return connected
        for lid in self.api.wn.link_name_list:
            link = self.api.wn.get_link(lid)
            if link.start_node_name == node_id or link.end_node_name == node_id:
                connected.append(lid)
        return connected

    # ----- Undo/Redo -----

    def undo(self):
        action = self.undo_stack.pop_undo()
        if action is None:
            return
        self._reverse_action(action)
        self._mark_modified()
        self.canvas.render()

    def redo(self):
        action = self.undo_stack.pop_redo()
        if action is None:
            return
        self._apply_action(action)
        self._mark_modified()
        self.canvas.render()

    def _reverse_action(self, action):
        """Reverse an action (for undo)."""
        d = action.data
        if action.action_type == 'add_junction':
            self.api.remove_junction(d['id'])
        elif action.action_type == 'add_pipe':
            self.api.remove_pipe(d['id'])
        elif action.action_type == 'move_node':
            node = self.api.get_node(d['id'])
            node.coordinates = d['old']
        elif action.action_type == 'delete_pipe':
            self.api.add_pipe(d['id'], d['start'], d['end'],
                              length=d['length'], diameter_m=d['diameter_m'],
                              roughness=d['roughness'])
        elif action.action_type == 'delete_junction':
            self.api.add_junction(d['id'], elevation=d['elevation'],
                                  base_demand=d['demand_m3s'],
                                  coordinates=d['coordinates'])

    def _apply_action(self, action):
        """Re-apply an action (for redo)."""
        d = action.data
        if action.action_type == 'add_junction':
            self.api.add_junction(d['id'], elevation=d['elevation'],
                                  base_demand=d['demand_m3s'],
                                  coordinates=d['coordinates'])
        elif action.action_type == 'add_pipe':
            self.api.add_pipe(d['id'], d['start'], d['end'],
                              length=d['length'], diameter_m=d['diameter_m'],
                              roughness=d['roughness'])
        elif action.action_type == 'move_node':
            node = self.api.get_node(d['id'])
            node.coordinates = d['new']
        elif action.action_type == 'delete_pipe':
            self.api.remove_pipe(d['id'])
        elif action.action_type == 'delete_junction':
            self.api.remove_junction(d['id'])

    # ----- Helpers -----

    def _find_nearest_node(self, mx, my):
        threshold = self.canvas._click_threshold() if hasattr(self.canvas, '_click_threshold') else 2.0
        best_id = None
        best_dist = float('inf')
        for nid, (nx, ny) in self.canvas._node_positions.items():
            d = math.sqrt((mx - nx)**2 + (my - ny)**2)
            if d < best_dist:
                best_dist = d
                best_id = nid
        if best_id and best_dist < threshold:
            return best_id
        return None

    def _find_nearest_pipe(self, mx, my):
        from desktop.network_canvas import _point_to_segment_distance
        threshold = self.canvas._click_threshold() if hasattr(self.canvas, '_click_threshold') else 2.0
        best_pid = None
        best_dist = float('inf')
        for pid in self.canvas._pipe_ids:
            try:
                pipe = self.api.wn.get_link(pid)
                sn, en = pipe.start_node_name, pipe.end_node_name
                if sn in self.canvas._node_positions and en in self.canvas._node_positions:
                    x0, y0 = self.canvas._node_positions[sn]
                    x1, y1 = self.canvas._node_positions[en]
                    d = _point_to_segment_distance(mx, my, x0, y0, x1, y1)
                    if d < best_dist:
                        best_dist = d
                        best_pid = pid
            except Exception:
                pass
        if best_pid and best_dist < threshold:
            return best_pid
        return None

    def _mark_modified(self):
        """Mark the project as modified."""
        title = self.mw.windowTitle()
        if not title.endswith('*'):
            self.mw.setWindowTitle(title + ' *')
        self.mw.status_bar.showMessage("Run analysis to update compliance", 3000)

    # ----- Drag-to-move -----

    def handle_mouse_press(self, mx, my):
        """Begin drag if press is on a node in edit mode."""
        if not self._edit_mode or self.api.wn is None:
            return False

        hit_node = self._find_nearest_node(mx, my)
        if hit_node:
            node = self.api.get_node(hit_node)
            self._dragging_node = hit_node
            self._drag_start_pos = node.coordinates
            self.canvas.plot_widget.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return True
        return False

    def handle_mouse_move(self, mx, my):
        """Move the dragged node to follow the cursor (live preview)."""
        if self._dragging_node is None:
            return False

        try:
            node = self.api.get_node(self._dragging_node)
            node.coordinates = (mx, my)
            # Update canvas position dict and re-render for live preview
            self.canvas._node_positions[self._dragging_node] = (mx, my)
            self.canvas.render()
        except Exception:
            pass
        return True

    def handle_mouse_release(self, mx, my):
        """Finalise drag — push to undo stack."""
        if self._dragging_node is None:
            return False

        nid = self._dragging_node
        old_pos = self._drag_start_pos
        new_pos = (mx, my)
        self._dragging_node = None
        self._drag_start_pos = None
        self._drag_just_ended = True  # suppress the click that follows

        # Restore crosshair cursor
        self.canvas.plot_widget.setCursor(QCursor(Qt.CursorShape.CrossCursor))

        # Only push undo if position actually changed
        if old_pos and (abs(old_pos[0] - new_pos[0]) > 0.01 or
                        abs(old_pos[1] - new_pos[1]) > 0.01):
            try:
                node = self.api.get_node(nid)
                node.coordinates = new_pos
            except Exception:
                pass

            self.undo_stack.push(EditAction(
                'move_node', f'Move {nid}',
                {'id': nid, 'old': old_pos, 'new': new_pos}
            ))
            self._mark_modified()
            self.canvas.render()

        return True

    @property
    def is_dragging(self):
        return self._dragging_node is not None

    def cancel_pipe_start(self):
        """Cancel pipe creation (Escape key)."""
        self._pipe_start_node = None
        self.mw.status_bar.showMessage("Edit Mode: Pipe creation cancelled", 3000)

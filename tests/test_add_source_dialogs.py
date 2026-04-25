"""
Tests for AddReservoirDialog, AddTankDialog, and the canvas Edit-mode
add-mode switch. PR #4 of the cold-start UX roadmap.
"""

from __future__ import annotations

import os
import sys

import pytest

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication

from desktop.preferences import set_pref


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def qapp():
    set_pref('skip_welcome', True)
    return QApplication.instance() or QApplication(sys.argv)


# ---------------------------------------------------------------------------
# AddReservoirDialog
# ---------------------------------------------------------------------------

class TestAddReservoirDialog:
    def test_default_values(self, qapp):
        from desktop.canvas_editor import AddReservoirDialog
        dlg = AddReservoirDialog('R1', 50.0, 75.0)
        assert dlg.id_input.text() == 'R1'
        assert dlg.head_spin.value() == 50.0
        assert dlg.x_spin.value() == 50.0
        assert dlg.y_spin.value() == 75.0

    def test_head_range_supports_australian_ahd(self, qapp):
        """The dialog accepts -100..2500 m AHD (Lake Eyre to Kosciuszko)."""
        from desktop.canvas_editor import AddReservoirDialog
        dlg = AddReservoirDialog('R1', 0, 0)
        # Negative head (Lake Eyre depth) accepted
        dlg.head_spin.setValue(-15.0)
        assert dlg.head_spin.value() == -15.0
        # Mountain reservoir accepted
        dlg.head_spin.setValue(2200.0)
        assert dlg.head_spin.value() == 2200.0


class TestAddTankDialog:
    def test_default_values_match_wsaa_typical(self, qapp):
        from desktop.canvas_editor import AddTankDialog
        dlg = AddTankDialog('T1', 100, 200)
        assert dlg.id_input.text() == 'T1'
        assert dlg.elev_spin.value() == 50.0
        assert dlg.init_level_spin.value() == 3.0
        assert dlg.min_level_spin.value() == 0.5
        assert dlg.max_level_spin.value() == 5.0
        assert dlg.diameter_spin.value() == 10.0


# ---------------------------------------------------------------------------
# CanvasEditor add-mode switch
# ---------------------------------------------------------------------------

class TestAddModeSwitch:
    def _stub_window(self, qtbot):
        from desktop.main_window import MainWindow
        w = MainWindow()
        qtbot.add_widget(w)
        # Bootstrap a fresh project so api.wn is non-None and we have one source
        w.api.bootstrap_project(name='pr4_test', source_type='reservoir',
                                 source_head_m=50.0)
        w.canvas.set_api(w.api)
        return w

    def test_default_add_mode_is_junction(self, qapp, qtbot):
        w = self._stub_window(qtbot)
        from desktop.canvas_editor import CanvasEditor
        assert w.editor.add_mode == CanvasEditor.ADD_MODE_JUNCTION

    def test_combo_switches_editor_add_mode(self, qapp, qtbot):
        w = self._stub_window(qtbot)
        w.canvas.add_mode_combo.setCurrentIndex(1)  # Reservoir
        assert w.editor.add_mode == 'reservoir'

        w.canvas.add_mode_combo.setCurrentIndex(2)  # Tank
        assert w.editor.add_mode == 'tank'

        w.canvas.add_mode_combo.setCurrentIndex(0)  # back to Junction
        assert w.editor.add_mode == 'junction'

    def test_setting_unknown_add_mode_raises(self, qapp, qtbot):
        w = self._stub_window(qtbot)
        with pytest.raises(ValueError):
            w.editor.add_mode = 'aquifer'

    def test_combo_has_three_items(self, qapp, qtbot):
        w = self._stub_window(qtbot)
        items = [w.canvas.add_mode_combo.itemText(i)
                  for i in range(w.canvas.add_mode_combo.count())]
        assert len(items) == 3
        assert any('Junction' in t for t in items)
        assert any('Reservoir' in t for t in items)
        assert any('Tank' in t for t in items)


# ---------------------------------------------------------------------------
# Click-routing through the editor
# ---------------------------------------------------------------------------

class TestClickRouting:
    """Confirm that handle_canvas_click adds the right kind of node based on
    the current add_mode. We can't synthesise mouse events trivially, so we
    stub the dialog and call handle_canvas_click directly."""

    def _stub_window(self, qtbot):
        from desktop.main_window import MainWindow
        w = MainWindow()
        qtbot.add_widget(w)
        w.api.bootstrap_project(name='pr4_click', source_type='reservoir',
                                 source_head_m=50.0)
        w.canvas.set_api(w.api)
        w.editor.edit_mode = True
        return w

    def _stub_dialog(self, module_attr_name, returned_id, **field_values):
        """Patch a dialog class on canvas_editor to a stub that auto-accepts
        and returns pre-set widget values."""
        from desktop import canvas_editor as ce

        class StubDialog:
            def __init__(self, default_id, x, y, parent=None):
                from PyQt6.QtWidgets import QLineEdit, QDoubleSpinBox
                self.id_input = QLineEdit(returned_id)
                self.x_spin = QDoubleSpinBox()
                self.x_spin.setRange(-9_999_999, 9_999_999)
                self.x_spin.setValue(x)
                self.y_spin = QDoubleSpinBox()
                self.y_spin.setRange(-9_999_999, 9_999_999)
                self.y_spin.setValue(y)
                for name, val in field_values.items():
                    spin = QDoubleSpinBox()
                    spin.setRange(-9_999_999, 9_999_999)
                    spin.setValue(val)
                    setattr(self, name, spin)

            def exec(self):
                return 1

        original = getattr(ce, module_attr_name)
        setattr(ce, module_attr_name, StubDialog)
        return original

    def test_junction_mode_click_adds_junction(self, qapp, qtbot):
        w = self._stub_window(qtbot)
        n_before = len(w.api.wn.junction_name_list)

        original = self._stub_dialog(
            'AddJunctionDialog', 'J7',
            elev_spin=42.0, demand_spin=0.05)
        try:
            w.editor.add_mode = 'junction'
            w.editor.handle_canvas_click(100.0, 200.0)
        finally:
            from desktop import canvas_editor as ce
            ce.AddJunctionDialog = original

        assert len(w.api.wn.junction_name_list) == n_before + 1
        assert 'J7' in w.api.wn.junction_name_list

    def test_reservoir_mode_click_adds_reservoir(self, qapp, qtbot):
        w = self._stub_window(qtbot)
        n_before = len(w.api.wn.reservoir_name_list)

        original = self._stub_dialog(
            'AddReservoirDialog', 'R7', head_spin=80.0)
        try:
            w.editor.add_mode = 'reservoir'
            w.editor.handle_canvas_click(150.0, 250.0)
        finally:
            from desktop import canvas_editor as ce
            ce.AddReservoirDialog = original

        assert len(w.api.wn.reservoir_name_list) == n_before + 1
        assert 'R7' in w.api.wn.reservoir_name_list
        # No new junction added
        assert len(w.api.wn.junction_name_list) == 0

    def test_tank_mode_click_adds_tank(self, qapp, qtbot):
        w = self._stub_window(qtbot)
        n_before = len(w.api.wn.tank_name_list)

        original = self._stub_dialog(
            'AddTankDialog', 'T7',
            elev_spin=60.0,
            init_level_spin=3.0,
            min_level_spin=0.5,
            max_level_spin=5.0,
            diameter_spin=10.0,
        )
        try:
            w.editor.add_mode = 'tank'
            w.editor.handle_canvas_click(200.0, 300.0)
        finally:
            from desktop import canvas_editor as ce
            ce.AddTankDialog = original

        assert len(w.api.wn.tank_name_list) == n_before + 1
        assert 'T7' in w.api.wn.tank_name_list

    def test_id_auto_increments(self, qapp, qtbot):
        """Adding two reservoirs in a row produces R2 (R1 already exists from bootstrap)."""
        w = self._stub_window(qtbot)
        # The bootstrap created R1 already

        from desktop import canvas_editor as ce
        original = ce.AddReservoirDialog

        class IdCapturingStub:
            captured = []

            def __init__(self, default_id, x, y, parent=None):
                IdCapturingStub.captured.append(default_id)
                # Reject so no actual reservoir is added — we just want to know
                # what ID would be defaulted
                pass

            def exec(self):
                return 0

        ce.AddReservoirDialog = IdCapturingStub
        try:
            w.editor.add_mode = 'reservoir'
            w.editor.handle_canvas_click(100, 100)
        finally:
            ce.AddReservoirDialog = original

        # The default ID offered to the user must be 'R2' since 'R1' is the
        # bootstrap source.
        assert IdCapturingStub.captured == ['R2']

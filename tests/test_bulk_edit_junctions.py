"""
Tests for the Bulk Edit Junctions dialog and CanvasEditor controller method.

PR #3 of the cold-start UX roadmap. Closes the asymmetric-bulk-editing
friction (Bulk Edit Pipes existed; junctions did not).
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
# Dialog
# ---------------------------------------------------------------------------

class TestBulkJunctionEditDialog:
    def test_no_fields_ticked_returns_empty_dict(self, qapp):
        """User opens the dialog and clicks OK without ticking anything —
        the controller should treat this as 'no change'."""
        from desktop.canvas_editor import BulkJunctionEditDialog
        dlg = BulkJunctionEditDialog(junction_ids=['J1', 'J2', 'J3'])
        assert dlg.get_values() == {}

    def test_title_includes_count(self, qapp):
        from desktop.canvas_editor import BulkJunctionEditDialog
        dlg = BulkJunctionEditDialog(junction_ids=['J1', 'J2', 'J3', 'J4', 'J5'])
        assert '5' in dlg.windowTitle()

    def test_elevation_field_collected_when_ticked(self, qapp):
        from desktop.canvas_editor import BulkJunctionEditDialog
        dlg = BulkJunctionEditDialog(junction_ids=['J1'])
        dlg.apply_elev_cb.setChecked(True)
        dlg.elev_spin.setValue(42.5)
        assert dlg.get_values() == {'elevation_m': 42.5}

    def test_absolute_demand_excludes_percentage(self, qapp):
        """Ticking absolute demand auto-unticks percentage demand."""
        from desktop.canvas_editor import BulkJunctionEditDialog
        dlg = BulkJunctionEditDialog(junction_ids=['J1'])

        dlg.apply_demand_pct_cb.setChecked(True)
        assert dlg.apply_demand_pct_cb.isChecked()

        dlg.apply_demand_cb.setChecked(True)
        assert not dlg.apply_demand_pct_cb.isChecked()

    def test_percentage_demand_excludes_absolute(self, qapp):
        from desktop.canvas_editor import BulkJunctionEditDialog
        dlg = BulkJunctionEditDialog(junction_ids=['J1'])

        dlg.apply_demand_cb.setChecked(True)
        assert dlg.apply_demand_cb.isChecked()

        dlg.apply_demand_pct_cb.setChecked(True)
        assert not dlg.apply_demand_cb.isChecked()

    def test_pattern_dropdown_lists_provided_patterns(self, qapp):
        from desktop.canvas_editor import BulkJunctionEditDialog
        dlg = BulkJunctionEditDialog(
            junction_ids=['J1'], available_patterns=['DAILY', 'PEAK', 'FIRE'])

        labels = [dlg.pattern_combo.itemText(i)
                   for i in range(dlg.pattern_combo.count())]
        assert '(none)' in labels
        for p in ('DAILY', 'PEAK', 'FIRE'):
            assert p in labels


# ---------------------------------------------------------------------------
# CanvasEditor.bulk_edit_junctions
# ---------------------------------------------------------------------------

class TestBulkEditJunctionsController:
    def _make_window_with_loop(self, qtbot):
        """Helper: a MainWindow with simple_loop loaded (6 junctions)."""
        from desktop.main_window import MainWindow
        w = MainWindow()
        qtbot.add_widget(w)
        tut = os.path.join(PROJECT_ROOT, 'tutorials', 'simple_loop', 'network.inp')
        w.api.load_network_from_path(tut)
        w.canvas.set_api(w.api)
        return w

    def _stub_dialog(self, returned_values: dict):
        """Patch BulkJunctionEditDialog so .exec() returns 1 (Accepted)
        and .get_values() returns the supplied dict."""
        from desktop import canvas_editor as ce

        class StubDialog:
            def __init__(self, parent=None, junction_ids=None,
                          available_patterns=None):
                self.junction_ids = junction_ids or []

            def exec(self):
                return 1

            def get_values(self):
                return dict(returned_values)

        original = ce.BulkJunctionEditDialog
        ce.BulkJunctionEditDialog = StubDialog
        return original

    def test_uniform_elevation_applies_to_all_junctions(self, qapp, qtbot):
        w = self._make_window_with_loop(qtbot)
        original = self._stub_dialog({'elevation_m': 100.0})
        try:
            w.editor.bulk_edit_junctions()
        finally:
            from desktop import canvas_editor as ce
            ce.BulkJunctionEditDialog = original

        for jid in w.api.wn.junction_name_list:
            assert w.api.wn.get_node(jid).elevation == pytest.approx(100.0)

    def test_uniform_absolute_demand_applies_to_all(self, qapp, qtbot):
        """User in cold-start brief: 30 lots × 0.05 LPS each."""
        w = self._make_window_with_loop(qtbot)
        original = self._stub_dialog({'base_demand_lps': 0.05})
        try:
            w.editor.bulk_edit_junctions()
        finally:
            from desktop import canvas_editor as ce
            ce.BulkJunctionEditDialog = original

        for jid in w.api.wn.junction_name_list:
            node = w.api.wn.get_node(jid)
            base_m3s = node.demand_timeseries_list[0].base_value
            assert base_m3s == pytest.approx(0.05 / 1000.0, rel=1e-9)

    def test_demand_factor_scales_existing_demand(self, qapp, qtbot):
        """Multiplying by 1.5 should scale every junction by 1.5x its existing
        base demand — not flatten them all to the same value."""
        w = self._make_window_with_loop(qtbot)

        # Capture baseline demands per junction
        before = {}
        for jid in w.api.wn.junction_name_list:
            node = w.api.wn.get_node(jid)
            before[jid] = float(node.demand_timeseries_list[0].base_value)

        original = self._stub_dialog({'demand_factor': 1.5})
        try:
            w.editor.bulk_edit_junctions()
        finally:
            from desktop import canvas_editor as ce
            ce.BulkJunctionEditDialog = original

        for jid, prev in before.items():
            current = float(w.api.wn.get_node(jid).demand_timeseries_list[0].base_value)
            assert current == pytest.approx(prev * 1.5, rel=1e-6), (
                f"junction {jid}: expected {prev * 1.5}, got {current}"
            )

    def test_no_fields_ticked_does_not_change_state(self, qapp, qtbot):
        """OK with nothing ticked is a no-op."""
        w = self._make_window_with_loop(qtbot)
        before = {jid: w.api.wn.get_node(jid).elevation
                  for jid in w.api.wn.junction_name_list}

        original = self._stub_dialog({})
        try:
            w.editor.bulk_edit_junctions()
        finally:
            from desktop import canvas_editor as ce
            ce.BulkJunctionEditDialog = original

        for jid, prev_elev in before.items():
            assert w.api.wn.get_node(jid).elevation == pytest.approx(prev_elev)

    def test_subset_only_affects_selected_junctions(self, qapp, qtbot):
        """Passing junction_ids restricts the bulk edit to that subset."""
        w = self._make_window_with_loop(qtbot)
        all_ids = list(w.api.wn.junction_name_list)
        target_ids = all_ids[:2]
        untouched_ids = all_ids[2:]

        before = {jid: w.api.wn.get_node(jid).elevation for jid in all_ids}

        original = self._stub_dialog({'elevation_m': 999.0})
        try:
            w.editor.bulk_edit_junctions(junction_ids=target_ids)
        finally:
            from desktop import canvas_editor as ce
            ce.BulkJunctionEditDialog = original

        for jid in target_ids:
            assert w.api.wn.get_node(jid).elevation == pytest.approx(999.0)
        for jid in untouched_ids:
            assert w.api.wn.get_node(jid).elevation == pytest.approx(before[jid])

    def test_menu_action_present(self, qapp, qtbot):
        from desktop.main_window import MainWindow
        w = MainWindow()
        qtbot.add_widget(w)
        items = []
        for top in w.menuBar().actions():
            if top.text().replace('&', '').lower() == 'edit':
                for sub in top.menu().actions():
                    if sub.text():
                        items.append(sub.text())
        assert any('junction' in t.lower() and 'bulk' in t.lower() for t in items), (
            f"Edit menu missing 'Bulk Edit Junctions...'. Got: {items}"
        )

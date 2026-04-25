"""
Tests for the menu shape after PR #5 of the cold-start UX roadmap.

Cold-start REPORT.md friction #6 ("menu organisation") flagged that:
  - Settings appeared in both File and Tools (Tools one was a stub)
  - Pipe Profile appeared in both Analysis and View (turned out to be
    different actions — calculation vs dock toggle — but with confusingly
    identical labels)
  - Analysis menu was a flat 19-item list mixing run / configure / report

These tests pin the post-PR shape so future menu edits don't silently
re-introduce the duplicates or flatten the submenus.
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


def _menu_action_labels(window, top_label):
    """Return the labels of all direct actions under the named top menu."""
    out = []
    for top in window.menuBar().actions():
        if top.text().replace('&', '').lower() == top_label.lower():
            for sub in top.menu().actions():
                if sub.text():
                    out.append(sub.text())
    return out


def _submenu(window, top_label, sub_label):
    """Return the QMenu for a named submenu inside a top-level menu."""
    for top in window.menuBar().actions():
        if top.text().replace('&', '').lower() == top_label.lower():
            for sub in top.menu().actions():
                if sub.text() and sub.text().replace('&', '').lower() == sub_label.lower():
                    return sub.menu()
    return None


# ---------------------------------------------------------------------------
# De-duplication invariants
# ---------------------------------------------------------------------------

class TestDuplicatesRemoved:
    def test_settings_only_in_file_menu(self, qapp, qtbot):
        from desktop.main_window import MainWindow
        w = MainWindow()
        qtbot.add_widget(w)

        file_items = [t.replace('&', '').lower()
                       for t in _menu_action_labels(w, 'file')]
        tools_items = [t.replace('&', '').lower()
                        for t in _menu_action_labels(w, 'tools')]

        # File menu has Settings...
        assert any('settings' in t for t in file_items), (
            f"File menu must include Settings. Got: {file_items}")
        # Tools menu does NOT
        assert not any('settings' in t for t in tools_items), (
            f"Tools menu must not include Settings (duplicate of File > "
            f"Settings, the Tools one was a stub). Got: {tools_items}")

    def test_view_pipe_profile_renamed_to_dock(self, qapp, qtbot):
        """View menu's Pipe Profile is a dock toggle — its label must
        disambiguate from Analysis > Reports > Pipe Profile (HGL)."""
        from desktop.main_window import MainWindow
        w = MainWindow()
        qtbot.add_widget(w)
        view_items = _menu_action_labels(w, 'view')
        # The dock toggle should not look identical to the calculation action
        assert any('dock' in t.lower() for t in view_items), (
            f"View menu should label its Pipe Profile entry as a dock. "
            f"Got: {view_items}")


# ---------------------------------------------------------------------------
# Analysis submenu structure
# ---------------------------------------------------------------------------

class TestAnalysisSubmenus:
    def test_analysis_has_four_named_submenus(self, qapp, qtbot):
        from desktop.main_window import MainWindow
        w = MainWindow()
        qtbot.add_widget(w)
        for sub_name in ('Run', 'Configure', 'Calibration', 'Reports'):
            assert _submenu(w, 'analysis', sub_name) is not None, (
                f"Analysis menu should contain a {sub_name!r} submenu after PR #5"
            )

    def test_run_submenu_contains_headline_solvers(self, qapp, qtbot):
        from desktop.main_window import MainWindow
        w = MainWindow()
        qtbot.add_widget(w)
        run = _submenu(w, 'analysis', 'Run')
        assert run is not None
        labels = [a.text() for a in run.actions() if a.text()]
        joined = ' '.join(labels).replace('&', '').lower()
        for word in ('steady', 'transient', 'extended period', 'fire flow', 'quality'):
            assert word in joined, (
                f"Analysis > Run should mention '{word}'. Got: {labels}")

    def test_configure_submenu_has_slurry_and_demand_patterns(self, qapp, qtbot):
        from desktop.main_window import MainWindow
        w = MainWindow()
        qtbot.add_widget(w)
        cfg = _submenu(w, 'analysis', 'Configure')
        assert cfg is not None
        labels = [a.text() for a in cfg.actions() if a.text()]
        joined = ' '.join(labels).replace('&', '').lower()
        for word in ('slurry', 'demand pattern', 'water quality config'):
            assert word in joined, (
                f"Analysis > Configure should mention '{word}'. Got: {labels}")

    def test_calibration_submenu_includes_wizard_field_data_residuals(self, qapp, qtbot):
        from desktop.main_window import MainWindow
        w = MainWindow()
        qtbot.add_widget(w)
        calib = _submenu(w, 'analysis', 'Calibration')
        assert calib is not None
        labels = [a.text() for a in calib.actions() if a.text()]
        joined = ' '.join(labels).replace('&', '').lower()
        for word in ('wizard', 'field data', 'residuals', 'sensitivity'):
            assert word in joined, (
                f"Analysis > Calibration should mention '{word}'. Got: {labels}")

    def test_reports_submenu_has_compliance_safety_pump_pipe_lcc(self, qapp, qtbot):
        from desktop.main_window import MainWindow
        w = MainWindow()
        qtbot.add_widget(w)
        rep = _submenu(w, 'analysis', 'Reports')
        assert rep is not None
        labels = [a.text() for a in rep.actions() if a.text()]
        joined = ' '.join(labels).replace('&', '').lower()
        for word in ('compliance', 'safety case', 'pump energy', 'profile', 'lifecycle'):
            assert word in joined, (
                f"Analysis > Reports should mention '{word}'. Got: {labels}")

    def test_top_level_analysis_has_no_direct_actions(self, qapp, qtbot):
        """All Analysis items should be inside the four submenus — flatness
        is what we just removed."""
        from desktop.main_window import MainWindow
        w = MainWindow()
        qtbot.add_widget(w)
        # Every top-level action under Analysis should itself be a submenu
        for top in w.menuBar().actions():
            if top.text().replace('&', '').lower() == 'analysis':
                for sub in top.menu().actions():
                    if not sub.text():
                        continue
                    assert sub.menu() is not None, (
                        f"Analysis item {sub.text()!r} should be inside a "
                        f"submenu after PR #5, but it's a direct action"
                    )


# ---------------------------------------------------------------------------
# Help menu links
# ---------------------------------------------------------------------------

class TestHelpDocLinks:
    def test_help_menu_has_user_guide_and_theory_manual(self, qapp, qtbot):
        from desktop.main_window import MainWindow
        w = MainWindow()
        qtbot.add_widget(w)
        items = _menu_action_labels(w, 'help')
        joined = ' '.join(items).lower()
        assert 'user guide' in joined, (
            f"Help menu must link to User Guide. Got: {items}")
        assert 'theory manual' in joined, (
            f"Help menu must link to Theory Manual. Got: {items}")

    def test_referenced_doc_files_exist(self):
        """Documents linked from Help should actually be on disk."""
        for fname in ('USER_GUIDE.md', 'THEORY_MANUAL.md'):
            path = os.path.join(PROJECT_ROOT, 'docs', fname)
            assert os.path.exists(path), (
                f"docs/{fname} must exist for Help > {fname[:-3]} link"
            )

    def test_open_docs_file_handles_missing_gracefully(self, qapp, qtbot, monkeypatch):
        """If a linked doc is missing, _open_docs_file warns rather than
        raising — keeps the GUI responsive even after a botched install."""
        from desktop.main_window import MainWindow
        from PyQt6.QtWidgets import QMessageBox

        w = MainWindow()
        qtbot.add_widget(w)
        captured = {}
        monkeypatch.setattr(QMessageBox, 'warning',
                             lambda *a, **kw: captured.setdefault('warned', True))

        # File definitely doesn't exist
        w._open_docs_file('NONEXISTENT_DOC.md')
        assert captured.get('warned'), (
            "_open_docs_file should warn when the file is missing, not raise"
        )

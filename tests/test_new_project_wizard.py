"""
Tests for the New Project wizard — PR #2 in the cold-start UX roadmap.

Covers:
  - api.bootstrap_project() for all 3 source types + error path
  - Wizard widget collection (defaults, source-type reactivity, material
    preset reactivity)
  - File > New cancellation preserves the existing network
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
# api.bootstrap_project
# ---------------------------------------------------------------------------

class TestBootstrapProject:
    def test_reservoir_source_creates_one_reservoir_zero_junctions(self, api_instance):
        result = api_instance.bootstrap_project(
            name='res_test', source_type='reservoir', source_head_m=80.0)

        assert 'error' not in result
        assert result['reservoirs'] == 1
        assert result['junctions'] == 0
        assert result['tanks'] == 0
        assert result['pipes'] == 0
        assert api_instance.wn is not None
        assert os.path.exists(api_instance._inp_file)

    def test_tank_source_creates_one_tank_zero_junctions(self, api_instance):
        result = api_instance.bootstrap_project(
            name='tank_test', source_type='tank', source_head_m=60.0)

        assert 'error' not in result
        assert result['tanks'] == 1
        assert result['junctions'] == 0
        assert result['reservoirs'] == 0

    def test_junction_source_creates_one_junction_zero_reservoirs(self, api_instance):
        """Source type 'junction' models a connection to an existing main —
        a single junction with elevation = the supplied head and zero demand."""
        result = api_instance.bootstrap_project(
            name='conn_test', source_type='junction', source_head_m=45.0,
            source_id='SOURCE')

        assert 'error' not in result
        assert result['junctions'] == 1
        assert result['reservoirs'] == 0
        assert result['tanks'] == 0
        assert 'SOURCE' in result['junction_list']

    def test_unknown_source_type_returns_error(self, api_instance):
        result = api_instance.bootstrap_project(
            name='bad', source_type='aquifer', source_head_m=50.0)
        assert 'error' in result
        assert 'aquifer' in result['error']

    def test_default_source_ids(self, api_instance):
        """Each source type has a sensible default ID when none is supplied."""
        api_instance.bootstrap_project(name='r', source_type='reservoir')
        assert 'R1' in api_instance.wn.reservoir_name_list

        api2 = type(api_instance)(work_dir=api_instance.work_dir)
        api2.bootstrap_project(name='t', source_type='tank')
        assert 'T1' in api2.wn.tank_name_list

        api3 = type(api_instance)(work_dir=api_instance.work_dir)
        api3.bootstrap_project(name='j', source_type='junction')
        assert 'J0' in api3.wn.junction_name_list

    def test_project_defaults_are_stashed(self, api_instance):
        """The project_defaults dict is preserved on the API for downstream
        dialogs to consult (e.g. AddPipeDialog)."""
        api_instance.bootstrap_project(
            name='defaults_test',
            source_type='reservoir',
            project_defaults={'material': 'PE100', 'roughness': 145, 'dn_mm': 110},
        )
        assert api_instance.project_defaults['material'] == 'PE100'
        assert api_instance.project_defaults['dn_mm'] == 110
        assert api_instance.project_metadata['name'] == 'defaults_test'
        assert api_instance.project_metadata['source_type'] == 'reservoir'

    def test_bootstrapped_network_is_extensible(self, api_instance):
        """Bootstrap + one junction + one pipe = a network EPANET can solve.

        The bootstrapped 1-source network is intentionally not runnable on
        its own (EPANET error 223 — "not enough nodes"). The right invariant
        is that a user can extend it through normal API/UI calls and reach
        a runnable state.
        """
        api_instance.bootstrap_project(name='extend_test', source_type='reservoir',
                                       source_head_m=80.0)
        api_instance.add_junction('J1', elevation=50.0, base_demand=5.0/1000,
                                  coordinates=(100, 0))
        api_instance.add_pipe('P1', 'R1', 'J1', length=500,
                              diameter_m=0.2, roughness=130)

        results = api_instance.run_steady_state(save_plot=False)
        assert 'error' not in results
        assert 'J1' in results['pressures']
        assert results['pressures']['J1']['min_m'] > 0


# ---------------------------------------------------------------------------
# NewProjectWizard widget
# ---------------------------------------------------------------------------

class TestNewProjectWizardWidget:
    def test_default_config_is_complete(self, qapp):
        from desktop.new_project_wizard import NewProjectWizard
        wiz = NewProjectWizard()
        cfg = wiz.get_config()

        for key in ('name', 'engineer', 'date', 'standard',
                    'source_type', 'source_id', 'source_head_m',
                    'project_defaults'):
            assert key in cfg, f"wizard config missing '{key}'"
        assert cfg['source_type'] in ('reservoir', 'tank', 'junction')
        assert cfg['source_head_m'] > 0
        for sub in ('material', 'roughness', 'dn_mm'):
            assert sub in cfg['project_defaults'], (
                f"project_defaults missing '{sub}'")

    def test_source_type_change_updates_default_id(self, qapp):
        """Switching source type pre-fills a sensible source ID."""
        from desktop.new_project_wizard import NewProjectWizard
        wiz = NewProjectWizard()
        wiz.source_type_combo.setCurrentIndex(0)  # reservoir
        assert wiz.source_id_input.text() == 'R1'

        wiz.source_type_combo.setCurrentIndex(1)  # tank
        assert wiz.source_id_input.text() == 'T1'

        wiz.source_type_combo.setCurrentIndex(2)  # junction
        assert wiz.source_id_input.text() == 'CONN1'

    def test_material_change_updates_roughness_and_dn(self, qapp):
        """Selecting a material preset updates the default roughness and DN."""
        from desktop.new_project_wizard import NewProjectWizard
        wiz = NewProjectWizard()

        wiz.material_combo.setCurrentText('Ductile Iron (AS 2280)')
        assert wiz.roughness_spin.value() == 130
        assert wiz.dn_spin.value() == 150

        wiz.material_combo.setCurrentText('Concrete (AS 4058)')
        assert wiz.roughness_spin.value() == 110
        assert wiz.dn_spin.value() == 300


# ---------------------------------------------------------------------------
# File > New integration
# ---------------------------------------------------------------------------

class TestFileNewIntegration:
    def test_cancel_preserves_existing_network(self, qapp, qtbot):
        """If the user opens File > New on a populated network and cancels,
        the original network must not be destroyed."""
        from desktop.main_window import MainWindow
        w = MainWindow()
        qtbot.add_widget(w)

        # Load a tutorial so there's something to preserve
        tut = os.path.join(PROJECT_ROOT, 'tutorials', 'simple_loop', 'network.inp')
        w.api.load_network_from_path(tut)
        w.canvas.set_api(w.api)
        original_inp = w._current_file = tut
        original_n_junctions = len(w.api.wn.junction_name_list)
        assert original_n_junctions > 0

        # Stub the wizard so it acts as if the user clicked Cancel
        from desktop import new_project_wizard as wmod
        original_cls = wmod.NewProjectWizard

        class CancelledWizard(original_cls):
            def exec(self):
                return 0  # Rejected
        wmod.NewProjectWizard = CancelledWizard
        # Also patch the symbol main_window.py imported at module-load time
        from desktop import main_window as mw
        original_imported = mw.NewProjectWizard
        mw.NewProjectWizard = CancelledWizard

        try:
            w._on_new()
        finally:
            wmod.NewProjectWizard = original_cls
            mw.NewProjectWizard = original_imported

        # Network preserved
        assert w.api.wn is not None
        assert len(w.api.wn.junction_name_list) == original_n_junctions
        assert w._current_file == original_inp

    def test_accept_creates_new_network(self, qapp, qtbot, tmp_path):
        """If the user accepts the wizard, the existing network is replaced."""
        from desktop.main_window import MainWindow
        w = MainWindow()
        qtbot.add_widget(w)

        # Stub wizard to act as if the user filled in fields and clicked OK
        from desktop import new_project_wizard as wmod
        from desktop import main_window as mw
        original_cls = wmod.NewProjectWizard
        original_imported = mw.NewProjectWizard

        class AcceptedWizard(original_cls):
            def exec(self):
                return 1  # Accepted

            def get_config(self):
                return {
                    'name': 'wizard_test',
                    'engineer': 'tester',
                    'date': '2026-04-25',
                    'standard': 'WSAA',
                    'source_type': 'reservoir',
                    'source_id': 'R1',
                    'source_head_m': 75.0,
                    'project_defaults': {'material': 'PVC', 'roughness': 145, 'dn_mm': 100},
                }
        wmod.NewProjectWizard = AcceptedWizard
        mw.NewProjectWizard = AcceptedWizard

        try:
            w._on_new()
        finally:
            wmod.NewProjectWizard = original_cls
            mw.NewProjectWizard = original_imported

        assert w.api.wn is not None
        assert len(w.api.wn.reservoir_name_list) == 1
        assert 'R1' in w.api.wn.reservoir_name_list
        assert len(w.api.wn.junction_name_list) == 0
        assert w.api.project_metadata['name'] == 'wizard_test'

    def test_welcome_dialog_has_create_new_button(self, qapp):
        """The Welcome dialog must offer the new-project path."""
        from desktop.welcome_dialog import WelcomeDialog
        dlg = WelcomeDialog()
        assert hasattr(WelcomeDialog, 'NEW_PROJECT')
        assert WelcomeDialog.NEW_PROJECT == 'new_project'
        # Confirm a button labelled 'Create New Project' exists
        from PyQt6.QtWidgets import QPushButton
        labels = [b.text() for b in dlg.findChildren(QPushButton)]
        assert any('Create New Project' in t for t in labels), (
            f"WelcomeDialog must have a 'Create New Project' button. Got: {labels}"
        )

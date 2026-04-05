"""
R-series UI tests:
  R2 Safety Case Dialog
  R3 Demo network exists and solvable
  R4 Run Demo action wired to Help menu
"""

import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QAction

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_INP = os.path.join(PROJECT_ROOT, 'tutorials', 'demo_network', 'network.inp')


@pytest.fixture(scope='module')
def app():
    qapp = QApplication.instance() or QApplication(sys.argv)
    yield qapp


@pytest.fixture
def main_window(app):
    from desktop.main_window import MainWindow
    w = MainWindow()
    yield w
    w.close()


# ---------- R3: Demo network exists and produces violations -------------------

def test_demo_network_file_exists():
    assert os.path.exists(DEMO_INP), \
        f'Demo network missing at {DEMO_INP}'


def test_demo_network_produces_pressure_violation():
    from epanet_api import HydraulicAPI
    api = HydraulicAPI()
    api.load_network(DEMO_INP)
    r = api.run_steady_state(save_plot=False)
    low_p = [n for n, p in r['pressures'].items()
             if p.get('avg_m', 100) < api.DEFAULTS['min_pressure_m']]
    assert low_p, 'Demo network should have at least one low-pressure node'


def test_demo_network_produces_velocity_violation():
    from epanet_api import HydraulicAPI
    api = HydraulicAPI()
    api.load_network(DEMO_INP)
    r = api.run_steady_state(save_plot=False)
    hi_v = [pid for pid, f in r['flows'].items()
            if f.get('max_velocity_ms', 0) > api.DEFAULTS['max_velocity_ms']]
    assert hi_v, 'Demo network should have at least one high-velocity pipe'


def test_demo_network_has_10_junctions():
    from epanet_api import HydraulicAPI
    api = HydraulicAPI()
    api.load_network(DEMO_INP)
    assert len(api.wn.junction_name_list) == 10


# ---------- R4: Demo action wired to Help menu --------------------------------

def test_run_demo_action_exists(main_window):
    """Help menu must contain a Run Demo action."""
    found = False
    for act in main_window.findChildren(QAction):
        if act.text().replace('&', '').lower().startswith('run demo'):
            found = True
            break
    assert found, 'Help > Run Demo action not found'


def test_run_demo_completes_without_crash(main_window, app):
    """Triggering Run Demo should load the network and run analysis."""
    # Find the action
    demo_act = None
    for act in main_window.findChildren(QAction):
        if act.text().replace('&', '').lower() == 'run demo':
            demo_act = act
            break
    assert demo_act is not None, 'Run Demo action missing'

    # Monkey-patch QMessageBox to avoid modal dialogs blocking the test
    from PyQt6.QtWidgets import QMessageBox
    original_info = QMessageBox.information
    QMessageBox.information = staticmethod(
        lambda *a, **kw: QMessageBox.StandardButton.Ok)
    try:
        demo_act.trigger()
        # Step chain uses QTimer — pump events so callbacks fire
        for _ in range(20):
            app.processEvents()
            import time
            time.sleep(0.1)
    finally:
        QMessageBox.information = original_info

    assert main_window.api.wn is not None
    assert len(main_window.api.wn.junction_name_list) == 10


# ---------- R2: Safety Case Dialog --------------------------------------------

def test_safety_case_dialog_opens(app):
    from desktop.safety_case_dialog import SafetyCaseDialog
    from epanet_api import HydraulicAPI
    api = HydraulicAPI()
    api.load_network(DEMO_INP)
    dlg = SafetyCaseDialog(api=api)
    assert dlg.windowTitle() == 'Safety Case Report'
    assert dlg.engineer_edit is not None
    assert dlg.project_ref_edit is not None
    assert dlg.wave_speed_spin.value() == 1100.0
    dlg.close()


def test_safety_case_dialog_generates_verdict(app):
    from desktop.safety_case_dialog import SafetyCaseDialog
    from epanet_api import HydraulicAPI
    api = HydraulicAPI()
    api.load_network(DEMO_INP)
    dlg = SafetyCaseDialog(api=api)
    dlg._on_generate()
    assert dlg.report is not None
    assert dlg.verdict_label.text() in (
        'APPROVED', 'CONDITIONAL APPROVAL', 'NOT APPROVED')
    # Summary text populated
    assert dlg.summary_text.toPlainText()
    assert dlg.export_btn.isEnabled()
    dlg.close()


def test_safety_case_dialog_exports_json(app, tmp_path):
    from desktop.safety_case_dialog import SafetyCaseDialog
    from epanet_api import HydraulicAPI
    import json
    api = HydraulicAPI()
    api.load_network(DEMO_INP)
    dlg = SafetyCaseDialog(api=api)
    dlg.engineer_edit.setText('Test Engineer')
    dlg.project_ref_edit.setText('TEST-001')
    dlg._on_generate()

    # Monkey-patch file dialog to return a tmp path
    from PyQt6.QtWidgets import QFileDialog, QMessageBox
    out = str(tmp_path / 'sc.json')
    original_save = QFileDialog.getSaveFileName
    original_info = QMessageBox.information
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **kw: (out, ''))
    QMessageBox.information = staticmethod(
        lambda *a, **kw: QMessageBox.StandardButton.Ok)
    try:
        dlg._on_export()
    finally:
        QFileDialog.getSaveFileName = original_save
        QMessageBox.information = original_info

    assert os.path.exists(out)
    with open(out) as f:
        data = json.load(f)
    assert data['title'] == 'Pipeline Safety Case Report'
    assert data['signature_block']['certifying_engineer'] == 'Test Engineer'
    assert data['signature_block']['project_reference'] == 'TEST-001'
    dlg.close()


def test_safety_case_action_in_analysis_menu(main_window):
    """Analysis menu must contain Safety Case Report action."""
    found = False
    for act in main_window.findChildren(QAction):
        if 'safety case' in act.text().replace('&', '').lower():
            found = True
            break
    assert found, 'Analysis > Safety Case Report action missing'

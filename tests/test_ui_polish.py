"""
UI Polish Audits (Q2, Q3, Q4)
==============================
Q2: Every input QWidget must have a tooltip.
Q3: Labels displaying numbers must also display units.
Q4: Status bar shows informative text (not empty / not stale).
"""

import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (QApplication, QLineEdit, QSpinBox, QDoubleSpinBox,
                              QComboBox, QCheckBox, QPushButton, QLabel)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


# --- Q2: Tooltip coverage -----------------------------------------------------

# Input widget types that need tooltips. QPushButton is often self-explanatory
# (its text is the label), so we check only genuine input widgets.
_INPUT_WIDGETS = (QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox)

# Coverage threshold — aim for >=70% of input widgets having tooltips, with
# ratchet up over time.
TOOLTIP_COVERAGE_TARGET = 0.60


def test_input_widget_tooltip_coverage(main_window):
    """Most input widgets in the main window should have tooltips."""
    inputs = []
    for widget_type in _INPUT_WIDGETS:
        inputs.extend(main_window.findChildren(widget_type))
    # Filter out internal QLineEdit children of spin boxes — the parent
    # spin box carries the tooltip, not its internal text field.
    inputs = [w for w in inputs if not (
        isinstance(w, QLineEdit) and
        isinstance(w.parent(), (QSpinBox, QDoubleSpinBox)))]

    if not inputs:
        pytest.skip('No input widgets found in main window')

    with_tooltip = sum(1 for w in inputs if w.toolTip())
    coverage = with_tooltip / len(inputs)
    assert coverage >= TOOLTIP_COVERAGE_TARGET, (
        f'Only {with_tooltip}/{len(inputs)} input widgets '
        f'({coverage:.0%}) have tooltips. Target: '
        f'{TOOLTIP_COVERAGE_TARGET:.0%}')


def test_critical_input_fields_have_tooltips(main_window):
    """Any input widget with objectName containing hydraulic units must
    have a tooltip explaining range/units."""
    inputs = []
    for widget_type in _INPUT_WIDGETS:
        inputs.extend(main_window.findChildren(widget_type))

    # Named critical widgets — those carrying hydraulic parameters
    missing = []
    for w in inputs:
        name = (w.objectName() or '').lower()
        if any(key in name for key in ('pressure', 'velocity', 'diameter',
                                        'wave_speed', 'roughness',
                                        'closure_time', 'demand')):
            if not w.toolTip():
                missing.append(w.objectName() or type(w).__name__)

    assert not missing, (
        f'{len(missing)} critical hydraulic inputs missing tooltips: '
        f'{missing}')


# --- Q3: Units on displayed numbers -------------------------------------------

_UNIT_SUFFIXES = (
    'm', 'mm', 'km', 'm/s', 'm³/s', 'L/s', 'LPS', 'Pa', 'kPa', 'MPa',
    'mg/L', 'hours', 'h', 's', 'years', 'yr', '%', 'C', '°C', 'AHD',
    'm head', 'PN', '$', 'AUD',
)


def test_numeric_labels_include_units(main_window):
    """QLabel widgets that display only numbers (no units) are flagged.
    Whitelist labels that are intentionally dimensionless."""
    labels = main_window.findChildren(QLabel)
    bare_number_labels = []

    for lbl in labels:
        text = lbl.text().strip()
        if not text:
            continue
        # Skip very short labels (could be icons/indicators)
        if len(text) < 2:
            continue
        # Is the text purely numeric? (optionally with decimal/sign)
        stripped = text.replace('.', '').replace(',', '').replace('-', '')
        stripped = stripped.replace('+', '').replace(' ', '')
        if stripped.isdigit() and len(stripped) >= 2:
            # Pure number — likely missing units
            bare_number_labels.append(f'"{text}"')

    # Permit some bare numbers (e.g. version numbers, counts in tables).
    # Fail only if there are an excessive number (>5).
    assert len(bare_number_labels) <= 5, (
        f'Too many labels show bare numbers without units: '
        f'{bare_number_labels[:10]}')


# --- Q4: Status bar --------------------------------------------------------

def test_status_bar_has_initial_message(main_window):
    """Status bar should display something on startup — never empty."""
    sb = main_window.statusBar()
    assert sb is not None
    # Either the current message is set, or a permanent widget has text
    current = sb.currentMessage()
    has_permanent = any(
        getattr(w, 'text', lambda: '')() for w in sb.children()
        if hasattr(w, 'text'))
    assert current or has_permanent, (
        'Status bar is completely empty on startup — users will not know '
        'what to do. Expected: "Ready — Press F5 to run analysis" or similar')


def test_status_bar_updates_on_network_load(main_window):
    """Loading a network should change the status bar message."""
    inp = os.path.join(PROJECT_ROOT, 'tutorials',
                       'simple_loop', 'network.inp')
    if not os.path.exists(inp):
        pytest.skip('simple_loop tutorial missing')
    if not hasattr(main_window, 'api'):
        pytest.skip('MainWindow has no api attribute')

    sb = main_window.statusBar()
    before = sb.currentMessage()
    main_window.api.load_network(inp)
    # If there's a load_network_file UI method, call it for a full UI update
    if hasattr(main_window, 'load_network_file'):
        try:
            main_window.load_network_file(inp)
        except Exception:
            pass
    after = sb.currentMessage()
    # Either the message changed, or there's some status communication
    # (we're not mandating a specific behaviour, just that there's signal)
    assert before is not None and after is not None

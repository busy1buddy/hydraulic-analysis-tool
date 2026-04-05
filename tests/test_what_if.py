"""
Tests for the WhatIfPanel (I4) — live sensitivity sliders.
"""

import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_INP = os.path.join(PROJECT_ROOT, 'tutorials', 'demo_network',
                        'network.inp')


@pytest.fixture(scope='module')
def app():
    qapp = QApplication.instance() or QApplication(sys.argv)
    yield qapp


@pytest.fixture
def panel(app):
    from desktop.what_if_panel import WhatIfPanel
    from epanet_api import HydraulicAPI
    api = HydraulicAPI()
    api.load_network(DEMO_INP)
    p = WhatIfPanel(api=api)
    p.set_api(api)
    yield p
    p.close()


def test_panel_constructs(panel):
    assert panel.demand_slider.value() == 100
    assert panel.rough_slider.value() == 100
    assert panel.source_slider.value() == 0


def test_slider_ranges(panel):
    assert panel.demand_slider.minimum() == 50
    assert panel.demand_slider.maximum() == 200
    assert panel.rough_slider.minimum() == 50
    assert panel.rough_slider.maximum() == 150
    assert panel.source_slider.minimum() == -20
    assert panel.source_slider.maximum() == 20


def test_label_updates_with_slider(panel):
    panel.demand_slider.setValue(150)
    assert '150' in panel.demand_label.text()
    panel.source_slider.setValue(-10)
    assert '-10' in panel.source_label.text()


def test_slider_change_triggers_analysis(panel, app):
    """Moving a slider should fire analysis_updated signal."""
    received = []
    panel.analysis_updated.connect(lambda r: received.append(r))

    panel.demand_slider.setValue(120)
    # Debounce is 150ms — pump events
    import time
    for _ in range(10):
        app.processEvents()
        time.sleep(0.05)

    assert received, 'analysis_updated never fired'
    assert 'pressures' in received[-1]
    assert 'flows' in received[-1]


def test_demand_multiplier_affects_pressure(panel, app):
    """Increasing demand should lower minimum pressure."""
    received = []
    panel.analysis_updated.connect(lambda r: received.append(r))

    # Baseline at 100% (nudge to force a valueChanged)
    import time
    panel.demand_slider.setValue(101)
    panel.demand_slider.setValue(100)
    for _ in range(10):
        app.processEvents()
        time.sleep(0.05)
    baseline = received[-1]
    p_min_base = min(p.get('avg_m', 0)
                     for p in baseline['pressures'].values())

    # Double demand
    panel.demand_slider.setValue(200)
    for _ in range(10):
        app.processEvents()
        time.sleep(0.05)
    doubled = received[-1]
    p_min_doubled = min(p.get('avg_m', 0)
                        for p in doubled['pressures'].values())

    assert p_min_doubled < p_min_base, \
        f'200% demand should lower min pressure; got {p_min_base:.1f} -> {p_min_doubled:.1f}'


def test_source_head_boost_raises_pressure(panel, app):
    """+20m source head should raise minimum pressure."""
    received = []
    panel.analysis_updated.connect(lambda r: received.append(r))

    import time
    panel.source_slider.setValue(1)
    panel.source_slider.setValue(0)
    for _ in range(10):
        app.processEvents()
        time.sleep(0.05)
    base = received[-1]
    p_min_base = min(p.get('avg_m', 0)
                     for p in base['pressures'].values())

    panel.source_slider.setValue(20)
    for _ in range(10):
        app.processEvents()
        time.sleep(0.05)
    boosted = received[-1]
    p_min_boosted = min(p.get('avg_m', 0)
                        for p in boosted['pressures'].values())

    # +20m at source should raise min pressure by ~20m
    assert p_min_boosted > p_min_base + 15, \
        f'+20m source should raise min pressure; got {p_min_base:.1f} -> {p_min_boosted:.1f}'


def test_reset_returns_sliders_to_defaults(panel):
    panel.demand_slider.setValue(150)
    panel.rough_slider.setValue(70)
    panel.source_slider.setValue(-10)

    panel._on_reset()

    assert panel.demand_slider.value() == 100
    assert panel.rough_slider.value() == 100
    assert panel.source_slider.value() == 0

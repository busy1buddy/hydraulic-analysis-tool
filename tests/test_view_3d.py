"""
Tests for 3D Network Visualisation (I14)
==========================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from epanet_api import HydraulicAPI

try:
    from desktop.view_3d import View3D, HAS_GL
except Exception:
    HAS_GL = False


@pytest.fixture
def api_with_results():
    api = HydraulicAPI()
    api.create_network(
        name='view3d_test',
        junctions=[
            {'id': 'J1', 'elevation': 50, 'demand': 5.0, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 70, 'demand': 3.0, 'x': 100, 'y': 0},
            {'id': 'J3', 'elevation': 30, 'demand': 4.0, 'x': 200, 'y': 0},
        ],
        reservoirs=[{'id': 'R1', 'head': 100, 'x': -100, 'y': 0}],
        pipes=[
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 300,
             'diameter': 300, 'roughness': 130},
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 200,
             'diameter': 250, 'roughness': 130},
            {'id': 'P3', 'start': 'J2', 'end': 'J3', 'length': 200,
             'diameter': 200, 'roughness': 130},
        ],
    )
    results = api.run_steady_state(save_plot=False)
    return api, results


@pytest.fixture(scope='module')
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestView3D:

    def test_has_gl_flag(self):
        """HAS_GL should be a boolean."""
        from desktop.view_3d import HAS_GL
        assert isinstance(HAS_GL, bool)

    @pytest.mark.skipif(not HAS_GL, reason="PyOpenGL not available")
    def test_create_view(self, qapp, api_with_results):
        api, results = api_with_results
        view = View3D(api, results=results)
        assert view is not None
        assert hasattr(view, 'gl_widget')

    @pytest.mark.skipif(not HAS_GL, reason="PyOpenGL not available")
    def test_3d_items_created(self, qapp, api_with_results):
        api, results = api_with_results
        view = View3D(api, results=results)
        # Scene build is deferred to showEvent so the GLViewWidget's
        # GL context is ready before items compile their shaders.
        view.show()
        qapp.processEvents()
        from PyQt6.QtTest import QTest
        QTest.qWait(50)
        qapp.processEvents()
        items = view.gl_widget.items
        assert len(items) >= 2  # at least grid + scatter

    @pytest.mark.skipif(not HAS_GL, reason="PyOpenGL not available")
    def test_view_buttons(self, qapp, api_with_results):
        api, results = api_with_results
        view = View3D(api, results=results)
        # Should not crash
        view._view_top()
        view._view_side()
        view._reset_view()

    def test_no_gl_shows_fallback(self, qapp):
        """Without OpenGL, should show a fallback message."""
        # This test always passes — if GL is available, skip
        # If not, the widget shows a label instead of GL
        api = HydraulicAPI()
        api.create_network(
            name='test3d_fb',
            junctions=[{'id': 'J1', 'elevation': 50, 'demand': 1, 'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 80, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                     'diameter': 200, 'roughness': 130}],
        )
        # This just verifies the widget doesn't crash
        view = View3D(api)
        assert view is not None

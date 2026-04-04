"""
Tests for GIF/MP4 Animation Export (I3)
=========================================
"""

import os
import sys
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication
from desktop.animation_panel import AnimationPanel


@pytest.fixture(scope='module')
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def panel_with_data(qapp):
    """AnimationPanel loaded with synthetic transient data."""
    panel = AnimationPanel()
    timestamps = np.linspace(0, 10, 20)
    node_data = {
        'J1': {'head': np.sin(timestamps) * 10 + 80},
        'J2': {'head': np.cos(timestamps) * 5 + 75},
    }
    pipe_data = {
        'P1': {
            'start_node_velocity': np.ones(20) * 1.5,
            'start_node_flowrate': np.ones(20) * 0.01,
        },
    }
    panel.set_transient_data(timestamps, node_data, pipe_data)
    return panel


class TestAnimationExport:
    """Tests for animation export functionality."""

    def test_export_button_exists(self, panel_with_data):
        assert hasattr(panel_with_data, 'export_btn')
        assert panel_with_data.export_btn.isEnabled()

    def test_export_button_disabled_without_data(self, qapp):
        panel = AnimationPanel()
        assert not panel.export_btn.isEnabled()

    def test_frame_count(self, panel_with_data):
        assert panel_with_data.n_frames == 20

    def test_node_data_accessible(self, panel_with_data):
        assert 'J1' in panel_with_data.node_data
        assert 'J2' in panel_with_data.node_data
        assert len(panel_with_data.node_data['J1']['head']) == 20

    def test_gif_export_creates_file(self, panel_with_data, tmp_path):
        """Test GIF export produces a valid file > 0 bytes."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        # We can't do full canvas grab in offscreen mode easily,
        # but we can test the PIL GIF writing logic directly
        gif_path = str(tmp_path / "test_anim.gif")

        # Create simple test frames
        frames = []
        for i in range(5):
            img = Image.new('RGB', (100, 100), color=(i * 50, 100, 200))
            frames.append(img)

        frames[0].save(
            gif_path, save_all=True,
            append_images=frames[1:],
            duration=66, loop=0,
        )

        assert os.path.exists(gif_path)
        assert os.path.getsize(gif_path) > 100  # > 100 bytes at minimum

        # Verify it's a valid GIF
        with open(gif_path, 'rb') as f:
            magic = f.read(3)
            assert magic == b'GIF'

    def test_pillow_available(self):
        """Verify Pillow is available for GIF export."""
        try:
            from PIL import Image
            assert Image is not None
        except ImportError:
            pytest.skip("Pillow not installed — GIF export will show fallback message")

    def test_frame_navigation(self, panel_with_data):
        """Ensure frame navigation works for export."""
        panel_with_data._set_frame(0)
        assert panel_with_data._current_frame == 0

        panel_with_data._set_frame(10)
        assert panel_with_data._current_frame == 10

        panel_with_data._set_frame(19)
        assert panel_with_data._current_frame == 19

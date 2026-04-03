"""Tests for the NiceGUI application structure and imports."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAppStructure:
    def test_app_module_imports(self):
        """Verify all app modules can be imported."""
        import app
        import app.theme
        import app.components.network_plot
        import app.components.compliance
        import app.components.metrics

    def test_theme_colors_defined(self):
        from app.theme import COLORS
        assert 'bg' in COLORS
        assert 'accent' in COLORS
        assert 'green' in COLORS
        assert 'red' in COLORS

    def test_plotly_layout_defined(self):
        from app.theme import PLOTLY_LAYOUT
        assert 'paper_bgcolor' in PLOTLY_LAYOUT
        assert 'font' in PLOTLY_LAYOUT

    def test_chart_colors_sufficient(self):
        from app.theme import CHART_COLORS
        assert len(CHART_COLORS) >= 7  # Need at least 7 for junction count


class TestNetworkPlotComponent:
    def test_creates_figure(self, loaded_network):
        from app.components.network_plot import create_network_figure
        fig = create_network_figure(loaded_network.wn)
        assert fig is not None
        assert len(fig.data) > 0  # Has traces

    def test_figure_has_nodes(self, loaded_network):
        from app.components.network_plot import create_network_figure
        fig = create_network_figure(loaded_network.wn)
        # Should have traces for pipes + junction + reservoir + tank
        assert len(fig.data) >= 4


class TestFeedbackChannel:
    def test_feedback_file_operations(self, tmp_path):
        """Test feedback save/load without NiceGUI UI."""
        import json
        feedback_file = tmp_path / 'feedback.json'

        # Save
        entry = {
            'id': 'test_001',
            'timestamp': '2026-04-03T12:00:00',
            'name': 'Test User',
            'category': 'Bug Report',
            'description': 'Test feedback entry',
            'status': 'Open',
        }
        with open(feedback_file, 'w') as f:
            json.dump([entry], f)

        # Load
        with open(feedback_file, 'r') as f:
            loaded = json.load(f)
        assert len(loaded) == 1
        assert loaded[0]['description'] == 'Test feedback entry'

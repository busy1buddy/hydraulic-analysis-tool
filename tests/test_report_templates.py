"""
Tests for Report Template System (J15)
========================================
"""

import os
import sys
import json
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from desktop.report_templates import (
    list_templates, save_template, load_template,
    DEFAULT_TEMPLATES, TEMPLATES_DIR,
)


class TestReportTemplates:

    def test_default_templates_exist(self):
        assert len(DEFAULT_TEMPLATES) == 3
        assert 'Standard — All Sections' in DEFAULT_TEMPLATES
        assert 'Executive — Summary Only' in DEFAULT_TEMPLATES
        assert 'Technical — Full Tables' in DEFAULT_TEMPLATES

    def test_list_includes_defaults(self):
        templates = list_templates()
        assert 'Standard — All Sections' in templates

    def test_standard_has_all_sections(self):
        template = DEFAULT_TEMPLATES['Standard — All Sections']
        for key in ['executive_summary', 'network_description', 'steady_state',
                     'compliance', 'transient', 'fire_flow', 'water_quality',
                     'conclusions']:
            assert template['sections'][key] is True

    def test_executive_minimal_sections(self):
        template = DEFAULT_TEMPLATES['Executive — Summary Only']
        assert template['sections']['executive_summary'] is True
        assert template['sections']['steady_state'] is False

    def test_save_and_load_roundtrip(self):
        """Save a template and load it back."""
        name = '_test_template_roundtrip'
        sections = {'executive_summary': True, 'steady_state': False}
        save_template(name, sections, description='Test template')

        loaded = load_template(name)
        assert loaded is not None
        assert loaded['sections']['executive_summary'] is True
        assert loaded['sections']['steady_state'] is False

        # Cleanup
        safe_name = name.strip()
        path = os.path.join(TEMPLATES_DIR, f'{safe_name}.json')
        if os.path.exists(path):
            os.remove(path)

    def test_template_has_description(self):
        for name, t in DEFAULT_TEMPLATES.items():
            assert 'description' in t
            assert len(t['description']) > 0

    def test_load_nonexistent_returns_none(self):
        result = load_template('NONEXISTENT_TEMPLATE_XYZ')
        assert result is None

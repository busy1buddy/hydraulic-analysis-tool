"""Tests for Australian pipe properties database."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPipeDatabase:
    def test_import(self):
        from data.au_pipes import PIPE_DATABASE
        assert len(PIPE_DATABASE) > 0

    def test_has_ductile_iron(self):
        from data.au_pipes import PIPE_DATABASE
        keys_lower = [k.lower() for k in PIPE_DATABASE]
        assert any('ductile' in k for k in keys_lower)

    def test_has_pvc(self):
        from data.au_pipes import PIPE_DATABASE
        keys_lower = [k.lower() for k in PIPE_DATABASE]
        assert any('pvc' in k for k in keys_lower)

    def test_has_pe(self):
        from data.au_pipes import PIPE_DATABASE
        keys_lower = [k.lower() for k in PIPE_DATABASE]
        assert any('pe' in k or 'hdpe' in k for k in keys_lower)

    def test_has_concrete(self):
        from data.au_pipes import PIPE_DATABASE
        keys_lower = [k.lower() for k in PIPE_DATABASE]
        assert any('concrete' in k for k in keys_lower)


class TestPipeLookup:
    def test_get_pipe_properties(self):
        from data.au_pipes import get_pipe_properties
        result = get_pipe_properties('Ductile Iron', 200)
        assert result is not None
        assert 'internal_diameter_mm' in result
        assert 'hazen_williams_c' in result
        assert 'wave_speed_ms' in result

    def test_invalid_material(self):
        from data.au_pipes import get_pipe_properties
        result = get_pipe_properties('titanium', 200)
        assert result is None

    def test_invalid_size(self):
        from data.au_pipes import get_pipe_properties
        result = get_pipe_properties('Ductile Iron', 999)
        assert result is None

    def test_list_materials(self):
        from data.au_pipes import list_materials
        materials = list_materials()
        assert len(materials) >= 3
        assert 'Ductile Iron' in materials

    def test_list_sizes(self):
        from data.au_pipes import list_sizes
        sizes = list_sizes('Ductile Iron')
        assert len(sizes) >= 4
        assert 200 in sizes

    def test_lookup_roughness(self):
        from data.au_pipes import lookup_roughness
        c_new = lookup_roughness('Ductile Iron', age_years=0)
        c_old = lookup_roughness('Ductile Iron', age_years=30)
        assert c_new > c_old  # Roughness decreases with age

    def test_lookup_wave_speed(self):
        from data.au_pipes import lookup_wave_speed
        ws = lookup_wave_speed('Ductile Iron')
        assert 900 <= ws <= 1300  # Typical range

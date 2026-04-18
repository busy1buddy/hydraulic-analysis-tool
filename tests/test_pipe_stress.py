"""Tests for pipe stress calculations."""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestHoopStress:
    def test_basic_calculation(self):
        from epanet_api.pipe_stress import hoop_stress
        # 1000 kPa, 200mm dia, 6mm wall
        s = hoop_stress(1000, 200, 6)
        # sigma = P*D/(2t) = 1.0 * 200 / (2*6) = 16.67 MPa
        assert abs(s - 16.67) < 0.1

    def test_zero_thickness(self):
        from epanet_api.pipe_stress import hoop_stress
        assert hoop_stress(1000, 200, 0) == 0

    def test_higher_pressure_more_stress(self):
        from epanet_api.pipe_stress import hoop_stress
        s1 = hoop_stress(500, 200, 6)
        s2 = hoop_stress(1000, 200, 6)
        assert s2 > s1


class TestVonMises:
    def test_combined_stress(self):
        from epanet_api.pipe_stress import von_mises_stress
        vm = von_mises_stress(100, -10, 50)
        assert vm > 0

    def test_uniaxial(self):
        from epanet_api.pipe_stress import von_mises_stress
        # Pure uniaxial = should equal the stress
        vm = von_mises_stress(100, 0, 0)
        assert abs(vm - 100) < 0.1


class TestBarlowWallThickness:
    def test_basic_design(self):
        from epanet_api.pipe_stress import barlow_wall_thickness
        result = barlow_wall_thickness(1600, 200, 300, safety_factor=2.0)
        assert result['min_thickness_mm'] > 0
        assert result['design_thickness_mm'] > result['min_thickness_mm']

    def test_higher_pressure_thicker_wall(self):
        from epanet_api.pipe_stress import barlow_wall_thickness
        r1 = barlow_wall_thickness(1000, 200, 300)
        r2 = barlow_wall_thickness(3000, 200, 300)
        assert r2['min_thickness_mm'] > r1['min_thickness_mm']


class TestFullAnalysis:
    def test_ductile_iron(self):
        from epanet_api.pipe_stress import analyze_pipe_stress
        result = analyze_pipe_stress(1000, 200, 7.0, 'ductile_iron')
        assert result['hoop_stress_MPa'] > 0
        assert result['safety_factor_hoop'] > 1.0
        assert result['status'] == 'OK'

    def test_high_pressure_warning(self):
        from epanet_api.pipe_stress import analyze_pipe_stress
        result = analyze_pipe_stress(5000, 200, 3.0, 'pvc_pn12')
        assert result['safety_factor_hoop'] < 3.0

    def test_transient_factor(self):
        from epanet_api.pipe_stress import analyze_pipe_stress
        r1 = analyze_pipe_stress(1000, 200, 7.0, 'ductile_iron', transient_factor=1.0)
        r2 = analyze_pipe_stress(1000, 200, 7.0, 'ductile_iron', transient_factor=2.0)
        assert r2['hoop_stress_MPa'] > r1['hoop_stress_MPa']
        assert r2['safety_factor_hoop'] < r1['safety_factor_hoop']

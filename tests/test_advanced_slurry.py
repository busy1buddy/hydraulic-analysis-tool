"""
Tests for Advanced Slurry Features (I15)
==========================================
Settling velocity, critical deposition velocity, concentration profile.
"""

import os
import sys
import math
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api.slurry_solver import (
    settling_velocity,
    critical_deposition_velocity,
    concentration_profile,
)


class TestSettlingVelocity:
    """Tests for single-particle settling velocity calculation."""

    def test_sand_in_water(self):
        """Fine sand (0.1 mm, ρ=2650) settling in water."""
        result = settling_velocity(0.1, rho_solid=2650)
        assert result['velocity_ms'] > 0
        assert result['velocity_ms'] < 0.1  # fine sand settles slowly
        assert 'Stokes' in result['regime'] or 'transitional' in result['regime']

    def test_coarse_gravel(self):
        """Coarse gravel (10 mm, ρ=2650) should settle fast."""
        result = settling_velocity(10.0, rho_solid=2650)
        assert result['velocity_ms'] > 0.1
        assert result['reynolds'] > 1  # not Stokes

    def test_zero_particle_size(self):
        result = settling_velocity(0, rho_solid=2650)
        assert result['velocity_ms'] == 0

    def test_neutral_buoyancy(self):
        """Particle with same density as fluid should not settle."""
        result = settling_velocity(1.0, rho_solid=1000, rho_fluid=1000)
        assert result['velocity_ms'] == 0
        assert result['regime'] == 'neutral'

    def test_increasing_size_increases_velocity(self):
        """Larger particles should settle faster."""
        v1 = settling_velocity(0.1, rho_solid=2650)['velocity_ms']
        v2 = settling_velocity(1.0, rho_solid=2650)['velocity_ms']
        v3 = settling_velocity(5.0, rho_solid=2650)['velocity_ms']
        assert v1 < v2 < v3

    def test_stokes_known_value(self):
        """Verify Stokes' law for very fine particle (d=0.01mm, Re<<1).
        V_s = d²×Δρ×g / (18×μ) = (1e-5)²×1650×9.81 / (18×0.001) = 0.0000899
        """
        result = settling_velocity(0.01, rho_solid=2650, rho_fluid=1000, mu_fluid=0.001)
        expected = (1e-5)**2 * 1650 * 9.81 / (18 * 0.001)
        assert abs(result['velocity_ms'] - expected) < 0.0001


class TestCriticalDepositionVelocity:
    """Tests for Durand critical deposition velocity."""

    def test_typical_mine_tailings(self):
        """300mm pipe, 0.5mm sand, Cv=10%."""
        result = critical_deposition_velocity(
            d_particle_mm=0.5, pipe_diameter_mm=300,
            concentration_vol=0.10)
        assert result['velocity_ms'] > 1.0
        assert result['velocity_ms'] < 5.0
        assert result['specific_gravity'] == 2.65

    def test_larger_pipe_higher_velocity(self):
        """Larger pipes need higher velocity to prevent settling."""
        v_small = critical_deposition_velocity(0.5, 150)['velocity_ms']
        v_large = critical_deposition_velocity(0.5, 600)['velocity_ms']
        assert v_large > v_small

    def test_coarser_particles_higher_velocity(self):
        """Coarser particles need higher velocity."""
        v_fine = critical_deposition_velocity(0.1, 300)['velocity_ms']
        v_coarse = critical_deposition_velocity(2.0, 300)['velocity_ms']
        assert v_coarse > v_fine

    def test_durand_known_range(self):
        """Durand F_L should be in range 0.5-2.0."""
        result = critical_deposition_velocity(0.5, 300)
        assert 0.5 <= result['durand_fl'] <= 2.0

    def test_basis_string_present(self):
        result = critical_deposition_velocity(0.5, 300)
        assert 'Durand' in result['basis']

    def test_zero_diameter_returns_zero(self):
        result = critical_deposition_velocity(0.5, 0)
        assert result['velocity_ms'] == 0


class TestConcentrationProfile:
    """Tests for Rouse vertical concentration profile."""

    def test_profile_has_points(self):
        result = concentration_profile(
            pipe_diameter_mm=300, velocity_ms=2.0,
            d_particle_mm=0.5, concentration_avg=0.10)
        assert len(result['y_positions']) == 20
        assert len(result['concentrations']) == 20

    def test_bottom_concentration_higher(self):
        """Concentration should be higher near the bottom of the pipe."""
        result = concentration_profile(
            pipe_diameter_mm=300, velocity_ms=1.5,
            d_particle_mm=1.0, concentration_avg=0.10)
        if len(result['concentrations']) >= 2:
            # Bottom should have higher concentration than top
            assert result['concentrations'][0] >= result['concentrations'][-1]

    def test_rouse_number_positive(self):
        result = concentration_profile(
            pipe_diameter_mm=300, velocity_ms=2.0,
            d_particle_mm=0.5)
        assert result['rouse_z'] >= 0

    def test_high_velocity_uniform_profile(self):
        """At very high velocity, profile should be more uniform (low Rouse z)."""
        result_slow = concentration_profile(300, 1.0, 0.5, concentration_avg=0.1)
        result_fast = concentration_profile(300, 5.0, 0.5, concentration_avg=0.1)
        # Faster flow = lower Rouse number = more uniform
        assert result_fast['rouse_z'] <= result_slow['rouse_z']

    def test_zero_velocity_returns_empty(self):
        result = concentration_profile(300, 0, 0.5)
        assert len(result['y_positions']) == 0

    def test_concentration_capped(self):
        """No concentration should exceed 65% (packing limit)."""
        result = concentration_profile(
            pipe_diameter_mm=300, velocity_ms=0.5,
            d_particle_mm=2.0, concentration_avg=0.5)
        for c in result['concentrations']:
            assert c <= 0.65

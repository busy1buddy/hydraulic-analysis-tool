"""
Boundary Condition Tests — QA Cycle 1
======================================
Tests for zero, negative, and extreme inputs that could cause
division by zero, NaN, or silent incorrect results.

Found during QA adversarial testing (2026-04-06).
"""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epanet_api.slurry_solver import (
    bingham_plastic_headloss,
    power_law_headloss,
    herschel_bulkley_headloss,
    settling_velocity,
    critical_deposition_velocity,
)
from epanet_api.pipe_stress import hoop_stress, analyze_pipe_stress


# ── Slurry Solver Boundary Tests ────────────────────────────────────────────

class TestBinghamBoundary:
    """Boundary tests for bingham_plastic_headloss."""

    VALID = dict(flow_m3s=0.02, diameter_m=0.2, length_m=100,
                 density=1800, tau_y=15.0, mu_p=0.05, roughness_mm=0.1)

    def test_zero_mu_p_no_crash(self):
        """Zero plastic viscosity must not crash (was ZeroDivisionError)."""
        r = bingham_plastic_headloss(**{**self.VALID, 'mu_p': 0})
        assert r['regime'] == 'error'
        assert 'error' in r

    def test_negative_mu_p_no_crash(self):
        """Negative plastic viscosity must not crash."""
        r = bingham_plastic_headloss(**{**self.VALID, 'mu_p': -0.01})
        assert r['regime'] == 'error'

    def test_zero_density_no_crash(self):
        """Zero density must return error, not crash (was ZeroDivisionError)."""
        r = bingham_plastic_headloss(**{**self.VALID, 'density': 0})
        assert r['regime'] == 'error'
        assert 'error' in r

    def test_zero_tau_y_newtonian(self):
        """Zero yield stress degenerates to Newtonian — valid physics."""
        r = bingham_plastic_headloss(**{**self.VALID, 'tau_y': 0})
        assert r['headloss_m'] >= 0
        assert math.isfinite(r['headloss_m'])

    def test_zero_flow_static(self):
        """Zero flow must return static regime."""
        r = bingham_plastic_headloss(**{**self.VALID, 'flow_m3s': 0})
        assert r['regime'] == 'static'
        assert r['headloss_m'] == 0

    def test_zero_diameter_safe(self):
        """Zero diameter must not crash."""
        r = bingham_plastic_headloss(**{**self.VALID, 'diameter_m': 0})
        assert r['regime'] == 'static'

    def test_extreme_flow_finite(self):
        """Very high flow must produce finite headloss."""
        r = bingham_plastic_headloss(**{**self.VALID, 'flow_m3s': 100})
        assert math.isfinite(r['headloss_m'])

    def test_negative_flow_abs(self):
        """Negative flow treated as absolute value."""
        r_pos = bingham_plastic_headloss(**{**self.VALID, 'flow_m3s': 0.02})
        r_neg = bingham_plastic_headloss(**{**self.VALID, 'flow_m3s': -0.02})
        assert abs(r_pos['headloss_m'] - r_neg['headloss_m']) < 0.001


class TestPowerLawBoundary:
    """Boundary tests for power_law_headloss."""

    VALID = dict(flow_m3s=0.02, diameter_m=0.2, length_m=100,
                 density=1200, K=0.5, n=0.8, roughness_mm=0.1)

    def test_zero_K_no_crash(self):
        """Zero consistency index must not crash (was ZeroDivisionError)."""
        r = power_law_headloss(**{**self.VALID, 'K': 0})
        assert r['regime'] == 'error'
        assert 'error' in r

    def test_zero_n_no_crash(self):
        """Zero flow behaviour index must not crash."""
        r = power_law_headloss(**{**self.VALID, 'n': 0})
        assert r['regime'] == 'error'

    def test_negative_K_no_crash(self):
        """Negative K must not crash."""
        r = power_law_headloss(**{**self.VALID, 'K': -0.5})
        assert r['regime'] == 'error'

    def test_zero_flow_static(self):
        """Zero flow must return static."""
        r = power_law_headloss(**{**self.VALID, 'flow_m3s': 0})
        assert r['regime'] == 'static'


class TestSettlingBoundary:
    """Boundary tests for settling_velocity."""

    def test_zero_mu_fluid_no_crash(self):
        """Zero fluid viscosity must not crash (was ZeroDivisionError)."""
        r = settling_velocity(1.0, 2650, 1000, mu_fluid=0)
        assert r['regime'] == 'error'
        assert 'error' in r

    def test_negative_mu_fluid_no_crash(self):
        """Negative fluid viscosity must not crash."""
        r = settling_velocity(1.0, 2650, 1000, mu_fluid=-0.001)
        assert r['regime'] == 'error'

    def test_zero_particle_size(self):
        """Zero particle size returns zero velocity."""
        r = settling_velocity(0, 2650, 1000)
        assert r['velocity_ms'] == 0

    def test_neutral_buoyancy(self):
        """Same density returns zero velocity."""
        r = settling_velocity(1.0, 1000, 1000)
        assert r['velocity_ms'] == 0


# ── Pipe Stress Boundary Tests ──────────────────────────────────────────────

class TestPipeStressBoundary:
    """Boundary tests for pipe stress calculations."""

    def test_zero_wall_thickness(self):
        """Zero wall thickness returns 0, not division error."""
        assert hoop_stress(1000, 200, 0) == 0

    def test_negative_wall_thickness(self):
        """Negative wall thickness returns 0."""
        assert hoop_stress(1000, 200, -5) == 0

    def test_zero_pressure(self):
        """Zero pressure gives zero stress."""
        assert hoop_stress(0, 200, 10) == 0

    def test_negative_pressure_allowed(self):
        """Negative pressure (vacuum) is physically valid."""
        s = hoop_stress(-100, 200, 10)
        assert s < 0  # Compressive

    def test_stress_analysis_zero_thickness(self):
        """Full stress analysis with zero thickness must not crash."""
        r = analyze_pipe_stress(1000, 200, 0)
        assert 'hoop_stress_MPa' in r


# ── API Boundary Tests ──────────────────────────────────────────────────────

class TestAPIBoundary:
    """Boundary tests for the HydraulicAPI."""

    def test_negative_elevation_valid(self):
        """Negative elevation (below sea level) is physically valid."""
        from epanet_api import HydraulicAPI
        api = HydraulicAPI()
        api.create_network(
            junctions=[
                {'id': 'J1', 'x': 0, 'y': 0, 'elevation': -10, 'demand': 5},
            ],
            reservoirs=[
                {'id': 'R1', 'x': 100, 'y': 0, 'elevation': 50, 'head': 50},
            ],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        r = api.run_steady_state(save_plot=False)
        assert 'error' not in r
        # Pressure at J1 should be positive (reservoir head is +50m, junction at -10m)
        p = r['pressures']['J1']
        assert p['min_m'] > 0

    def test_zero_demand_no_crash(self):
        """Zero demand is valid — all nodes at static head."""
        from epanet_api import HydraulicAPI
        api = HydraulicAPI()
        api.create_network(
            junctions=[
                {'id': 'J1', 'x': 0, 'y': 0, 'elevation': 0, 'demand': 0},
            ],
            reservoirs=[
                {'id': 'R1', 'x': 100, 'y': 0, 'elevation': 50, 'head': 50},
            ],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        r = api.run_steady_state(save_plot=False)
        assert 'error' not in r

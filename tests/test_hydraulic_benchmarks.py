"""
Hydraulic Benchmark Tests
==========================
Converted from docs/reviews/2026-04-03/hydraulic-benchmarks.md.

Each benchmark verifies a fundamental hydraulic calculation against
a hand-calculated reference value with a stated tolerance.

Source references cited inline per CLAUDE.md code conventions.
"""

import math
import pytest
import numpy as np

from epanet_api import HydraulicAPI
from pipe_stress import hoop_stress, radial_stress, axial_stress, von_mises_stress, barlow_wall_thickness
from slurry_solver import bingham_plastic_headloss
from data.pump_curves import get_pump_head


# =========================================================================
# Benchmark 1 — Joukowsky Water Hammer
# Reference: Joukowsky (1898), dH = a × dV / g
# =========================================================================

class TestBenchmark1Joukowsky:
    """Joukowsky pressure rise: dH = a * dV / g."""

    def setup_method(self):
        self.api = HydraulicAPI()
        # Inputs from benchmark spec
        self.result = self.api.joukowsky(wave_speed=1000, velocity_change=1.5)

    def test_head_rise(self):
        # Hand calc: dH = 1000 * 1.5 / 9.81 = 152.91 m
        expected = 1000 * 1.5 / 9.81  # 152.905 m
        assert abs(self.result['head_rise_m'] - expected) < 0.5, (
            f"Joukowsky head rise {self.result['head_rise_m']} m != expected {expected:.2f} m (±0.5 m)"
        )

    def test_pressure_rise(self):
        # dP = rho * a * dV = 1000 * 1000 * 1.5 = 1,500,000 Pa = 1500 kPa
        assert abs(self.result['pressure_rise_kPa'] - 1500) < 10

    def test_slurry_pressure_rise(self):
        """Slurry (rho=1500) pressure rise should be 50% higher than water."""
        result_slurry = self.api.joukowsky(wave_speed=1000, velocity_change=1.5, density=1500)
        # dP = 1500 * 1000 * 1.5 = 2,250,000 Pa = 2250 kPa
        assert abs(result_slurry['pressure_rise_kPa'] - 2250) < 10
        # Head rise is the same regardless of density
        assert abs(result_slurry['head_rise_m'] - self.result['head_rise_m']) < 0.1


# =========================================================================
# Benchmark 2 — Hoop Stress (Thin-Wall Theory)
# Reference: Barlow's formula, σ_h = P × D / (2t)
# =========================================================================

class TestBenchmark2HoopStress:
    """Hoop stress: σ_h = P * D / (2t)."""

    def test_hoop_stress(self):
        # Inputs: P=1000 kPa (1.0 MPa), D=300 mm, t=8 mm
        # Hand calc: σ_h = (1.0 * 300) / (2 * 8) = 18.75 MPa
        result = hoop_stress(pressure_kPa=1000, diameter_mm=300, wall_thickness_mm=8)
        assert abs(result - 18.75) < 0.01, (
            f"Hoop stress {result} MPa != expected 18.75 MPa (±0.01)"
        )


# =========================================================================
# Benchmark 3 — Von Mises Equivalent Stress
# Reference: σ_vm = √(0.5 × ((σ1−σ2)² + (σ2−σ3)² + (σ3−σ1)²))
# =========================================================================

class TestBenchmark3VonMises:
    """Von Mises equivalent stress from combined loading."""

    def test_von_mises(self):
        # Inputs: σ_h=18.75, σ_r=-1.0, σ_a=9.375
        # Hand calc: √(0.5 × ((18.75+1)² + (-1-9.375)² + (9.375-18.75)²))
        #          = √(0.5 × (390.0625 + 107.640625 + 87.890625))
        #          = √(292.797) ≈ 17.11 MPa
        sigma_h = 18.75
        sigma_r = -1.0
        sigma_a = 9.375
        expected = math.sqrt(0.5 * ((sigma_h - sigma_r)**2 +
                                     (sigma_r - sigma_a)**2 +
                                     (sigma_a - sigma_h)**2))
        result = von_mises_stress(sigma_h, sigma_r, sigma_a)
        assert abs(result - expected) < 0.5, (
            f"Von Mises {result} MPa != expected {expected:.2f} MPa (±0.5)"
        )


# =========================================================================
# Benchmark 4 — Barlow Minimum Wall Thickness
# Reference: t_min = P × D / (2S), where S = allowable/SF
# =========================================================================

class TestBenchmark4BarlowWall:
    """Barlow wall thickness design."""

    def test_min_wall_thickness(self):
        # Inputs: P=1000 kPa, D=300 mm, S=300 MPa (DI), SF=2.0
        # Hand calc: t = (1.0 * 300) / (2 * 300/2.0) = 300/300 = 1.0 mm
        result = barlow_wall_thickness(
            pressure_kPa=1000, diameter_mm=300,
            allowable_stress_MPa=300, safety_factor=2.0,
            corrosion_allowance_mm=0,
        )
        assert abs(result['min_thickness_mm'] - 1.0) < 0.1, (
            f"Barlow min wall {result['min_thickness_mm']} mm != expected 1.0 mm (±0.1)"
        )

    def test_design_thickness_with_corrosion(self):
        # With 1 mm corrosion allowance: t_design = 1.0 + 1.0 = 2.0 mm
        result = barlow_wall_thickness(
            pressure_kPa=1000, diameter_mm=300,
            allowable_stress_MPa=300, safety_factor=2.0,
            corrosion_allowance_mm=1.0,
        )
        assert abs(result['design_thickness_mm'] - 2.0) < 0.1


# =========================================================================
# Benchmark 5 — Steady-State Mass Balance
# Reference: Conservation of mass — Σ Q_in − Σ Q_out = demand at each junction
# =========================================================================

class TestBenchmark5MassBalance:
    """Mass balance at every junction in australian_network.inp."""

    def setup_method(self):
        self.api = HydraulicAPI()
        self.api.load_network('australian_network.inp')
        self.results = self.api.run_steady_state(save_plot=False)

    def test_mass_balance_all_junctions(self):
        # At t=0, sum of flows into each junction minus flows out must equal
        # the actual simulated demand (not the base_demand pattern value).
        # We verify that WNTR's own flow solution is self-consistent.
        sr = self.api.get_steady_results()
        flows = sr.link['flowrate']
        demands = sr.node['demand']
        wn = self.api.wn
        tolerance_m3s = 0.01 / 1000  # 0.01 LPS in m³/s

        for junc_name in wn.junction_name_list:
            # Actual simulated demand at t=0
            demand = float(demands[junc_name].iloc[0])

            net_flow = 0  # positive = inflow
            for link_name in wn.link_name_list:
                link = wn.get_link(link_name)
                q = float(flows[link_name].iloc[0])
                if link.end_node_name == junc_name:
                    net_flow += q
                elif link.start_node_name == junc_name:
                    net_flow -= q

            # net_flow should equal demand (flow into junction = demand withdrawn)
            imbalance = abs(net_flow - demand)
            assert imbalance < tolerance_m3s, (
                f"Mass imbalance at {junc_name}: {imbalance*1000:.6f} LPS > 0.01 LPS"
            )


# =========================================================================
# Benchmark 6 — Bingham Plastic Newtonian Baseline (B1 fix verification)
# Reference: Buckingham-Reiner at τ_y=0 reduces to Hagen-Poiseuille
#            hf = 128μLQ / (πρgD⁴)
# =========================================================================

class TestBenchmark6BinghamNewtonianBaseline:
    """At τ_y≈0 the Bingham solver must match Hagen-Poiseuille."""

    def test_laminar_newtonian_headloss(self):
        # Inputs: Q=1e-5 m³/s, D=0.02 m, L=100 m, μ=0.001 Pa·s, ρ=1000
        # Hagen-Poiseuille: hf = 128*μ*L*Q / (π*ρ*g*D⁴)
        Q = 0.00001
        D = 0.02
        L = 100
        mu = 0.001
        rho = 1000
        g = 9.81
        expected = 128 * mu * L * Q / (math.pi * rho * g * D**4)
        # expected ≈ 0.02596 m

        # Use very small τ_y to approach Newtonian limit.
        # τ_y=0.0001 Pa gives He~0.004, Buckingham-Reiner correction negligible.
        # Solver rounds to 3 decimals, so allow rounding tolerance.
        result = bingham_plastic_headloss(
            flow_m3s=Q, diameter_m=D, length_m=L,
            density=rho, tau_y=0.0001,  # near-zero yield stress
            mu_p=mu, roughness_mm=0.001,
        )

        # Tolerance: 5% of expected (per benchmark spec), plus 0.001 m rounding margin
        diff_pct = abs(result['headloss_m'] - expected) / expected
        assert diff_pct < 0.05, (
            f"Bingham Newtonian baseline: got {result['headloss_m']:.6f} m, "
            f"expected {expected:.6f} m (diff {diff_pct*100:.1f}% > 5%)"
        )

    def test_darcy_not_fanning(self):
        """The fix changed 16/Re to 64/Re. Verify result is ~4x the old buggy value."""
        # The old bug returned ~0.006 m; the fix should return ~0.026 m
        result = bingham_plastic_headloss(
            flow_m3s=0.00001, diameter_m=0.02, length_m=100,
            density=1000, tau_y=0.001, mu_p=0.001,
            roughness_mm=0.001,
        )
        # Must be above 0.020 m (old buggy value was 0.006 m)
        assert result['headloss_m'] > 0.020, (
            f"Headloss {result['headloss_m']} m too low — likely still using Fanning (16/Re)"
        )


# =========================================================================
# Benchmark 7 — Hazen-Williams Headloss
# Reference: hf = (10.67 × L × Q^1.852) / (C^1.852 × D^4.87)
# =========================================================================

class TestBenchmark7HazenWilliams:
    """Hazen-Williams headloss for pipe P1 in australian_network.inp."""

    def setup_method(self):
        self.api = HydraulicAPI()
        self.api.load_network('australian_network.inp')
        self.results = self.api.run_steady_state(save_plot=False)

    def test_headloss_pipe_p1(self):
        # P1: L=500 m, D=0.3 m, C=130
        # Simulated flow at t=0
        sr = self.api.get_steady_results()
        Q_m3s = abs(float(sr.link['flowrate']['P1'].iloc[0]))

        pipe = self.api.get_link('P1')
        L = pipe.length
        D = pipe.diameter
        C = pipe.roughness

        # Hand calc: hf = (10.67 * L * Q^1.852) / (C^1.852 * D^4.87)
        hf_hand = (10.67 * L * Q_m3s**1.852) / (C**1.852 * D**4.87)

        # EPANET headloss: head difference between endpoints at t=0
        pressures = sr.node['head']
        start_head = float(pressures[pipe.start_node_name].iloc[0])
        end_head = float(pressures[pipe.end_node_name].iloc[0])
        hf_sim = abs(start_head - end_head)

        # Tolerance: 5%
        assert abs(hf_sim - hf_hand) / hf_hand < 0.05, (
            f"HW headloss: simulated {hf_sim:.4f} m vs hand {hf_hand:.4f} m (>5% diff)"
        )


# =========================================================================
# Benchmark 8 — Pump Affinity Laws
# Reference: Q2/Q1 = N2/N1; H2/H1 = (N2/N1)²
# =========================================================================

class TestBenchmark8PumpAffinity:
    """Pump affinity laws: flow scales linearly, head quadratically with speed."""

    def test_flow_scaling(self):
        # WSP-200-40 at 100%: Q1=30 LPS
        # At 80%: Q2 = 30 * 0.8 = 24.0 LPS
        # Affinity: flow point shifts from 30 to 24.0 LPS
        Q1 = 30.0
        speed_ratio = 0.80
        Q2_expected = Q1 * speed_ratio  # 24.0 LPS

        # The pump curve get_pump_head scales flow by speed_pct/100
        # Verify head at the scaled flow point
        H1 = get_pump_head('WSP-200-40', Q1, speed_pct=100)
        H2 = get_pump_head('WSP-200-40', Q2_expected, speed_pct=80)

        # Head ratio should be speed_ratio²
        head_ratio = H2 / H1
        expected_head_ratio = speed_ratio**2  # 0.64
        assert abs(head_ratio - expected_head_ratio) < 0.01, (
            f"Head ratio {head_ratio:.4f} != expected {expected_head_ratio:.4f} (±1%)"
        )

    def test_head_at_80pct_speed(self):
        # At 80% speed, Q=24 LPS: expected H2 = 24.32 m
        H2 = get_pump_head('WSP-200-40', 24.0, speed_pct=80)
        assert abs(H2 - 24.32) < 0.5, (
            f"Head at 80% speed: {H2:.2f} m != expected 24.32 m (±0.5)"
        )


# =========================================================================
# Benchmark 9 — Pipe Velocity = Q/A
# Reference: V = Q / A = Q / (π(D/2)²)
# =========================================================================

class TestBenchmark9VelocityQoverA:
    """Velocity for every pipe must equal Q/A within numerical precision."""

    def setup_method(self):
        self.api = HydraulicAPI()
        self.api.load_network('australian_network.inp')
        self.results = self.api.run_steady_state(save_plot=False)

    def test_velocity_equals_q_over_a(self):
        sr = self.api.get_steady_results()
        flows = sr.link['flowrate']
        tolerance = 0.01  # m/s

        for pipe_name in self.api.get_link_list('pipe'):
            pipe = self.api.get_link(pipe_name)
            Q = abs(float(flows[pipe_name].iloc[0]))  # m³/s at t=0
            A = math.pi * (pipe.diameter / 2)**2
            V_calc = Q / A if A > 0 else 0

            # Get simulated velocity from results
            flow_data = self.results['flows'].get(pipe_name, {})
            # Use avg velocity at t=0 — compute from flow directly
            # V_sim from WNTR flow / area
            V_sim = V_calc  # WNTR doesn't store velocity directly; we compute it

            # The real check: does our reported velocity match Q/A?
            reported_v = flow_data.get('max_velocity_ms', 0)
            # For single-timestep at t=0, max ≈ Q/A
            # Use the raw flow series for exact check
            Q_series = flows[pipe_name].abs()
            V_max_calc = float(Q_series.max()) / A if A > 0 else 0

            assert abs(reported_v - V_max_calc) < tolerance, (
                f"Pipe {pipe_name}: reported V={reported_v:.4f}, Q/A={V_max_calc:.4f} "
                f"(diff {abs(reported_v - V_max_calc):.6f} > {tolerance})"
            )


# =========================================================================
# Benchmark 10 — WSAA Compliance Thresholds
# Reference: WSAA Guidelines for water distribution systems
# =========================================================================

class TestBenchmark10WSAAThresholds:
    """WSAA compliance thresholds must match documented values exactly."""

    def setup_method(self):
        self.api = HydraulicAPI()

    def test_min_pressure(self):
        # WSAA WSA 03-2011 Table 3.1: min 20 m
        assert self.api.DEFAULTS['min_pressure_m'] == 20

    def test_max_pressure(self):
        # WSAA WSA 03-2011: max 50 m (residential)
        assert self.api.DEFAULTS['max_pressure_m'] == 50

    def test_max_velocity(self):
        # WSAA: max 2.0 m/s
        assert self.api.DEFAULTS['max_velocity_ms'] == 2.0

    def test_pipe_rating(self):
        # PN35 ductile iron: 3500 kPa
        assert self.api.DEFAULTS['pipe_rating_kPa'] == 3500

"""
Slurry Solver Validation Tests
================================
Validates Bingham plastic solver against hand calculations and
published Buckingham-Reiner solutions.
"""
import math
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from slurry_solver import bingham_plastic_headloss


class TestBuckinghamReinerValidation:

    def test_case1_laminar_moderate_slurry(self):
        """tau_y=10, mu_p=0.05, D=0.1, L=100, Q=0.005, rho=1200."""
        r = bingham_plastic_headloss(0.005, 0.1, 100, 1200, 10, 0.05)
        assert r['regime'] == 'laminar'
        assert 1500 < r['reynolds'] < 1600
        assert 47000 < r['hedstrom'] < 49000
        # Darcy-Weisbach cross-check
        V = 0.005 / (math.pi * 0.05**2)
        hl_check = r['friction_factor'] * (100/0.1) * V**2 / (2*9.81)
        assert abs(r['headloss_m'] - hl_check) < 0.01

    def test_case2_laminar_heavy_slurry(self):
        """tau_y=50, mu_p=0.1, D=0.15, L=200, Q=0.01, rho=1500."""
        r = bingham_plastic_headloss(0.01, 0.15, 200, 1500, 50, 0.1)
        assert r['regime'] == 'laminar'
        # B-R hand calc
        Re = r['reynolds']
        He = r['hedstrom']
        f_br = 64/Re * (1 + He/(6*Re) - He**4/(3e7*Re**7))
        assert abs(r['friction_factor'] - max(f_br, 64/Re)) < 0.001

    def test_newtonian_limit(self):
        """At tau_y~0, must match Hagen-Poiseuille within 5%."""
        r = bingham_plastic_headloss(0.00001, 0.02, 100, 1000, 0.0001, 0.001, 0.001)
        expected = 128 * 0.001 * 100 * 0.00001 / (math.pi * 1000 * 9.81 * 0.02**4)
        assert abs(r['headloss_m'] - expected) / expected < 0.05

    def test_darcy_not_fanning(self):
        """Friction factor must be Darcy (64/Re), not Fanning (16/Re)."""
        r = bingham_plastic_headloss(0.00001, 0.02, 100, 1000, 0.0001, 0.001, 0.001)
        assert r['headloss_m'] > 0.020  # Fanning would give ~0.006

    def test_zero_flow(self):
        r = bingham_plastic_headloss(0.0, 0.2, 100, 1500, 10, 0.02)
        assert r['headloss_m'] == 0

    def test_higher_yield_more_headloss(self):
        r_low = bingham_plastic_headloss(0.01, 0.2, 100, 1200, 5, 0.05)
        r_high = bingham_plastic_headloss(0.01, 0.2, 100, 1200, 50, 0.05)
        assert r_high['headloss_m'] > r_low['headloss_m']

    def test_higher_flow_more_headloss(self):
        r_low = bingham_plastic_headloss(0.005, 0.2, 100, 1200, 10, 0.05)
        r_high = bingham_plastic_headloss(0.02, 0.2, 100, 1200, 10, 0.05)
        assert r_high['headloss_m'] > r_low['headloss_m']

    def test_buckingham_reiner_floor(self):
        """max(f_BR, 64/Re) should always apply."""
        r = bingham_plastic_headloss(0.001, 0.1, 100, 1200, 1, 0.05)
        if r['regime'] == 'laminar':
            assert r['friction_factor'] >= 64 / r['reynolds'] - 0.001

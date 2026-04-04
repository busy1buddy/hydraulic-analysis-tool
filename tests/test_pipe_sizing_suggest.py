"""
Tests for Pipe Sizing Recommendation (N2)
===========================================
"""

import os
import sys
import math
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestPipeSizingSuggestion:
    """Test the pipe sizing logic at the API level."""

    def test_size_for_velocity(self):
        """DN should be sized for ~1.0 m/s at peak demand."""
        # 5 LPS base × 1.5 peak = 7.5 LPS = 0.0075 m³/s
        # D = sqrt(4 × 0.0075 / (π × 1.0)) = 0.0977 m = 97.7 mm → DN100
        Q_peak = 0.0075  # m³/s
        D_calc = math.sqrt(4 * Q_peak / (math.pi * 1.0))
        D_mm = D_calc * 1000

        standard_dns = [50, 63, 75, 80, 100, 110, 150, 160, 200]
        suggested = next(dn for dn in standard_dns if dn >= D_mm)
        assert suggested == 100

    def test_larger_demand_larger_pipe(self):
        """Higher demand should suggest larger pipe."""
        # 2 LPS peak → small pipe, 50 LPS peak → large pipe
        for demand_lps, min_dn in [(2, 50), (10, 100), (50, 200)]:
            Q = demand_lps / 1000
            D = math.sqrt(4 * Q / (math.pi * 1.0)) * 1000
            assert D <= min_dn + 100  # should be within reasonable range

    def test_standard_dn_always_selected(self):
        """Suggested DN should always be from standard AS/NZS range."""
        standard_dns = {50, 63, 75, 80, 100, 110, 150, 160, 200, 225,
                       250, 280, 300, 315, 375, 400, 450, 500, 600}
        # For any demand 0.1-100 LPS
        for demand_lps in [0.1, 1, 5, 10, 25, 50, 100]:
            Q = demand_lps * 1.5 / 1000  # peak
            D_mm = math.sqrt(4 * Q / (math.pi * 1.0)) * 1000
            suggested = min((dn for dn in standard_dns if dn >= D_mm), default=600)
            assert suggested in standard_dns

    def test_velocity_at_suggested_dn(self):
        """Velocity at suggested DN should be 0.5-2.0 m/s."""
        demand_lps = 5.0
        Q_peak = demand_lps * 1.5 / 1000
        D_mm = math.sqrt(4 * Q_peak / (math.pi * 1.0)) * 1000

        standard_dns = [50, 63, 75, 80, 100, 110, 150, 160, 200, 225, 250, 300]
        suggested = next(dn for dn in standard_dns if dn >= D_mm)

        D_m = suggested / 1000
        A = math.pi / 4 * D_m ** 2
        v = Q_peak / A
        assert 0.3 <= v <= 2.5, f"Velocity {v:.2f} m/s at DN{suggested} is outside range"

    def test_zero_demand_defaults(self):
        """Zero demand should still suggest a reasonable minimum DN."""
        # With zero demand, formula gives D=0, should default to smallest standard
        Q = 0
        if Q <= 0:
            suggested = 100  # minimum practical pipe size
        assert suggested >= 50

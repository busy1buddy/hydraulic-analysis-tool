"""Tests for pump curve database and recommendation engine."""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPumpDatabase:
    def test_has_pumps(self):
        from data.pump_curves import PUMP_DATABASE
        assert len(PUMP_DATABASE) >= 5

    def test_list_pumps(self):
        from data.pump_curves import list_pumps
        pumps = list_pumps()
        assert len(pumps) >= 5

    def test_list_water_pumps(self):
        from data.pump_curves import list_pumps
        pumps = list_pumps(application='water')
        assert all('slurry' not in p['pump_id'].lower() for p in pumps)

    def test_list_slurry_pumps(self):
        from data.pump_curves import list_pumps
        pumps = list_pumps(application='slurry')
        assert len(pumps) >= 1


class TestPumpCurves:
    def test_get_head_at_zero_flow(self):
        from data.pump_curves import get_pump_head
        head = get_pump_head('WSP-200-40', 0)
        assert head == 45  # Shutoff head

    def test_head_decreases_with_flow(self):
        from data.pump_curves import get_pump_head
        h1 = get_pump_head('WSP-200-40', 10)
        h2 = get_pump_head('WSP-200-40', 40)
        assert h1 > h2

    def test_speed_reduction(self):
        from data.pump_curves import get_pump_head
        h_100 = get_pump_head('WSP-200-40', 20, speed_pct=100)
        h_80 = get_pump_head('WSP-200-40', 20, speed_pct=80)
        assert h_80 < h_100

    def test_get_efficiency(self):
        from data.pump_curves import get_pump_efficiency
        eff = get_pump_efficiency('WSP-200-40', 30)
        assert 60 < eff < 85  # Should be near BEP

    def test_invalid_pump(self):
        from data.pump_curves import get_pump_head
        assert get_pump_head('NONEXISTENT', 10) is None


class TestSystemCurve:
    def test_generates_points(self):
        from data.pump_curves import generate_system_curve
        curve = generate_system_curve(30, 500, 200)
        assert len(curve) > 10
        assert curve[0][1] == 30  # Static head at zero flow

    def test_increases_with_flow(self):
        from data.pump_curves import generate_system_curve
        curve = generate_system_curve(30, 500, 200)
        # System head should increase with flow
        assert curve[-1][1] > curve[0][1]


class TestPumpRecommendation:
    def test_recommend_for_duty(self):
        from data.pump_curves import recommend_pump
        recs = recommend_pump(required_flow_lps=20, required_head_m=35)
        assert len(recs) >= 1
        assert recs[0]['head_at_duty_m'] >= 35

    def test_recommend_slurry(self):
        from data.pump_curves import recommend_pump
        recs = recommend_pump(required_flow_lps=30, required_head_m=25,
                             application='slurry')
        assert len(recs) >= 1

    def test_no_match(self):
        from data.pump_curves import recommend_pump
        recs = recommend_pump(required_flow_lps=1000, required_head_m=500)
        assert len(recs) == 0


class TestOperatingPoint:
    def test_find_operating_point(self):
        from data.pump_curves import find_operating_point, generate_system_curve
        sys_curve = generate_system_curve(20, 500, 200, roughness=130)
        op = find_operating_point('WSP-200-40', sys_curve)
        assert op is not None
        assert op['flow_lps'] > 0
        assert op['head_m'] > 0
        assert op['efficiency_pct'] > 0

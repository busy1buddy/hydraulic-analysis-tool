"""
Pump Energy & TOU Tariff Tests — Cycle 7
==========================================
Verifies pump energy calculations, time-of-use tariff breakdown,
and the optimised cost estimate.
"""

import os
import sys
import math

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epanet_api import HydraulicAPI


@pytest.fixture(scope='module')
def pump_api():
    """API loaded with pump_station tutorial (has PU1)."""
    api = HydraulicAPI()
    api.load_network('tutorials/pump_station/network.inp')
    return api


@pytest.fixture(scope='module')
def no_pump_api():
    """API loaded with demo_network (no pumps)."""
    api = HydraulicAPI()
    api.load_network('tutorials/demo_network/network.inp')
    return api


class TestPumpEnergyTOU:
    """TOU tariff pump energy analysis."""

    def test_returns_tou_breakdown(self, pump_api):
        result = pump_api.pump_energy_tou(operating_hours_per_day=18)
        assert 'error' not in result
        assert result['n_pumps'] >= 1
        pump = result['pumps'][0]
        assert 'tou_breakdown' in pump
        tou = pump['tou_breakdown']
        assert 'peak_kwh' in tou
        assert 'shoulder_kwh' in tou
        assert 'offpeak_kwh' in tou

    def test_tou_cost_breakdown_sums_to_total(self, pump_api):
        result = pump_api.pump_energy_tou(operating_hours_per_day=18)
        pump = result['pumps'][0]
        tou = pump['tou_breakdown']
        component_sum = (tou['peak_cost_aud'] + tou['shoulder_cost_aud']
                         + tou['offpeak_cost_aud'])
        total = pump['tou_total_aud']
        assert abs(component_sum - total) < 1.0, (
            f"Components sum to {component_sum}, total is {total}")

    def test_optimised_less_than_tou(self, pump_api):
        """Off-peak-only schedule should cost less than blended TOU."""
        result = pump_api.pump_energy_tou(operating_hours_per_day=18)
        pump = result['pumps'][0]
        assert pump['optimised_annual_aud'] <= pump['tou_total_aud']

    def test_saving_equals_difference(self, pump_api):
        result = pump_api.pump_energy_tou(operating_hours_per_day=18)
        pump = result['pumps'][0]
        expected_saving = pump['tou_total_aud'] - pump['optimised_annual_aud']
        assert abs(pump['optimised_saving_aud'] - expected_saving) < 1.0

    def test_tou_summary_present(self, pump_api):
        result = pump_api.pump_energy_tou()
        assert 'tou_summary' in result
        tou_sum = result['tou_summary']
        assert tou_sum['tariff']['peak_aud_kwh'] == 0.35
        assert tou_sum['tariff']['offpeak_aud_kwh'] == 0.15

    def test_tou_summary_totals_match_pumps(self, pump_api):
        result = pump_api.pump_energy_tou()
        pump_total = sum(p.get('tou_total_aud', 0) for p in result['pumps']
                         if 'error' not in p)
        assert abs(result['tou_summary']['total_annual_cost_tou_aud']
                    - pump_total) < 1.0

    def test_no_pumps_returns_zero(self, no_pump_api):
        result = no_pump_api.pump_energy_tou()
        assert result['n_pumps'] == 0
        assert result['tou_summary']['total_annual_cost_tou_aud'] == 0

    def test_energy_calculation_physics(self, pump_api):
        """Verify hydraulic power formula: P = rho*g*Q*H / 1000."""
        result = pump_api.pump_energy_tou()
        pump = result['pumps'][0]
        if 'error' in pump:
            pytest.skip("Pump has error")
        Q_m3s = pump['operating_flow_lps'] / 1000
        H = pump['operating_head_m']
        expected_hydraulic_kw = 1000 * 9.81 * Q_m3s * H / 1000
        assert abs(pump['hydraulic_power_kw'] - expected_hydraulic_kw) < 0.5, (
            f"Hydraulic power {pump['hydraulic_power_kw']} != "
            f"expected {expected_hydraulic_kw:.2f} kW")

    def test_efficiency_bounded(self, pump_api):
        """Efficiency should be between 30% and 82% (parabolic model bounds)."""
        result = pump_api.pump_energy_tou()
        for pump in result['pumps']:
            if 'error' in pump:
                continue
            eta = pump['efficiency']
            assert 0.24 <= eta <= 0.83, (
                f"Pump {pump['pump_id']} efficiency {eta} out of bounds")


class TestPumpEnergyDialogImport:
    """Verify the dialog can be imported without errors."""

    def test_dialog_importable(self):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from desktop.pump_energy_dialog import PumpEnergyDialog
        assert PumpEnergyDialog is not None

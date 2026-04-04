"""
EPANET Verification Test Suite
================================
Compares our HydraulicAPI results against WNTR's EpanetSimulator
reference output for the official EPA test networks (Net1, Net2, Net3).

These are regression tests: if our results ever diverge from the
EPANET 2.2 reference, these tests catch it.

See docs/validation/epanet_verification.md for full results.
"""

import os
import sys
import math

import pytest
import numpy as np
import wntr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epanet_api import HydraulicAPI


# Locate WNTR's bundled EPA test networks
_WNTR_NETS = os.path.join(os.path.dirname(wntr.__file__), 'library', 'networks')


def _load_and_compare(net_name):
    """Load a network through both paths and return max differences."""
    path = os.path.join(_WNTR_NETS, f'{net_name}.inp')
    assert os.path.exists(path), f'{net_name}.inp not found in WNTR library'

    # Reference: direct WNTR EpanetSimulator
    wn_ref = wntr.network.WaterNetworkModel(path)
    ref = wntr.sim.EpanetSimulator(wn_ref).run_sim()

    # Ours: via HydraulicAPI
    api = HydraulicAPI()
    api.load_network_from_path(path)
    api.run_steady_state(save_plot=False)
    ours = api.get_steady_results()

    # Pressure comparison (all nodes, all timesteps)
    ref_p = ref.node['pressure']
    our_p = ours.node['pressure']
    diff_p = (ref_p - our_p).abs()
    max_p = float(diff_p.max().max())

    # Flow comparison (all links, all timesteps)
    ref_f = ref.link['flowrate']
    our_f = ours.link['flowrate']
    diff_f = (ref_f - our_f).abs()
    max_f = float(diff_f.max().max())

    # Velocity comparison
    max_v = 0.0
    if 'velocity' in ref.link and 'velocity' in ours.link:
        ref_v = ref.link['velocity']
        our_v = ours.link['velocity']
        diff_v = (ref_v - our_v).abs()
        max_v = float(diff_v.max().max())

    info = {
        'junctions': len(wn_ref.junction_name_list),
        'pipes': len(wn_ref.pipe_name_list),
        'pumps': len(wn_ref.pump_name_list),
        'tanks': len(wn_ref.tank_name_list),
        'timesteps': len(ref_p.index),
        'max_pressure_diff_m': max_p,
        'max_flow_diff_m3s': max_f,
        'max_velocity_diff_ms': max_v,
    }
    return info


# =========================================================================
# Net1 — Simple network (9 junctions, 1 pump, 1 tank, 24h)
# =========================================================================

class TestNet1:

    @pytest.fixture(autouse=True, scope='class')
    def results(self):
        TestNet1._info = _load_and_compare('Net1')

    def test_network_loaded(self):
        assert self._info['junctions'] == 9
        assert self._info['pipes'] == 12
        assert self._info['pumps'] == 1
        assert self._info['tanks'] == 1

    def test_timesteps(self):
        assert self._info['timesteps'] == 25  # 24h + initial

    def test_pressure_exact(self):
        assert self._info['max_pressure_diff_m'] < 0.001, (
            f"Net1 pressure diff {self._info['max_pressure_diff_m']:.6f} m > 0.001 m"
        )

    def test_flow_exact(self):
        assert self._info['max_flow_diff_m3s'] < 0.00001, (
            f"Net1 flow diff {self._info['max_flow_diff_m3s']:.8f} m3/s > 1e-5"
        )

    def test_velocity_exact(self):
        assert self._info['max_velocity_diff_ms'] < 0.001, (
            f"Net1 velocity diff {self._info['max_velocity_diff_ms']:.6f} m/s > 0.001"
        )

    def test_zero_pressure_diff(self):
        """Our solver is EPANET via WNTR — difference should be exactly zero."""
        assert self._info['max_pressure_diff_m'] == 0.0

    def test_zero_flow_diff(self):
        assert self._info['max_flow_diff_m3s'] == 0.0


# =========================================================================
# Net2 — Tank network (35 junctions, 1 tank, 55h)
# =========================================================================

class TestNet2:

    @pytest.fixture(autouse=True, scope='class')
    def results(self):
        TestNet2._info = _load_and_compare('Net2')

    def test_network_loaded(self):
        assert self._info['junctions'] == 35
        assert self._info['pipes'] == 40
        assert self._info['tanks'] == 1

    def test_timesteps(self):
        assert self._info['timesteps'] == 56

    def test_pressure_exact(self):
        assert self._info['max_pressure_diff_m'] < 0.001

    def test_flow_exact(self):
        assert self._info['max_flow_diff_m3s'] < 0.00001

    def test_zero_pressure_diff(self):
        assert self._info['max_pressure_diff_m'] == 0.0

    def test_zero_flow_diff(self):
        assert self._info['max_flow_diff_m3s'] == 0.0


# =========================================================================
# Net3 — Large network (92 junctions, 2 pumps, 3 tanks, 168h)
# =========================================================================

class TestNet3:

    @pytest.fixture(autouse=True, scope='class')
    def results(self):
        TestNet3._info = _load_and_compare('Net3')

    def test_network_loaded(self):
        assert self._info['junctions'] == 92
        assert self._info['pipes'] == 117
        assert self._info['pumps'] == 2
        assert self._info['tanks'] == 3

    def test_timesteps(self):
        assert self._info['timesteps'] == 169  # 168h + initial

    def test_pressure_exact(self):
        assert self._info['max_pressure_diff_m'] < 0.001

    def test_flow_exact(self):
        assert self._info['max_flow_diff_m3s'] < 0.00001

    def test_velocity_exact(self):
        assert self._info['max_velocity_diff_ms'] < 0.001

    def test_zero_pressure_diff(self):
        assert self._info['max_pressure_diff_m'] == 0.0

    def test_zero_flow_diff(self):
        assert self._info['max_flow_diff_m3s'] == 0.0


# =========================================================================
# Cross-network: our API summary values are consistent with raw results
# =========================================================================

class TestAPISummaryConsistency:
    """Verify our API's summary dict (min/max/avg) matches the raw WNTR data."""

    def test_net1_pressure_summary(self):
        path = os.path.join(_WNTR_NETS, 'Net1.inp')
        api = HydraulicAPI()
        api.load_network_from_path(path)
        results = api.run_steady_state(save_plot=False)
        raw = api.get_steady_results()

        for jid in ['10', '11', '12', '32']:
            raw_p = raw.node['pressure'][jid]
            summary = results['pressures'][jid]

            assert abs(summary['min_m'] - float(raw_p.min())) < 0.1, (
                f"{jid}: min_m {summary['min_m']} != raw min {float(raw_p.min())}"
            )
            assert abs(summary['max_m'] - float(raw_p.max())) < 0.1, (
                f"{jid}: max_m {summary['max_m']} != raw max {float(raw_p.max())}"
            )
            assert abs(summary['avg_m'] - float(raw_p.mean())) < 0.1, (
                f"{jid}: avg_m {summary['avg_m']} != raw mean {float(raw_p.mean())}"
            )

    def test_net1_flow_summary(self):
        path = os.path.join(_WNTR_NETS, 'Net1.inp')
        api = HydraulicAPI()
        api.load_network_from_path(path)
        results = api.run_steady_state(save_plot=False)
        raw = api.get_steady_results()

        for lid in ['10', '11', '12']:
            raw_f = raw.link['flowrate'][lid] * 1000  # m3/s to LPS
            summary = results['flows'][lid]

            assert abs(summary['avg_lps'] - float(raw_f.mean())) < 0.1, (
                f"{lid}: avg_lps {summary['avg_lps']} != raw mean {float(raw_f.mean())}"
            )

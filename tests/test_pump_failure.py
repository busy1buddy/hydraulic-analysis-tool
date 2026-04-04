"""
Tests for Pump Failure Impact Analysis (Innovation Q2)
=======================================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestPumpFailureImpact:

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.pump_failure_impact()
        assert 'error' in result

    def test_no_pumps_in_network(self):
        api = HydraulicAPI()
        api.create_network(
            name='no_pumps',
            junctions=[{'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0}],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                     'diameter': 200, 'roughness': 130}],
        )
        result = api.pump_failure_impact()
        assert 'error' in result
        assert result['pump_count'] == 0

    def test_pump_station_tutorial(self):
        """Test on pump station tutorial if available."""
        path = os.path.join(ROOT, 'tutorials', 'pump_station', 'network.inp')
        if not os.path.exists(path):
            pytest.skip("Pump station tutorial not found")
        api = HydraulicAPI()
        api.load_network_from_path(path)
        result = api.pump_failure_impact()
        assert 'impacts' in result
        assert result['total_pumps_analysed'] > 0

    def test_multistage_pump_tutorial(self):
        """Test on multistage pump tutorial if available."""
        path = os.path.join(ROOT, 'tutorials', 'multistage_pump', 'network.inp')
        if not os.path.exists(path):
            pytest.skip("Multistage pump tutorial not found")
        api = HydraulicAPI()
        api.load_network_from_path(path)
        result = api.pump_failure_impact()
        assert 'impacts' in result

    def test_impact_structure(self):
        """Test result structure on any network with pumps."""
        path = os.path.join(ROOT, 'tutorials', 'pump_station', 'network.inp')
        if not os.path.exists(path):
            pytest.skip("Pump station tutorial not found")
        api = HydraulicAPI()
        api.load_network_from_path(path)
        result = api.pump_failure_impact()
        for impact in result['impacts']:
            assert 'pump_id' in impact
            assert 'severity' in impact
            if 'error' not in impact:
                assert 'affected_nodes' in impact
                assert 'customers_without_supply' in impact
                assert impact['severity'] in ('CRITICAL', 'HIGH', 'LOW')

    def test_specific_pump_id(self):
        """Test analysing a specific pump."""
        path = os.path.join(ROOT, 'tutorials', 'pump_station', 'network.inp')
        if not os.path.exists(path):
            pytest.skip("Pump station tutorial not found")
        api = HydraulicAPI()
        api.load_network_from_path(path)
        pumps = list(api.wn.pump_name_list)
        if not pumps:
            pytest.skip("No pumps")
        result = api.pump_failure_impact(pump_id=pumps[0])
        assert result['total_pumps_analysed'] == 1

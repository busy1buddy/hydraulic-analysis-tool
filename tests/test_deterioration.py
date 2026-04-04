"""
Tests for Asset Deterioration (J9), SCADA Simulation (J11), Cost Database (J12)
================================================================================
"""

import os
import sys
import csv
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


@pytest.fixture
def api():
    api = HydraulicAPI()
    api.create_network(
        name='deter_test',
        junctions=[
            {'id': 'J1', 'elevation': 50, 'demand': 5.0, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 55, 'demand': 3.0, 'x': 200, 'y': 0},
        ],
        reservoirs=[{'id': 'R1', 'head': 100, 'x': -200, 'y': 0}],
        pipes=[
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
             'diameter': 300, 'roughness': 130},
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 400,
             'diameter': 250, 'roughness': 130},
        ],
    )
    return api


class TestAssetDeterioration:

    def test_predict_condition(self, api):
        """Predict pipe condition at future years."""
        api.set_pipe_condition('P1', install_year=1980, condition_score=3.0,
                               material='DI')
        result = api.predict_deterioration(pipe_id='P1', current_year=2026,
                                            forecast_years=[2030, 2040, 2050])
        assert 2030 in result
        assert 2040 in result
        assert result[2030]['condition_score'] >= 3.0  # can only get worse
        assert result[2050]['condition_score'] >= result[2030]['condition_score']

    def test_failure_year_estimated(self, api):
        """Should estimate when condition reaches 5 (failed)."""
        api.set_pipe_condition('P1', install_year=1960, condition_score=4.5,
                               material='AC')  # AC deteriorates fastest
        result = api.predict_deterioration('P1', current_year=2026,
                                            forecast_years=list(range(2026, 2100)))
        failure_years = [y for y, d in result.items() if d['condition_score'] >= 4.9]
        assert len(failure_years) > 0  # should predict failure eventually

    def test_no_condition_data(self, api):
        result = api.predict_deterioration('P2')  # no condition set
        assert 'error' in result or len(result) > 0


class TestSCADASimulation:

    def test_csv_demand_import(self, api, tmp_path):
        """Import time-series demands from CSV and run EPS."""
        csv_path = str(tmp_path / "demands.csv")
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp_h', 'J1', 'J2'])
            writer.writerow([0, 5.0, 3.0])
            writer.writerow([1, 7.0, 4.0])
            writer.writerow([2, 6.0, 3.5])

        result = api.run_scada_replay(csv_path)
        assert 'error' not in result
        assert result['n_timesteps'] >= 2


class TestCostDatabaseEditor:

    def test_default_costs_exist(self):
        assert len(HydraulicAPI.PIPE_COST_PER_M) > 5
        assert 300 in HydraulicAPI.PIPE_COST_PER_M

    def test_custom_cost_override(self, api):
        original = HydraulicAPI.PIPE_COST_PER_M.get(300, 0)
        api.set_pipe_cost(300, 500)
        assert api.get_pipe_cost(300) == 500
        # Restore
        HydraulicAPI.PIPE_COST_PER_M[300] = original

    def test_import_costs_csv(self, api, tmp_path):
        csv_path = str(tmp_path / "costs.csv")
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['dn_mm', 'cost_per_m'])
            writer.writerow([100, 150])
            writer.writerow([200, 280])

        count = api.import_pipe_costs_csv(csv_path)
        assert count == 2

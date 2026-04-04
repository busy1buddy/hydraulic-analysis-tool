"""
Tests for Advanced Slurry Pipeline Design (M6)
================================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from slurry_solver import (wasp_critical_velocity, derate_pump_for_slurry,
                            critical_deposition_velocity)
from epanet_api import HydraulicAPI


class TestWaspCriticalVelocity:

    def test_basic_calculation(self):
        """Wasp model should return positive velocity for valid inputs."""
        result = wasp_critical_velocity(
            d_particle_mm=0.5, pipe_diameter_mm=200,
            rho_solid=2650, rho_fluid=1000, concentration_vol=0.1)
        assert result['velocity_ms'] > 0
        assert result['method'] == 'wasp'

    def test_larger_pipe_higher_velocity(self):
        """Larger pipes need higher velocity to prevent deposition."""
        small = wasp_critical_velocity(0.5, 100, concentration_vol=0.1)
        large = wasp_critical_velocity(0.5, 300, concentration_vol=0.1)
        assert large['velocity_ms'] > small['velocity_ms']

    def test_heavier_particles_higher_velocity(self):
        """Denser particles settle faster, need higher velocity."""
        light = wasp_critical_velocity(0.5, 200, rho_solid=1800, concentration_vol=0.1)
        heavy = wasp_critical_velocity(0.5, 200, rho_solid=4000, concentration_vol=0.1)
        assert heavy['velocity_ms'] > light['velocity_ms']

    def test_zero_inputs_handled(self):
        result = wasp_critical_velocity(0, 200, concentration_vol=0.1)
        assert result['velocity_ms'] == 0

    def test_durand_vs_wasp_same_order(self):
        """Both models should give similar order of magnitude."""
        durand = critical_deposition_velocity(0.5, 200, concentration_vol=0.1)
        wasp = wasp_critical_velocity(0.5, 200, concentration_vol=0.1)
        # Both should be in 1-5 m/s range for typical conditions
        assert 0.5 < durand['velocity_ms'] < 10
        assert 0.5 < wasp['velocity_ms'] < 10


class TestPumpDerating:

    def test_basic_derating(self):
        """Slurry head and efficiency should be less than water."""
        result = derate_pump_for_slurry(
            head_water_m=50, efficiency_water=0.75,
            concentration_vol=0.15)
        assert result['head_slurry_m'] < 50
        assert result['efficiency_slurry'] < 0.75

    def test_zero_concentration_no_change(self):
        """At Cv=0, should get water values (no derating)."""
        result = derate_pump_for_slurry(
            head_water_m=50, efficiency_water=0.75,
            concentration_vol=0.0)
        assert result['head_slurry_m'] == 50
        assert result['efficiency_slurry'] == 0.75

    def test_power_increase(self):
        """Power factor should be > 1.0 for slurry."""
        result = derate_pump_for_slurry(
            head_water_m=50, efficiency_water=0.75,
            concentration_vol=0.20)
        assert result['power_increase_factor'] > 1.0

    def test_mixture_sg(self):
        """Mixture SG should be > 1 for slurry."""
        result = derate_pump_for_slurry(
            head_water_m=50, efficiency_water=0.75,
            concentration_vol=0.15, rho_solid=2650)
        assert result['mixture_sg'] > 1.0

    def test_correction_factors_range(self):
        """Correction factors should be between 0.4 and 1.0."""
        result = derate_pump_for_slurry(
            head_water_m=50, efficiency_water=0.75,
            concentration_vol=0.20)
        assert 0.4 <= result['head_correction_CH'] <= 1.0
        assert 0.4 <= result['efficiency_correction_Ceta'] <= 1.0


class TestSlurryDesignReport:

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.slurry_design_report()
        assert 'error' in result

    def test_report_structure(self):
        api = HydraulicAPI()
        api.create_network(
            name='slurry_report',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 5, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 3, 'x': 200, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -100, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 400,
                 'diameter': 150, 'roughness': 130},
            ],
        )
        report = api.slurry_design_report(d_particle_mm=0.5, concentration_vol=0.15)
        assert 'carrier_fluid' in report
        assert 'solids' in report
        assert 'mixture' in report
        assert 'pipe_analysis' in report
        assert 'summary' in report

    def test_pipe_analysis_per_pipe(self):
        api = HydraulicAPI()
        api.create_network(
            name='slurry_pipes',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 5, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -100, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        report = api.slurry_design_report()
        assert len(report['pipe_analysis']) == 1
        pa = report['pipe_analysis'][0]
        assert 'actual_velocity_ms' in pa
        assert 'design_critical_ms' in pa
        assert 'safety_margin_pct' in pa
        assert 'status' in pa

    def test_mining_tutorial_network(self):
        """Run on the mining slurry tutorial if available."""
        api = HydraulicAPI()
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'tutorials', 'mining_slurry_line', 'network.inp')
        if not os.path.exists(path):
            pytest.skip("Mining tutorial not found")
        api.load_network_from_path(path)
        report = api.slurry_design_report(d_particle_mm=1.0, rho_solid=2650,
                                           concentration_vol=0.20)
        assert report['summary']['total_pipes'] > 0
        assert report['mixture']['specific_gravity'] > 1.0

    def test_sorted_by_risk(self):
        """Pipe analysis should be sorted by safety margin (most at-risk first)."""
        api = HydraulicAPI()
        api.create_network(
            name='slurry_sort',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 5, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 3, 'x': 200, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -100, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
                 'diameter': 300, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 400,
                 'diameter': 150, 'roughness': 130},
            ],
        )
        report = api.slurry_design_report()
        pa = report['pipe_analysis']
        for i in range(len(pa) - 1):
            assert pa[i]['safety_margin_pct'] <= pa[i+1]['safety_margin_pct']

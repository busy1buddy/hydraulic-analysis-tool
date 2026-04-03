"""Tests for Australian WSAA standards compliance checking logic."""

import pytest


class TestWSAAPressureThresholds:
    def test_low_pressure_detected(self, api_instance, simple_network_params):
        """Create network where junction pressure will be near threshold."""
        # Use the known australian_network where J4 is below 20m
        api_instance.load_network('australian_network.inp')
        results = api_instance.run_steady_state(save_plot=False)

        low_pressure_warnings = [
            c for c in results['compliance']
            if c['type'] == 'WARNING' and 'pressure' in c['message'].lower()
            and float(c['message'].split('m')[0].split()[-1]) < 20
        ]
        assert len(low_pressure_warnings) > 0

    def test_ok_when_all_above_threshold(self, api_instance):
        """Create a network where all pressures are above 20m."""
        api_instance.create_network(
            name='high_pressure_test',
            reservoirs=[{'id': 'R1', 'head': 100, 'x': 0, 'y': 0}],
            junctions=[{'id': 'J1', 'elevation': 30, 'demand': 1, 'x': 10, 'y': 0}],
            pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                    'diameter': 300, 'roughness': 140}],
            duration_hrs=1,
        )
        api_instance.load_network('high_pressure_test.inp')
        results = api_instance.run_steady_state(save_plot=False)

        pressure_warnings = [c for c in results['compliance']
                            if 'pressure' in c.get('message', '').lower()
                            and c['type'] == 'WARNING']
        # High head (100m) with low elevation (30m) = ~70m pressure, well above 20m
        # But this may trigger max pressure > 50m warning
        low_pressure = [c for c in pressure_warnings
                       if '< 20m' in c.get('message', '') or 'minimum' in c.get('message', '').lower()]
        assert len(low_pressure) == 0


class TestVelocityLimits:
    def test_velocity_warning_detected(self, steady_results):
        """Australian network has pipes exceeding 2.0 m/s."""
        vel_warnings = [c for c in steady_results['compliance']
                       if 'velocity' in c.get('message', '').lower()]
        assert len(vel_warnings) > 0

    def test_velocity_threshold_is_2ms(self, api_instance):
        """Verify the threshold is set to 2.0 m/s."""
        assert api_instance.DEFAULTS['max_velocity_ms'] == 2.0


class TestTransientPipeRating:
    def test_pn35_threshold(self, api_instance):
        """Verify PN35 = 3500 kPa threshold."""
        assert api_instance.DEFAULTS['pipe_rating_kPa'] == 3500

    def test_default_scenario_within_rating(self, transient_results):
        """Standard 0.5s closure should not exceed PN35."""
        for name, data in transient_results['junctions'].items():
            assert data['max_pressure_kPa'] < 3500, \
                f"{name} exceeded PN35: {data['max_pressure_kPa']} kPa"

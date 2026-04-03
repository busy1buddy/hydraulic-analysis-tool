"""End-to-end usability tests - complete workflows an engineer would follow."""

import os
import json
import pytest


class TestLoadAndAnalyseWorkflow:
    """Test the most common workflow: load a network and run analysis."""

    def test_full_steady_state_workflow(self, api_instance):
        """Load network -> run steady-state -> check compliance -> export."""
        # Load
        summary = api_instance.load_network('australian_network.inp')
        assert summary['junctions'] > 0

        # Analyse
        results = api_instance.run_steady_state(save_plot=True)
        assert 'pressures' in results
        assert 'flows' in results
        assert 'compliance' in results

        # Plot was generated
        assert 'plot' in results
        assert os.path.exists(results['plot'])

        # Export
        path = api_instance.export_results_json(results, 'workflow_test.json')
        assert os.path.exists(path)
        with open(path) as f:
            exported = json.load(f)
        assert exported['pressures'] == results['pressures']

    def test_full_transient_workflow(self, api_instance):
        """Load network -> run transient -> check surge -> review mitigation."""
        # Load
        api_instance.load_network('transient_network.inp')

        # Analyse
        results = api_instance.run_transient(
            valve_name='V1', closure_time=0.5,
            wave_speed=1000, sim_duration=20, save_plot=True
        )

        # Surge calculated
        assert results['max_surge_m'] > 0
        assert results['max_surge_kPa'] > 0

        # Compliance checked
        assert len(results['compliance']) > 0

        # Mitigation provided
        assert len(results['mitigation']) > 0

        # Plot generated
        assert 'plot' in results
        assert os.path.exists(results['plot'])


class TestCreateAndAnalyseWorkflow:
    """Test creating a network from scratch and analysing it."""

    def test_create_then_analyse(self, api_instance):
        """Create network -> load it -> run steady-state."""
        api_instance.create_network(
            name='usability_test',
            reservoirs=[{'id': 'R1', 'head': 75, 'x': 0, 'y': 0}],
            junctions=[
                {'id': 'J1', 'elevation': 45, 'demand': 5, 'x': 10, 'y': 0},
                {'id': 'J2', 'elevation': 40, 'demand': 8, 'x': 20, 'y': 0},
            ],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
                 'diameter': 250, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 400,
                 'diameter': 200, 'roughness': 120},
            ],
            duration_hrs=24,
            pattern=[0.5, 0.4, 0.3, 0.3, 0.5, 0.8,
                     1.2, 1.5, 1.3, 1.0, 0.9, 0.8,
                     0.7, 0.6, 0.7, 0.9, 1.3, 1.5,
                     1.4, 1.2, 1.0, 0.8, 0.7, 0.6],
        )

        # Re-load created network
        api_instance.load_network('usability_test.inp')
        results = api_instance.run_steady_state(save_plot=False)

        assert len(results['pressures']) == 2
        assert len(results['flows']) == 2


class TestNetworkDiscovery:
    """Test that users can discover available networks."""

    def test_list_shows_all_networks(self, api_instance):
        networks = api_instance.list_networks()
        assert 'australian_network.inp' in networks
        assert 'transient_network.inp' in networks

    def test_network_info_readable(self, api_instance):
        summary = api_instance.load_network('australian_network.inp')
        # Engineer should be able to understand this at a glance
        assert 'junctions' in summary
        assert 'pipes' in summary
        assert 'junction_list' in summary
        assert 'pipe_list' in summary


class TestJoukowskyQuickCalc:
    """Test the quick Joukowsky calculator engineers use frequently."""

    def test_ductile_iron_scenario(self, api_instance):
        """Typical ductile iron pipe with 1.5 m/s velocity change."""
        result = api_instance.joukowsky(wave_speed=1000, velocity_change=1.5)
        assert result['head_rise_m'] > 100  # Should be ~153m
        assert result['pressure_rise_kPa'] > 1000  # Should be ~1500 kPa

    def test_pvc_scenario(self, api_instance):
        """PVC pipe - lower wave speed, lower surge."""
        result = api_instance.joukowsky(wave_speed=400, velocity_change=1.5)
        assert result['head_rise_m'] < 100  # PVC surge should be lower than DI

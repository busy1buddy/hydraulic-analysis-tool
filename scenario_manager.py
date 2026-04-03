"""
Scenario Manager
=================
Manages named scenarios for side-by-side what-if analysis.
Supports pipe upsizing/downsizing, demand growth, material changes,
and pattern changes. Compares results between scenarios.
"""

import os
import json
import copy
import numpy as np
import wntr

from epanet_api import HydraulicAPI


class ScenarioManager:
    """Manages multiple analysis scenarios for comparison."""

    def __init__(self, work_dir=None):
        self.work_dir = work_dir or os.path.dirname(os.path.abspath(__file__))
        self.scenarios = {}  # name -> {params, network_file, results}

    def create_scenario(self, name, base_network, modifications=None, description=''):
        """
        Create a new scenario based on an existing network with modifications.

        Parameters
        ----------
        name : str
            Unique scenario name.
        base_network : str
            Base .inp file to modify (from models/).
        modifications : list of dict
            List of modifications to apply. Each dict has:
            - type: 'pipe_diameter', 'pipe_roughness', 'demand_factor',
                    'demand_set', 'add_junction', 'add_pipe'
            - target: element ID (for pipe/junction mods)
            - value: new value
        description : str
            Human-readable description of what this scenario tests.

        Returns
        -------
        dict with scenario info.
        """
        api = HydraulicAPI(self.work_dir)
        api.load_network(base_network)

        modifications = modifications or []

        for mod in modifications:
            mod_type = mod['type']

            if mod_type == 'pipe_diameter':
                pipe = api.wn.get_link(mod['target'])
                pipe.diameter = mod['value'] / 1000  # mm to m

            elif mod_type == 'pipe_roughness':
                pipe = api.wn.get_link(mod['target'])
                pipe.roughness = mod['value']

            elif mod_type == 'demand_factor':
                factor = mod['value']
                for jname in api.wn.junction_name_list:
                    junc = api.wn.get_node(jname)
                    if junc.demand_timeseries_list:
                        junc.demand_timeseries_list[0].base_value *= factor

            elif mod_type == 'demand_set':
                junc = api.wn.get_node(mod['target'])
                junc.demand_timeseries_list[0].base_value = mod['value'] / 1000

            elif mod_type == 'add_junction':
                api.wn.add_junction(
                    mod['id'], elevation=mod.get('elevation', 40),
                    base_demand=mod.get('demand', 0) / 1000,
                    coordinates=(mod.get('x', 0), mod.get('y', 0)),
                )

            elif mod_type == 'add_pipe':
                api.wn.add_pipe(
                    mod['id'], mod['start'], mod['end'],
                    length=mod.get('length', 100),
                    diameter=mod.get('diameter', 200) / 1000,
                    roughness=mod.get('roughness', 130),
                )

        # Save modified network
        scenario_file = f'scenario_{name}.inp'
        scenario_path = os.path.join(api.model_dir, scenario_file)
        wntr.network.write_inpfile(api.wn, scenario_path)

        self.scenarios[name] = {
            'name': name,
            'description': description,
            'base_network': base_network,
            'modifications': modifications,
            'network_file': scenario_file,
            'results': None,
        }

        return self.scenarios[name]

    def run_scenario(self, name):
        """Run steady-state analysis on a scenario."""
        if name not in self.scenarios:
            return {'error': f'Scenario "{name}" not found'}

        scenario = self.scenarios[name]
        api = HydraulicAPI(self.work_dir)
        api.load_network(scenario['network_file'])
        results = api.run_steady_state(save_plot=False)
        scenario['results'] = results
        return results

    def run_all(self):
        """Run all scenarios."""
        for name in self.scenarios:
            self.run_scenario(name)

    def compare(self, scenario_a, scenario_b):
        """
        Compare two scenarios side-by-side.

        Returns dict with pressure differences, flow differences,
        and compliance comparison.
        """
        a = self.scenarios.get(scenario_a)
        b = self.scenarios.get(scenario_b)

        if not a or not b:
            return {'error': 'One or both scenarios not found'}
        if not a['results'] or not b['results']:
            return {'error': 'Run both scenarios first'}

        r_a = a['results']
        r_b = b['results']

        comparison = {
            'scenario_a': scenario_a,
            'scenario_b': scenario_b,
            'description_a': a['description'],
            'description_b': b['description'],
            'pressure_diff': {},
            'flow_diff': {},
            'compliance_a': r_a['compliance'],
            'compliance_b': r_b['compliance'],
            'summary': [],
        }

        # Pressure differences
        common_junctions = set(r_a['pressures'].keys()) & set(r_b['pressures'].keys())
        for j in sorted(common_junctions):
            pa = r_a['pressures'][j]
            pb = r_b['pressures'][j]
            comparison['pressure_diff'][j] = {
                'a_min': pa['min_m'], 'b_min': pb['min_m'],
                'diff_min': round(pb['min_m'] - pa['min_m'], 1),
                'a_avg': pa['avg_m'], 'b_avg': pb['avg_m'],
                'diff_avg': round(pb['avg_m'] - pa['avg_m'], 1),
            }

        # Flow differences
        common_pipes = set(r_a['flows'].keys()) & set(r_b['flows'].keys())
        for p in sorted(common_pipes):
            fa = r_a['flows'][p]
            fb = r_b['flows'][p]
            comparison['flow_diff'][p] = {
                'a_avg': fa['avg_lps'], 'b_avg': fb['avg_lps'],
                'diff_avg': round(fb['avg_lps'] - fa['avg_lps'], 2),
                'a_vel': fa['avg_velocity_ms'], 'b_vel': fb['avg_velocity_ms'],
                'diff_vel': round(fb['avg_velocity_ms'] - fa['avg_velocity_ms'], 2),
            }

        # Summary
        improved = sum(1 for j in comparison['pressure_diff'].values() if j['diff_min'] > 0)
        worsened = sum(1 for j in comparison['pressure_diff'].values() if j['diff_min'] < 0)
        comparison['summary'].append(
            f'Pressure: {improved} junctions improved, {worsened} worsened'
        )

        warnings_a = sum(1 for c in r_a['compliance'] if c['type'] == 'WARNING')
        warnings_b = sum(1 for c in r_b['compliance'] if c['type'] == 'WARNING')
        if warnings_b < warnings_a:
            comparison['summary'].append(
                f'Compliance warnings reduced from {warnings_a} to {warnings_b}')
        elif warnings_b > warnings_a:
            comparison['summary'].append(
                f'Compliance warnings increased from {warnings_a} to {warnings_b}')
        else:
            comparison['summary'].append(f'Same number of compliance warnings ({warnings_a})')

        return comparison

    def list_scenarios(self):
        """Return list of all scenario names and descriptions."""
        return [{'name': s['name'], 'description': s['description'],
                 'base_network': s['base_network'],
                 'has_results': s['results'] is not None}
                for s in self.scenarios.values()]

    def export_comparison(self, comparison, filename='comparison.json'):
        """Export comparison results to JSON."""
        path = os.path.join(self.work_dir, 'output', filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(comparison, f, indent=2, default=str)
        return path

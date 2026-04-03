"""
EPANET Hydraulic Analysis API
==============================
Unified Python API wrapping WNTR, EPyT, and TSNet for hydraulic
and transient analysis. Designed for Australian engineering practice.

Usage from Claude Code:
    from epanet_api import HydraulicAPI
    api = HydraulicAPI()
    api.create_network(...)
    results = api.run_steady_state()
    transient = api.run_transient(valve='V1', closure_time=0.5)
"""

import sys
import io
import os
import json
import numpy as np
import wntr
import tsnet
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Force UTF-8 output on Windows (skip if pytest or already wrapped)
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class HydraulicAPI:
    """Unified API for EPANET hydraulic and transient analysis."""

    # Australian standard unit defaults
    DEFAULTS = {
        'flow_units': 'LPS',          # Litres per second
        'headloss': 'H-W',            # Hazen-Williams
        'min_pressure_m': 20,          # WSAA minimum pressure (m)
        'max_pressure_m': 50,          # WSAA maximum static pressure (m)
        'max_velocity_ms': 2.0,        # Maximum pipe velocity (m/s)
        'pipe_rating_kPa': 3500,       # PN35 ductile iron
        'wave_speed_ms': 1000,         # Ductile iron wave speed
    }

    def __init__(self, work_dir=None):
        self.work_dir = work_dir or os.path.dirname(os.path.abspath(__file__))
        self.model_dir = os.path.join(self.work_dir, 'models')
        self.output_dir = os.path.join(self.work_dir, 'output')
        os.makedirs(self.model_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        self.wn = None
        self.tm = None
        self.steady_results = None
        self.transient_results = None
        self._inp_file = None

    # =========================================================================
    # NETWORK CREATION
    # =========================================================================

    def load_network(self, inp_file):
        """Load an existing EPANET .inp file from the models/ directory."""
        self._inp_file = os.path.join(self.model_dir, inp_file)
        if not os.path.exists(self._inp_file):
            # Fall back to work_dir for backward compatibility
            alt = os.path.join(self.work_dir, inp_file)
            if os.path.exists(alt):
                self._inp_file = alt
        self.wn = wntr.network.WaterNetworkModel(self._inp_file)
        return self.get_network_summary()

    def create_network(self, name="network",
                       junctions=None, reservoirs=None, tanks=None,
                       pipes=None, valves=None,
                       duration_hrs=24, pattern=None):
        """
        Create a new EPANET network programmatically.

        Parameters
        ----------
        name : str
            Network name
        junctions : list of dict
            [{'id': 'J1', 'elevation': 50, 'demand': 5.0, 'x': 0, 'y': 0}]
        reservoirs : list of dict
            [{'id': 'R1', 'head': 80, 'x': 0, 'y': 50}]
        tanks : list of dict
            [{'id': 'T1', 'elevation': 55, 'init_level': 3, 'min_level': 0.5,
              'max_level': 5, 'diameter': 12, 'x': 30, 'y': 70}]
        pipes : list of dict
            [{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
              'diameter': 300, 'roughness': 130}]
        valves : list of dict
            [{'id': 'V1', 'start': 'J1', 'end': 'J2', 'diameter': 200,
              'type': 'TCV', 'setting': 1}]
        duration_hrs : int
            Simulation duration in hours
        pattern : list of float
            24-hour demand multiplier pattern
        """
        self.wn = wntr.network.WaterNetworkModel()
        self.wn.options.hydraulic.headloss = self.DEFAULTS['headloss']

        # Add reservoirs
        for r in (reservoirs or []):
            self.wn.add_reservoir(r['id'], base_head=r['head'],
                                coordinates=(r.get('x', 0), r.get('y', 0)))

        # Add junctions
        for j in (junctions or []):
            self.wn.add_junction(j['id'], base_demand=j.get('demand', 0) / 1000,
                                elevation=j['elevation'],
                                coordinates=(j.get('x', 0), j.get('y', 0)))

        # Add tanks
        for t in (tanks or []):
            self.wn.add_tank(t['id'], elevation=t['elevation'],
                           init_level=t.get('init_level', 3),
                           min_level=t.get('min_level', 0.5),
                           max_level=t.get('max_level', 5),
                           diameter=t.get('diameter', 10),
                           coordinates=(t.get('x', 0), t.get('y', 0)))

        # Add pipes
        for p in (pipes or []):
            self.wn.add_pipe(p['id'], p['start'], p['end'],
                           length=p['length'],
                           diameter=p['diameter'] / 1000,  # mm to m
                           roughness=p.get('roughness', 130))

        # Add valves
        for v in (valves or []):
            self.wn.add_valve(v['id'], v['start'], v['end'],
                            diameter=v.get('diameter', 200) / 1000,
                            valve_type=v.get('type', 'TCV'),
                            minor_loss=v.get('minor_loss', 0),
                            initial_setting=v.get('setting', 1))

        # Add demand pattern
        if pattern:
            self.wn.add_pattern('1', pattern)
            for j_name in self.wn.junction_name_list:
                junc = self.wn.get_node(j_name)
                junc.demand_timeseries_list[0].pattern_name = '1'

        # Set simulation time
        self.wn.options.time.duration = duration_hrs * 3600
        self.wn.options.time.hydraulic_timestep = 3600
        self.wn.options.time.report_timestep = 3600

        # Save to .inp file in models directory
        self._inp_file = os.path.join(self.model_dir, f'{name}.inp')
        wntr.network.write_inpfile(self.wn, self._inp_file)

        return self.get_network_summary()

    def get_network_summary(self):
        """Return a summary dict of the current network."""
        if self.wn is None:
            return {'error': 'No network loaded'}

        return {
            'junctions': len(self.wn.junction_name_list),
            'reservoirs': len(self.wn.reservoir_name_list),
            'tanks': len(self.wn.tank_name_list),
            'pipes': len(self.wn.pipe_name_list),
            'valves': len(self.wn.valve_name_list),
            'pumps': len(self.wn.pump_name_list),
            'duration_hrs': self.wn.options.time.duration / 3600,
            'junction_list': list(self.wn.junction_name_list),
            'pipe_list': list(self.wn.pipe_name_list),
        }

    # =========================================================================
    # NETWORK MUTATION (all mutations must go through these methods)
    # =========================================================================

    def add_junction(self, jid, elevation=0, base_demand=0, coordinates=None):
        """Add a junction to the network. Demand in m³/s (WNTR internal)."""
        if self.wn is None:
            raise RuntimeError("No network loaded")
        self.wn.add_junction(jid, elevation=elevation, base_demand=base_demand,
                             coordinates=coordinates)

    def update_junction(self, jid, elevation=None, base_demand=None, coordinates=None):
        """Update junction properties."""
        if self.wn is None:
            raise RuntimeError("No network loaded")
        node = self.wn.get_node(jid)
        if elevation is not None:
            node.elevation = elevation
        if base_demand is not None and node.demand_timeseries_list:
            node.demand_timeseries_list[0].base_value = base_demand
        if coordinates is not None:
            node.coordinates = coordinates

    def remove_junction(self, jid):
        """Remove a junction (node) from the network."""
        if self.wn is None:
            raise RuntimeError("No network loaded")
        self.wn.remove_node(jid)

    def add_pipe(self, pid, start_node, end_node, length=100, diameter_m=0.3,
                 roughness=130):
        """Add a pipe. Diameter in metres (WNTR internal)."""
        if self.wn is None:
            raise RuntimeError("No network loaded")
        self.wn.add_pipe(pid, start_node, end_node, length=length,
                         diameter=diameter_m, roughness=roughness)

    def update_pipe(self, pid, length=None, diameter_m=None, roughness=None):
        """Update pipe properties. Diameter in metres."""
        if self.wn is None:
            raise RuntimeError("No network loaded")
        pipe = self.wn.get_link(pid)
        if length is not None:
            pipe.length = length
        if diameter_m is not None:
            pipe.diameter = diameter_m
        if roughness is not None:
            pipe.roughness = roughness

    def remove_pipe(self, pid):
        """Remove a pipe (link) from the network."""
        if self.wn is None:
            raise RuntimeError("No network loaded")
        self.wn.remove_link(pid)

    def remove_node(self, nid):
        """Remove any node type from the network."""
        if self.wn is None:
            raise RuntimeError("No network loaded")
        self.wn.remove_node(nid)

    def remove_link(self, lid):
        """Remove any link type from the network."""
        if self.wn is None:
            raise RuntimeError("No network loaded")
        self.wn.remove_link(lid)

    def get_node(self, nid):
        """Get a node object for read-only property access."""
        if self.wn is None:
            raise RuntimeError("No network loaded")
        return self.wn.get_node(nid)

    def get_link(self, lid):
        """Get a link object for read-only property access."""
        if self.wn is None:
            raise RuntimeError("No network loaded")
        return self.wn.get_link(lid)

    def get_node_list(self, node_type=None):
        """Return list of node IDs, optionally filtered by type."""
        if self.wn is None:
            return []
        if node_type == 'junction':
            return list(self.wn.junction_name_list)
        elif node_type == 'reservoir':
            return list(self.wn.reservoir_name_list)
        elif node_type == 'tank':
            return list(self.wn.tank_name_list)
        return (list(self.wn.junction_name_list) +
                list(self.wn.reservoir_name_list) +
                list(self.wn.tank_name_list))

    def get_link_list(self, link_type=None):
        """Return list of link IDs, optionally filtered by type."""
        if self.wn is None:
            return []
        if link_type == 'pipe':
            return list(self.wn.pipe_name_list)
        elif link_type == 'pump':
            return list(self.wn.pump_name_list)
        elif link_type == 'valve':
            return list(self.wn.valve_name_list)
        return (list(self.wn.pipe_name_list) +
                list(self.wn.pump_name_list) +
                list(self.wn.valve_name_list))

    def get_steady_results(self):
        """Return the raw steady-state WNTR results object."""
        return self.steady_results

    def get_transient_model(self):
        """Return the TSNet transient model object."""
        return self.tm

    def write_inp(self, path):
        """Write the current network to an .inp file."""
        if self.wn is None:
            raise RuntimeError("No network loaded")
        wntr.network.write_inpfile(self.wn, path)

    # =========================================================================
    # STEADY-STATE ANALYSIS
    # =========================================================================

    def run_steady_state(self, save_plot=True):
        """
        Run extended period hydraulic simulation using EPANET solver.

        Returns dict with pressures, flows, velocities, and compliance check.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Call load_network() or create_network() first.'}

        sim = wntr.sim.EpanetSimulator(self.wn)
        self.steady_results = sim.run_sim()

        pressures = self.steady_results.node['pressure']
        flows = self.steady_results.link['flowrate']

        # Build results dict
        results = {
            'pressures': {},
            'flows': {},
            'compliance': [],
        }

        # Junction pressures
        for junc in self.wn.junction_name_list:
            p = pressures[junc]
            results['pressures'][junc] = {
                'min_m': round(float(p.min()), 1),
                'max_m': round(float(p.max()), 1),
                'avg_m': round(float(p.mean()), 1),
            }

        # Pipe flows and velocities
        for pipe_name in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pipe_name)
            f = flows[pipe_name]
            area = np.pi * (pipe.diameter / 2) ** 2
            if area <= 0:
                continue  # skip degenerate pipe with zero diameter
            v_avg = abs(float(f.mean())) / area
            # abs() required — flow can be negative on reversing pipes
            v_max = float(f.abs().max()) / area

            results['flows'][pipe_name] = {
                'min_lps': round(float(f.min()) * 1000, 2),
                'max_lps': round(float(f.max()) * 1000, 2),
                'avg_lps': round(float(f.mean()) * 1000, 2),
                'avg_velocity_ms': round(v_avg, 2),
                'max_velocity_ms': round(v_max, 2),
            }

        # Australian compliance check
        for junc in self.wn.junction_name_list:
            p_min = pressures[junc].min()
            p_max = pressures[junc].max()
            if p_min < self.DEFAULTS['min_pressure_m']:
                results['compliance'].append({
                    'type': 'WARNING',
                    'element': junc,
                    'message': f'Min pressure {p_min:.1f}m < {self.DEFAULTS["min_pressure_m"]}m (WSAA minimum)',
                })
            if p_max > self.DEFAULTS['max_pressure_m']:
                results['compliance'].append({
                    'type': 'WARNING',
                    'element': junc,
                    'message': f'Max pressure {p_max:.1f}m > {self.DEFAULTS["max_pressure_m"]}m (consider PRV)',
                })

        for pipe_name in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pipe_name)
            area = np.pi * (pipe.diameter / 2) ** 2
            if area <= 0:
                continue  # skip degenerate pipe with zero diameter
            # abs() required — flow can be negative on reversing pipes
            v_max = float(flows[pipe_name].abs().max()) / area
            if v_max > self.DEFAULTS['max_velocity_ms']:
                results['compliance'].append({
                    'type': 'WARNING',
                    'element': pipe_name,
                    'message': f'Velocity {v_max:.2f} m/s > {self.DEFAULTS["max_velocity_ms"]} m/s limit',
                })

        if not results['compliance']:
            results['compliance'].append({
                'type': 'OK',
                'message': 'All parameters within Australian standards (WSAA guidelines)',
            })

        # Generate plot
        if save_plot:
            plot_path = self._plot_steady_state()
            results['plot'] = plot_path

        return results

    def _plot_steady_state(self):
        """Generate steady-state results plot."""
        pressures = self.steady_results.node['pressure']
        flows = self.steady_results.link['flowrate']
        junction_pressures = pressures[self.wn.junction_name_list]
        pipe_flows = flows[self.wn.pipe_name_list]

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle('Hydraulic Analysis Results', fontsize=14, fontweight='bold')

        hours = junction_pressures.index / 3600

        ax1 = axes[0]
        for junc in self.wn.junction_name_list:
            ax1.plot(hours, junction_pressures[junc], label=junc, linewidth=1.5)
        ax1.axhline(y=self.DEFAULTS['min_pressure_m'], color='red', linestyle='--',
                   alpha=0.7, label=f'Min {self.DEFAULTS["min_pressure_m"]}m (WSAA)')
        ax1.set_xlabel('Time (hours)')
        ax1.set_ylabel('Pressure (m)')
        ax1.set_title('Junction Pressures')
        ax1.legend(fontsize=8, ncol=2)
        ax1.grid(True, alpha=0.3)

        ax2 = axes[1]
        for pipe_name in self.wn.pipe_name_list:
            ax2.plot(hours, pipe_flows[pipe_name] * 1000, label=pipe_name, linewidth=1.5)
        ax2.set_xlabel('Time (hours)')
        ax2.set_ylabel('Flow (LPS)')
        ax2.set_title('Pipe Flows')
        ax2.legend(fontsize=8, ncol=2)
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        path = os.path.join(self.output_dir, 'api_steady_results.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        return path

    # =========================================================================
    # FIRE FLOW ANALYSIS
    # =========================================================================

    def run_fire_flow(self, node_id, flow_lps=25, min_pressure_m=12, save_plot=True):
        """
        Run fire flow analysis at a specific junction.

        Temporarily adds fire flow demand to the specified node, runs a
        steady-state simulation, and checks whether all junctions maintain
        the minimum residual pressure required under WSAA fire flow
        conditions (default 12 m).

        Parameters
        ----------
        node_id : str
            Junction ID where fire flow is applied.
        flow_lps : float
            Fire flow demand in litres per second (default 25 LPS).
        min_pressure_m : float
            Minimum residual pressure required at all junctions during
            fire flow (default 12 m per WSAA).
        save_plot : bool
            Whether to save a bar chart of residual pressures.

        Returns dict with residual pressures, compliance, and plot path.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Call load_network() or create_network() first.'}

        # Store original demand and apply fire flow
        node = self.wn.get_node(node_id)
        demand_ts = node.demand_timeseries_list[0]
        original_demand = demand_ts.base_value
        demand_ts.base_value = original_demand + (flow_lps / 1000)  # LPS to m3/s

        try:
            # Run steady-state simulation with fire flow applied
            sim = wntr.sim.EpanetSimulator(self.wn)
            fire_results = sim.run_sim()
            pressures = fire_results.node['pressure']

            results = {
                'fire_node': node_id,
                'fire_flow_lps': flow_lps,
                'residual_pressures': {},
                'fire_node_pressure_m': 0.0,
                'available_flow_lps': flow_lps,
                'compliance': [],
            }

            # Record pressures at all junctions
            for junc in self.wn.junction_name_list:
                p = pressures[junc]
                p_min = round(float(p.min()), 1)
                results['residual_pressures'][junc] = p_min

            # Fire node pressure
            fire_p = pressures[node_id]
            results['fire_node_pressure_m'] = round(float(fire_p.min()), 1)

            # Compliance checks
            # Check fire node itself
            if results['fire_node_pressure_m'] < min_pressure_m:
                results['compliance'].append({
                    'type': 'CRITICAL',
                    'element': node_id,
                    'message': (f'Fire flow node pressure {results["fire_node_pressure_m"]:.1f}m '
                                f'< {min_pressure_m}m minimum (WSAA fire flow)'),
                })

            # Check all other junctions
            for junc in self.wn.junction_name_list:
                p_min = results['residual_pressures'][junc]
                if p_min < min_pressure_m:
                    if junc != node_id:  # Already reported fire node above
                        results['compliance'].append({
                            'type': 'WARNING',
                            'element': junc,
                            'message': (f'Pressure {p_min:.1f}m < {min_pressure_m}m '
                                        f'during fire flow at {node_id}'),
                        })

            if not results['compliance']:
                results['compliance'].append({
                    'type': 'OK',
                    'message': (f'All junctions maintain >= {min_pressure_m}m '
                                f'during {flow_lps} LPS fire flow at {node_id}'),
                })

            if save_plot:
                plot_path = self._plot_fire_flow(results, min_pressure_m)
                results['plot'] = plot_path

        finally:
            # Always restore original demand
            demand_ts.base_value = original_demand

        return results

    def _plot_fire_flow(self, results, min_pressure_m):
        """Generate fire flow residual pressure bar chart."""
        junctions = list(results['residual_pressures'].keys())
        pressures = [results['residual_pressures'][j] for j in junctions]

        fig, ax = plt.subplots(figsize=(10, 5))
        fig.suptitle(f'Fire Flow Analysis - {results["fire_flow_lps"]} LPS at {results["fire_node"]}',
                     fontsize=12, fontweight='bold')

        colors = ['red' if p < min_pressure_m else 'steelblue' for p in pressures]
        bars = ax.bar(junctions, pressures, color=colors, edgecolor='black', linewidth=0.5)

        ax.axhline(y=min_pressure_m, color='red', linestyle='--', alpha=0.7,
                   label=f'Min {min_pressure_m}m (WSAA fire flow)')
        ax.set_xlabel('Junction')
        ax.set_ylabel('Residual Pressure (m)')
        ax.set_title('Residual Pressures During Fire Flow')
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')

        # Highlight the fire flow node
        for i, j in enumerate(junctions):
            if j == results['fire_node']:
                bars[i].set_edgecolor('orange')
                bars[i].set_linewidth(2.5)

        plt.tight_layout()
        path = os.path.join(self.output_dir, 'api_fire_flow_results.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        return path

    # =========================================================================
    # WATER QUALITY (WATER AGE) ANALYSIS
    # =========================================================================

    def run_water_quality(self, parameter='age', duration_hrs=72, save_plot=True):
        """
        Run water quality (water age) analysis.

        Configures the EPANET quality parameter to 'AGE', extends the
        simulation duration, and reports maximum / average water age at
        each junction.  Junctions where the maximum water age exceeds
        24 hours are flagged as stagnation risks.

        Parameters
        ----------
        parameter : str
            Quality parameter ('age', 'chemical', 'trace').
            Typically 'age' for water age analysis.
        duration_hrs : float
            Simulation duration in hours (default 72 for water age
            to reach steady state).
        save_plot : bool
            Whether to save a bar chart of water age results.

        Returns dict with junction quality data, stagnation risks,
        and compliance items.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Call load_network() or create_network() first.'}

        # Save original settings
        original_duration = self.wn.options.time.duration
        original_quality_param = getattr(self.wn.options.quality, 'parameter', 'NONE')

        try:
            # Configure quality simulation
            self.wn.options.quality.parameter = parameter.upper()
            self.wn.options.time.duration = int(duration_hrs * 3600)

            # Run simulation
            sim = wntr.sim.EpanetSimulator(self.wn)
            quality_results = sim.run_sim()
            quality = quality_results.node['quality']

            results = {
                'parameter': parameter.upper(),
                'duration_hrs': duration_hrs,
                'junction_quality': {},
                'stagnation_risk': [],
                'compliance': [],
            }

            # Analyse water age at each junction
            # WNTR water age is in seconds — convert to hours for WSAA comparison
            for junc in self.wn.junction_name_list:
                q = quality[junc]
                max_age_hrs = round(float(q.max()) / 3600, 2)
                avg_age_hrs = round(float(q.mean()) / 3600, 2)

                results['junction_quality'][junc] = {
                    'max_age_hrs': max_age_hrs,
                    'avg_age_hrs': avg_age_hrs,
                }

                # Flag stagnation risk (> 24 hours)
                if max_age_hrs > 24.0:
                    results['stagnation_risk'].append(junc)

            # Compliance items
            for junc in results['stagnation_risk']:
                age = results['junction_quality'][junc]['max_age_hrs']
                results['compliance'].append({
                    'type': 'WARNING',
                    'element': junc,
                    'message': f'Water age {age:.1f} hrs > 24 hrs (stagnation risk)',
                })

            if not results['compliance']:
                results['compliance'].append({
                    'type': 'OK',
                    'message': 'All junctions have water age <= 24 hrs',
                })

            if save_plot:
                plot_path = self._plot_water_quality(results)
                results['plot'] = plot_path

        finally:
            # Restore original settings
            self.wn.options.time.duration = original_duration
            self.wn.options.quality.parameter = original_quality_param

        return results

    def _plot_water_quality(self, results):
        """Generate water quality (water age) bar chart."""
        junctions = list(results['junction_quality'].keys())
        max_ages = [results['junction_quality'][j]['max_age_hrs'] for j in junctions]
        avg_ages = [results['junction_quality'][j]['avg_age_hrs'] for j in junctions]

        fig, ax = plt.subplots(figsize=(10, 5))
        fig.suptitle(f'Water Quality Analysis - {results["parameter"]} '
                     f'({results["duration_hrs"]}hr simulation)',
                     fontsize=12, fontweight='bold')

        x = np.arange(len(junctions))
        width = 0.35

        bars_max = ax.bar(x - width / 2, max_ages, width, label='Max Age',
                          color=['red' if a > 24 else 'steelblue' for a in max_ages],
                          edgecolor='black', linewidth=0.5)
        bars_avg = ax.bar(x + width / 2, avg_ages, width, label='Avg Age',
                          color='lightblue', edgecolor='black', linewidth=0.5)

        ax.axhline(y=24, color='red', linestyle='--', alpha=0.7,
                   label='24hr stagnation threshold')
        ax.set_xlabel('Junction')
        ax.set_ylabel('Water Age (hours)')
        ax.set_title('Water Age at Junctions')
        ax.set_xticks(x)
        ax.set_xticklabels(junctions)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()
        path = os.path.join(self.output_dir, 'api_water_quality_results.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        return path

    # =========================================================================
    # TRANSIENT (WATER HAMMER) ANALYSIS
    # =========================================================================

    def run_transient(self, valve_name, closure_time=0.5, start_time=2.0,
                      final_open=0.0, closure_shape=1,
                      sim_duration=20, wave_speed=None,
                      save_plot=True):
        """
        Run water hammer / transient analysis using TSNet MOC solver.

        Parameters
        ----------
        valve_name : str
            Name of valve to close (must exist in network)
        closure_time : float
            Duration of valve closure in seconds
        start_time : float
            Time at which closure begins (seconds)
        final_open : float
            Final open percentage (0 = fully closed)
        closure_shape : int
            Closure profile shape (1=linear, 2=quadratic)
        sim_duration : float
            Total simulation time in seconds
        wave_speed : float
            Wave speed in m/s (default: 1000 for ductile iron)
        save_plot : bool
            Whether to save plot image

        Returns dict with transient pressures, surge values, compliance.
        """
        if self._inp_file is None:
            return {'error': 'No network file. Call load_network() or create_network() first.'}

        ws = wave_speed or self.DEFAULTS['wave_speed_ms']

        # Load into TSNet
        tm = tsnet.network.TransientModel(self._inp_file)
        tm.set_wavespeed(ws)
        tm.set_time(sim_duration)

        # Define valve closure
        rule = [closure_time, start_time, final_open, closure_shape]
        tm.valve_closure(valve_name, rule)

        # Initialize and run
        tm = tsnet.simulation.Initializer(tm, 0, engine='DD')
        tm = tsnet.simulation.MOCSimulator(tm)

        self.tm = tm
        g = 9.81
        t = tm.simulation_timestamps

        results = {
            'wave_speed_ms': ws,
            'closure_time_s': closure_time,
            'valve': valve_name,
            'junctions': {},
            'compliance': [],
            'max_surge_m': 0,
            'max_surge_kPa': 0,
        }

        pipe_rating_m = self.DEFAULTS['pipe_rating_kPa'] / g

        for node_name in tm.junction_name_list:
            node = tm.get_node(node_name)
            head = node.head
            steady = head[0]
            max_h = float(np.max(head))
            min_h = float(np.min(head))
            delta_h = max_h - steady

            # WSAA compliance checks gauge pressure, not total head
            gauge_max_m = max_h - node.elevation
            gauge_max_kPa = gauge_max_m * g

            results['junctions'][node_name] = {
                'steady_head_m': round(steady, 1),
                'max_head_m': round(max_h, 1),
                'min_head_m': round(min_h, 1),
                'surge_m': round(delta_h, 1),
                'surge_kPa': round(delta_h * g, 0),
                'max_pressure_kPa': round(gauge_max_kPa, 0),
            }

            if delta_h > results['max_surge_m']:
                results['max_surge_m'] = round(delta_h, 1)
                results['max_surge_kPa'] = round(delta_h * g, 0)

            # Compliance — compare gauge pressure to PN35 rating
            if gauge_max_kPa > self.DEFAULTS['pipe_rating_kPa']:
                results['compliance'].append({
                    'type': 'CRITICAL',
                    'element': node_name,
                    'message': f'Transient gauge pressure {gauge_max_kPa:.0f} kPa EXCEEDS PN35 rating',
                })
            elif gauge_max_kPa > self.DEFAULTS['pipe_rating_kPa'] * 0.8:
                results['compliance'].append({
                    'type': 'WARNING',
                    'element': node_name,
                    'message': f'Transient gauge pressure {gauge_max_kPa:.0f} kPa exceeds 80% of PN35',
                })

            min_pressure_head = min_h - node.elevation
            if min_pressure_head < 0:
                results['compliance'].append({
                    'type': 'CRITICAL',
                    'element': node_name,
                    'message': f'Negative pressure ({min_pressure_head:.1f}m) - column separation risk',
                })

        if not results['compliance']:
            results['compliance'].append({
                'type': 'OK',
                'message': 'All transient pressures within PN35 pipe rating',
            })

        # Mitigation recommendations
        surge = results['max_surge_m']
        if surge > 50:
            results['mitigation'] = [
                'Install air/vacuum surge vessels (size per AS/NZS 2566)',
                'Replace with slow-closing actuated valves (>10s closure)',
                'Install pressure relief valves at critical points',
                'Non-return valves with controlled closure',
            ]
        elif surge > 20:
            results['mitigation'] = [
                'Extend valve closure time to >5 seconds',
                'Consider surge anticipation valves',
                'Review pipe class ratings with safety factor',
            ]
        else:
            results['mitigation'] = ['Surge within acceptable limits']

        if save_plot:
            plot_path = self._plot_transient(tm, wave_speed=ws,
                                            closure_time=closure_time,
                                            start_time=start_time)
            results['plot'] = plot_path

        return results

    def _plot_transient(self, tm, wave_speed, closure_time, start_time):
        """Generate transient analysis plot."""
        t = tm.simulation_timestamps
        g = 9.81
        pipe_rating_m = self.DEFAULTS['pipe_rating_kPa'] / g

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle(f'Water Hammer - Wave Speed: {wave_speed} m/s | '
                     f'Closure: {closure_time}s',
                     fontsize=12, fontweight='bold')

        ax1 = axes[0]
        for node_name in tm.junction_name_list:
            node = tm.get_node(node_name)
            ax1.plot(t, node.head, label=node_name, linewidth=1.2)
        ax1.axvline(x=start_time, color='green', linestyle=':', alpha=0.7,
                   label='Valve closure')
        ax1.set_xlabel('Time (seconds)')
        ax1.set_ylabel('Head (m)')
        ax1.set_title('Hydraulic Head at Junctions')
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)

        ax2 = axes[1]
        positions, max_h, min_h, steady_h, labels = [], [], [], [], []
        for i, node_name in enumerate(tm.junction_name_list):
            node = tm.get_node(node_name)
            positions.append(i)
            max_h.append(float(np.max(node.head)))
            min_h.append(float(np.min(node.head)))
            steady_h.append(float(node.head[0]))
            labels.append(node_name)

        ax2.fill_between(positions, min_h, max_h, alpha=0.3, color='red',
                        label='Transient envelope')
        ax2.plot(positions, steady_h, 'bo-', linewidth=2, label='Steady state')
        ax2.plot(positions, max_h, 'r^-', linewidth=1, label='Max transient')
        ax2.plot(positions, min_h, 'rv-', linewidth=1, label='Min transient')
        ax2.set_xticks(positions)
        ax2.set_xticklabels(labels)
        ax2.set_xlabel('Junction')
        ax2.set_ylabel('Head (m)')
        ax2.set_title('Pressure Envelope')
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        path = os.path.join(self.output_dir, 'api_transient_results.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        return path

    # =========================================================================
    # PUMP TRANSIENT ANALYSIS
    # =========================================================================

    def run_pump_trip(self, pump_name, trip_time=2.0, sim_duration=30,
                      wave_speed=1000, save_plot=True):
        """
        Run pump trip (sudden shutdown) transient analysis using TSNet.

        Simulates a pump tripping off, which causes a sudden drop in
        flow and can generate negative pressure waves downstream and
        positive pressure waves upstream.

        Parameters
        ----------
        pump_name : str
            Name of the pump to trip (must exist in network).
        trip_time : float
            Duration of pump shutdown in seconds.
        sim_duration : float
            Total simulation time in seconds.
        wave_speed : float
            Wave speed in m/s (default: 1000 for ductile iron).
        save_plot : bool
            Whether to save plot image.

        Returns dict with transient pressures, surge values, compliance.
        """
        if self._inp_file is None:
            return {'error': 'No network file. Call load_network() or create_network() first.'}

        ws = wave_speed or self.DEFAULTS['wave_speed_ms']

        # Load into TSNet
        tm = tsnet.network.TransientModel(self._inp_file)
        tm.set_wavespeed(ws)
        tm.set_time(sim_duration)

        # Define pump shut-off rule: [tc, ts, se, m]
        # tc = trip duration, ts = start time (immediate), se = final %, m = shape
        rule = [trip_time, 0.0, 0, 1]
        tm.pump_shut_off(pump_name, rule)

        # Initialize and run MOC simulation
        tm = tsnet.simulation.Initializer(tm, 0, engine='DD')
        tm = tsnet.simulation.MOCSimulator(tm)

        self.tm = tm
        return self._build_pump_results(tm, pump_name, 'trip', trip_time,
                                        ws, save_plot)

    def run_pump_startup(self, pump_name, ramp_time=10.0, sim_duration=30,
                         wave_speed=1000, save_plot=True):
        """
        Run pump startup transient analysis using TSNet.

        Simulates a controlled pump startup with a ramp time. A slow
        startup reduces transient pressures compared to an instant start.

        Parameters
        ----------
        pump_name : str
            Name of the pump to start (must exist in network).
        ramp_time : float
            Duration of pump ramp-up in seconds.
        sim_duration : float
            Total simulation time in seconds.
        wave_speed : float
            Wave speed in m/s (default: 1000 for ductile iron).
        save_plot : bool
            Whether to save plot image.

        Returns dict with transient pressures, surge values, compliance.
        """
        if self._inp_file is None:
            return {'error': 'No network file. Call load_network() or create_network() first.'}

        ws = wave_speed or self.DEFAULTS['wave_speed_ms']

        # Load into TSNet
        tm = tsnet.network.TransientModel(self._inp_file)
        tm.set_wavespeed(ws)
        tm.set_time(sim_duration)

        # Define pump start-up rule: [tc, ts, se, m]
        # tc = ramp duration, ts = start time, se = final open %, m = shape
        rule = [ramp_time, 0.0, 1, 1]
        tm.pump_start_up(pump_name, rule)

        # Initialize and run MOC simulation
        tm = tsnet.simulation.Initializer(tm, 0, engine='DD')
        tm = tsnet.simulation.MOCSimulator(tm)

        self.tm = tm
        return self._build_pump_results(tm, pump_name, 'startup', ramp_time,
                                        ws, save_plot)

    def _build_pump_results(self, tm, pump_name, operation, duration_s,
                            wave_speed, save_plot):
        """Build results dict from a pump transient simulation."""
        g = 9.81

        results = {
            'pump_name': pump_name,
            'operation': operation,
            'duration_s': duration_s,
            'wave_speed_ms': wave_speed,
            'junctions': {},
            'compliance': [],
            'max_surge_m': 0,
            'max_surge_kPa': 0,
        }

        for node_name in tm.junction_name_list:
            node = tm.get_node(node_name)
            head = node.head
            steady = head[0]
            max_h = float(np.max(head))
            min_h = float(np.min(head))
            delta_h = max_h - steady

            # WSAA compliance checks gauge pressure, not total head
            gauge_max_m = max_h - node.elevation
            gauge_max_kPa = gauge_max_m * g

            results['junctions'][node_name] = {
                'steady_head_m': round(steady, 1),
                'max_head_m': round(max_h, 1),
                'min_head_m': round(min_h, 1),
                'surge_m': round(delta_h, 1),
                'surge_kPa': round(delta_h * g, 0),
                'max_pressure_kPa': round(gauge_max_kPa, 0),
            }

            if delta_h > results['max_surge_m']:
                results['max_surge_m'] = round(delta_h, 1)
                results['max_surge_kPa'] = round(delta_h * g, 0)

            # Compliance — compare gauge pressure to PN35 rating
            if gauge_max_kPa > self.DEFAULTS['pipe_rating_kPa']:
                results['compliance'].append({
                    'type': 'CRITICAL',
                    'element': node_name,
                    'message': f'Transient gauge pressure {gauge_max_kPa:.0f} kPa EXCEEDS PN35 rating',
                })
            elif gauge_max_kPa > self.DEFAULTS['pipe_rating_kPa'] * 0.8:
                results['compliance'].append({
                    'type': 'WARNING',
                    'element': node_name,
                    'message': f'Transient gauge pressure {gauge_max_kPa:.0f} kPa exceeds 80% of PN35',
                })

            min_pressure_head = min_h - node.elevation
            if min_pressure_head < 0:
                results['compliance'].append({
                    'type': 'CRITICAL',
                    'element': node_name,
                    'message': f'Negative pressure ({min_pressure_head:.1f}m) - column separation risk',
                })

        if not results['compliance']:
            results['compliance'].append({
                'type': 'OK',
                'message': 'All transient pressures within PN35 pipe rating',
            })

        # Mitigation recommendations
        surge = results['max_surge_m']
        if operation == 'trip':
            if surge > 50:
                results['mitigation'] = [
                    'Install surge vessels at pump station discharge',
                    'Add flywheel to pump to extend run-down time',
                    'Install non-return valve with controlled closure',
                    'Consider standby pump with auto-start',
                ]
            elif surge > 20:
                results['mitigation'] = [
                    'Install air/vacuum valves at high points',
                    'Consider surge anticipation valve',
                    'Review pump inertia and run-down characteristics',
                ]
            else:
                results['mitigation'] = ['Pump trip surge within acceptable limits']
        else:
            if surge > 50:
                results['mitigation'] = [
                    'Extend pump ramp-up time using VSD',
                    'Install surge vessels at pump discharge',
                    'Implement soft-start motor controller',
                ]
            elif surge > 20:
                results['mitigation'] = [
                    'Use variable speed drive for gradual startup',
                    'Ensure discharge valve opens before pump starts',
                ]
            else:
                results['mitigation'] = ['Pump startup surge within acceptable limits']

        if save_plot:
            plot_path = self._plot_pump_transient(tm, pump_name, operation,
                                                  duration_s, wave_speed)
            results['plot'] = plot_path

        return results

    def _plot_pump_transient(self, tm, pump_name, operation, duration_s,
                             wave_speed):
        """Generate pump transient analysis plot."""
        t = tm.simulation_timestamps
        g = 9.81

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        op_label = 'Trip' if operation == 'trip' else 'Startup'
        fig.suptitle(f'Pump {op_label} - {pump_name} | '
                     f'Wave Speed: {wave_speed} m/s | '
                     f'Duration: {duration_s}s',
                     fontsize=12, fontweight='bold')

        ax1 = axes[0]
        for node_name in tm.junction_name_list:
            node = tm.get_node(node_name)
            ax1.plot(t, node.head, label=node_name, linewidth=1.2)
        ax1.set_xlabel('Time (seconds)')
        ax1.set_ylabel('Head (m)')
        ax1.set_title('Hydraulic Head at Junctions')
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)

        ax2 = axes[1]
        positions, max_h, min_h, steady_h, labels = [], [], [], [], []
        for i, node_name in enumerate(tm.junction_name_list):
            node = tm.get_node(node_name)
            positions.append(i)
            max_h.append(float(np.max(node.head)))
            min_h.append(float(np.min(node.head)))
            steady_h.append(float(node.head[0]))
            labels.append(node_name)

        ax2.fill_between(positions, min_h, max_h, alpha=0.3, color='red',
                         label='Transient envelope')
        ax2.plot(positions, steady_h, 'bo-', linewidth=2, label='Steady state')
        ax2.plot(positions, max_h, 'r^-', linewidth=1, label='Max transient')
        ax2.plot(positions, min_h, 'rv-', linewidth=1, label='Min transient')
        ax2.set_xticks(positions)
        ax2.set_xticklabels(labels)
        ax2.set_xlabel('Junction')
        ax2.set_ylabel('Head (m)')
        ax2.set_title('Pressure Envelope')
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        path = os.path.join(self.output_dir,
                            f'api_pump_{operation}_results.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        return path

    # =========================================================================
    # REPORT GENERATION
    # =========================================================================

    def generate_report(self, format='docx', steady_results=None,
                        transient_results=None, fire_flow_results=None,
                        water_quality_results=None,
                        title='Hydraulic Analysis Report',
                        engineer_name='', project_name=''):
        """
        Generate a professional report from analysis results.

        Parameters
        ----------
        format : str
            Output format: 'docx' or 'pdf'.
        steady_results : dict or None
            Results from run_steady_state().
        transient_results : dict or None
            Results from run_transient().
        fire_flow_results : dict or None
            Results from run_fire_flow().
        water_quality_results : dict or None
            Results from run_water_quality().
        title : str
            Report title.
        engineer_name : str
            Engineer name shown on the cover page.
        project_name : str
            Project name (overrides title on cover page if provided).

        Returns
        -------
        str
            Path to the generated report file.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Call load_network() or create_network() first.'}

        # -- Build enriched network summary with node/link details --
        summary = self.get_network_summary()
        summary['nodes'] = self._get_node_details()
        summary['links'] = self._get_link_details()

        # -- Collect results --
        combined = {}
        if steady_results is not None:
            combined['steady_state'] = steady_results
        if transient_results is not None:
            combined['transient'] = transient_results
        if fire_flow_results is not None:
            combined['fire_flow'] = fire_flow_results
        if water_quality_results is not None:
            combined['water_quality'] = water_quality_results

        # -- Generate report --
        if format == 'docx':
            from reports.docx_report import generate_docx_report
            out_path = os.path.join(self.output_dir, 'report.docx')
            generate_docx_report(
                combined, summary, out_path,
                title=title, engineer_name=engineer_name,
                project_name=project_name,
            )
        elif format == 'pdf':
            from reports.pdf_report import generate_pdf_report
            out_path = os.path.join(self.output_dir, 'report.pdf')
            generate_pdf_report(
                combined, summary, out_path,
                title=title, engineer_name=engineer_name,
                project_name=project_name,
            )
        else:
            return {'error': f'Unsupported format: {format}. Use "docx" or "pdf".'}

        return out_path

    def _get_node_details(self):
        """Return list of node dicts with id, type, elevation, demand."""
        nodes = []
        for name in self.wn.junction_name_list:
            node = self.wn.get_node(name)
            nodes.append({
                'id': name, 'type': 'junction',
                'elevation': node.elevation,
                'demand_lps': round(node.base_demand * 1000, 2),
            })
        for name in self.wn.reservoir_name_list:
            node = self.wn.get_node(name)
            nodes.append({
                'id': name, 'type': 'reservoir',
                'head': node.base_head,
            })
        for name in self.wn.tank_name_list:
            node = self.wn.get_node(name)
            nodes.append({
                'id': name, 'type': 'tank',
                'elevation': node.elevation,
            })
        return nodes

    def _get_link_details(self):
        """Return list of link dicts with id, type, start, end, length, etc."""
        links = []
        for name in self.wn.pipe_name_list:
            pipe = self.wn.get_link(name)
            links.append({
                'id': name, 'type': 'pipe',
                'start': pipe.start_node_name, 'end': pipe.end_node_name,
                'length': pipe.length,
                'diameter_mm': round(pipe.diameter * 1000),
                'roughness': pipe.roughness,
            })
        for name in self.wn.valve_name_list:
            valve = self.wn.get_link(name)
            links.append({
                'id': name, 'type': 'valve',
                'start': valve.start_node_name, 'end': valve.end_node_name,
                'diameter_mm': round(valve.diameter * 1000),
            })
        return links

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def export_results_json(self, results, filename='results.json'):
        """Export results to JSON file in the output/ directory."""
        path = os.path.join(self.output_dir, filename)
        # Convert numpy types for JSON serialization
        def convert(obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            elif isinstance(obj, (np.floating,)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj

        with open(path, 'w') as f:
            json.dump(results, f, indent=2, default=convert)
        return path

    def list_networks(self):
        """List all .inp files in the models/ directory."""
        if os.path.exists(self.model_dir):
            return [f for f in os.listdir(self.model_dir) if f.endswith('.inp')]
        return []

    def joukowsky(self, wave_speed, velocity_change):
        """
        Calculate Joukowsky pressure rise.
        dH = (a * dV) / g
        """
        g = 9.81
        dH = (wave_speed * velocity_change) / g
        dP_kPa = dH * g
        return {
            'head_rise_m': round(dH, 1),
            'pressure_rise_kPa': round(dP_kPa, 0),
            'wave_speed_ms': wave_speed,
            'velocity_change_ms': velocity_change,
        }


# =========================================================================
# CLI INTERFACE - Run directly from command line
# =========================================================================
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='EPANET Hydraulic Analysis API')
    parser.add_argument('command', choices=['steady', 'transient', 'summary', 'joukowsky'],
                       help='Analysis to run')
    parser.add_argument('--inp', required=True, help='EPANET .inp file')
    parser.add_argument('--valve', help='Valve name for transient analysis')
    parser.add_argument('--closure-time', type=float, default=0.5,
                       help='Valve closure time (seconds)')
    parser.add_argument('--wave-speed', type=float, default=1000,
                       help='Wave speed (m/s)')
    parser.add_argument('--duration', type=float, default=20,
                       help='Transient simulation duration (seconds)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()
    api = HydraulicAPI()

    if args.command == 'summary':
        result = api.load_network(args.inp)
    elif args.command == 'steady':
        api.load_network(args.inp)
        result = api.run_steady_state()
    elif args.command == 'transient':
        if not args.valve:
            parser.error('--valve is required for transient analysis')
        api.load_network(args.inp)
        result = api.run_transient(args.valve,
                                  closure_time=args.closure_time,
                                  wave_speed=args.wave_speed,
                                  sim_duration=args.duration)
    elif args.command == 'joukowsky':
        result = api.joukowsky(args.wave_speed, 1.0)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for k, v in result.items():
            print(f"  {k}: {v}")

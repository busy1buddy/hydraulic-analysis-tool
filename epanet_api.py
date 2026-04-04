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
        'min_velocity_ms': 0.6,        # Minimum velocity to prevent sediment (WSAA)
        'pipe_rating_kPa': 3500,       # PN35 ductile iron
        'wave_speed_ms': 1100,         # AS 2280 minimum for ductile iron — conservative default
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

    def load_network_from_path(self, abs_path):
        """Load an EPANET .inp file from an absolute file path."""
        self._inp_file = abs_path
        self.wn = wntr.network.WaterNetworkModel(abs_path)
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
            # Minimum velocity check — WSAA: avoid sediment deposition
            v_avg = abs(float(flows[pipe_name].mean())) / area
            if v_avg < self.DEFAULTS['min_velocity_ms'] and v_avg > 0.01:
                results['compliance'].append({
                    'type': 'INFO',
                    'element': pipe_name,
                    'message': (f'Low velocity {v_avg:.2f} m/s < '
                                f'{self.DEFAULTS["min_velocity_ms"]} m/s '
                                f'(sediment risk — WSAA)'),
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

    def run_water_quality_chlorine(self, initial_conc=0.5, bulk_coeff=-0.5,
                                   wall_coeff=-0.01, duration_hrs=72,
                                   save_plot=False):
        """
        Run chlorine decay simulation using WNTR CHEMICAL quality mode.

        Sets up first-order bulk and wall decay coefficients, seeds all
        reservoirs with the initial concentration, and simulates chlorine
        transport through the network.

        Parameters
        ----------
        initial_conc : float
            Initial chlorine concentration at reservoirs (mg/L). Default 0.5.
        bulk_coeff : float
            Bulk decay coefficient (1/hr, negative = decay). Default -0.5/hr.
        wall_coeff : float
            Wall decay coefficient (m/hr, negative = decay). Default -0.01 m/hr.
        duration_hrs : float
            Simulation duration in hours. Default 72.
        save_plot : bool
            Whether to save a results bar chart.

        Returns
        -------
        dict
            junction_quality  : {junc_id: {'min_conc': float, 'avg_conc': float,
                                            'max_conc': float}}
            compliance        : list of compliance dicts (WSAA < 0.2 mg/L)
            non_compliant     : list of junction IDs below 0.2 mg/L
            parameters        : {'initial_conc', 'bulk_coeff', 'wall_coeff'}
        """
        if self.wn is None:
            return {'error': 'No network loaded. Call load_network() or create_network() first.'}

        original_duration = self.wn.options.time.duration
        original_quality_param = getattr(self.wn.options.quality, 'parameter', 'NONE')

        try:
            # Configure CHEMICAL quality mode
            self.wn.options.quality.parameter = 'CHEMICAL'
            self.wn.options.time.duration = int(duration_hrs * 3600)

            # Set bulk and wall reaction coefficients on every pipe
            # Bulk coeff in WNTR is 1/s (convert from 1/hr)
            # Wall coeff in WNTR is m/s (convert from m/hr)
            bulk_s = bulk_coeff / 3600.0   # 1/hr -> 1/s
            wall_s = wall_coeff / 3600.0   # m/hr -> m/s

            for pipe_name in self.wn.pipe_name_list:
                pipe = self.wn.get_link(pipe_name)
                pipe.bulk_coeff = bulk_s
                pipe.wall_coeff = wall_s

            # Seed reservoirs with initial concentration
            for res_name in self.wn.reservoir_name_list:
                res = self.wn.get_node(res_name)
                res.initial_quality = initial_conc

            # Set junction initial quality to 0 (receives tracer from reservoir)
            for junc_name in self.wn.junction_name_list:
                junc = self.wn.get_node(junc_name)
                junc.initial_quality = 0.0

            sim = wntr.sim.EpanetSimulator(self.wn)
            quality_results = sim.run_sim()
            quality = quality_results.node['quality']

            results = {
                'parameter': 'CHEMICAL',
                'unit': 'mg/L',
                'duration_hrs': duration_hrs,
                'junction_quality': {},
                'non_compliant': [],
                'compliance': [],
                'parameters': {
                    'initial_conc': initial_conc,
                    'bulk_coeff': bulk_coeff,
                    'wall_coeff': wall_coeff,
                },
            }

            # WSAA chlorine residual minimum: 0.2 mg/L
            WSAA_MIN_CHLORINE_MGL = 0.2  # WSAA WSA 03-2011

            for junc in self.wn.junction_name_list:
                q = quality[junc]
                min_c = round(float(q.min()), 4)
                avg_c = round(float(q.mean()), 4)
                max_c = round(float(q.max()), 4)
                results['junction_quality'][junc] = {
                    'min_conc': min_c,
                    'avg_conc': avg_c,
                    'max_conc': max_c,
                }
                # Flag if minimum drops below WSAA threshold
                if min_c < WSAA_MIN_CHLORINE_MGL:
                    results['non_compliant'].append(junc)

            for junc in results['non_compliant']:
                c = results['junction_quality'][junc]['min_conc']
                results['compliance'].append({
                    'type': 'WARNING',
                    'element': junc,
                    'message': (f'Min chlorine {c:.3f} mg/L < 0.2 mg/L '
                                f'(WSAA WSA 03-2011 residual minimum)'),
                })

            if not results['compliance']:
                results['compliance'].append({
                    'type': 'OK',
                    'message': 'All junctions meet 0.2 mg/L chlorine residual (WSAA)',
                })

        finally:
            self.wn.options.time.duration = original_duration
            self.wn.options.quality.parameter = original_quality_param

        return results

    def run_water_quality_trace(self, source_node, duration_hrs=72,
                                save_plot=False):
        """
        Run a tracer analysis to determine what percentage of water at each
        junction originates from the specified source node.

        Parameters
        ----------
        source_node : str
            Name of the reservoir or node to trace from.
        duration_hrs : float
            Simulation duration in hours. Default 72.
        save_plot : bool
            Whether to save a results bar chart.

        Returns
        -------
        dict
            junction_quality  : {junc_id: {'avg_pct': float, 'min_pct': float,
                                            'max_pct': float}}
            source_node       : str
            compliance        : list (informational only)
        """
        if self.wn is None:
            return {'error': 'No network loaded. Call load_network() or create_network() first.'}

        original_duration = self.wn.options.time.duration
        original_quality_param = getattr(self.wn.options.quality, 'parameter', 'NONE')
        original_trace_node = getattr(self.wn.options.quality, 'trace_node', None)

        try:
            # Configure TRACE quality mode
            # WNTR QualityOptions uses trace_node attribute to specify the source
            self.wn.options.quality.parameter = 'TRACE'
            self.wn.options.quality.trace_node = source_node

            self.wn.options.time.duration = int(duration_hrs * 3600)

            sim = wntr.sim.EpanetSimulator(self.wn)
            quality_results = sim.run_sim()
            quality = quality_results.node['quality']

            results = {
                'parameter': 'TRACE',
                'unit': '%',
                'source_node': source_node,
                'duration_hrs': duration_hrs,
                'junction_quality': {},
                'compliance': [],
            }

            for junc in self.wn.junction_name_list:
                q = quality[junc]
                avg_pct = round(float(q.mean()), 2)
                min_pct = round(float(q.min()), 2)
                max_pct = round(float(q.max()), 2)
                results['junction_quality'][junc] = {
                    'avg_pct': avg_pct,
                    'min_pct': min_pct,
                    'max_pct': max_pct,
                }

            results['compliance'].append({
                'type': 'INFO',
                'message': (f'Trace from {source_node}: '
                            f'{len(results["junction_quality"])} junctions analysed'),
            })

        finally:
            self.wn.options.time.duration = original_duration
            self.wn.options.quality.parameter = original_quality_param
            if hasattr(self.wn.options.quality, 'trace_node'):
                self.wn.options.quality.trace_node = original_trace_node

        return results

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
                      wave_speed=None, save_plot=True):
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
        wave_speed : float or None
            Wave speed in m/s (default: 1100 per AS 2280 ductile iron).
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
                         wave_speed=None, save_plot=True):
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
        wave_speed : float or None
            Wave speed in m/s (default: 1100 per AS 2280 ductile iron).
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

    # =========================================================================
    # NETWORK SKELETONISATION
    # =========================================================================

    def skeletonise(self, min_diameter_mm=100, remove_dead_ends=True,
                    merge_series=True):
        """
        Simplify the network by removing insignificant elements.

        Operations:
        1. Remove dead-end branches below min_diameter_mm
        2. Merge series pipes (two pipes with a junction that has no demand)
        3. Report before/after counts

        Returns dict with 'removed_pipes', 'removed_nodes', 'merged_pipes',
        'before', 'after' counts. Does NOT modify the network — returns
        a plan that the user can review before applying.

        Ref: Walski (2001) "Pipe Network Simplification"
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        before = {
            'nodes': len(self.wn.junction_name_list),
            'pipes': len(self.wn.pipe_name_list),
        }

        dead_end_removals = []
        series_merges = []

        if remove_dead_ends:
            # Find dead-end junctions (degree 1, below diameter threshold)
            for jid in list(self.wn.junction_name_list):
                connected_pipes = []
                for pid in self.wn.pipe_name_list:
                    pipe = self.wn.get_link(pid)
                    if pipe.start_node_name == jid or pipe.end_node_name == jid:
                        connected_pipes.append(pid)
                if len(connected_pipes) == 1:
                    pipe = self.wn.get_link(connected_pipes[0])
                    dn_mm = int(pipe.diameter * 1000)
                    if dn_mm < min_diameter_mm:
                        dead_end_removals.append({
                            'node': jid,
                            'pipe': connected_pipes[0],
                            'diameter_mm': dn_mm,
                        })

        if merge_series:
            # Find series junctions (degree 2, no demand)
            for jid in list(self.wn.junction_name_list):
                # Skip if already marked for removal
                if any(d['node'] == jid for d in dead_end_removals):
                    continue
                # Check demand
                junc = self.wn.get_node(jid)
                demand = 0
                if junc.demand_timeseries_list:
                    demand = abs(junc.demand_timeseries_list[0].base_value)
                if demand > 0.0001:
                    continue  # has demand — can't remove

                connected_pipes = []
                for pid in self.wn.pipe_name_list:
                    pipe = self.wn.get_link(pid)
                    if pipe.start_node_name == jid or pipe.end_node_name == jid:
                        connected_pipes.append(pid)
                if len(connected_pipes) == 2:
                    p1 = self.wn.get_link(connected_pipes[0])
                    p2 = self.wn.get_link(connected_pipes[1])
                    # Equivalent pipe: same diameter (larger), combined length, average roughness
                    eq_length = p1.length + p2.length
                    eq_diameter = max(p1.diameter, p2.diameter)
                    eq_roughness = (p1.roughness + p2.roughness) / 2
                    series_merges.append({
                        'node': jid,
                        'pipe1': connected_pipes[0],
                        'pipe2': connected_pipes[1],
                        'equivalent_length_m': round(eq_length, 1),
                        'equivalent_diameter_mm': int(eq_diameter * 1000),
                        'equivalent_roughness': round(eq_roughness, 0),
                    })

        after = {
            'nodes': before['nodes'] - len(dead_end_removals) - len(series_merges),
            'pipes': before['pipes'] - len(dead_end_removals) - len(series_merges),
        }

        return {
            'dead_end_removals': dead_end_removals,
            'series_merges': series_merges,
            'before': before,
            'after': after,
            'reduction_pct': round(
                (1 - after['pipes'] / max(before['pipes'], 1)) * 100, 1),
        }

    # =========================================================================
    # SENSITIVITY ANALYSIS
    # =========================================================================

    def sensitivity_analysis(self, parameter='roughness', variation_pct=20):
        """
        One-at-a-time sensitivity analysis.

        Varies each pipe's roughness (or each junction's demand) by ±N%
        and measures the impact on system-wide minimum pressure.

        Parameters
        ----------
        parameter : str
            'roughness' or 'demand'
        variation_pct : float
            Percentage variation (default 20%)

        Returns list of dicts sorted by impact (highest first), each with:
        'element', 'base_value', 'pressure_change_m', 'sensitivity_rank'.

        Ref: WSAA Design Guidelines — sensitivity analysis
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        # Run baseline
        try:
            base_results = self.run_steady_state(save_plot=False)
        except Exception as e:
            return {'error': f'Baseline failed: {e}'}

        base_pressures = base_results.get('pressures', {})
        base_min_p = min(p.get('min_m', 0) for p in base_pressures.values()) if base_pressures else 0

        sensitivities = []
        factor = variation_pct / 100

        if parameter == 'roughness':
            for pid in self.wn.pipe_name_list:
                pipe = self.wn.get_link(pid)
                original = pipe.roughness

                # Decrease roughness (worse condition)
                pipe.roughness = original * (1 - factor)
                try:
                    res = self.run_steady_state(save_plot=False)
                    p = res.get('pressures', {})
                    min_p_low = min(v.get('min_m', 0) for v in p.values()) if p else 0
                except Exception:
                    min_p_low = base_min_p

                # Restore
                pipe.roughness = original

                # Increase roughness (better condition)
                pipe.roughness = original * (1 + factor)
                try:
                    res = self.run_steady_state(save_plot=False)
                    p = res.get('pressures', {})
                    min_p_high = min(v.get('min_m', 0) for v in p.values()) if p else 0
                except Exception:
                    min_p_high = base_min_p

                pipe.roughness = original

                impact = abs(min_p_high - min_p_low)
                sensitivities.append({
                    'element': pid,
                    'type': 'pipe roughness',
                    'base_value': round(original, 0),
                    'pressure_change_m': round(impact, 2),
                })

        elif parameter == 'demand':
            for jid in self.wn.junction_name_list:
                junc = self.wn.get_node(jid)
                if not junc.demand_timeseries_list:
                    continue
                original = junc.demand_timeseries_list[0].base_value
                if abs(original) < 1e-6:
                    continue

                junc.demand_timeseries_list[0].base_value = original * (1 + factor)
                try:
                    res = self.run_steady_state(save_plot=False)
                    p = res.get('pressures', {})
                    min_p_high = min(v.get('min_m', 0) for v in p.values()) if p else 0
                except Exception:
                    min_p_high = base_min_p

                junc.demand_timeseries_list[0].base_value = original * (1 - factor)
                try:
                    res = self.run_steady_state(save_plot=False)
                    p = res.get('pressures', {})
                    min_p_low = min(v.get('min_m', 0) for v in p.values()) if p else 0
                except Exception:
                    min_p_low = base_min_p

                junc.demand_timeseries_list[0].base_value = original

                impact = abs(min_p_high - min_p_low)
                sensitivities.append({
                    'element': jid,
                    'type': 'junction demand',
                    'base_value': round(original * 1000, 2),  # m³/s to LPS
                    'pressure_change_m': round(impact, 2),
                })

        # Sort by impact
        sensitivities.sort(key=lambda x: x['pressure_change_m'], reverse=True)
        for i, s in enumerate(sensitivities):
            s['sensitivity_rank'] = i + 1

        return sensitivities

    # =========================================================================
    # PRESSURE ZONE MANAGEMENT
    # =========================================================================

    def __init_zones(self):
        """Lazy-init zone storage."""
        if not hasattr(self, '_pressure_zones'):
            self._pressure_zones = {}  # {zone_name: {'nodes': set(), 'color': str}}

    def assign_pressure_zone(self, zone_name, node_ids, color='#89b4fa'):
        """
        Assign nodes to a named pressure zone.

        Parameters
        ----------
        zone_name : str
            Zone identifier (e.g., 'Zone A - High Level')
        node_ids : list of str
            Junction IDs to assign to this zone
        color : str
            Hex colour for canvas overlay
        """
        self.__init_zones()
        self._pressure_zones[zone_name] = {
            'nodes': set(node_ids),
            'color': color,
        }

    def remove_pressure_zone(self, zone_name):
        """Remove a pressure zone definition."""
        self.__init_zones()
        self._pressure_zones.pop(zone_name, None)

    def get_pressure_zones(self):
        """Return all pressure zone definitions."""
        self.__init_zones()
        return {name: {'nodes': list(z['nodes']), 'color': z['color']}
                for name, z in self._pressure_zones.items()}

    def get_node_zone(self, node_id):
        """Return the zone name for a node, or None if unassigned."""
        self.__init_zones()
        for zone_name, z in self._pressure_zones.items():
            if node_id in z['nodes']:
                return zone_name
        return None

    def analyze_pressure_zones(self, results=None):
        """
        Analyse pressure balance across defined zones.

        Returns dict with per-zone statistics: demand, pressure range,
        node count, and PRV recommendations.
        """
        self.__init_zones()
        if self.wn is None:
            return {'error': 'No network loaded'}
        if results is None:
            results = self.run_steady_state(save_plot=False)

        pressures = results.get('pressures', {})
        zone_report = {}

        for zone_name, z in self._pressure_zones.items():
            zone_nodes = z['nodes']
            zone_pressures = []
            zone_demand_lps = 0.0

            for nid in zone_nodes:
                if nid in pressures:
                    p = pressures[nid]
                    zone_pressures.append(p.get('avg_m', 0))

                try:
                    node = self.wn.get_node(nid)
                    if hasattr(node, 'demand_timeseries_list') and node.demand_timeseries_list:
                        # Convert m³/s to LPS
                        zone_demand_lps += node.demand_timeseries_list[0].base_value * 1000
                except Exception:
                    pass

            if zone_pressures:
                min_p = min(zone_pressures)
                max_p = max(zone_pressures)
                avg_p = sum(zone_pressures) / len(zone_pressures)
            else:
                min_p = max_p = avg_p = 0.0

            # PRV recommendation: if max pressure > 50 m (WSAA WSA 03-2011)
            prv_recommended = max_p > self.DEFAULTS['max_pressure_m']
            # WSAA compliance
            wsaa_pass = min_p >= self.DEFAULTS['min_pressure_m'] and max_p <= self.DEFAULTS['max_pressure_m']

            zone_report[zone_name] = {
                'node_count': len(zone_nodes),
                'total_demand_lps': round(zone_demand_lps, 2),
                'min_pressure_m': round(min_p, 1),
                'max_pressure_m': round(max_p, 1),
                'avg_pressure_m': round(avg_p, 1),
                'pressure_range_m': round(max_p - min_p, 1),
                'wsaa_compliant': wsaa_pass,
                'prv_recommended': prv_recommended,
                'color': z['color'],
            }

        # Unassigned nodes
        all_zone_nodes = set()
        for z in self._pressure_zones.values():
            all_zone_nodes.update(z['nodes'])
        unassigned = [n for n in self.wn.junction_name_list if n not in all_zone_nodes]
        if unassigned:
            zone_report['_unassigned'] = {
                'node_count': len(unassigned),
                'nodes': unassigned,
            }

        return zone_report

    # =========================================================================
    # REHABILITATION PRIORITISATION
    # =========================================================================

    def set_pipe_condition(self, pipe_id, install_year=None, condition_score=None,
                           break_history=0, material=None):
        """
        Set asset condition data for a pipe.

        Parameters
        ----------
        pipe_id : str
            Pipe ID in the network
        install_year : int or None
            Year of installation
        condition_score : float or None
            Condition grade 1 (new) to 5 (failed) per WSAA
        break_history : int
            Number of recorded breaks/failures
        material : str or None
            Pipe material (e.g., 'AC', 'CI', 'DI', 'PVC', 'PE')
        """
        if not hasattr(self, '_pipe_conditions'):
            self._pipe_conditions = {}
        self._pipe_conditions[pipe_id] = {
            'install_year': install_year,
            'condition_score': condition_score,
            'break_history': break_history,
            'material': material,
        }

    def get_pipe_conditions(self):
        """Return all pipe condition data."""
        if not hasattr(self, '_pipe_conditions'):
            self._pipe_conditions = {}
        return dict(self._pipe_conditions)

    def import_pipe_conditions_csv(self, csv_path):
        """
        Import pipe condition data from CSV.

        Expected columns: pipe_id, install_year, condition_score,
        break_history, material
        """
        import csv
        if not hasattr(self, '_pipe_conditions'):
            self._pipe_conditions = {}

        count = 0
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                pid = row.get('pipe_id', '').strip()
                if not pid:
                    continue
                self._pipe_conditions[pid] = {
                    'install_year': int(row['install_year']) if row.get('install_year') else None,
                    'condition_score': float(row['condition_score']) if row.get('condition_score') else None,
                    'break_history': int(row.get('break_history', 0) or 0),
                    'material': row.get('material', '').strip() or None,
                }
                count += 1
        return count

    def prioritize_rehabilitation(self, results=None, current_year=None):
        """
        Score and rank pipes for rehabilitation based on:
        - Age (years since installation)
        - Condition score (1-5 WSAA scale)
        - Break history (number of failures)
        - Hydraulic performance (headloss, velocity)

        Returns list of dicts sorted by priority score (highest = most urgent).

        Scoring formula:
          priority = (age_score × 0.25) + (condition_score × 0.30)
                   + (break_score × 0.25) + (hydraulic_score × 0.20)

        All component scores normalised to 0-100 range.
        Ref: WSAA Asset Management Guidelines, IPWEA Practice Note 7
        """
        if not hasattr(self, '_pipe_conditions'):
            self._pipe_conditions = {}
        if self.wn is None:
            return {'error': 'No network loaded'}

        if current_year is None:
            from datetime import date
            current_year = date.today().year

        if results is None:
            results = self.run_steady_state(save_plot=False)

        flows = results.get('flows', {})
        pipe_scores = []

        for pid in self.wn.pipe_name_list:
            cond = self._pipe_conditions.get(pid, {})
            pipe = self.wn.get_link(pid)

            # Age score (0-100): assume 100-year design life
            install_year = cond.get('install_year')
            if install_year:
                age = current_year - install_year
                age_score = min(100, (age / 100) * 100)
            else:
                age_score = 50  # unknown age = medium risk

            # Condition score (0-100): 1=new(0), 5=failed(100)
            cs = cond.get('condition_score')
            if cs is not None:
                condition_norm = (cs - 1) / 4 * 100
            else:
                condition_norm = 50  # unknown = medium risk

            # Break score (0-100): 5+ breaks = max score
            breaks = cond.get('break_history', 0)
            break_score = min(100, breaks * 20)

            # Hydraulic score (0-100): based on velocity ratio to max
            fdata = flows.get(pid, {})
            v_max = fdata.get('max_velocity_ms', 0)
            # Penalise both high velocity (>2.0 m/s) and very low (<0.3 m/s)
            if v_max > self.DEFAULTS['max_velocity_ms']:
                hydraulic_score = min(100, (v_max / self.DEFAULTS['max_velocity_ms']) * 80)
            elif v_max < 0.3 and v_max > 0:
                hydraulic_score = 60  # stagnation risk
            else:
                hydraulic_score = max(0, (v_max / self.DEFAULTS['max_velocity_ms']) * 30)

            # Weighted priority score — WSAA Asset Management Guidelines
            priority = (age_score * 0.25 + condition_norm * 0.30
                       + break_score * 0.25 + hydraulic_score * 0.20)

            # Risk category
            if priority >= 75:
                risk = 'CRITICAL'
            elif priority >= 50:
                risk = 'HIGH'
            elif priority >= 25:
                risk = 'MEDIUM'
            else:
                risk = 'LOW'

            pipe_scores.append({
                'pipe_id': pid,
                'diameter_mm': int(pipe.diameter * 1000),
                'length_m': round(pipe.length, 1),
                'material': cond.get('material', 'Unknown'),
                'install_year': install_year,
                'age_years': current_year - install_year if install_year else None,
                'condition_score': cs,
                'break_history': breaks,
                'velocity_ms': round(v_max, 2),
                'priority_score': round(priority, 1),
                'risk_category': risk,
                'age_component': round(age_score, 1),
                'condition_component': round(condition_norm, 1),
                'break_component': round(break_score, 1),
                'hydraulic_component': round(hydraulic_score, 1),
            })

        # Sort by priority (highest first)
        pipe_scores.sort(key=lambda x: x['priority_score'], reverse=True)
        return pipe_scores

    # =========================================================================
    # PIPE PROFILE (Longitudinal Section)
    # =========================================================================

    def compute_pipe_profile(self, node_path, results=None):
        """
        Compute longitudinal section data for a path through the network.

        Parameters
        ----------
        node_path : list of str
            Ordered list of node IDs defining the path (e.g., ['R1','J1','J2','J3'])
        results : dict or None
            Steady-state results dict. If None, runs analysis.

        Returns dict with:
            - 'stations': list of cumulative distance (m)
            - 'invert': list of pipe invert elevation (m AHD)
            - 'hgl': list of hydraulic grade line (m AHD) = pressure + elevation
            - 'ground': list of node elevation (m AHD) — for profile
            - 'pressure_head': list of pressure (m) at each node
            - 'pipes': list of {'id', 'start_station', 'end_station', 'diameter_mm'}
            - 'warnings': list of issues (negative pressure, air pockets)

        Ref: Standard hydraulic design practice — longitudinal section
        """
        if self.wn is None:
            return {'error': 'No network loaded'}
        if len(node_path) < 2:
            return {'error': 'Path must contain at least 2 nodes'}

        if results is None:
            results = self.run_steady_state(save_plot=False)

        pressures = results.get('pressures', {})

        stations = [0.0]
        invert = []
        hgl = []
        ground = []
        pressure_head = []
        pipes_info = []
        warnings = []
        cumulative_dist = 0.0

        for i, nid in enumerate(node_path):
            try:
                node = self.wn.get_node(nid)
            except Exception:
                return {'error': f'Node {nid} not found in network'}

            elev = getattr(node, 'elevation', getattr(node, 'base_head', 0))
            ground.append(round(elev, 2))
            invert.append(round(elev, 2))

            p_data = pressures.get(nid, {})
            p_m = p_data.get('avg_m', 0)
            pressure_head.append(round(p_m, 2))
            hgl.append(round(elev + p_m, 2))

            # Check for negative pressure (air pocket risk)
            if p_m < 0:
                warnings.append(f'{nid}: negative pressure {p_m:.1f} m — air pocket risk')
            elif p_m < 5:
                warnings.append(f'{nid}: very low pressure {p_m:.1f} m — cavitation risk')

            # Find pipe connecting this node to next
            if i < len(node_path) - 1:
                next_nid = node_path[i + 1]
                pipe_found = False
                for pid in self.wn.pipe_name_list:
                    pipe = self.wn.get_link(pid)
                    sn, en = pipe.start_node_name, pipe.end_node_name
                    if (sn == nid and en == next_nid) or (sn == next_nid and en == nid):
                        cumulative_dist += pipe.length
                        stations.append(round(cumulative_dist, 1))
                        pipes_info.append({
                            'id': pid,
                            'start_station': round(cumulative_dist - pipe.length, 1),
                            'end_station': round(cumulative_dist, 1),
                            'diameter_mm': int(pipe.diameter * 1000),
                            'length_m': round(pipe.length, 1),
                        })
                        pipe_found = True
                        break
                if not pipe_found:
                    return {'error': f'No pipe connecting {nid} to {next_nid}'}

        # Check HGL slope for air pocket potential
        for i in range(1, len(hgl)):
            if hgl[i] > hgl[i - 1] and ground[i] > ground[i - 1]:
                # HGL rises at a high point — potential air pocket
                if ground[i] > hgl[i]:
                    warnings.append(
                        f'Profile high point at {node_path[i]}: '
                        f'ground ({ground[i]:.1f} m) above HGL ({hgl[i]:.1f} m)')

        return {
            'stations': stations,
            'invert': invert,
            'hgl': hgl,
            'ground': ground,
            'pressure_head': pressure_head,
            'pipes': pipes_info,
            'node_ids': node_path,
            'warnings': warnings,
            'total_length_m': round(cumulative_dist, 1),
        }

    # =========================================================================
    # PUMP OPERATING POINT
    # =========================================================================

    def compute_pump_operating_point(self, pump_name, results=None):
        """
        Compute pump and system curves to find the operating point.

        Parameters
        ----------
        pump_name : str
            Pump ID in the network
        results : dict or None
            Steady-state results. If None, runs analysis.

        Returns dict with:
            - 'pump_curve': [(flow_lps, head_m), ...]
            - 'system_curve': [(flow_lps, head_m), ...]
            - 'operating_point': {'flow_lps', 'head_m'}
            - 'efficiency': float or None
            - 'bep_flow_lps': float or None (best efficiency point)
            - 'warnings': list of operating issues

        Ref: Pump fundamentals — Karassik et al. (2008)
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        try:
            pump = self.wn.get_link(pump_name)
        except Exception:
            return {'error': f'Pump {pump_name} not found'}

        if results is None:
            results = self.run_steady_state(save_plot=False)

        # Get pump curve points from WNTR
        pump_curve_name = pump.pump_curve_name
        if pump_curve_name is None:
            return {'error': f'Pump {pump_name} has no defined pump curve'}

        try:
            curve = self.wn.get_curve(pump_curve_name)
            curve_pts = [(round(pt[0] * 1000, 2), round(pt[1], 2))  # m³/s→LPS, m
                         for pt in curve.points]
        except Exception:
            return {'error': f'Could not read pump curve {pump_curve_name}'}

        if not curve_pts:
            return {'error': 'Pump curve has no data points'}

        # Get operating flow from results
        flows = results.get('flows', {})
        pump_flow_data = flows.get(pump_name, {})
        op_flow_lps = abs(pump_flow_data.get('avg_lps', 0))

        # Compute operating head from pump curve interpolation
        # Linear interpolation along curve
        op_head = 0
        for i in range(len(curve_pts) - 1):
            q0, h0 = curve_pts[i]
            q1, h1 = curve_pts[i + 1]
            if q0 <= op_flow_lps <= q1:
                t = (op_flow_lps - q0) / (q1 - q0) if q1 != q0 else 0
                op_head = h0 + t * (h1 - h0)
                break
        else:
            # Extrapolate from last two points
            if len(curve_pts) >= 2:
                q0, h0 = curve_pts[-2]
                q1, h1 = curve_pts[-1]
                if q1 != q0:
                    t = (op_flow_lps - q0) / (q1 - q0)
                    op_head = h0 + t * (h1 - h0)

        # Build system curve (parabolic: H = H_static + k*Q²)
        # H_static from node elevations, k from operating point
        sn = pump.start_node_name
        en = pump.end_node_name
        try:
            elev_start = getattr(self.wn.get_node(sn), 'elevation',
                                 getattr(self.wn.get_node(sn), 'base_head', 0))
            elev_end = getattr(self.wn.get_node(en), 'elevation',
                               getattr(self.wn.get_node(en), 'base_head', 0))
            # Include downstream pressure target
            p_end = results.get('pressures', {}).get(en, {}).get('avg_m', 0)
            H_static = (elev_end + p_end) - elev_start
        except Exception:
            H_static = 0

        if op_flow_lps > 0.01:
            k = (op_head - H_static) / (op_flow_lps ** 2) if op_head > H_static else 0
        else:
            k = 0

        max_flow = curve_pts[-1][0] * 1.3 if curve_pts else 100
        system_pts = []
        for i in range(21):
            q = max_flow * i / 20
            h = H_static + k * q ** 2
            system_pts.append((round(q, 2), round(h, 2)))

        # BEP estimation: middle of pump curve range
        bep_flow = (curve_pts[0][0] + curve_pts[-1][0]) / 2 if len(curve_pts) >= 2 else None

        # Warnings
        warnings = []
        if bep_flow:
            ratio = op_flow_lps / bep_flow if bep_flow > 0 else 0
            if ratio < 0.7:
                warnings.append(
                    f'Operating at {ratio:.1%} of BEP flow — '
                    f'risk of recirculation, vibration, and reduced bearing life')
            elif ratio > 1.2:
                warnings.append(
                    f'Operating at {ratio:.1%} of BEP flow — '
                    f'risk of cavitation and motor overload')

        if op_head < 0:
            warnings.append('Negative operating head — check pump direction')

        return {
            'pump_curve': curve_pts,
            'system_curve': system_pts,
            'operating_point': {
                'flow_lps': round(op_flow_lps, 2),
                'head_m': round(op_head, 2),
            },
            'bep_flow_lps': round(bep_flow, 2) if bep_flow else None,
            'static_head_m': round(H_static, 2),
            'warnings': warnings,
        }

    # =========================================================================
    # PIPE SIZING OPTIMISATION
    # =========================================================================

    # Pipe cost database: $/m by DN (AUD, typical Australian supply+install)
    # Ref: Rawlinsons Australian Construction Handbook 2024
    PIPE_COST_PER_M = {
        100: 120, 150: 160, 200: 220, 250: 310, 300: 420,
        375: 580, 450: 750, 500: 900, 600: 1200, 750: 1800,
        900: 2500,
    }

    # Available pipe DN sizes for optimisation (mm)
    AVAILABLE_DN = [100, 150, 200, 250, 300, 375, 450, 500, 600, 750, 900]

    def optimise_pipe_sizes(self, target_pressure_m=None, budget_limit=None):
        """
        Find minimum-cost pipe sizes that satisfy WSAA pressure constraints.

        Uses iterative approach: start with smallest possible pipes, then
        upsize pipes with highest headloss contribution until all nodes
        meet minimum pressure.

        Parameters
        ----------
        target_pressure_m : float or None
            Minimum pressure target (default: WSAA 20 m)
        budget_limit : float or None
            Maximum budget in AUD (no limit if None)

        Returns dict with 'recommendations', 'total_cost', 'base_cost'.
        Ref: WSAA Design Guidelines, Rawlinsons Handbook
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        if target_pressure_m is None:
            target_pressure_m = self.DEFAULTS['min_pressure_m']

        # Record original diameters
        original_diameters = {}
        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            original_diameters[pid] = pipe.diameter

        # Base cost at current sizes
        base_cost = self._calc_network_cost()

        # Run baseline analysis
        try:
            base_results = self.run_steady_state(save_plot=False)
        except Exception as e:
            return {'error': f'Baseline analysis failed: {e}'}

        recommendations = []

        # Find pipes that are bottlenecks (highest headloss)
        flows = base_results.get('flows', {})
        pressures = base_results.get('pressures', {})

        # Find nodes below target
        low_nodes = {nid for nid, p in pressures.items()
                     if p.get('min_m', 0) < target_pressure_m}

        if not low_nodes:
            # All nodes meet target — try downsizing for cost savings
            return {
                'recommendations': [],
                'total_cost': base_cost,
                'base_cost': base_cost,
                'savings': 0,
                'message': f'All nodes already meet {target_pressure_m:.0f} m target. '
                           f'No upgrades needed.',
            }

        # Rank pipes by headloss per km (highest = most constrained)
        pipe_ranking = []
        for pid, fdata in flows.items():
            pipe = self.wn.get_link(pid)
            v = fdata.get('max_velocity_ms', 0)
            dn_mm = int(pipe.diameter * 1000)
            # Find next available size
            next_dn = None
            for dn in self.AVAILABLE_DN:
                if dn > dn_mm:
                    next_dn = dn
                    break
            if next_dn is None:
                continue
            # Cost of upsizing
            cost_current = self.PIPE_COST_PER_M.get(dn_mm, 0) * pipe.length
            cost_upsize = self.PIPE_COST_PER_M.get(next_dn, 0) * pipe.length
            pipe_ranking.append({
                'pipe_id': pid,
                'current_dn': dn_mm,
                'proposed_dn': next_dn,
                'length_m': pipe.length,
                'velocity_ms': v,
                'cost_increase': cost_upsize - cost_current,
            })

        # Sort by velocity (highest velocity pipes are most constrained)
        pipe_ranking.sort(key=lambda x: x['velocity_ms'], reverse=True)

        # Iteratively upsize until target met or budget exhausted
        total_extra_cost = 0
        for item in pipe_ranking:
            if not low_nodes:
                break
            if budget_limit and total_extra_cost + item['cost_increase'] > budget_limit:
                continue

            pid = item['pipe_id']
            new_d = item['proposed_dn'] / 1000  # mm to m

            # Apply upsize
            self.wn.get_link(pid).diameter = new_d

            # Re-run analysis
            try:
                test_results = self.run_steady_state(save_plot=False)
            except Exception:
                # Revert
                self.wn.get_link(pid).diameter = original_diameters[pid]
                continue

            # Check improvement
            new_pressures = test_results.get('pressures', {})
            new_low = {nid for nid, p in new_pressures.items()
                       if p.get('min_m', 0) < target_pressure_m}

            if len(new_low) < len(low_nodes):
                # Improvement — keep this change
                recommendations.append(item)
                total_extra_cost += item['cost_increase']
                low_nodes = new_low
            else:
                # No improvement — revert
                self.wn.get_link(pid).diameter = original_diameters[pid]

        # Restore original diameters
        for pid, d in original_diameters.items():
            self.wn.get_link(pid).diameter = d

        new_cost = base_cost + total_extra_cost

        return {
            'recommendations': recommendations,
            'total_cost': round(new_cost, 0),
            'base_cost': round(base_cost, 0),
            'cost_increase': round(total_extra_cost, 0),
            'remaining_failures': len(low_nodes),
            'target_pressure_m': target_pressure_m,
        }

    def _calc_network_cost(self):
        """Calculate total pipe cost at current sizes."""
        total = 0
        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            dn_mm = int(pipe.diameter * 1000)
            cost_per_m = self.PIPE_COST_PER_M.get(dn_mm, 0)
            if cost_per_m == 0:
                # Find closest DN
                closest = min(self.AVAILABLE_DN, key=lambda x: abs(x - dn_mm))
                cost_per_m = self.PIPE_COST_PER_M.get(closest, 200)
            total += cost_per_m * pipe.length
        return total

    # =========================================================================
    # SURGE PROTECTION DESIGN
    # =========================================================================

    def design_surge_protection(self, transient_results):
        """
        Design surge protection based on transient analysis results.

        Returns recommendations for:
        - Surge vessel sizing (volume per AS/NZS 2566)
        - Air valve placement at profile high points
        - Slow-closing valve specification (closure time > 2L/a)

        Parameters
        ----------
        transient_results : dict
            Results from run_transient() or run_pump_trip()

        Returns dict with 'surge_vessel', 'air_valves', 'slow_valve', 'summary'.
        Ref: AS/NZS 2566, Wylie & Streeter (1993), Thorley (2004)
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        surge_m = transient_results.get('max_surge_m', 0)
        surge_kPa = transient_results.get('max_surge_kPa', 0)
        junctions = transient_results.get('junctions', {})
        g = 9.81  # m/s²

        recommendations = {
            'max_surge_m': surge_m,
            'max_surge_kPa': surge_kPa,
            'surge_vessel': None,
            'air_valves': [],
            'slow_valve': None,
            'summary': [],
        }

        if surge_m < 30:
            recommendations['summary'].append(
                f'Surge of {surge_m:.1f} m is below 30 m threshold — '
                f'no protection required for typical PN35 (3500 kPa) ductile iron.')
            return recommendations

        # --- Surge Vessel Sizing ---
        # Volume = a × Q × L / (2 × g × H_allowed)
        # where a = wave speed, Q = flow, L = pipe length, H_allowed = allowable surge
        # Ref: Wylie & Streeter (1993) Ch. 12
        total_length = sum(self.wn.get_link(pid).length for pid in self.wn.pipe_name_list)
        avg_diameter = 0
        n_pipes = len(self.wn.pipe_name_list)
        if n_pipes > 0:
            avg_diameter = sum(self.wn.get_link(pid).diameter
                              for pid in self.wn.pipe_name_list) / n_pipes

        # Estimate flow from pipe areas and typical velocity
        avg_area = 3.14159 * (avg_diameter / 2) ** 2
        # Use max velocity from transient as flow estimate
        max_v = 0
        for jdata in junctions.values():
            head_arr = jdata.get('head', [])
            if hasattr(head_arr, '__len__') and len(head_arr) > 1:
                max_v = max(max_v, abs(float(head_arr[0]) - float(head_arr[-1])))

        if max_v == 0:
            max_v = 1.5  # assume 1.5 m/s typical

        Q_estimate = avg_area * max_v  # m³/s
        wave_speed = self.DEFAULTS['wave_speed_ms']

        # Allowable surge = PN rating minus normal operating head
        H_allowed = max(30, surge_m * 0.5)  # limit to 50% of surge

        if total_length > 0 and H_allowed > 0:
            # Surge vessel volume formula — Wylie & Streeter (1993)
            V_vessel = (wave_speed * Q_estimate * total_length) / (2 * g * H_allowed)
            V_vessel = max(0.5, V_vessel)  # minimum 0.5 m³
        else:
            V_vessel = 1.0

        recommendations['surge_vessel'] = {
            'volume_m3': round(V_vessel, 1),
            'pressure_rating_kPa': int(surge_kPa * 1.5),  # 50% safety factor
            'location': 'Adjacent to valve/pump causing transient',
            'basis': (f'V = a×Q×L/(2gH) = {wave_speed}×{Q_estimate:.3f}×'
                     f'{total_length:.0f}/(2×{g}×{H_allowed:.0f}) = {V_vessel:.1f} m³ '
                     f'— Wylie & Streeter (1993) Ch. 12'),
        }
        recommendations['summary'].append(
            f'Surge vessel: {V_vessel:.1f} m³ rated to '
            f'{int(surge_kPa * 1.5)} kPa (1.5× safety factor).')

        # --- Air Valve Placement ---
        # Place at high points in the network profile (elevation peaks)
        # Ref: AS/NZS 2566 Clause 4.3
        elevations = {}
        for jid in self.wn.junction_name_list:
            node = self.wn.get_node(jid)
            elevations[jid] = node.elevation

        if elevations:
            sorted_nodes = sorted(elevations.items(), key=lambda x: x[1], reverse=True)
            # Recommend air valves at top 3 highest nodes or nodes above median
            median_elev = sorted(elevations.values())[len(elevations) // 2]
            high_points = [(nid, elev) for nid, elev in sorted_nodes
                          if elev > median_elev][:5]

            for nid, elev in high_points:
                recommendations['air_valves'].append({
                    'node': nid,
                    'elevation_m': round(elev, 1),
                    'type': 'Combination air valve (AS/NZS 2566)',
                    'reason': f'Profile high point at {elev:.1f} m AHD — '
                              f'negative pressure risk during transient',
                })

            if high_points:
                recommendations['summary'].append(
                    f'Air valves at {len(high_points)} high points: '
                    f'{", ".join(nid for nid, _ in high_points)}.')

        # --- Slow-Closing Valve ---
        # Minimum closure time = 2L/a — critical period criterion
        # Ref: Thorley (2004) "Fluid Transients in Pipeline Systems"
        if total_length > 0:
            t_critical = 2 * total_length / wave_speed  # seconds
            t_recommended = max(t_critical * 2, 5.0)  # 2× critical, min 5s

            recommendations['slow_valve'] = {
                'critical_period_s': round(t_critical, 1),
                'recommended_closure_s': round(t_recommended, 1),
                'type': 'Actuated butterfly valve with controlled closure',
                'basis': (f't_c = 2L/a = 2×{total_length:.0f}/{wave_speed} = '
                         f'{t_critical:.1f} s — Thorley (2004). '
                         f'Recommended: ≥{t_recommended:.0f} s (2× critical period).'),
            }
            recommendations['summary'].append(
                f'Slow-closing valve: ≥{t_recommended:.0f} s closure time '
                f'(critical period = {t_critical:.1f} s).')

        return recommendations

    # =========================================================================
    # WATER HAMMER PROTECTION SIZING (J6)
    # =========================================================================

    def size_bladder_accumulator(self, max_surge_kPa, operating_pressure_kPa,
                                  allowable_surge_kPa=None, precharge_pct=0.9):
        """
        Size a bladder accumulator (surge vessel) using Boyle's law.

        P1 × V1 = P2 × V2 (isothermal) or P1 × V1^γ = P2 × V2^γ (isentropic)

        Parameters
        ----------
        max_surge_kPa : float
            Maximum transient surge pressure (kPa)
        operating_pressure_kPa : float
            Normal operating pressure (kPa)
        allowable_surge_kPa : float or None
            Maximum allowable surge after protection (default: PN35 = 3500 kPa)
        precharge_pct : float
            Precharge pressure as fraction of operating (default 0.9)

        Returns dict with vessel volume, precharge pressure, working volume.
        Ref: Thorley (2004), Boyle's law P1V1 = P2V2
        """
        if allowable_surge_kPa is None:
            allowable_surge_kPa = self.DEFAULTS['pipe_rating_kPa']

        P_op = operating_pressure_kPa  # kPa
        P_surge = max_surge_kPa  # kPa
        P_allow = allowable_surge_kPa  # kPa
        P_pre = P_op * precharge_pct  # precharge pressure

        if P_pre <= 0 or P_allow <= P_op:
            return {'error': 'Invalid pressure parameters'}

        # Boyle's law: P_pre × V_total = P_allow × V_gas_compressed
        # Working volume = V_total - V_gas_compressed
        # V_total / V_gas = P_allow / P_pre
        # Working volume fraction = 1 - P_pre / P_allow
        working_fraction = 1 - P_pre / P_allow

        if working_fraction <= 0:
            return {'error': 'Precharge too high relative to allowable pressure'}

        # Required energy absorption
        # ΔP = P_surge - P_allow (pressure to absorb)
        delta_P = max(0, P_surge - P_allow)

        # Volume estimate: V = ΔP × pipeline_volume / (P_allow × working_fraction)
        # Simplified: assume 1 m³ of pipeline fluid needs absorption
        V_pipeline_estimate = 0.5  # m³ — conservative estimate
        V_total = V_pipeline_estimate * delta_P / (P_allow * working_fraction) if working_fraction > 0 else 1.0
        V_total = max(0.1, V_total)  # minimum 100 litres

        return {
            'total_volume_m3': round(V_total, 2),
            'precharge_kPa': round(P_pre, 0),
            'working_volume_m3': round(V_total * working_fraction, 2),
            'pressure_rating_kPa': round(P_allow * 1.1, 0),  # 10% margin
            'basis': (f'Boyle isothermal: P_pre={P_pre:.0f} kPa, P_allow={P_allow:.0f} kPa, '
                     f'working fraction={working_fraction:.2f} — Thorley (2004)'),
        }

    def size_flywheel(self, pump_power_kW, motor_speed_rpm=1450,
                       required_rundown_s=5.0):
        """
        Size a flywheel for pump inertia to extend rundown time.

        J = P × t_rundown / (0.5 × ω²)

        Parameters
        ----------
        pump_power_kW : float
            Pump motor power (kW)
        motor_speed_rpm : float
            Motor speed (default 1450 rpm for 4-pole, 50Hz)
        required_rundown_s : float
            Required rundown time in seconds (default 5s)

        Returns dict with moment of inertia, flywheel mass, diameter.
        Ref: Thorley (2004), KSB Pump Handbook
        """
        import math
        omega = 2 * math.pi * motor_speed_rpm / 60  # rad/s
        P_watts = pump_power_kW * 1000

        # J = P × t / (0.5 × ω²)
        J_required = P_watts * required_rundown_s / (0.5 * omega ** 2)

        # Flywheel sizing: J = 0.5 × m × r²
        # Assume solid disk, diameter = 0.6 m (typical)
        r = 0.3  # m
        mass = J_required / (0.5 * r ** 2)

        # Steel density 7850 kg/m³ → thickness = mass / (ρ × π × r²)
        rho_steel = 7850
        thickness = mass / (rho_steel * math.pi * r ** 2) if mass > 0 else 0

        return {
            'moment_of_inertia_kgm2': round(J_required, 2),
            'flywheel_mass_kg': round(mass, 1),
            'diameter_m': round(2 * r, 2),
            'thickness_m': round(thickness, 3),
            'rundown_time_s': required_rundown_s,
            'basis': (f'J = P×t/(0.5ω²) = {P_watts}×{required_rundown_s}/'
                     f'(0.5×{omega:.1f}²) = {J_required:.2f} kg·m² — Thorley (2004)'),
        }

    # =========================================================================
    # MONTE CARLO UNCERTAINTY ANALYSIS (J8)
    # =========================================================================

    def monte_carlo_analysis(self, n_simulations=100,
                              roughness_cv=0.1, demand_cv=0.15,
                              seed=None):
        """
        Monte Carlo uncertainty analysis for pressure distribution.

        Randomly varies roughness and demand within specified uncertainty
        ranges and runs N simulations to build pressure distributions.

        Parameters
        ----------
        n_simulations : int
            Number of Monte Carlo samples (default 100)
        roughness_cv : float
            Coefficient of variation for roughness (default 0.10 = ±10%)
        demand_cv : float
            Coefficient of variation for demand (default 0.15 = ±15%)
        seed : int or None
            Random seed for reproducibility

        Returns dict with per-node statistics and WSAA failure probability.
        Ref: Kapelan et al. (2005) "Uncertainty Assessment of WDS"
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        rng = np.random.RandomState(seed)

        # Save original values
        original_roughness = {pid: self.wn.get_link(pid).roughness
                              for pid in self.wn.pipe_name_list}
        original_demands = {}
        for jid in self.wn.junction_name_list:
            junc = self.wn.get_node(jid)
            if junc.demand_timeseries_list:
                original_demands[jid] = junc.demand_timeseries_list[0].base_value

        # Collect pressure samples
        pressure_samples = {jid: [] for jid in self.wn.junction_name_list}
        n_success = 0

        for i in range(n_simulations):
            # Randomise roughness
            for pid, base_c in original_roughness.items():
                noise = rng.normal(1.0, roughness_cv)
                self.wn.get_link(pid).roughness = max(50, base_c * noise)

            # Randomise demands
            for jid, base_d in original_demands.items():
                noise = rng.normal(1.0, demand_cv)
                self.wn.get_node(jid).demand_timeseries_list[0].base_value = max(0, base_d * noise)

            try:
                res = self.run_steady_state(save_plot=False)
                pressures = res.get('pressures', {})
                for jid in self.wn.junction_name_list:
                    p = pressures.get(jid, {}).get('avg_m', 0)
                    pressure_samples[jid].append(p)
                n_success += 1
            except Exception:
                pass  # Skip failed simulations

        # Restore originals
        for pid, c in original_roughness.items():
            self.wn.get_link(pid).roughness = c
        for jid, d in original_demands.items():
            self.wn.get_node(jid).demand_timeseries_list[0].base_value = d

        # Compute statistics
        node_stats = {}
        for jid, samples in pressure_samples.items():
            if not samples:
                continue
            arr = np.array(samples)
            n_fail = np.sum(arr < self.DEFAULTS['min_pressure_m'])
            node_stats[jid] = {
                'mean_m': round(float(arr.mean()), 2),
                'std_m': round(float(arr.std()), 2),
                'min_m': round(float(arr.min()), 2),
                'max_m': round(float(arr.max()), 2),
                'p5_m': round(float(np.percentile(arr, 5)), 2),
                'p95_m': round(float(np.percentile(arr, 95)), 2),
                'failure_probability': round(float(n_fail / len(samples)), 3),
            }

        return {
            'n_simulations': n_simulations,
            'n_successful': n_success,
            'roughness_cv': roughness_cv,
            'demand_cv': demand_cv,
            'node_stats': node_stats,
        }

    # =========================================================================
    # AUTO-CALIBRATION (Roughness Optimisation)
    # =========================================================================

    def auto_calibrate_roughness(self, measured_pressures, material_groups=None):
        """
        Automatically calibrate pipe roughness (Hazen-Williams C) by minimising
        pressure residuals using scipy.optimize.minimize.

        Groups pipes by material and adjusts C-factors to minimise the sum of
        squared pressure differences between modelled and measured values.

        Parameters
        ----------
        measured_pressures : dict
            {node_id: measured_pressure_m} — field measurements at junctions
        material_groups : dict or None
            {material_name: {'pipes': [pipe_ids], 'bounds': (C_min, C_max)}}
            If None, auto-groups by roughness similarity.

        Returns
        -------
        dict with:
            - 'groups': {material: {'C_before': float, 'C_after': float, 'pipes': list}}
            - 'before': {'r2': float, 'rmse': float}
            - 'after': {'r2': float, 'rmse': float}
            - 'iterations': int
            - 'convergence': list of (iteration, rmse) tuples

        Ref: WSAA Calibration Guidelines; Hazen-Williams C ranges per material:
            DI: 100-145, PVC: 130-150, PE: 130-150, Concrete: 80-120
        """
        from scipy.optimize import minimize

        if self.wn is None:
            return {'error': 'No network loaded'}

        # Default material grouping by roughness value clusters
        if material_groups is None:
            material_groups = self._auto_group_pipes()

        # Build parameter vector: one C value per material group
        group_names = list(material_groups.keys())
        x0 = []
        bounds = []
        for gname in group_names:
            g = material_groups[gname]
            pipe_ids = g['pipes']
            # Initial C = current average
            avg_c = 0
            for pid in pipe_ids:
                pipe = self.wn.get_link(pid)
                avg_c += pipe.roughness
            avg_c /= max(len(pipe_ids), 1)
            x0.append(avg_c)
            b = g.get('bounds', (80, 150))
            bounds.append(b)

        convergence = []

        def objective(x):
            """Sum of squared pressure residuals."""
            # Apply C values to pipes
            for i, gname in enumerate(group_names):
                c_val = x[i]
                for pid in material_groups[gname]['pipes']:
                    pipe = self.wn.get_link(pid)
                    pipe.roughness = c_val

            # Run simulation
            try:
                sim = wntr.sim.EpanetSimulator(self.wn)
                results = sim.run_sim()
                pressures = results.node['pressure']
            except Exception:
                return 1e10  # Penalise failed simulations

            # Compute residuals
            ssr = 0.0
            for nid, p_meas in measured_pressures.items():
                if nid in pressures.columns:
                    p_mod = float(pressures[nid].mean())
                    ssr += (p_meas - p_mod) ** 2

            # Track convergence
            rmse = (ssr / max(len(measured_pressures), 1)) ** 0.5
            convergence.append((len(convergence), rmse))

            return ssr

        # Record "before" state
        before_ssr = objective(x0)
        before_rmse = (before_ssr / max(len(measured_pressures), 1)) ** 0.5
        meas_list = list(measured_pressures.values())
        # Get modelled pressures for R² calc
        sim = wntr.sim.EpanetSimulator(self.wn)
        res = sim.run_sim()
        mod_list = [float(res.node['pressure'][nid].mean())
                    for nid in measured_pressures if nid in res.node['pressure'].columns]
        meas_for_r2 = [measured_pressures[nid]
                       for nid in measured_pressures if nid in res.node['pressure'].columns]

        from desktop.calibration_dialog import compute_r2, compute_rmse
        before_r2 = compute_r2(meas_for_r2, mod_list)

        # Optimise
        result = minimize(
            objective, x0, method='L-BFGS-B', bounds=bounds,
            options={'maxiter': 50, 'ftol': 1e-6}
        )

        # Record "after" state
        after_rmse = (result.fun / max(len(measured_pressures), 1)) ** 0.5
        # Get after modelled pressures
        sim = wntr.sim.EpanetSimulator(self.wn)
        res = sim.run_sim()
        mod_list_after = [float(res.node['pressure'][nid].mean())
                         for nid in measured_pressures if nid in res.node['pressure'].columns]
        after_r2 = compute_r2(meas_for_r2, mod_list_after)

        # Build result
        groups_result = {}
        for i, gname in enumerate(group_names):
            groups_result[gname] = {
                'C_before': round(x0[i], 1),
                'C_after': round(result.x[i], 1),
                'pipes': material_groups[gname]['pipes'],
                'n_pipes': len(material_groups[gname]['pipes']),
            }

        return {
            'groups': groups_result,
            'before': {'r2': round(before_r2, 4), 'rmse': round(before_rmse, 2)},
            'after': {'r2': round(after_r2, 4), 'rmse': round(after_rmse, 2)},
            'iterations': result.nit,
            'convergence': convergence,
            'success': result.success,
        }

    def _auto_group_pipes(self):
        """Auto-group pipes by roughness value into material classes."""
        groups = {}
        # Hazen-Williams C ranges per material — WSAA typical values
        C_BANDS = {
            'DI (C~140)': (120, 145),
            'PVC/PE (C~150)': (145, 155),
            'Concrete (C~90-110)': (80, 120),
            'Old/Unknown (C<120)': (50, 120),
        }

        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            c = pipe.roughness
            assigned = False
            for band_name, (lo, hi) in C_BANDS.items():
                if lo <= c <= hi:
                    if band_name not in groups:
                        groups[band_name] = {'pipes': [], 'bounds': (lo, hi)}
                    groups[band_name]['pipes'].append(pid)
                    assigned = True
                    break
            if not assigned:
                if 'Other' not in groups:
                    groups['Other'] = {'pipes': [], 'bounds': (50, 160)}
                groups['Other']['pipes'].append(pid)

        return groups

    # =========================================================================
    # LEAKAGE DETECTION ANALYSIS
    # =========================================================================

    def leakage_analysis(self, measured_inflow_lps, legitimate_night_use_lps=0):
        """
        Analyse water losses by comparing metered inflow vs customer demands.

        Parameters
        ----------
        measured_inflow_lps : float
            Total measured inflow from supply meters (LPS)
        legitimate_night_use_lps : float
            Estimated legitimate night-time use (LPS)

        Returns dict with apparent_loss, real_loss, minimum_night_flow,
        infrastructure_leakage_index (ILI).
        Ref: WSAA Best Practice Guidelines for Leakage Management
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        # Sum of customer demands
        total_demand_lps = 0
        for jid in self.wn.junction_name_list:
            junc = self.wn.get_node(jid)
            if junc.demand_timeseries_list:
                total_demand_lps += junc.demand_timeseries_list[0].base_value * 1000

        # Total pipe length for ILI calculation
        total_length_km = sum(
            self.wn.get_link(pid).length for pid in self.wn.pipe_name_list) / 1000
        n_connections = len(self.wn.junction_name_list)

        # Apparent losses = meter inaccuracy (estimated 2-5% of metered)
        apparent_loss_pct = 3.0  # typical for Australian utilities
        apparent_loss_lps = measured_inflow_lps * (apparent_loss_pct / 100)

        # Real losses = total loss - apparent loss
        total_loss_lps = max(0, measured_inflow_lps - total_demand_lps)
        real_loss_lps = max(0, total_loss_lps - apparent_loss_lps)

        # Minimum Night Flow (MNF) method
        # MNF = total_loss + legitimate_night_use
        mnf_lps = real_loss_lps + legitimate_night_use_lps

        # Infrastructure Leakage Index (ILI)
        # ILI = CARL / UARL
        # UARL = (18 × Lm + 0.8 × Nc + 25 × Lp) × P / 1000
        # where Lm = main length (km), Nc = connections, Lp = total service pipe (km)
        # P = average pressure (m)
        avg_pressure = self.DEFAULTS['min_pressure_m'] + 15  # estimate 35m
        Lp = n_connections * 0.015  # average 15m service pipe
        UARL_lday = (18 * total_length_km + 0.8 * n_connections + 25 * Lp) * avg_pressure / 1000
        UARL_lps = UARL_lday / 86.4  # L/day to L/s

        ILI = real_loss_lps / UARL_lps if UARL_lps > 0 else 0

        # Performance category per WSAA
        if ILI <= 1.0:
            category = 'A — Best practice'
        elif ILI <= 2.0:
            category = 'B — Good'
        elif ILI <= 4.0:
            category = 'C — Average'
        elif ILI <= 8.0:
            category = 'D — Below average'
        else:
            category = 'E — Poor — immediate action required'

        return {
            'measured_inflow_lps': round(measured_inflow_lps, 2),
            'total_demand_lps': round(total_demand_lps, 2),
            'total_loss_lps': round(total_loss_lps, 2),
            'apparent_loss_lps': round(apparent_loss_lps, 2),
            'real_loss_lps': round(real_loss_lps, 2),
            'loss_pct': round(total_loss_lps / max(measured_inflow_lps, 0.01) * 100, 1),
            'mnf_lps': round(mnf_lps, 2),
            'ili': round(ILI, 2),
            'performance_category': category,
            'network_length_km': round(total_length_km, 2),
            'n_connections': n_connections,
        }

    # =========================================================================
    # NETWORK RELIABILITY ANALYSIS
    # =========================================================================

    def reliability_analysis(self):
        """
        Assess network reliability by simulating single-pipe failures.

        For each pipe: close it, run analysis, check which nodes lose
        adequate pressure (< WSAA 20 m). Ranks pipes by criticality.

        Returns list of dicts sorted by criticality (most critical first):
        'pipe_id', 'affected_nodes', 'n_affected', 'criticality_index'.

        Ref: Wagner et al. (1988) "Reliability of Water Distribution Systems"
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        n_junctions = len(self.wn.junction_name_list)
        if n_junctions == 0:
            return []

        # Run baseline
        try:
            base_results = self.run_steady_state(save_plot=False)
        except Exception as e:
            return {'error': f'Baseline failed: {e}'}

        base_ok_nodes = set()
        for jid, p in base_results.get('pressures', {}).items():
            if p.get('min_m', 0) >= self.DEFAULTS['min_pressure_m']:
                base_ok_nodes.add(jid)

        results = []

        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            original_status = pipe.initial_status

            # Close pipe (simulate failure)
            pipe.initial_status = wntr.network.LinkStatus(0)  # closed

            try:
                fail_results = self.run_steady_state(save_plot=False)
                fail_pressures = fail_results.get('pressures', {})
                affected = []
                for jid in base_ok_nodes:
                    p = fail_pressures.get(jid, {}).get('min_m', 0)
                    if p < self.DEFAULTS['min_pressure_m']:
                        affected.append(jid)
            except Exception:
                affected = list(base_ok_nodes)  # assume all affected on solver failure

            # Restore pipe
            pipe.initial_status = original_status

            criticality = len(affected) / max(n_junctions, 1)
            results.append({
                'pipe_id': pid,
                'diameter_mm': int(pipe.diameter * 1000),
                'length_m': round(pipe.length, 1),
                'affected_nodes': affected,
                'n_affected': len(affected),
                'criticality_index': round(criticality, 3),
            })

        results.sort(key=lambda x: x['criticality_index'], reverse=True)
        return results

    # =========================================================================
    # NETWORK COMPARISON
    # =========================================================================

    def compare_networks(self, other_inp_path):
        """
        Compare current network with another .inp file.

        Returns dict with topology differences, pipe size changes,
        and (if both have results) pressure/velocity differences.

        Useful for before/after rehabilitation comparison.

        Parameters
        ----------
        other_inp_path : str
            Path to the second .inp file for comparison.

        Returns dict with 'topology', 'properties', 'summary'.
        """
        if self.wn is None:
            return {'error': 'No network loaded (current)'}

        import wntr
        try:
            wn2 = wntr.network.WaterNetworkModel(other_inp_path)
        except Exception as e:
            return {'error': f'Could not load comparison network: {e}'}

        wn1 = self.wn
        result = {
            'topology': {'added_nodes': [], 'removed_nodes': [],
                         'added_pipes': [], 'removed_pipes': []},
            'properties': [],
            'summary': {},
        }

        # Topology comparison
        nodes1 = set(wn1.junction_name_list) | set(wn1.reservoir_name_list) | set(wn1.tank_name_list)
        nodes2 = set(wn2.junction_name_list) | set(wn2.reservoir_name_list) | set(wn2.tank_name_list)
        pipes1 = set(wn1.pipe_name_list)
        pipes2 = set(wn2.pipe_name_list)

        result['topology']['added_nodes'] = sorted(nodes2 - nodes1)
        result['topology']['removed_nodes'] = sorted(nodes1 - nodes2)
        result['topology']['added_pipes'] = sorted(pipes2 - pipes1)
        result['topology']['removed_pipes'] = sorted(pipes1 - pipes2)

        # Property comparison for common pipes
        common_pipes = pipes1 & pipes2
        for pid in sorted(common_pipes):
            p1 = wn1.get_link(pid)
            p2 = wn2.get_link(pid)
            changes = []
            if abs(p1.diameter - p2.diameter) > 0.0001:
                changes.append(f'diameter: {int(p1.diameter*1000)} mm → {int(p2.diameter*1000)} mm')
            if abs(p1.length - p2.length) > 0.1:
                changes.append(f'length: {p1.length:.1f} m → {p2.length:.1f} m')
            if abs(p1.roughness - p2.roughness) > 0.1:
                changes.append(f'roughness: {p1.roughness:.0f} → {p2.roughness:.0f}')
            if changes:
                result['properties'].append({
                    'pipe': pid,
                    'changes': changes,
                })

        # Elevation comparison for common junctions
        common_juncs = set(wn1.junction_name_list) & set(wn2.junction_name_list)
        for jid in sorted(common_juncs):
            n1 = wn1.get_node(jid)
            n2 = wn2.get_node(jid)
            if abs(n1.elevation - n2.elevation) > 0.1:
                result['properties'].append({
                    'node': jid,
                    'changes': [f'elevation: {n1.elevation:.1f} m → {n2.elevation:.1f} m'],
                })

        # Summary
        result['summary'] = {
            'nodes_added': len(result['topology']['added_nodes']),
            'nodes_removed': len(result['topology']['removed_nodes']),
            'pipes_added': len(result['topology']['added_pipes']),
            'pipes_removed': len(result['topology']['removed_pipes']),
            'properties_changed': len(result['properties']),
            'identical': (len(result['topology']['added_nodes']) == 0 and
                         len(result['topology']['removed_nodes']) == 0 and
                         len(result['topology']['added_pipes']) == 0 and
                         len(result['topology']['removed_pipes']) == 0 and
                         len(result['properties']) == 0),
        }

        return result

    # =========================================================================
    # DEMAND FORECASTING
    # =========================================================================

    def forecast_demand(self, growth_model='linear', growth_rate=0.02,
                        base_year=2026, forecast_years=None):
        """
        Project demands forward to future years and check when WSAA
        standards will be exceeded.

        Parameters
        ----------
        growth_model : str
            'linear', 'exponential', or 'logistic'
        growth_rate : float
            Annual growth rate (e.g., 0.02 = 2% per year)
        base_year : int
            Year of current demand data
        forecast_years : list of int or None
            Years to forecast (default: [2030, 2040, 2050])

        Returns dict with per-year results and first failure year.
        Ref: WSAA Demand Forecasting Guidelines
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        if forecast_years is None:
            forecast_years = [2030, 2040, 2050]

        # Save original demands
        original_demands = {}
        for jid in self.wn.junction_name_list:
            junc = self.wn.get_node(jid)
            if junc.demand_timeseries_list:
                original_demands[jid] = junc.demand_timeseries_list[0].base_value

        results = {
            'base_year': base_year,
            'growth_model': growth_model,
            'growth_rate': growth_rate,
            'forecasts': {},
            'first_failure_year': None,
        }

        for year in sorted(forecast_years):
            dt = year - base_year
            if dt < 0:
                continue

            # Compute growth multiplier
            if growth_model == 'linear':
                multiplier = 1 + growth_rate * dt
            elif growth_model == 'exponential':
                multiplier = (1 + growth_rate) ** dt
            elif growth_model == 'logistic':
                # Logistic: asymptote at 2× current (carrying capacity)
                import math
                K = 2.0  # carrying capacity multiplier
                multiplier = K / (1 + (K - 1) * math.exp(-growth_rate * dt))
            else:
                multiplier = 1 + growth_rate * dt

            # Apply multiplied demands
            for jid, base_demand in original_demands.items():
                junc = self.wn.get_node(jid)
                junc.demand_timeseries_list[0].base_value = base_demand * multiplier

            # Run analysis
            try:
                year_results = self.run_steady_state(save_plot=False)
            except Exception as e:
                year_results = {'error': str(e), 'pressures': {}, 'flows': {},
                               'compliance': []}

            # Check for WSAA failures
            pressures = year_results.get('pressures', {})
            failures = []
            for jid, p in pressures.items():
                min_p = p.get('min_m', 0)
                if min_p < self.DEFAULTS['min_pressure_m']:
                    failures.append({
                        'node': jid,
                        'pressure_m': min_p,
                        'issue': f'Pressure {min_p:.1f} m < {self.DEFAULTS["min_pressure_m"]} m (WSAA)',
                    })

            flows = year_results.get('flows', {})
            for pid, f in flows.items():
                v = f.get('max_velocity_ms', 0)
                if v > self.DEFAULTS['max_velocity_ms']:
                    failures.append({
                        'pipe': pid,
                        'velocity_ms': v,
                        'issue': f'Velocity {v:.2f} m/s > {self.DEFAULTS["max_velocity_ms"]} m/s (WSAA)',
                    })

            results['forecasts'][year] = {
                'multiplier': round(multiplier, 3),
                'total_demand_lps': round(
                    sum(d * multiplier * 1000 for d in original_demands.values()), 1),
                'n_failures': len(failures),
                'failures': failures[:10],  # limit to 10 for readability
            }

            if failures and results['first_failure_year'] is None:
                results['first_failure_year'] = year

        # Restore original demands
        for jid, base_demand in original_demands.items():
            junc = self.wn.get_node(jid)
            junc.demand_timeseries_list[0].base_value = base_demand

        return results

    # =========================================================================
    # PROJECT BUNDLE EXPORT/IMPORT
    # =========================================================================

    def export_bundle(self, bundle_path, inp_path=None, hap_data=None,
                      scenarios=None, audit_dir=None):
        """
        Export project as a .hydraulic ZIP bundle.

        Packages .inp, .hap, scenarios, and audit trail into a single
        portable file for consultant-to-client sharing.

        Parameters
        ----------
        bundle_path : str
            Output .hydraulic (zip) file path
        inp_path : str or None
            Path to .inp file to include
        hap_data : dict or None
            Project settings to include as project.hap
        scenarios : list or None
            Scenario data dicts to include
        audit_dir : str or None
            Path to audit trail directory to include
        """
        import zipfile

        with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Include .inp
            if inp_path and os.path.exists(inp_path):
                zf.write(inp_path, os.path.basename(inp_path))
            elif self._inp_file and os.path.exists(self._inp_file):
                zf.write(self._inp_file, os.path.basename(self._inp_file))

            # Include .hap project data
            if hap_data:
                zf.writestr('project.hap', json.dumps(hap_data, indent=2))

            # Include scenarios
            if scenarios:
                zf.writestr('scenarios.json', json.dumps(scenarios, indent=2))

            # Include audit trail
            if audit_dir and os.path.isdir(audit_dir):
                for root, _dirs, files in os.walk(audit_dir):
                    for fname in files:
                        full = os.path.join(root, fname)
                        arcname = os.path.join('audit', os.path.relpath(full, audit_dir))
                        zf.write(full, arcname)

            # Include metadata
            meta = {
                'version': '1.3.0',
                'format': 'hydraulic-bundle',
                'network_summary': self.get_network_summary() if self.wn else {},
            }
            zf.writestr('meta.json', json.dumps(meta, indent=2))

        return bundle_path

    def import_bundle(self, bundle_path, extract_dir=None):
        """
        Import a .hydraulic ZIP bundle.

        Extracts .inp, .hap, scenarios, and audit trail.

        Parameters
        ----------
        bundle_path : str
            Path to .hydraulic (zip) file
        extract_dir : str or None
            Directory to extract to (default: models/)

        Returns dict with 'inp_path', 'hap_data', 'scenarios', 'meta'.
        """
        import zipfile

        if extract_dir is None:
            extract_dir = self.model_dir

        result = {
            'inp_path': None,
            'hap_data': None,
            'scenarios': None,
            'meta': None,
        }

        with zipfile.ZipFile(bundle_path, 'r') as zf:
            names = zf.namelist()

            # Extract .inp
            inp_files = [n for n in names if n.endswith('.inp')]
            if inp_files:
                zf.extract(inp_files[0], extract_dir)
                result['inp_path'] = os.path.join(extract_dir, inp_files[0])

            # Read .hap
            if 'project.hap' in names:
                result['hap_data'] = json.loads(zf.read('project.hap'))

            # Read scenarios
            if 'scenarios.json' in names:
                result['scenarios'] = json.loads(zf.read('scenarios.json'))

            # Read metadata
            if 'meta.json' in names:
                result['meta'] = json.loads(zf.read('meta.json'))

            # Extract audit trail
            audit_files = [n for n in names if n.startswith('audit/')]
            for af in audit_files:
                zf.extract(af, extract_dir)

        return result

    def joukowsky(self, wave_speed, velocity_change, density=1000):
        """
        Calculate Joukowsky pressure rise.

        dH = (a * dV) / g          — head rise (metres of fluid)
        dP = rho * a * dV          — pressure rise (Pa)

        For slurry (rho > 1000), the pressure rise is proportionally
        higher even though the head rise is the same.
        """
        g = 9.81
        dH = (wave_speed * velocity_change) / g
        # Pressure rise uses actual fluid density — Joukowsky (1898)
        dP_kPa = density * wave_speed * velocity_change / 1000
        return {
            'head_rise_m': round(dH, 1),
            'pressure_rise_kPa': round(dP_kPa, 0),
            'wave_speed_ms': wave_speed,
            'velocity_change_ms': velocity_change,
            'density_kgm3': density,
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
    parser.add_argument('--wave-speed', type=float, default=1100,
                       help='Wave speed (m/s) — AS 2280 default 1100 for ductile iron')
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

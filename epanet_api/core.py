"""
Core network creation and mutation mixin for HydraulicAPI.

Provides methods for loading, creating, querying, and mutating
EPANET network models via WNTR.
"""

import os
import wntr


class CoreMixin:
    """Network creation, loading, mutation, and query methods."""

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
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

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

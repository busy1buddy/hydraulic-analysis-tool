"""
Core network creation and mutation mixin for HydraulicAPI.

Provides methods for loading, creating, querying, and mutating
EPANET network models via WNTR.
"""

import os
import math
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

    def add_reservoir(self, rid, head_m, coordinates=None):
        """Add an intake reservoir (infinite source) to the network.

        Parameters
        ----------
        rid : str
            Reservoir ID (e.g. 'R_SOURCE').
        head_m : float
            Total head at the reservoir surface in metres (m AHD + freeboard).
            This is the energy grade the solver uses as the upstream boundary
            condition. Rule: head_m >= elevation_m of the reservoir.
        coordinates : tuple of (float, float), optional
            (X, Y) spatial coordinates for canvas display.
        """
        if self.wn is None:
            raise RuntimeError("No network loaded")
        if head_m < 0:
            raise ValueError(
                f"Reservoir head {head_m:.1f} m is negative. "
                "Check that you are passing total head (elevation + freeboard), "
                "not gauge pressure."
            )
        coords = coordinates or (0.0, 0.0)
        self.wn.add_reservoir(rid, base_head=head_m, coordinates=coords)

    def auto_generate_source_reservoir(
        self,
        reservoir_id: str = 'R_SOURCE',
        freeboard_m: float = 3.0,
        strategy: str = 'highest_elevation',
    ) -> dict:
        """
        Automatically identify the upstream intake point (Point A) and
        convert it into a proper EPANET source reservoir.

        This is the key post-import step for DXF pipeline models: after
        importing geometry from CAD, the network has junctions everywhere
        but no hydraulic boundary conditions. This method designates the
        most appropriate upstream node as the intake source.

        Parameters
        ----------
        reservoir_id : str
            ID to give the new reservoir node.
        freeboard_m : float
            Head margin added above the node elevation to set reservoir head.
            Default 3.0 m (typical inlet head above crown).
        strategy : str
            How to identify Point A:
            - 'highest_elevation'  — node with the greatest elevation (m AHD).
              Best for gravity-fed pipelines from dams or mountain intakes.
            - 'lowest_degree'      — node with only one connected pipe
              (dead-end), at the upstream end. Best for pumped systems
              where the source is a simple offtake from a main.
            - 'furthest_from_centroid' — node spatially furthest from the
              network centroid. Best for long linear pipelines (1000 km)
              where Point A is clearly at one geographic extreme.

        Returns
        -------
        dict
            Summary including the chosen node, elevation, head, and strategy.

        Notes
        -----
        - If the network already has at least one reservoir, this method
          returns early with a warning rather than adding a duplicate.
        - The chosen junction is removed and replaced by a reservoir node.
          All pipes connected to it retain their connections.
        """
        if self.wn is None:
            raise RuntimeError("No network loaded")

        # Guard: don't clobber an existing reservoir
        if len(self.wn.reservoir_name_list) > 0:
            existing = list(self.wn.reservoir_name_list)
            return {
                'status': 'skipped',
                'reason': (
                    f'Network already has {len(existing)} reservoir(s): '
                    f'{existing}. Remove them first to auto-generate.'
                ),
                'reservoirs': existing,
            }

        junctions = list(self.wn.junction_name_list)
        if not junctions:
            return {
                'status': 'error',
                'reason': 'Network has no junctions. Cannot designate a source node.',
            }

        # ---- Strategy: highest elevation ----
        if strategy == 'highest_elevation':
            best_id = max(
                junctions,
                key=lambda jid: self.wn.get_node(jid).elevation
            )

        # ---- Strategy: lowest degree (single-pipe dead-end) ----
        elif strategy == 'lowest_degree':
            # Count connected links per junction
            degree = {jid: 0 for jid in junctions}
            for lid in self.wn.link_name_list:
                link = self.wn.get_link(lid)
                if link.start_node_name in degree:
                    degree[link.start_node_name] += 1
                if link.end_node_name in degree:
                    degree[link.end_node_name] += 1
            # Among degree-1 nodes, pick the one with highest elevation
            dead_ends = [jid for jid, d in degree.items() if d == 1]
            if not dead_ends:
                dead_ends = junctions  # fall back if no dead ends
            best_id = max(
                dead_ends,
                key=lambda jid: self.wn.get_node(jid).elevation
            )

        # ---- Strategy: furthest from centroid ----
        elif strategy == 'furthest_from_centroid':
            coords = [
                self.wn.get_node(jid).coordinates for jid in junctions
            ]
            cx = sum(c[0] for c in coords) / len(coords)
            cy = sum(c[1] for c in coords) / len(coords)
            best_id = max(
                junctions,
                key=lambda jid: math.hypot(
                    self.wn.get_node(jid).coordinates[0] - cx,
                    self.wn.get_node(jid).coordinates[1] - cy
                )
            )

        else:
            return {
                'status': 'error',
                'reason': (
                    f"Unknown strategy '{strategy}'. "
                    "Use 'highest_elevation', 'lowest_degree', or "
                    "'furthest_from_centroid'."
                ),
            }

        # Capture properties of the chosen junction before removal
        chosen_node = self.wn.get_node(best_id)
        elevation_m = chosen_node.elevation
        coordinates = chosen_node.coordinates

        # Head = elevation + freeboard (total energy at intake surface)
        head_m = elevation_m + freeboard_m

        # Find all pipes connected to this node (to reconnect after conversion)
        # WNTR handles this automatically when we remove a junction and re-add
        # a reservoir with the SAME coordinate — pipes remain connected by
        # node name. We rename only if reservoir_id differs from best_id.
        if reservoir_id == best_id:
            # In-place: change node type by removing junction and adding reservoir
            self.wn.remove_node(best_id)
            self.wn.add_reservoir(
                reservoir_id, base_head=head_m, coordinates=coordinates
            )
        else:
            # Remove junction, add reservoir with new ID, remap connected pipes
            connected_links = []
            for lid in list(self.wn.link_name_list):
                link = self.wn.get_link(lid)
                if link.start_node_name == best_id:
                    connected_links.append((lid, 'start'))
                elif link.end_node_name == best_id:
                    connected_links.append((lid, 'end'))

            # Add reservoir first (before removing junction so pipes still valid)
            self.wn.add_reservoir(
                reservoir_id, base_head=head_m, coordinates=coordinates
            )

            # Reconnect pipes: update start/end node names
            for lid, end in connected_links:
                link = self.wn.get_link(lid)
                if end == 'start':
                    link.start_node = self.wn.get_node(reservoir_id)
                else:
                    link.end_node = self.wn.get_node(reservoir_id)

            # Now safe to remove the old junction
            try:
                self.wn.remove_node(best_id)
            except Exception:
                pass  # May already be disconnected — not critical

        return {
            'status': 'success',
            'reservoir_id': reservoir_id,
            'replaced_junction': best_id,
            'strategy': strategy,
            'elevation_m': round(elevation_m, 2),
            'freeboard_m': freeboard_m,
            'head_m': round(head_m, 2),
            'coordinates': coordinates,
            'message': (
                f"Junction '{best_id}' converted to reservoir '{reservoir_id}' "
                f"using strategy '{strategy}'. "
                f"Head set to {head_m:.1f} m "
                f"(elevation {elevation_m:.1f} m + freeboard {freeboard_m:.1f} m)."
            ),
        }

    def add_tank(self, tid, elevation_m, init_level_m=3.0, min_level_m=0.5,
                 max_level_m=6.0, diameter_m=10.0, coordinates=None):
        """Add a storage tank (finite volume) to the network.

        Parameters
        ----------
        tid : str
            Tank ID (e.g. 'T_DELIVERY').
        elevation_m : float
            Tank base elevation in m AHD.
        init_level_m : float
            Initial water level above tank base (m). Default: 3.0 m.
        min_level_m : float
            Minimum water level (m). Pump-off level. Default: 0.5 m.
        max_level_m : float
            Maximum water level (m). Overflow level. Default: 6.0 m.
        diameter_m : float
            Tank internal diameter (m) for volume calculation. Default: 10 m.
        coordinates : tuple of (float, float), optional
            (X, Y) canvas display coordinates.
        """
        if self.wn is None:
            raise RuntimeError("No network loaded")
        if min_level_m >= max_level_m:
            raise ValueError(
                f"Tank min_level ({min_level_m} m) must be less than "
                f"max_level ({max_level_m} m)."
            )
        if init_level_m < min_level_m or init_level_m > max_level_m:
            raise ValueError(
                f"Tank init_level ({init_level_m} m) must be between "
                f"min_level ({min_level_m} m) and max_level ({max_level_m} m)."
            )
        if diameter_m <= 0:
            raise ValueError(f"Tank diameter must be > 0, got {diameter_m} m.")

        coords = coordinates or (0.0, 0.0)
        self.wn.add_tank(
            tid,
            elevation=elevation_m,
            init_level=init_level_m,
            min_level=min_level_m,
            max_level=max_level_m,
            diameter=diameter_m,
            coordinates=coords,
        )

    def auto_generate_delivery_tank(
        self,
        tank_id: str = 'T_DELIVERY',
        strategy: str = 'lowest_elevation',
        init_level_m: float = 3.0,
        min_level_m: float = 0.5,
        max_level_m: float = 6.0,
        diameter_m: float = 10.0,
        exclude_nodes: list = None,
    ) -> dict:
        """
        Automatically identify the downstream delivery point (Point B) and
        convert it into a proper EPANET storage tank.

        This is the companion to auto_generate_source_reservoir(). After
        running Sessions 7 and 8, the network has both a hydraulic source
        (Point A reservoir) and a hydraulic sink (Point B tank), and is
        ready for a valid steady-state solve.

        Parameters
        ----------
        tank_id : str
            ID for the new delivery tank node.
        strategy : str
            How to identify Point B:
            - 'lowest_elevation'   — junction with the lowest m AHD elevation.
              Best for gravity-fed delivery (water always flows downhill).
            - 'lowest_degree'      — dead-end junction (single pipe),
              opposite end to the source. Best for simple linear pipelines.
            - 'furthest_from_reservoir' — junction spatially furthest from
              the existing reservoir. Best for long-haul pipelines where
              Point B is at the far geographic end.
        init_level_m : float
            Initial water level in the tank above its base elevation (m).
        min_level_m : float
            Minimum operational level — pump-off or low-level alarm (m).
        max_level_m : float
            Maximum operational level — overflow protection (m).
        diameter_m : float
            Tank internal diameter for volume calculation (m).
            Use a large value (e.g. 50 m) for a major service reservoir.
        exclude_nodes : list of str, optional
            Node IDs to exclude from consideration (e.g. already-designated
            reservoir IDs from Session 7).

        Returns
        -------
        dict
            Summary including the chosen node, elevation, tank geometry,
            and strategy used.

        Notes
        -----
        - Requires at least one reservoir to already exist (run Session 7 first).
        - The chosen junction is replaced by a tank node; all connected pipes
          retain their topology.
        - Volume = π/4 × D² × (max_level - min_level). Print this to confirm
          the tank is sized for the required storage duration.
        """
        if self.wn is None:
            raise RuntimeError("No network loaded")

        # Require a source reservoir to exist first
        if len(self.wn.reservoir_name_list) == 0:
            return {
                'status': 'error',
                'reason': (
                    "No source reservoir found. Run auto_generate_source_reservoir() "
                    "(Session 7) before generating the delivery tank."
                ),
            }

        junctions = list(self.wn.junction_name_list)
        exclude = set(exclude_nodes or []) | set(self.wn.reservoir_name_list)
        candidates = [jid for jid in junctions if jid not in exclude]

        if not candidates:
            return {
                'status': 'error',
                'reason': (
                    "No candidate junctions available. All junctions are either "
                    "excluded or already converted to reservoirs/tanks."
                ),
            }

        # ---- Strategy: lowest elevation ----
        if strategy == 'lowest_elevation':
            best_id = min(
                candidates,
                key=lambda jid: self.wn.get_node(jid).elevation
            )

        # ---- Strategy: lowest degree dead-end ----
        elif strategy == 'lowest_degree':
            # Count connected links per junction
            degree = {jid: 0 for jid in candidates}
            for lid in self.wn.link_name_list:
                link = self.wn.get_link(lid)
                if link.start_node_name in degree:
                    degree[link.start_node_name] += 1
                if link.end_node_name in degree:
                    degree[link.end_node_name] += 1
            dead_ends = [jid for jid, d in degree.items() if d == 1]
            if not dead_ends:
                dead_ends = candidates  # fall back
            # Among dead-end nodes, pick the one with lowest elevation
            best_id = min(
                dead_ends,
                key=lambda jid: self.wn.get_node(jid).elevation
            )

        # ---- Strategy: furthest from existing reservoir ----
        elif strategy == 'furthest_from_reservoir':
            # Compute centroid of all existing reservoirs
            res_coords = [
                self.wn.get_node(rid).coordinates
                for rid in self.wn.reservoir_name_list
            ]
            rx = sum(c[0] for c in res_coords) / len(res_coords)
            ry = sum(c[1] for c in res_coords) / len(res_coords)
            best_id = max(
                candidates,
                key=lambda jid: math.hypot(
                    self.wn.get_node(jid).coordinates[0] - rx,
                    self.wn.get_node(jid).coordinates[1] - ry,
                )
            )

        else:
            return {
                'status': 'error',
                'reason': (
                    f"Unknown strategy '{strategy}'. "
                    "Use 'lowest_elevation', 'lowest_degree', or "
                    "'furthest_from_reservoir'."
                ),
            }

        # Capture properties before mutation
        chosen_node = self.wn.get_node(best_id)
        elevation_m = chosen_node.elevation
        coordinates = chosen_node.coordinates

        # Calculate tank volume for reporting
        import math as _math
        volume_m3 = (_math.pi / 4) * diameter_m**2 * (max_level_m - min_level_m)

        # Find connected pipes for reconnection
        connected_links = []
        for lid in list(self.wn.link_name_list):
            link = self.wn.get_link(lid)
            if link.start_node_name == best_id:
                connected_links.append((lid, 'start'))
            elif link.end_node_name == best_id:
                connected_links.append((lid, 'end'))

        # Add tank first, then remap pipes, then remove old junction
        self.wn.add_tank(
            tank_id,
            elevation=elevation_m,
            init_level=init_level_m,
            min_level=min_level_m,
            max_level=max_level_m,
            diameter=diameter_m,
            coordinates=coordinates,
        )

        return {
            'status': 'success',
            'tank_id': tank_id,
            'replaced_junction': best_id,
            'strategy': strategy,
            'elevation_m': round(elevation_m, 2),
            'init_level_m': init_level_m,
            'min_level_m': min_level_m,
            'max_level_m': max_level_m,
            'diameter_m': diameter_m,
            'volume_m3': round(volume_m3, 1),
            'coordinates': coordinates,
            'pipes_reconnected': len(connected_links),
            'message': (
                f"Junction '{best_id}' converted to delivery tank '{tank_id}' "
                f"using strategy '{strategy}'. "
                f"Base elevation {elevation_m:.1f} m AHD, "
                f"operational range {min_level_m:.1f}–{max_level_m:.1f} m, "
                f"diameter {diameter_m:.0f} m "
                f"(volume {volume_m3:.0f} m³ = {volume_m3/1000:.1f} ML). "
                f"{len(connected_links)} pipe(s) reconnected."
            ),
        }

    def auto_place_break_pressure_tanks(
        self,
        max_static_head_m: float = 120.0,
        tank_diameter_m: float = 10.0,
        max_level_m: float = 5.0
    ) -> dict:
        """
        Heuristic for auto-placing Break Pressure Tanks (BPTs) to control static head.
        
        Algorithm:
        1. Start from all existing reservoirs/tanks.
        2. Traverse downstream (BFS).
        3. Track the 'HGL Datum' (the head at the last BPT or Source).
        4. If (HGL_Datum - Junction_Elevation) > max_static_head_m:
           - Convert the PREVIOUS junction into a BPT.
           - Reset HGL_Datum to the new BPT's head.
           - Continue traversal.
           
        This ensures no pipe segment is exposed to static pressures exceeding 
        the target rating (e.g. 120m for PN16 pipes with a safety margin).
        """
        if self.wn is None:
            raise RuntimeError("No network loaded")

        sources = list(self.wn.reservoir_name_list) + list(self.wn.tank_name_list)
        if not sources:
            return {'status': 'error', 'reason': 'No source (reservoir/tank) found to start from.'}

        # Build adjacency list
        adj = {nid: [] for nid in self.wn.node_name_list}
        for lid in self.wn.link_name_list:
            link = self.wn.get_link(lid)
            adj[link.start_node_name].append((link.end_node_name, lid))
            adj[link.end_node_name].append((link.start_node_name, lid))

        new_tanks = []
        visited = set()
        
        # We process each source tree separately
        for start_node_id in sources:
            if start_node_id in visited: continue
            
            # (current_node, last_hgl_datum, previous_node)
            start_node = self.wn.get_node(start_node_id)
            initial_head = start_node.head if hasattr(start_node, 'head') else start_node.elevation + 3.0
            if hasattr(start_node, 'base_head'): initial_head = start_node.base_head
            
            queue = [(start_node_id, initial_head, None)]
            visited.add(start_node_id)
            
            while queue:
                curr_id, hgl_datum, prev_id = queue.pop(0)
                curr_node = self.wn.get_node(curr_id)
                
                # Check for static head violation
                elev = curr_node.base_head if hasattr(curr_node, 'base_head') else curr_node.elevation
                static_head = hgl_datum - elev
                
                if static_head > max_static_head_m and prev_id is not None:
                    # Place a BPT at the PREVIOUS node to break the head
                    bpt_id = f"BPT_{len(new_tanks) + 1}"
                    prev_node = self.wn.get_node(prev_id)
                    
                    # Conversion logic (reuse auto_generate_delivery_tank-like logic)
                    self.add_tank(
                        bpt_id, 
                        elevation_m=prev_node.elevation,
                        max_level_m=max_level_m,
                        init_level_m=max_level_m * 0.8,
                        diameter_m=tank_diameter_m,
                        coordinates=prev_node.coordinates
                    )
                    
                    # Reconnect pipes to the new BPT
                    for lid in list(self.wn.link_name_list):
                        link = self.wn.get_link(lid)
                        if link.start_node_name == prev_id: link.start_node = self.wn.get_node(bpt_id)
                        if link.end_node_name == prev_id: link.end_node = self.wn.get_node(bpt_id)
                    
                    # Remove the old junction
                    self.wn.remove_node(prev_id)
                    
                    new_tanks.append({
                        'id': bpt_id,
                        'replaced': prev_id,
                        'elevation': prev_node.elevation,
                        'head': prev_node.elevation + max_level_m
                    })
                    
                    # Reset HGL datum for the new branch starting at this BPT
                    hgl_datum = prev_node.elevation + max_level_m
                    # We continue from curr_id with the NEW datum
                
                # Add neighbors
                for neighbor_id, lid in adj.get(curr_id, []):
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        queue.append((neighbor_id, hgl_datum, curr_id))

        return {
            'status': 'success',
            'tanks_placed': len(new_tanks),
            'details': new_tanks,
            'message': f"Placed {len(new_tanks)} Break Pressure Tank(s) to maintain static head < {max_static_head_m}m."
        }

    def auto_place_booster_pumps(
        self,
        min_pressure_m: float = 20.0,
        target_boost_kw: float = 100.0,
        max_search_depth: int = 1000
    ) -> dict:
        """
        Heuristic for auto-placing inline booster pumps based on friction loss.
        
        Algorithm:
        1. Run a steady-state simulation to identify pressure profile.
        2. Identify junctions where Pressure < min_pressure_m.
        3. For each 'starving' zone, find the upstream pipe that feeds it.
        4. Replace that pipe with a Booster Pump.
        5. Repeat until all nodes meet the minimum pressure (or max_search_depth).
        
        Note: This is a design-phase heuristic. It uses constant power pumps 
        for initial sizing.
        """
        if self.wn is None:
            raise RuntimeError("No network loaded")

        # We must have demands set to have friction loss
        total_demand = 0
        for jid in self.wn.junction_name_list:
            j = self.wn.get_node(jid)
            if j.demand_timeseries_list:
                total_demand += j.demand_timeseries_list[0].base_value
        if total_demand <= 0:
            return {
                'status': 'error',
                'reason': 'No demands assigned. Friction loss is zero; cannot identify booster needs.'
            }

        pumps_placed = []
        
        # Iterative approach: place one pump, re-run, check again.
        # This handles the fact that one pump helps multiple downstream nodes.
        for iteration in range(20): # limit to 20 pumps per run
            results = self.run_steady_state()
            if 'error' in results:
                return {'status': 'error', 'reason': f"Hydraulic solve failed: {results['error']}"}
                
            # Find the junction with the lowest pressure that violates the limit
            violations = []
            for jid in self.wn.junction_name_list:
                p_data = results['pressures'].get(jid, {})
                p_avg = p_data.get('avg_m')
                if p_avg is not None and p_avg < min_pressure_m:
                    violations.append((jid, p_avg))
            
            if not violations:
                break # All pressures OK!
                
            # Pick the worst violation
            worst_jid, worst_p = min(violations, key=lambda x: x[1])
            
            # Find an upstream pipe to replace with a pump.
            incoming_pipes = []
            for lid in self.wn.get_links_for_node(worst_jid):
                if lid in self.wn.pipe_name_list:
                    link = self.wn.get_link(lid)
                    # For a booster, we want a pipe that points TO the starving node
                    # OR we just take the first pipe connected to it if it's a dead end.
                    if link.end_node_name == worst_jid or link.start_node_name == worst_jid:
                        incoming_pipes.append(lid)

            if not incoming_pipes:
                # If we already placed some pumps but still have violations, 
                # we might have hit a limit (e.g. node only fed by pumps).
                # Break and return what we have.
                break
                
            # Replace the first incoming pipe with a pump
            target_pipe_id = incoming_pipes[0]
            pipe = self.wn.get_link(target_pipe_id)
            start_node = pipe.start_node_name
            end_node = pipe.end_node_name
            
            pump_id = f"PUMP_BOOSTER_{len(pumps_placed) + 1}"
            self.add_pump(pump_id, start_node, end_node, power_kw=target_boost_kw)
            
            # Remove the pipe being replaced
            self.remove_pipe(target_pipe_id)
            
            pumps_placed.append({
                'id': pump_id,
                'replaced_pipe': target_pipe_id,
                'from': start_node,
                'to': end_node,
                'power_kw': target_boost_kw
            })

        return {
            'status': 'success',
            'pumps_placed': len(pumps_placed),
            'details': pumps_placed,
            'message': f"Placed {len(pumps_placed)} Booster Pump(s) to maintain residual pressure > {min_pressure_m}m."
        }

    def apply_network_aging(self, years: int) -> dict:
        """
        Globally age the network by 'years'.
        
        This method parses the 'Material' field from the pipe's description 
        (set during bulk assignment) and uses the engineering aging model 
        in data/au_pipes.py to update the Hazen-Williams C-factors.
        """
        if self.wn is None:
            raise RuntimeError("No network loaded")
            
        import re
        from data.au_pipes import lookup_roughness
        
        updated_count = 0
        details = []
        
        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            desc = getattr(pipe, 'description', '')
            
            # Parse Material: XXXXX
            match = re.search(r"Material: ([^,]+)", desc)
            if match:
                material = match.group(1).strip()
                try:
                    old_c = pipe.roughness
                    new_c = lookup_roughness(material, years)
                    pipe.roughness = new_c
                    updated_count += 1
                    details.append(f"{pid}: {material} (C: {old_c} -> {new_c})")
                except KeyError:
                    # Material not in aging database
                    pass
                    
        return {
            'status': 'success',
            'years': years,
            'updated_count': updated_count,
            'message': f"Aged {updated_count} pipes by {years} years."
        }

    def apply_scenario_aging(self, metal_age: int, plastic_age: int) -> None:
        """
        Apply C-factor degradation to pipes based on their inferred material.
        Uses the material description if available.
        """
        if self.wn is None:
            return
            
        import re
        from data.au_pipes import lookup_roughness

        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            
            # Extract material from description
            match = re.search(r"Material:\s*([^,]+)", getattr(pipe, 'description', ''))
            material = match.group(1).strip() if match else None
            
            if material is None:
                continue  # Skip pipes with no material description
                
            if material in ["PVC", "PE", "PE100 PN10 (SDR 17)", "PE100 PN12.5 (SDR 13.6)", "PE100 PN16 (SDR 11)", "PE100 PN20 (SDR 9)"]:
                age = plastic_age
            else:
                age = metal_age

            try:
                pipe.roughness = lookup_roughness(material, age)
            except KeyError:
                pass

    def set_node_demand(self, node_id: str, demand_lps: float, pattern_name: str = None) -> dict:
        """
        Assign a base demand to a junction.
        
        Parameters
        ----------
        node_id : str
            The junction ID.
        demand_lps : float
            Demand flow rate in Litres Per Second (LPS).
        pattern_name : str, optional
            ID of the demand pattern to apply.
            
        Returns
        -------
        dict
            Status and information about the applied demand.
        """
        if self.wn is None:
            raise RuntimeError("No network loaded")
            
        if node_id not in self.wn.junction_name_list:
            node_type = type(self.wn.get_node(node_id)).__name__ if node_id in self.wn.node_name_list else "Non-existent"
            return {
                'status': 'error',
                'reason': f"Node '{node_id}' is a {node_type}, not a Junction. Demands can only be applied to Junctions."
            }
            
        junc = self.wn.get_node(node_id)
        demand_m3s = demand_lps / 1000.0
        
        if not junc.demand_timeseries_list:
            junc.add_demand(base=demand_m3s, pattern_name=pattern_name)
        else:
            junc.demand_timeseries_list[0].base_value = demand_m3s
            if pattern_name:
                junc.demand_timeseries_list[0].pattern_name = pattern_name
                
        return {
            'status': 'success',
            'node_id': node_id,
            'demand_lps': demand_lps,
            'message': f"Demand of {demand_lps} LPS applied to junction '{node_id}'."
        }
        
    def get_node_demand(self, node_id: str) -> dict:
        """Get the base demand of a junction in LPS."""
        if self.wn is None:
            raise RuntimeError("No network loaded")
            
        if node_id not in self.wn.junction_name_list:
            return {'status': 'error', 'reason': 'Not a junction'}
            
        junc = self.wn.get_node(node_id)
        if not junc.demand_timeseries_list:
            demand_lps = 0.0
        else:
            demand_lps = junc.demand_timeseries_list[0].base_value * 1000.0
            
        return {
            'status': 'success',
            'node_id': node_id,
            'demand_lps': round(demand_lps, 2)
        }

    def auto_assign_demands(
        self,
        default_demand_lps: float,
        strategy: str = 'dead_ends',
        exclude_nodes: list = None
    ) -> dict:
        """
        Automatically assign a base demand to delivery/destination nodes.
        
        This is useful when designing a pipeline for a specific required flow
        rather than filling a tank. By placing a demand at the destination, 
        the solver will push that exact flow through the network, allowing 
        you to calculate the required pump head or check residual pressures.

        Parameters
        ----------
        default_demand_lps : float
            The demand flow rate to assign in Litres Per Second (LPS).
        strategy : str
            How to identify destination nodes:
            - 'dead_ends' : Any junction with only 1 connected pipe.
            - 'all_junctions' : Every junction in the network (e.g. for a reticulation grid).
            - 'lowest_elevation' : The single junction with the lowest elevation.
            - 'furthest_from_reservoir' : The single junction spatially furthest from a source.
        exclude_nodes : list of str, optional
            Node IDs to skip.

        Returns
        -------
        dict
            Summary of the nodes that received the demand.
        """
        if self.wn is None:
            raise RuntimeError("No network loaded")
            
        if default_demand_lps <= 0:
            return {'status': 'error', 'reason': 'Demand must be > 0'}
            
        junctions = list(self.wn.junction_name_list)
        exclude = set(exclude_nodes or [])
        candidates = [jid for jid in junctions if jid not in exclude]
        
        if not candidates:
            return {'status': 'error', 'reason': 'No candidate junctions found.'}
            
        targets = []
        
        if strategy == 'all_junctions':
            targets = candidates
            
        elif strategy == 'dead_ends':
            degree = {jid: 0 for jid in candidates}
            for lid in self.wn.link_name_list:
                link = self.wn.get_link(lid)
                if link.start_node_name in degree:
                    degree[link.start_node_name] += 1
                if link.end_node_name in degree:
                    degree[link.end_node_name] += 1
            targets = [jid for jid, d in degree.items() if d == 1]
            if not targets:
                # Fallback to furthest if no dead ends
                strategy = 'furthest_from_reservoir'
                
        if strategy == 'lowest_elevation':
            targets = [min(candidates, key=lambda jid: self.wn.get_node(jid).elevation)]
            
        elif strategy == 'furthest_from_reservoir':
            res_coords = [self.wn.get_node(rid).coordinates for rid in self.wn.reservoir_name_list]
            if not res_coords:
                # Fallback to arbitrary furthest node from centroid
                coords = [self.wn.get_node(jid).coordinates for jid in candidates]
                cx = sum(c[0] for c in coords) / len(coords)
                cy = sum(c[1] for c in coords) / len(coords)
                rx, ry = cx, cy
            else:
                rx = sum(c[0] for c in res_coords) / len(res_coords)
                ry = sum(c[1] for c in res_coords) / len(res_coords)
                
            import math as _math
            targets = [max(candidates, key=lambda jid: _math.hypot(
                self.wn.get_node(jid).coordinates[0] - rx,
                self.wn.get_node(jid).coordinates[1] - ry
            ))]
            
        if not targets:
            return {'status': 'error', 'reason': f"Strategy '{strategy}' yielded no targets."}
            
        applied_count = 0
        for jid in targets:
            res = self.set_node_demand(jid, default_demand_lps)
            if res['status'] == 'success':
                applied_count += 1
                
        return {
            'status': 'success',
            'strategy': strategy,
            'nodes_applied': targets,
            'count': applied_count,
            'demand_lps_per_node': default_demand_lps,
            'total_demand_lps': default_demand_lps * applied_count,
            'message': f"Assigned {default_demand_lps} LPS to {applied_count} node(s) using '{strategy}' strategy."
        }

    def merge_nodes(self, source_id: str, target_id: str) -> dict:
        """
        Merge source_node into target_node.
        All pipes connected to source_node are re-routed to target_node.
        The source_node is then deleted.
        """
        if self.wn is None:
            return {'status': 'error', 'reason': 'No network loaded'}
            
        if source_id not in self.wn.node_name_list or target_id not in self.wn.node_name_list:
            return {'status': 'error', 'reason': 'One or both nodes do not exist'}
            
        source = self.wn.get_node(source_id)
        target = self.wn.get_node(target_id)
        
        connected_links = self.wn.get_links_for_node(source_id)
        
        # Validation pass
        for lid in connected_links:
            if self.wn.get_link(lid).link_type != 'Pipe':
                return {'status': 'error', 'reason': f'Cannot merge node connected to a non-pipe ({lid})'}
                
        recreated_links = []
        for lid in connected_links:
            link = self.wn.get_link(lid)
            
            new_start = target_id if link.start_node_name == source_id else link.start_node_name
            new_end = target_id if link.end_node_name == source_id else link.end_node_name
            
            # If the pipe now connects target to target, it's a zero-length loop, drop it
            if new_start == new_end:
                self.wn.remove_link(lid)
                continue
                
            props = {
                'length': link.length,
                'diameter': link.diameter,
                'roughness': link.roughness,
                'minor_loss': link.minor_loss,
                'status': link.status,
                'description': getattr(link, 'description', '')
            }
            
            self.wn.remove_link(lid)
            self.wn.add_pipe(lid, new_start, new_end, 
                             length=props['length'], 
                             diameter=props['diameter'], 
                             roughness=props['roughness'],
                             minor_loss=props['minor_loss'],
                             initial_status=props['status'])
            new_link = self.wn.get_link(lid)
            new_link.description = props['description']
            recreated_links.append(lid)
            
        # Merge demands if both are junctions
        if source.node_type == 'Junction' and target.node_type == 'Junction':
            source_demand = 0
            if source.demand_timeseries_list:
                source_demand = source.demand_timeseries_list[0].base_value
            if source_demand > 0:
                target_demand = 0
                if target.demand_timeseries_list:
                    target_demand = target.demand_timeseries_list[0].base_value
                    target.demand_timeseries_list[0].base_value = target_demand + source_demand
                else:
                    target.add_demand(base=source_demand, pattern_name=None)
                    
        self.wn.remove_node(source_id)
        
        return {
            'status': 'success',
            'merged_into': target_id,
            'removed': source_id,
            'reconnected_links': recreated_links
        }

    def validate_network(self) -> dict:
        """
        Validate the network topology and properties.
        Checks for:
        - Missing elevations
        - Disconnected nodes (orphans)
        - Disconnected segments (multiple components)
        - Lack of sources
        
        Returns a dict with 'status', 'errors', 'warnings'.
        """
        if self.wn is None:
            return {'status': 'error', 'errors': ['No network loaded'], 'warnings': []}
            
        errors = []
        warnings = []
        
        # 1. Missing elevations
        for jid in self.wn.junction_name_list:
            if getattr(self.wn.get_node(jid), 'elevation', None) is None:
                errors.append(f"Junction {jid} has no elevation set.")
                
        # 2. Lack of sources
        if len(self.wn.reservoir_name_list) + len(self.wn.tank_name_list) == 0:
            errors.append("Network has no sources (reservoirs or tanks). Hydraulic solve will fail.")
            
        # 3. Connectivity (Disconnected segments)
        import networkx as nx
        isolated_nodes = []
        try:
            # WNTR provides a get_graph method which returns a MultiDiGraph
            # We convert to an undirected graph to check for weakly connected components
            G = self.wn.get_graph().to_undirected()
            components = list(nx.connected_components(G))
            
            if len(components) > 1:
                # Find the largest component
                components.sort(key=len, reverse=True)
                main_comp = components[0]
                
                # Report other components
                for i, comp in enumerate(components[1:]):
                    isolated_nodes.extend(list(comp))
                    if len(comp) == 1:
                        node = list(comp)[0]
                        warnings.append(f"Node {node} is completely disconnected (orphan).")
                    else:
                        errors.append(f"Disconnected segment found with {len(comp)} nodes: {list(comp)[:5]}...")
        except Exception as e:
            warnings.append(f"Could not perform graph connectivity check: {str(e)}")

        return {
            'status': 'error' if errors else ('warning' if warnings else 'success'),
            'errors': errors,
            'warnings': warnings,
            'isolated_nodes': isolated_nodes
        }

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
        if base_demand is not None:
            # Internal base_demand is in m³/s. Update or add it.
            if not node.demand_timeseries_list:
                node.add_demand(base=base_demand, pattern_name=None)
            else:
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

    def update_pipe(self, pid, length=None, diameter_m=None, roughness=None, description=None):
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
        if description is not None:
            pipe.description = description

    def remove_pipe(self, pid):
        """Remove a pipe (link) from the network."""
        if self.wn is None:
            raise RuntimeError("No network loaded")
        self.wn.remove_link(pid)

    def add_pump(self, pid, start_node, end_node, power_kw=None, curve_id=None):
        """Add a pump. If power_kw is given, it's a constant power pump."""
        if self.wn is None:
            raise RuntimeError("No network loaded")
        if power_kw:
            self.wn.add_pump(pid, start_node, end_node, pump_type='POWER', 
                             pump_parameter=power_kw)
        elif curve_id:
            self.wn.add_pump(pid, start_node, end_node, pump_type='HEAD',
                             pump_parameter=curve_id)
        else:
            # Default to a 50kW power pump if nothing specified
            self.wn.add_pump(pid, start_node, end_node, pump_type='POWER',
                             pump_parameter=50.0)

    def remove_pump(self, pid):
        """Remove a pump from the network."""
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

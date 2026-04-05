import os, json, csv, math, wntr, numpy as np


class AdvancedMixin:

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
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}
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
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}
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
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

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
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

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
    # CHLORINE BOOSTER STATION DESIGN (J14)
    # =========================================================================

    WSAA_MIN_CHLORINE_MGL = 0.2  # WSAA WSA 03-2011 minimum residual

    def design_chlorine_boosters(self, wq_results=None, target_residual_mgl=None):
        """
        Identify locations where chlorine drops below minimum and
        recommend booster station placement and dosing.

        Parameters
        ----------
        wq_results : dict or None
            Water quality results from run_water_quality(parameter='chlorine').
            If None, runs chlorine analysis.
        target_residual_mgl : float or None
            Target residual (default: WSAA 0.2 mg/L)

        Returns dict with 'deficient_nodes', 'booster_recommendations', 'summary'.
        Ref: WSAA Water Quality Management Guidelines
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        if target_residual_mgl is None:
            target_residual_mgl = self.WSAA_MIN_CHLORINE_MGL

        if wq_results is None:
            try:
                wq_results = self.run_water_quality(
                    parameter='chlorine', duration_hrs=72,
                    initial_conc=1.0, bulk_coeff=-0.5, wall_coeff=-0.1)
            except Exception as e:
                return {'error': f'Water quality analysis failed: {e}'}

        junction_quality = wq_results.get('junction_quality', {})

        # Find nodes below minimum
        deficient = []
        for jid, qdata in junction_quality.items():
            min_cl = qdata.get('min_chlorine_mgl', qdata.get('min_age_hrs', 1.0))
            avg_cl = qdata.get('avg_chlorine_mgl', qdata.get('avg_age_hrs', 1.0))
            if min_cl < target_residual_mgl:
                deficient.append({
                    'node': jid,
                    'min_chlorine_mgl': round(min_cl, 3),
                    'avg_chlorine_mgl': round(avg_cl, 3),
                    'deficit_mgl': round(target_residual_mgl - min_cl, 3),
                })

        if not deficient:
            return {
                'deficient_nodes': [],
                'booster_recommendations': [],
                'summary': f'All nodes maintain ≥{target_residual_mgl} mg/L — '
                           f'no booster stations needed.',
            }

        # Sort by deficit (worst first)
        deficient.sort(key=lambda x: x['deficit_mgl'], reverse=True)

        # Recommend booster stations
        # Strategy: place at upstream nodes that feed the most deficient areas
        # Simplified: recommend at the most deficient node
        boosters = []
        for d in deficient[:3]:  # up to 3 boosters
            # Dose = target - current minimum + safety margin
            dose = target_residual_mgl - d['min_chlorine_mgl'] + 0.1
            boosters.append({
                'node': d['node'],
                'recommended_dose_mgl': round(dose, 2),
                'target_residual_mgl': target_residual_mgl,
                'reason': f'Minimum chlorine {d["min_chlorine_mgl"]:.3f} mg/L '
                          f'< {target_residual_mgl} mg/L (WSAA)',
            })

        return {
            'deficient_nodes': deficient,
            'booster_recommendations': boosters,
            'summary': f'{len(deficient)} nodes below {target_residual_mgl} mg/L. '
                       f'Recommended {len(boosters)} booster station(s).',
        }


    # =========================================================================
    # SCADA REPLAY (J11)
    # =========================================================================

    def run_scada_replay(self, csv_path):
        """
        Run EPS with actual measured demands from CSV.

        CSV format: timestamp_h, node1, node2, ... (demands in LPS)

        Parameters
        ----------
        csv_path : str
            Path to CSV with time-series demands

        Returns dict with timestep results and comparison metrics.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        import csv as csv_mod
        with open(csv_path, 'r') as f:
            reader = csv_mod.DictReader(f)
            rows = list(reader)

        if not rows:
            return {'error': 'CSV is empty'}

        # Get column names (first is timestamp, rest are node IDs)
        columns = list(rows[0].keys())
        time_col = columns[0]
        node_cols = columns[1:]

        n_timesteps = len(rows)

        # Configure simulation duration
        timestamps = [float(r[time_col]) for r in rows]
        duration_hrs = max(timestamps) if timestamps else 24
        timestep_s = 3600  # 1-hour default
        if n_timesteps >= 2:
            dt = (timestamps[1] - timestamps[0]) * 3600
            timestep_s = max(300, int(dt))

        self.wn.options.time.duration = int(duration_hrs * 3600)
        self.wn.options.time.hydraulic_timestep = timestep_s
        self.wn.options.time.pattern_timestep = timestep_s
        self.wn.options.time.report_timestep = timestep_s

        # Create demand patterns from CSV data
        for node_id in node_cols:
            if node_id in self.wn.junction_name_list:
                values = [float(r[node_id]) / 1000 for r in rows]  # LPS to m³/s
                avg_demand = sum(values) / len(values) if values else 0
                # Set base demand and pattern multipliers
                junc = self.wn.get_node(node_id)
                if junc.demand_timeseries_list:
                    junc.demand_timeseries_list[0].base_value = avg_demand
                    if avg_demand > 0:
                        multipliers = [v / avg_demand for v in values]
                    else:
                        multipliers = [1.0] * len(values)
                    pat_name = f'scada_{node_id}'
                    try:
                        self.wn.add_pattern(pat_name, multipliers)
                    except Exception:
                        pass  # pattern may already exist
                    junc.demand_timeseries_list[0].pattern_name = pat_name

        # Run simulation
        try:
            results = self.run_steady_state(save_plot=False)
        except Exception as e:
            return {'error': f'Simulation failed: {e}'}

        return {
            'n_timesteps': n_timesteps,
            'duration_hrs': duration_hrs,
            'pressures': results.get('pressures', {}),
            'flows': results.get('flows', {}),
            'compliance': results.get('compliance', []),
        }


    # =========================================================================
    # SMART ERROR RECOVERY (L5)
    # =========================================================================

    def diagnose_network(self):
        """
        Diagnose common network problems and suggest fixes.

        Checks for:
        - Disconnected nodes (not reachable from any source)
        - Zero-demand dead ends that may cause convergence issues
        - Zero-length or zero-diameter pipes
        - Missing sources (no reservoirs or tanks)
        - Negative elevations (possible data entry error for AHD)
        - Duplicate pipe IDs or overlapping pipes

        Returns dict with 'issues' list and 'suggestions'.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        issues = []

        # Check for sources
        n_sources = len(self.wn.reservoir_name_list) + len(self.wn.tank_name_list)
        if n_sources == 0:
            issues.append({
                'severity': 'CRITICAL',
                'type': 'no_source',
                'message': 'Network has no reservoir or tank — analysis will fail.',
                'suggestion': 'Add at least one reservoir with a fixed head.',
            })

        # Check for disconnected nodes
        topo = self.analyse_topology()
        if 'error' not in topo:
            if topo['isolated_count'] > 0:
                issues.append({
                    'severity': 'CRITICAL',
                    'type': 'disconnected_nodes',
                    'message': f'{topo["isolated_count"]} node(s) not connected to any source.',
                    'nodes': topo['isolated_nodes'],
                    'suggestion': 'Connect isolated nodes to the network or remove them.',
                })
            if topo['dead_end_count'] > 5:
                issues.append({
                    'severity': 'WARNING',
                    'type': 'many_dead_ends',
                    'message': f'{topo["dead_end_count"]} dead-end nodes detected.',
                    'suggestion': 'Dead ends can cause water quality issues. '
                                  'Consider looping the network where possible.',
                })

        # Check for zero-length or zero-diameter pipes
        zero_length = []
        zero_diameter = []
        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            if pipe.length <= 0:
                zero_length.append(pid)
            if pipe.diameter <= 0:
                zero_diameter.append(pid)

        if zero_length:
            issues.append({
                'severity': 'CRITICAL',
                'type': 'zero_length_pipe',
                'message': f'{len(zero_length)} pipe(s) with zero or negative length.',
                'pipes': zero_length,
                'suggestion': 'Set pipe length to actual distance between nodes.',
            })
        if zero_diameter:
            issues.append({
                'severity': 'CRITICAL',
                'type': 'zero_diameter_pipe',
                'message': f'{len(zero_diameter)} pipe(s) with zero diameter.',
                'pipes': zero_diameter,
                'suggestion': 'Set pipe diameter to design DN (e.g., 0.150 m for DN150).',
            })

        # Check for negative elevations
        neg_elev = []
        for jid in self.wn.junction_name_list:
            node = self.wn.get_node(jid)
            if node.elevation < -50:  # allow small negatives for below-datum
                neg_elev.append({'node': jid, 'elevation': node.elevation})

        if neg_elev:
            issues.append({
                'severity': 'WARNING',
                'type': 'negative_elevation',
                'message': f'{len(neg_elev)} node(s) with elevation below -50 m AHD.',
                'nodes': neg_elev,
                'suggestion': 'Check if elevations are in correct units (m AHD). '
                              'Australian elevations are rarely below -15 m AHD.',
            })

        # Check for very high demands that might cause convergence failure
        high_demand = []
        for jid in self.wn.junction_name_list:
            node = self.wn.get_node(jid)
            try:
                d_lps = node.demand_timeseries_list[0].base_value * 1000
                if d_lps > 100:  # > 100 LPS is unusual for a single junction
                    high_demand.append({'node': jid, 'demand_lps': round(d_lps, 1)})
            except (IndexError, AttributeError):
                pass

        if high_demand:
            issues.append({
                'severity': 'INFO',
                'type': 'high_demand',
                'message': f'{len(high_demand)} node(s) with demand > 100 LPS.',
                'nodes': high_demand,
                'suggestion': 'Verify demand values are in correct units (LPS, not m³/s).',
            })

        # Check for unreasonable roughness values
        bad_roughness = []
        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            C = pipe.roughness
            if C < 50 or C > 160:
                bad_roughness.append({'pipe': pid, 'roughness': C})

        if bad_roughness:
            issues.append({
                'severity': 'WARNING',
                'type': 'roughness_range',
                'message': f'{len(bad_roughness)} pipe(s) with unusual Hazen-Williams C value.',
                'pipes': bad_roughness,
                'suggestion': 'Typical HW-C range: 90 (old concrete) to 150 (new PVC). '
                              'Check if Darcy-Weisbach roughness was used by mistake.',
            })

        # Summary
        n_critical = sum(1 for i in issues if i['severity'] == 'CRITICAL')
        n_warning = sum(1 for i in issues if i['severity'] == 'WARNING')
        n_info = sum(1 for i in issues if i['severity'] == 'INFO')

        return {
            'issues': issues,
            'issue_count': len(issues),
            'critical': n_critical,
            'warnings': n_warning,
            'info': n_info,
            'can_run': n_critical == 0,
            'summary': (f'{n_critical} critical, {n_warning} warnings, {n_info} info'
                       if issues else 'No issues detected — network appears healthy.'),
        }


    # =========================================================================
    # QUICK NETWORK ASSESSMENT (Innovation Q3)
    # =========================================================================

    def quick_assessment(self):
        """
        Generate a comprehensive quick assessment for an unknown network.

        Designed for the scenario: engineer receives a 20-year-old .inp file
        with no documentation. This method gives them a complete picture in
        seconds — topology, hydraulics, compliance, risks, and recommendations.

        Returns dict with all assessment sections.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        assessment = {
            'network_name': os.path.basename(self._inp_file) if self._inp_file else 'Unknown',
        }

        # 1. Basic summary
        assessment['summary'] = self.get_network_summary()

        # 2. Topology
        assessment['topology'] = self.analyse_topology()

        # 3. Run analysis
        try:
            results = self.run_steady_state(save_plot=False)
            assessment['analysis_status'] = 'OK'
        except Exception as e:
            assessment['analysis_status'] = f'FAILED: {e}'
            results = None

        # 4. Hydraulic fingerprint
        if results:
            assessment['fingerprint'] = self.hydraulic_fingerprint()

        # 5. Resilience
        if results:
            assessment['resilience'] = self.compute_resilience_index(results)

        # 6. Quality score
        if results:
            assessment['quality_score'] = self.compute_quality_score(results)

        # 7. Diagnostics
        assessment['diagnostics'] = self.diagnose_network()

        # 8. Material inventory (from roughness values)
        material_counts = {'DI (C=120-140)': 0, 'PVC (C=140-150)': 0,
                          'Concrete (C=90-120)': 0, 'Unknown': 0}
        for pid in self.wn.pipe_name_list:
            C = self.wn.get_link(pid).roughness
            if 120 <= C <= 140:
                material_counts['DI (C=120-140)'] += 1
            elif 140 < C <= 150:
                material_counts['PVC (C=140-150)'] += 1
            elif 90 <= C < 120:
                material_counts['Concrete (C=90-120)'] += 1
            else:
                material_counts['Unknown'] += 1
        assessment['material_inventory'] = material_counts

        # 9. Pipe size distribution
        size_dist = {}
        for pid in self.wn.pipe_name_list:
            dn = int(self.wn.get_link(pid).diameter * 1000)
            size_dist[dn] = size_dist.get(dn, 0) + 1
        assessment['pipe_sizes'] = dict(sorted(size_dist.items()))

        # 10. Recommendations
        recs = []
        if assessment.get('diagnostics', {}).get('critical', 0) > 0:
            recs.append('Fix critical diagnostic issues before running analysis.')
        topo = assessment.get('topology', {})
        if topo.get('dead_end_count', 0) > 5:
            recs.append(f'Network has {topo["dead_end_count"]} dead ends — '
                       f'consider looping for water quality.')
        if topo.get('bridge_count', 0) > 0:
            recs.append(f'{topo["bridge_count"]} bridge pipes identified — '
                       f'single points of failure.')
        ri = assessment.get('resilience', {})
        if ri.get('resilience_index', 1) < 0.15:
            recs.append('Low resilience index — network is vulnerable to failures.')
        qs = assessment.get('quality_score', {})
        if qs.get('total_score', 100) < 60:
            recs.append(f'Quality score {qs.get("total_score", "?")}/100 — '
                       f'significant improvements needed.')
        if not recs:
            recs.append('Network appears healthy. Run detailed analysis for more insight.')
        assessment['recommendations'] = recs

        return assessment


    # =========================================================================
    # AUTOMATED TUTORIAL GENERATOR (M8)
    # =========================================================================

    def generate_tutorial(self, output_dir=None):
        """
        Auto-generate a tutorial package for the current network.

        Creates:
        - README.md with network description, features, analysis steps
        - Pre-computed results summary
        - Suggested analysis workflow

        Parameters
        ----------
        output_dir : str or None
            Directory to write tutorial files. If None, uses
            tutorials/{network_name}/

        Returns dict with generated file paths.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        name = os.path.splitext(
            os.path.basename(self._inp_file) if self._inp_file else 'network'
        )[0].replace(' ', '_')

        if output_dir is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 'tutorials', name)

        os.makedirs(output_dir, exist_ok=True)

        # Gather data
        summary = self.get_network_summary()
        topo = self.analyse_topology()

        try:
            results = self.run_steady_state(save_plot=False)
            pressures = results.get('pressures', {})
            flows = results.get('flows', {})
        except Exception:
            results = None
            pressures = {}
            flows = {}

        ri = self.compute_resilience_index(results) if results else {}
        qs = self.compute_quality_score(results) if results else {}

        # Build README
        lines = [
            f'# Tutorial: {name.replace("_", " ").title()}',
            '',
            '## Network Description',
            '',
            f'- **Junctions:** {summary.get("junctions", 0)}',
            f'- **Pipes:** {summary.get("pipes", 0)}',
            f'- **Reservoirs:** {summary.get("reservoirs", 0)}',
            f'- **Tanks:** {summary.get("tanks", 0)}',
            f'- **Pumps:** {summary.get("pumps", 0)}',
        ]

        if 'error' not in topo:
            lines.extend([
                '',
                '## Topology',
                '',
                f'- Dead ends: {topo["dead_end_count"]}',
                f'- Independent loops: {topo["loops"]}',
                f'- Bridge pipes: {topo["bridge_count"]}',
                f'- Connectivity ratio: {topo["connectivity_ratio"]}',
            ])

        if pressures:
            p_vals = [p.get('avg_m', 0) for p in pressures.values()]
            v_vals = [f.get('max_velocity_ms', 0) for f in flows.values()]
            lines.extend([
                '',
                '## Expected Results (Steady-State)',
                '',
                f'- Pressure range: {min(p_vals):.1f} - {max(p_vals):.1f} m',
                f'- Max velocity: {max(v_vals):.2f} m/s',
            ])

        if 'error' not in ri:
            lines.extend([
                f'- Resilience index: {ri["resilience_index"]:.3f} (Grade {ri["grade"]})',
            ])

        if 'error' not in qs:
            lines.extend([
                f'- Quality score: {qs["total_score"]:.0f}/100 (Grade {qs["grade"]})',
            ])

        lines.extend([
            '',
            '## Suggested Analysis Steps',
            '',
            '1. Open network: File > Open, select `network.inp`',
            '2. Run steady-state: Analysis > Steady State (F5)',
            '3. Check WSAA compliance in status bar',
            '4. Try different colour modes: Pressure, Velocity, Headloss',
            '5. Use Probe tool to inspect individual elements',
            '6. Run fire flow analysis: Analysis > Fire Flow Wizard (F8)',
            '7. Generate report: Reports > Generate Report (DOCX)',
        ])

        if summary.get('pumps', 0) > 0:
            lines.append('8. Check pump operating points in Properties panel')

        lines.extend([
            '',
            '## Key Features to Explore',
            '',
        ])

        if topo.get('dead_end_count', 0) > 0:
            lines.append(f'- **Dead ends**: {topo["dead_end_count"]} dead-end nodes '
                        f'— check water quality implications')
        if topo.get('loops', 0) > 0:
            lines.append(f'- **Looped network**: {topo["loops"]} loops '
                        f'provide path redundancy')
        if summary.get('pumps', 0) > 0:
            lines.append('- **Pump stations**: check operating point and BEP')

        lines.extend([
            '',
            '---',
            '*Auto-generated by Hydraulic Analysis Tool*',
        ])

        readme_path = os.path.join(output_dir, 'README.md')
        with open(readme_path, 'w') as f:
            f.write('\n'.join(lines))

        return {
            'output_dir': output_dir,
            'readme_path': readme_path,
            'network_name': name,
            'summary': summary,
        }


    # =========================================================================
    # DEMAND PATTERN LIBRARY (M5)
    # =========================================================================

    @staticmethod
    def get_pattern_library():
        """
        Load the demand pattern library from data/demand_patterns.json.

        Returns dict with pattern names as keys and pattern data as values.
        Each pattern contains 'name', 'source', 'description', 'category',
        and 'multipliers' (24 hourly values starting at midnight).

        Ref: WSAA WSA 03-2011 Table 4.2 (residential), various sources for others
        """
        patterns_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'demand_patterns.json')
        if not os.path.exists(patterns_path):
            return {'error': f'Pattern library not found at {patterns_path}'}

        import json
        with open(patterns_path, 'r') as f:
            data = json.load(f)

        return data.get('patterns', {})

    @staticmethod
    def get_pattern(pattern_id):
        """Get a single pattern by ID (e.g. 'residential_wsaa')."""
        library = AdvancedMixin.get_pattern_library()
        if isinstance(library, dict) and 'error' in library:
            return library
        if pattern_id not in library:
            return {'error': f'Pattern "{pattern_id}" not found. '
                    f'Available: {", ".join(library.keys())}'}
        return library[pattern_id]

    def apply_pattern_to_nodes(self, pattern_id, node_ids=None):
        """
        Apply a demand pattern from the library to network nodes.

        Parameters
        ----------
        pattern_id : str
            Pattern ID from the library (e.g. 'residential_wsaa')
        node_ids : list of str or None
            Specific junction IDs to apply to. If None, applies to all junctions.

        Returns dict with count of nodes updated.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        pattern_data = self.get_pattern(pattern_id)
        if 'error' in pattern_data:
            return pattern_data

        multipliers = pattern_data['multipliers']
        pattern_name = f'pat_{pattern_id}'

        # Add pattern to WNTR model
        if pattern_name not in self.wn.pattern_name_list:
            self.wn.add_pattern(pattern_name, multipliers)

        # Get target nodes
        if node_ids is None:
            node_ids = list(self.wn.junction_name_list)

        count = 0
        for nid in node_ids:
            try:
                node = self.wn.get_node(nid)
                if hasattr(node, 'demand_timeseries_list') and node.demand_timeseries_list:
                    node.demand_timeseries_list[0].pattern_name = pattern_name
                    count += 1
            except KeyError:
                continue

        return {
            'pattern_applied': pattern_id,
            'pattern_name': pattern_data['name'],
            'nodes_updated': count,
            'multipliers': multipliers,
        }

    @staticmethod
    def save_custom_pattern(pattern_id, name, multipliers, source='Custom',
                            description='', category='custom'):
        """
        Save a custom pattern to the pattern library.

        Parameters
        ----------
        pattern_id : str
            Unique ID for the pattern
        name : str
            Display name
        multipliers : list of float
            24 hourly multiplier values
        """
        if len(multipliers) != 24:
            return {'error': 'Pattern must have exactly 24 hourly values'}

        patterns_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'demand_patterns.json')

        import json
        with open(patterns_path, 'r') as f:
            data = json.load(f)

        data['patterns'][pattern_id] = {
            'name': name,
            'source': source,
            'description': description,
            'category': category,
            'multipliers': multipliers,
        }

        with open(patterns_path, 'w') as f:
            json.dump(data, f, indent=2)

        return {'saved': pattern_id, 'name': name}


    # =========================================================================
    # BATCH ANALYSIS MODE (L10)
    # =========================================================================

    def batch_analyse(self, inp_files, analyses=None):
        """
        Run analyses on multiple .inp files and return combined results.

        Parameters
        ----------
        inp_files : list of str
            Paths to .inp files
        analyses : list of str or None
            Analyses to run. Options: 'steady', 'topology', 'fingerprint',
            'diagnose', 'compliance'. Default: all.

        Returns list of dicts, one per file.
        """
        if analyses is None:
            analyses = ['steady', 'topology', 'fingerprint', 'diagnose', 'compliance']

        results = []
        for inp_path in inp_files:
            entry = {
                'file': os.path.basename(inp_path),
                'path': inp_path,
                'analyses': {},
            }
            try:
                self.load_network_from_path(inp_path)
            except Exception as e:
                entry['error'] = f'Failed to load: {e}'
                results.append(entry)
                continue

            if 'steady' in analyses:
                try:
                    entry['analyses']['steady'] = self.run_steady_state(save_plot=False)
                except Exception as e:
                    entry['analyses']['steady'] = {'error': str(e)}

            if 'topology' in analyses:
                entry['analyses']['topology'] = self.analyse_topology()

            if 'fingerprint' in analyses:
                entry['analyses']['fingerprint'] = self.hydraulic_fingerprint()

            if 'diagnose' in analyses:
                entry['analyses']['diagnose'] = self.diagnose_network()

            if 'compliance' in analyses:
                entry['analyses']['compliance'] = self.run_design_compliance_check()

            results.append(entry)

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


    # =========================================================================
    # SMART NETWORK HEALTH SUMMARY (O6)
    # =========================================================================

    def network_health_summary(self):
        """
        Generate a plain English network health summary suitable for
        pasting directly into an engineering report.

        Returns dict with one-paragraph summary, key metrics, and
        top 3 recommendations.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        summary = self.get_network_summary()
        try:
            results = self.run_steady_state(save_plot=False)
        except Exception as e:
            return {'error': f'Analysis failed: {e}'}

        # Compute key metrics
        pressures = results.get('pressures', {})
        flows = results.get('flows', {})
        compliance = results.get('compliance', [])

        p_vals = [p.get('avg_m', 0) for p in pressures.values()]
        v_vals = [f.get('max_velocity_ms', 0) for f in flows.values()]

        min_p = min(p_vals) if p_vals else 0
        max_p = max(p_vals) if p_vals else 0
        max_v = max(v_vals) if v_vals else 0

        wsaa_issues = sum(1 for c in compliance if c.get('type') in ('WARNING', 'CRITICAL'))

        # Get resilience and quality score
        ri = self.compute_resilience_index(results)
        qs = self.compute_quality_score(results)
        topo = self.analyse_topology()

        ri_val = ri.get('resilience_index', 0)
        qs_val = qs.get('total_score', 0)
        grade = qs.get('grade', '?')

        total_length_km = sum(
            self.wn.get_link(pid).length for pid in self.wn.pipe_name_list) / 1000
        total_demand_lps = sum(
            self.wn.get_node(jid).demand_timeseries_list[0].base_value * 1000
            for jid in self.wn.junction_name_list
            if self.wn.get_node(jid).demand_timeseries_list)

        # Build prose paragraph
        health_word = ('healthy' if qs_val >= 75 else
                       'adequate' if qs_val >= 60 else
                       'concerning' if qs_val >= 45 else 'poor')

        compliance_text = ('fully compliant' if wsaa_issues == 0
                          else f'has {wsaa_issues} WSAA compliance issue(s)')

        paragraph = (
            f"The network comprises {summary.get('junctions', 0)} junctions and "
            f"{summary.get('pipes', 0)} pipes totalling {total_length_km:.1f} km, "
            f"delivering {total_demand_lps:.1f} LPS total demand. "
            f"Current overall health is {health_word} "
            f"(quality score {qs_val:.0f}/100, grade {grade}). "
            f"The network {compliance_text}, with pressures ranging from "
            f"{min_p:.1f} m to {max_p:.1f} m and maximum pipe velocity of "
            f"{max_v:.2f} m/s. Network resilience (Todini index) is "
            f"{ri_val:.3f} ({ri.get('grade', '?')}), indicating "
            f"{ri.get('interpretation', 'unknown').lower()}"
        )

        if topo.get('dead_end_count', 0) > 0 or topo.get('bridge_count', 0) > 0:
            paragraph += (
                f" Topology: {topo.get('loops', 0)} independent loops, "
                f"{topo.get('dead_end_count', 0)} dead ends, "
                f"{topo.get('bridge_count', 0)} single-point-of-failure pipes."
            )

        # Top 3 recommendations
        recommendations = []
        if wsaa_issues > 0:
            recommendations.append(
                f'Address {wsaa_issues} WSAA compliance issue(s) as top priority')
        if ri_val < 0.3:
            recommendations.append(
                'Improve network redundancy — resilience below 0.3 target '
                '(add looping pipes where possible)')
        if topo.get('bridge_count', 0) > 0:
            recommendations.append(
                f'{topo["bridge_count"]} bridge pipes represent single points '
                f'of failure — consider parallel connections')
        if max_v > 2.0:
            recommendations.append(
                f'Peak velocity {max_v:.2f} m/s exceeds WSAA 2.0 m/s — upsize pipes')
        if min_p < 20:
            recommendations.append(
                f'Low pressure detected ({min_p:.1f} m) — consider booster or pipe upsize')

        if not recommendations:
            recommendations.append('Network performing well — continue monitoring')

        return {
            'summary_paragraph': paragraph,
            'recommendations': recommendations[:3],
            'metrics': {
                'quality_score': qs_val,
                'grade': grade,
                'resilience_index': ri_val,
                'min_pressure_m': round(min_p, 1),
                'max_pressure_m': round(max_p, 1),
                'max_velocity_ms': round(max_v, 2),
                'wsaa_issues': wsaa_issues,
                'total_length_km': round(total_length_km, 1),
                'total_demand_lps': round(total_demand_lps, 1),
            },
        }

    # =========================================================================
    # LEARNING MODE FOR GRADUATE ENGINEERS (O1)
    # =========================================================================

    def explain_analysis(self, results=None):
        """
        Generate educational explanations of analysis results for learning.

        Produces a tutorial-style walkthrough explaining WHY results are
        what they are, with references to hydraulic principles and
        Australian standards.

        Parameters
        ----------
        results : dict or None
            Steady-state results. If None, runs analysis first.

        Returns dict with lessons, explanations, and reference links.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        if results is None:
            try:
                results = self.run_steady_state(save_plot=False)
            except Exception as e:
                return {'error': f'Analysis failed: {e}'}

        pressures = results.get('pressures', {})
        flows = results.get('flows', {})

        lessons = []

        # Lesson 1: Pressure distribution
        if pressures:
            p_vals = [p.get('avg_m', 0) for p in pressures.values()]
            max_p = max(p_vals)
            min_p = min(p_vals)
            max_node = max(pressures, key=lambda k: pressures[k].get('avg_m', 0))
            min_node = min(pressures, key=lambda k: pressures[k].get('avg_m', 0))

            lessons.append({
                'topic': 'Pressure Distribution',
                'observation': f'Pressures range from {min_p:.1f} m at {min_node} to '
                               f'{max_p:.1f} m at {max_node}',
                'explanation': (
                    "Pressure at a node equals the total head (elevation + pressure head) "
                    "from the source, minus accumulated headloss along the flow path. "
                    "Higher elevation nodes have lower pressure. Nodes far from sources "
                    "lose pressure to friction (Hazen-Williams: hL = 10.67 × L × Q^1.852 / "
                    "(C^1.852 × D^4.87))."),
                'standard': 'WSAA WSA 03-2011 Table 3.1: 20-50 m residential target',
                'action': (
                    f'If {min_node} is below 20 m, consider: (1) larger pipes on '
                    'the critical path; (2) a booster pump; (3) raising reservoir '
                    'level. If above 50 m, add a PRV.'),
                'reference': 'WSAA WSA 03-2011 §3.2.1',
            })

        # Lesson 2: Pipe velocity
        if flows:
            v_vals = [f.get('max_velocity_ms', 0) for f in flows.values()]
            if v_vals:
                max_v = max(v_vals)
                max_v_pipe = max(flows, key=lambda k: flows[k].get('max_velocity_ms', 0))
                lessons.append({
                    'topic': 'Pipe Velocity',
                    'observation': f'Maximum velocity {max_v:.2f} m/s in pipe {max_v_pipe}',
                    'explanation': (
                        "Velocity = Q/A. High velocity causes erosion, noise, and large "
                        "headloss (headloss ∝ V^1.85 for Hazen-Williams). Low velocity "
                        "(< 0.6 m/s) allows sediment settling, especially for non-potable "
                        "or slurry lines."),
                    'standard': 'WSAA WSA 03-2011: max 2.0 m/s; min 0.6 m/s to prevent settling',
                    'action': (
                        'If velocity > 2.0 m/s, upsize pipe by one DN step. '
                        'If < 0.6 m/s, consider flushing program or smaller pipe.'),
                    'reference': 'WSAA WSA 03-2011 §3.2.3',
                })

        # Lesson 3: Headloss intensity
        if flows:
            hl_values = []
            for pid, f in flows.items():
                hl = f.get('headloss_m_per_km', None)
                if hl is not None:
                    hl_values.append((pid, hl))
            if hl_values:
                hl_values.sort(key=lambda x: x[1], reverse=True)
                worst_pipe, worst_hl = hl_values[0]
                lessons.append({
                    'topic': 'Headloss Intensity',
                    'observation': f'Highest headloss {worst_hl:.2f} m/km in pipe {worst_pipe}',
                    'explanation': (
                        "Headloss per km indicates hydraulic efficiency. Values above "
                        "10 m/km indicate undersized pipes. Values below 1 m/km may "
                        "indicate oversized pipes (capital inefficient)."),
                    'standard': 'Industry rule of thumb: 1-5 m/km optimal design range',
                    'action': (
                        'If > 10 m/km, upsize pipe. If < 1 m/km, pipe may be oversized '
                        'for current demand — check design horizon.'),
                    'reference': 'White, Fluid Mechanics 8th ed. Ch. 6',
                })

        # Lesson 4: WSAA compliance
        compliance = results.get('compliance', [])
        n_issues = len(compliance) if isinstance(compliance, list) else 0
        lessons.append({
            'topic': 'WSAA Compliance',
            'observation': f'{n_issues} compliance issues flagged',
            'explanation': (
                "WSAA WSA 03-2011 is the Australian design code. Non-compliance does "
                "not mean the network fails, but it signals deviations from accepted "
                "standards that must be justified in a design report."),
            'standard': 'WSAA WSA 03-2011 (full standard)',
            'action': (
                'Review each flagged issue. Document approved deviations in the '
                'design basis report with engineering justification.'),
            'reference': 'WSAA WSA 03-2011',
        })

        return {
            'n_lessons': len(lessons),
            'lessons': lessons,
            'note': (
                'Learning Mode explains what the numbers mean, why they matter, '
                'and what to do next — for graduate engineers building intuition.'),
        }

    # =========================================================================
    # O4 — OPERATIONS DASHBOARD
    # =========================================================================

    def operations_dashboard(self, results=None):
        """
        Produce an operator-focused snapshot of current network state.

        Returns the data an operations team wants on one screen:
        - Tank levels (fill %, turnover)
        - Pump status and duty
        - Critical pressure nodes (lowest 5, highest 5)
        - Active alerts (compliance violations)
        - KPIs: total demand, total supply, headloss

        Returns dict structured for a live dashboard view.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        if results is None:
            try:
                results = self.run_steady_state(save_plot=False)
            except Exception as e:
                return {'error': f'Analysis failed: {e}'}

        pressures = results.get('pressures', {})
        flows = results.get('flows', {})

        # Pressure sort
        p_sorted = sorted(
            [(nid, p.get('avg_m', 0)) for nid, p in pressures.items()],
            key=lambda x: x[1])
        lowest_5 = [{'node': n, 'pressure_m': round(p, 1)} for n, p in p_sorted[:5]]
        highest_5 = [{'node': n, 'pressure_m': round(p, 1)}
                     for n, p in p_sorted[-5:][::-1]]

        # Tanks
        tanks = []
        for tid in self.wn.tank_name_list:
            t = self.wn.get_node(tid)
            level = None
            try:
                level = float(t.init_level)
            except Exception:
                pass
            fill_pct = None
            try:
                span = float(t.max_level) - float(t.min_level)
                if span > 0:
                    fill_pct = round((level - float(t.min_level)) / span * 100, 1)
            except Exception:
                pass
            tanks.append({
                'id': tid,
                'level_m': round(level, 2) if level is not None else None,
                'fill_pct': fill_pct,
            })

        # Pumps
        pumps = []
        for pid in self.wn.pump_name_list:
            p = self.wn.get_link(pid)
            status_val = getattr(p, 'initial_status', None)
            status_str = str(status_val) if status_val is not None else 'Unknown'
            pumps.append({
                'id': pid,
                'status': status_str,
                'type': getattr(p, 'pump_type', 'POWER'),
            })

        # Alerts from compliance
        compliance = results.get('compliance', [])
        alerts = compliance if isinstance(compliance, list) else []

        # KPIs
        total_demand_lps = 0.0
        for jid in self.wn.junction_name_list:
            try:
                d = self.wn.get_node(jid).demand_timeseries_list[0].base_value
                total_demand_lps += d * 1000
            except (IndexError, AttributeError):
                pass

        total_headloss_m = 0.0
        for pid, f in flows.items():
            hl = f.get('headloss_m', 0)
            if hl:
                total_headloss_m += hl

        # Traffic-light status
        n_alerts = len(alerts)
        if n_alerts == 0:
            status_light = 'green'
        elif n_alerts <= 5:
            status_light = 'amber'
        else:
            status_light = 'red'

        return {
            'status_light': status_light,
            'kpis': {
                'total_demand_lps': round(total_demand_lps, 1),
                'total_headloss_m': round(total_headloss_m, 1),
                'n_junctions': len(self.wn.junction_name_list),
                'n_pipes': len(self.wn.pipe_name_list),
                'n_active_alerts': n_alerts,
            },
            'lowest_pressures': lowest_5,
            'highest_pressures': highest_5,
            'tanks': tanks,
            'pumps': pumps,
            'alerts': alerts[:10],
            'note': 'Operations snapshot — refresh after each steady-state run.',
        }

    # =========================================================================
    # O5 — AUTOMATED NETWORK DOCUMENTATION
    # =========================================================================

    def generate_network_documentation(self):
        """
        Auto-generate a Markdown description of the network.

        Produces a design-basis document suitable for engineering review:
        - Network inventory (junctions, tanks, reservoirs, pipes, pumps, valves)
        - Size distribution
        - Material distribution (if known)
        - Topology summary
        - Operating assumptions

        Returns dict with 'markdown' string ready to write to .md file.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        wn = self.wn
        n_junc = len(wn.junction_name_list)
        n_tank = len(wn.tank_name_list)
        n_res = len(wn.reservoir_name_list)
        n_pipe = len(wn.pipe_name_list)
        n_pump = len(wn.pump_name_list)
        n_valve = len(wn.valve_name_list)

        # Pipe size distribution
        dn_counts = {}
        total_length = 0.0
        for pid in wn.pipe_name_list:
            p = wn.get_link(pid)
            dn = int(round(p.diameter * 1000))  # m → mm
            dn_counts[dn] = dn_counts.get(dn, 0) + 1
            total_length += p.length

        # Elevation range
        elevs = []
        for jid in wn.junction_name_list:
            try:
                elevs.append(wn.get_node(jid).elevation)
            except Exception:
                pass
        elev_min = min(elevs) if elevs else 0
        elev_max = max(elevs) if elevs else 0

        # Build markdown
        lines = []
        lines.append(f'# Network Documentation — {wn.name or "Unnamed"}')
        lines.append('')
        lines.append('## 1. Inventory')
        lines.append('')
        lines.append('| Asset | Count |')
        lines.append('|-------|-------|')
        lines.append(f'| Junctions | {n_junc} |')
        lines.append(f'| Tanks | {n_tank} |')
        lines.append(f'| Reservoirs | {n_res} |')
        lines.append(f'| Pipes | {n_pipe} |')
        lines.append(f'| Pumps | {n_pump} |')
        lines.append(f'| Valves | {n_valve} |')
        lines.append('')
        lines.append(f'Total pipe length: **{total_length / 1000:.2f} km**')
        lines.append('')
        lines.append('## 2. Elevation')
        lines.append('')
        lines.append(f'- Minimum: {elev_min:.1f} m AHD')
        lines.append(f'- Maximum: {elev_max:.1f} m AHD')
        lines.append(f'- Range: {elev_max - elev_min:.1f} m')
        lines.append('')
        lines.append('## 3. Pipe Size Distribution')
        lines.append('')
        lines.append('| DN (mm) | Count |')
        lines.append('|---------|-------|')
        for dn in sorted(dn_counts):
            lines.append(f'| {dn} | {dn_counts[dn]} |')
        lines.append('')
        lines.append('## 4. Design Standards')
        lines.append('')
        lines.append('- WSAA WSA 03-2011 (Water Supply Code)')
        lines.append(f'- Minimum pressure: {self.DEFAULTS["min_pressure_m"]} m head')
        lines.append(f'- Maximum pressure: {self.DEFAULTS["max_pressure_m"]} m head')
        lines.append(f'- Maximum velocity: {self.DEFAULTS["max_velocity_ms"]} m/s')
        lines.append(f'- Minimum velocity: {self.DEFAULTS["min_velocity_ms"]} m/s')
        lines.append('')
        lines.append('## 5. Notes')
        lines.append('')
        lines.append('Auto-generated by EPANET Toolkit. Review all assumptions before '
                     'issuing for construction.')
        lines.append('')

        markdown = '\n'.join(lines)
        return {
            'markdown': markdown,
            'n_sections': 5,
            'total_length_km': round(total_length / 1000, 2),
            'elevation_range_m': round(elev_max - elev_min, 1),
            'n_pipe_sizes': len(dn_counts),
        }

    # =========================================================================
    # O9 — ENGINEERING KNOWLEDGE BASE
    # =========================================================================

    KNOWLEDGE_BASE = {
        'hazen_williams': {
            'topic': 'Hazen-Williams Headloss',
            'formula': 'hL = 10.67 × L × Q^1.852 / (C^1.852 × D^4.87)',
            'units': 'hL (m), L (m), Q (m³/s), D (m)',
            'applies_to': 'Turbulent water flow, DN ≥ 50 mm, common civil use',
            'limitations': 'Only valid for water at ~15°C; poor for non-water fluids',
            'reference': 'Williams & Hazen (1920); cited WSAA WSA 03-2011',
        },
        'darcy_weisbach': {
            'topic': 'Darcy-Weisbach Headloss',
            'formula': 'hL = f × (L/D) × V² / (2g)',
            'units': 'hL (m), L (m), D (m), V (m/s), g (9.81 m/s²)',
            'applies_to': 'Any Newtonian fluid, all Re regimes, more rigorous',
            'limitations': 'Requires friction factor (Colebrook-White iteration)',
            'reference': 'White, Fluid Mechanics 8th ed. Ch. 6',
        },
        'joukowsky': {
            'topic': 'Joukowsky Surge Pressure',
            'formula': 'ΔP = ρ × a × ΔV',
            'units': 'ΔP (Pa), ρ (kg/m³), a (m/s wave speed), ΔV (m/s)',
            'applies_to': 'Rapid valve closure, pump trip — instantaneous change',
            'limitations': 'Upper bound; real surges include reflections, friction',
            'reference': 'Joukowsky (1898); Wylie & Streeter, Fluid Transients',
        },
        'lamont_break_rate': {
            'topic': 'Lamont Pipe Break Rate',
            'formula': 'N(t) = N₀ × exp(A × (t - t₀))',
            'units': 'breaks/km/year',
            'applies_to': 'Mains rehabilitation planning, deterioration modelling',
            'limitations': 'Material-specific coefficients; calibrate locally',
            'reference': 'Lamont (1981) AWWA Journal 73(5)',
        },
        'wsaa_min_pressure': {
            'topic': 'WSAA Minimum Service Pressure',
            'value': '20 m head',
            'applies_to': 'Residential reticulation at meter',
            'reference': 'WSAA WSA 03-2011 §3.2.1 Table 3.1',
        },
        'wsaa_max_pressure': {
            'topic': 'WSAA Maximum Service Pressure',
            'value': '50 m head (residential); 80 m (commercial/industrial)',
            'applies_to': 'Static pressure limit to protect fittings',
            'reference': 'WSAA WSA 03-2011 §3.2.1',
        },
        'wsaa_max_velocity': {
            'topic': 'WSAA Maximum Pipe Velocity',
            'value': '2.0 m/s',
            'applies_to': 'Peak demand steady-state design',
            'limitations': 'Higher values allowed in fire flow / emergency',
            'reference': 'WSAA WSA 03-2011 §3.2.3',
        },
        'fire_flow': {
            'topic': 'Fire Flow Residual Pressure',
            'value': '12 m residual at 25 L/s at remotest hydrant',
            'applies_to': 'Residential fire-fighting capacity',
            'reference': 'WSAA WSA 03-2011 §3.4',
        },
        'as2280_ductile_iron': {
            'topic': 'Ductile Iron Pipe (DICL)',
            'pn_ratings': 'PN25, PN35',
            'c_factor_new': '140',
            'c_factor_aged': '120',
            'wave_speed': '1100 m/s minimum',
            'reference': 'AS 2280',
        },
        'as1477_pvc': {
            'topic': 'PVC Pipe',
            'pn_ratings': 'PN12, PN18',
            'c_factor': '145-150',
            'od_series': 'OD ≠ DN — DN100→110, DN150→160, DN200→225',
            'reference': 'AS/NZS 1477',
        },
        'as4130_pe': {
            'topic': 'PE/HDPE Pipe',
            'pn_ratings': 'SDR11 PN16',
            'c_factor': '140-150',
            'design_stress_short_term': '20-22 MPa (PE100)',
            'reference': 'AS/NZS 4130',
        },
        'bingham_plastic': {
            'topic': 'Bingham Plastic Slurry',
            'formula': 'τ = τy + μp × (dV/dy)',
            'applies_to': 'High-concentration mineral slurries',
            'laminar_friction': 'Use Darcy f = 64/Re_B (NEVER Fanning 16/Re_B)',
            'reference': 'Wasp, Kenny & Gandhi (1977)',
        },
    }

    def knowledge_base(self, topic=None):
        """
        Query the built-in hydraulic engineering knowledge base.

        Parameters
        ----------
        topic : str or None
            Specific topic key (e.g. 'hazen_williams', 'joukowsky',
            'wsaa_min_pressure'). If None, returns full index.

        Returns dict with formula, units, limitations, and standard reference.
        """
        if topic is None:
            return {
                'topics': sorted(self.KNOWLEDGE_BASE.keys()),
                'n_topics': len(self.KNOWLEDGE_BASE),
                'note': 'Call knowledge_base(topic="<key>") for details.',
            }

        if topic not in self.KNOWLEDGE_BASE:
            return {
                'error': f'Unknown topic: {topic}',
                'available_topics': sorted(self.KNOWLEDGE_BASE.keys()),
            }

        entry = dict(self.KNOWLEDGE_BASE[topic])
        entry['topic_key'] = topic
        return entry

    def search_knowledge_base(self, query):
        """
        Keyword search over the knowledge base.

        Parameters
        ----------
        query : str
            Text to match against topic, formula, or content

        Returns list of matching entries.
        """
        if not query:
            return {'matches': [], 'n_matches': 0}

        q = query.lower()
        matches = []
        for key, entry in self.KNOWLEDGE_BASE.items():
            haystack = ' '.join(str(v).lower() for v in entry.values())
            haystack += ' ' + key.lower()
            if q in haystack:
                matches.append({'topic_key': key, **entry})

        return {'matches': matches, 'n_matches': len(matches), 'query': query}

    # =========================================================================
    # O10 — PERFORMANCE PROFILING FOR LARGE NETWORKS
    # =========================================================================

    def performance_profile(self):
        """
        Profile the loaded network for size and suggest optimisations.

        Returns performance metrics, identifies potential bottlenecks, and
        recommends model reduction strategies (skeletonisation, clustering)
        for networks that are slow to solve or hard to visualise.

        Returns dict with metrics, bottleneck candidates, and recommendations.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        import time as _time

        wn = self.wn
        n_junc = len(wn.junction_name_list)
        n_pipe = len(wn.pipe_name_list)
        n_pump = len(wn.pump_name_list)
        n_valve = len(wn.valve_name_list)
        n_tank = len(wn.tank_name_list)
        n_total_nodes = n_junc + n_tank + len(wn.reservoir_name_list)

        # Size category
        if n_total_nodes < 100:
            size_category = 'small'
        elif n_total_nodes < 1000:
            size_category = 'medium'
        elif n_total_nodes < 10000:
            size_category = 'large'
        else:
            size_category = 'very_large'

        # Short-pipe candidates (for skeletonisation)
        short_pipes = []
        tiny_diameter_pipes = []
        for pid in wn.pipe_name_list:
            p = wn.get_link(pid)
            if p.length < 10.0:
                short_pipes.append(pid)
            if p.diameter * 1000 < 50:  # DN < 50 mm
                tiny_diameter_pipes.append(pid)

        # Dead-end junctions (degree 1)
        degree = {jid: 0 for jid in wn.junction_name_list}
        for pid in wn.pipe_name_list:
            p = wn.get_link(pid)
            if p.start_node_name in degree:
                degree[p.start_node_name] += 1
            if p.end_node_name in degree:
                degree[p.end_node_name] += 1
        dead_ends = [j for j, d in degree.items() if d == 1]
        series_nodes = [j for j, d in degree.items() if d == 2]

        # Time a single steady-state run
        solve_time_s = None
        try:
            t0 = _time.perf_counter()
            self.run_steady_state(save_plot=False)
            solve_time_s = round(_time.perf_counter() - t0, 3)
        except Exception:
            pass

        recommendations = []
        if size_category in ('large', 'very_large'):
            recommendations.append(
                f'Network has {n_total_nodes} nodes — consider skeletonising '
                f'pipes < 50 mm diameter ({len(tiny_diameter_pipes)} candidates) '
                f'using api.skeletonise().')
        if len(short_pipes) > 10:
            recommendations.append(
                f'{len(short_pipes)} pipes are < 10 m long. Merging these '
                f'with adjacent pipes reduces solve time without loss of accuracy.')
        if len(series_nodes) > n_junc * 0.3:
            recommendations.append(
                f'{len(series_nodes)} junctions are series nodes (degree 2). '
                f'Merging series pipes can reduce model size by ~30%.')
        if solve_time_s is not None and solve_time_s > 5.0:
            recommendations.append(
                f'Steady-state solve took {solve_time_s}s. For iterative '
                f'analysis (calibration, Monte Carlo) consider skeletonisation '
                f'to cut runtime by 5-20x.')
        if not recommendations:
            recommendations.append(
                'Network size is manageable — no optimisation required.')

        return {
            'size_category': size_category,
            'metrics': {
                'n_junctions': n_junc,
                'n_pipes': n_pipe,
                'n_pumps': n_pump,
                'n_valves': n_valve,
                'n_tanks': n_tank,
                'n_total_nodes': n_total_nodes,
                'n_dead_ends': len(dead_ends),
                'n_series_nodes': len(series_nodes),
                'n_short_pipes_lt_10m': len(short_pipes),
                'n_tiny_diameter_pipes_lt_50mm': len(tiny_diameter_pipes),
                'steady_state_solve_time_s': solve_time_s,
            },
            'recommendations': recommendations,
            'note': (
                'Use api.skeletonise() to merge series pipes and drop small '
                'branches. Validate skeletonised model against full model '
                'before using in design.'),
        }

    # =========================================================================
    # SAFETY CASE REPORT — formal regulatory submission (Innovation #2)
    # =========================================================================

    def safety_case_report(self, wave_speed_ms=1100, valve_closure_s=0.5,
                           max_transient_pressure_m=150.0,
                           slurry_critical_velocity_ms=None):
        """
        Generate a formal Safety Case Report for regulatory submission.

        Assesses pipeline failure risk with explicit margins:
          - Steady-state pressure/velocity compliance
          - Transient surge adequacy (worst-case Joukowsky)
          - Water hammer worst-case scenario
          - Slurry settling risk (critical velocity margin) — if applicable
        All outputs cite the relevant Australian Standard and include
        pass/fail margins (not just pass/fail).

        Parameters
        ----------
        wave_speed_ms : float
            Wave speed for surge calculation (AS 2280 default 1100 m/s)
        valve_closure_s : float
            Worst-case (instantaneous) valve closure time
        max_transient_pressure_m : float
            Maximum allowable transient pressure (PN rating in m head)
        slurry_critical_velocity_ms : float or None
            If set, performs slurry settling margin check per pipe

        Returns dict suitable for formal regulatory PDF submission.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        from datetime import datetime, timezone
        import hashlib

        # Network hash for audit trail — reads the .inp file if present
        network_hash = None
        if self._inp_file and os.path.exists(self._inp_file):
            try:
                with open(self._inp_file, 'rb') as f:
                    network_hash = hashlib.sha256(f.read()).hexdigest()
            except Exception:
                network_hash = None

        report = {
            'title': 'Pipeline Safety Case Report',
            'network': (self._inp_file or 'Unnamed network'),
            'network_sha256': network_hash,
            'issued': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'issued_utc_iso8601': datetime.now(timezone.utc).isoformat(),
            'software_version': getattr(self, 'SOFTWARE_VERSION', 'unknown'),
            'sections': [],
            'overall_verdict': 'APPROVED',
            'verdict_reasons': [],
        }

        # Steady-state compliance
        try:
            steady = self.run_steady_state(save_plot=False)
        except Exception as e:
            return {'error': f'Steady-state solve failed: {e}. '
                             f'Fix: Check network connectivity and demand balance.'}

        pressures = steady.get('pressures', {})
        flows = steady.get('flows', {})
        p_min = min((p.get('min_m', 0) for p in pressures.values()),
                    default=0)
        p_max = max((p.get('max_m', 0) for p in pressures.values()),
                    default=0)
        v_max = max((f.get('max_velocity_ms', 0) for f in flows.values()),
                    default=0)

        wsaa_p_min = self.DEFAULTS['min_pressure_m']
        wsaa_p_max = self.DEFAULTS['max_pressure_m']
        wsaa_v_max = self.DEFAULTS['max_velocity_ms']

        s1 = {
            'section': '1. Steady-State Compliance',
            'standard': 'WSAA WSA 03-2011 Table 3.1',
            'checks': [
                {'item': 'Minimum service pressure',
                 'measured': f'{p_min:.1f} m',
                 'limit': f'>= {wsaa_p_min} m',
                 'margin': f'{p_min - wsaa_p_min:+.1f} m',
                 'status': 'PASS' if p_min >= wsaa_p_min else 'FAIL'},
                {'item': 'Maximum static pressure',
                 'measured': f'{p_max:.1f} m',
                 'limit': f'<= {wsaa_p_max} m',
                 'margin': f'{wsaa_p_max - p_max:+.1f} m',
                 'status': 'PASS' if p_max <= wsaa_p_max else 'FAIL'},
                {'item': 'Maximum pipe velocity',
                 'measured': f'{v_max:.2f} m/s',
                 'limit': f'<= {wsaa_v_max} m/s',
                 'margin': f'{wsaa_v_max - v_max:+.2f} m/s',
                 'status': 'PASS' if v_max <= wsaa_v_max else 'FAIL'},
            ],
            'overall': ('PASS' if all([p_min >= wsaa_p_min,
                                        p_max <= wsaa_p_max,
                                        v_max <= wsaa_v_max])
                        else 'FAIL'),
        }
        report['sections'].append(s1)
        if s1['overall'] == 'FAIL':
            report['verdict_reasons'].append('Steady-state compliance FAIL')

        # Worst-case Joukowsky surge
        surge_head = wave_speed_ms * v_max / 9.81
        peak_transient_m = p_max + surge_head
        surge_margin_m = max_transient_pressure_m - peak_transient_m

        s2 = {
            'section': '2. Worst-Case Transient (Joukowsky)',
            'standard': 'AS 2200; Wylie & Streeter Fluid Transients',
            'assumptions': {
                'wave_speed_ms': wave_speed_ms,
                'trigger_velocity_ms': round(v_max, 3),
                'closure_scenario': 'instantaneous (upper bound)',
            },
            'checks': [
                {'item': 'Surge head rise (Joukowsky)',
                 'measured': f'{surge_head:.1f} m',
                 'formula': 'dH = a x dV / g',
                 'status': 'INFO'},
                {'item': 'Peak transient pressure',
                 'measured': f'{peak_transient_m:.1f} m',
                 'limit': f'<= {max_transient_pressure_m:.0f} m (PN rating)',
                 'margin': f'{surge_margin_m:+.1f} m',
                 'status': 'PASS' if surge_margin_m >= 0 else 'FAIL'},
            ],
            'overall': 'PASS' if surge_margin_m >= 0 else 'FAIL',
        }
        report['sections'].append(s2)
        if s2['overall'] == 'FAIL':
            report['verdict_reasons'].append(
                'Transient pressure exceeds PN rating')

        # Water hammer mitigation adequacy
        max_pipe_length = max(
            (self.wn.get_link(pid).length
             for pid in self.wn.pipe_name_list), default=0)
        critical_period_s = 2 * max_pipe_length / wave_speed_ms
        closure_adequate = valve_closure_s >= critical_period_s

        s3 = {
            'section': '3. Water Hammer Mitigation',
            'standard': 'AS 2200; TSNet transient analysis',
            'checks': [
                {'item': 'Longest pipe length (critical path)',
                 'measured': f'{max_pipe_length:.0f} m',
                 'status': 'INFO'},
                {'item': 'Critical period 2L/a',
                 'measured': f'{critical_period_s:.2f} s',
                 'status': 'INFO'},
                {'item': 'Valve closure time vs critical period',
                 'measured': f'{valve_closure_s:.2f} s',
                 'limit': f'>= {critical_period_s:.2f} s for slow closure',
                 'margin': f'{valve_closure_s - critical_period_s:+.2f} s',
                 'status': ('PASS' if closure_adequate
                            else 'REVIEW - rapid closure; surge protection required')},
            ],
            'overall': 'PASS' if closure_adequate else 'REVIEW',
        }
        report['sections'].append(s3)
        if not closure_adequate:
            report['verdict_reasons'].append(
                'Valve closure is within critical period - surge '
                'protection (accumulator, bypass, or slow-close valve) '
                'must be installed')

        # Slurry settling risk (optional)
        if slurry_critical_velocity_ms is not None:
            settling_issues = []
            for pid, f in flows.items():
                v = f.get('max_velocity_ms', 0)
                margin = v - slurry_critical_velocity_ms
                if margin < 0:
                    settling_issues.append({
                        'pipe': pid,
                        'velocity_ms': round(v, 2),
                        'critical_ms': slurry_critical_velocity_ms,
                        'margin_ms': round(margin, 2),
                    })
            s4 = {
                'section': '4. Slurry Settling Risk',
                'standard': 'Durand (1952); Wilson/Addie/Clift (2006)',
                'critical_velocity_ms': slurry_critical_velocity_ms,
                'n_pipes_below_critical': len(settling_issues),
                'issues': settling_issues[:20],
                'overall': 'PASS' if not settling_issues else 'FAIL',
            }
            report['sections'].append(s4)
            if settling_issues:
                report['verdict_reasons'].append(
                    f'{len(settling_issues)} pipes below critical '
                    f'deposition velocity - sediment accumulation risk')

        # Verdict
        if report['verdict_reasons']:
            if any('FAIL' in r or 'exceeds' in r or 'critical' in r
                    for r in report['verdict_reasons']):
                report['overall_verdict'] = 'NOT APPROVED'
            else:
                report['overall_verdict'] = 'CONDITIONAL APPROVAL'

        # Explicit documentation of model assumptions for regulatory review
        report['assumptions'] = [
            {'item': 'Joukowsky head rise',
             'formula': 'dH = a x dV / g',
             'note': 'Density-independent for head-based pressure; for '
                     'slurry PRESSURE units use rho_slurry x a x dV.'},
            {'item': 'Critical period 2L/a',
             'note': 'Assumes rigid pipe wave speed. For PVC/PE the '
                     'effective wave speed is lower (pipe compliance), '
                     'so 2L/a here is CONSERVATIVE - real critical '
                     'period on flexible pipe will be longer.'},
            {'item': 'Wave speed',
             'value_ms': wave_speed_ms,
             'note': 'AS 2280 default 1100 m/s for ductile iron. '
                     'PVC ~450 m/s, PE ~250-400 m/s.'},
            {'item': 'Pressure units',
             'note': 'All pressures in m head (water gauge). Convert '
                     'to kPa via P_kPa = rho x g x H / 1000.'},
        ]

        report['signature_block'] = {
            'prepared_by': 'EPANET Hydraulic Analysis Toolkit',
            'reviewer': '(sign here)',
            'date': '(sign here)',
            'is_digitally_signed': False,
            'disclaimer': (
                'Safety Case auto-generated from model inputs. Requires '
                'review by a Chartered/RPEQ engineer prior to submission. '
                'Model assumptions must be validated against field data. '
                'Rigid-pipe wave speed assumption is conservative; '
                'validate against manufacturer data for PVC/PE lines. '
                'Signature block is visual only - not cryptographically '
                'signed. For legally binding compliance case, obtain '
                'engineer wet signature or digital certificate.'),
        }

        return report

    # =========================================================================
    # R6 — NETWORK VALIDITY CHECKER
    # =========================================================================

    def validate_network(self):
        """
        Pre-analysis network validation. Catches common modelling errors
        before running steady-state.

        Checks:
          - Isolated nodes (degree 0)
          - Zero-length pipes
          - Zero-diameter pipes
          - Negative elevations (unusual — flag for review)
          - Missing source (no reservoir or tank)
          - Duplicate IDs (WNTR would already reject these on load)
          - Disconnected subgraphs (more than one connected component)
          - Pumps with no curve
          - Pipes referencing non-existent nodes (WNTR would reject these)

        Returns dict with per-check results and overall valid/invalid verdict.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        issues = []
        warnings = []
        wn = self.wn

        # Source presence
        if not wn.reservoir_name_list and not wn.tank_name_list:
            issues.append({
                'type': 'no_source',
                'severity': 'ERROR',
                'message': 'Network has no reservoir or tank. Fix: add at '
                           'least one reservoir (fixed head) or tank.',
            })

        # Zero-length / zero-diameter pipes
        zero_len, zero_dia = [], []
        for pid in wn.pipe_name_list:
            p = wn.get_link(pid)
            if p.length <= 0:
                zero_len.append(pid)
            if p.diameter <= 0:
                zero_dia.append(pid)
        if zero_len:
            issues.append({
                'type': 'zero_length_pipe',
                'severity': 'ERROR',
                'pipes': zero_len,
                'message': f'{len(zero_len)} pipes have zero length. Fix: '
                           f'set length > 0 via api.update_pipe(pipe_id, '
                           f'length=...).',
            })
        if zero_dia:
            issues.append({
                'type': 'zero_diameter_pipe',
                'severity': 'ERROR',
                'pipes': zero_dia,
                'message': f'{len(zero_dia)} pipes have zero diameter. Fix: '
                           f'set diameter (mm) via api.update_pipe(pipe_id, '
                           f'diameter=...).',
            })

        # Node degree + connectivity (undirected)
        degree = {nid: 0 for nid in wn.node_name_list}
        adjacency = {nid: set() for nid in wn.node_name_list}
        for pid in wn.pipe_name_list + wn.pump_name_list + wn.valve_name_list:
            link = wn.get_link(pid)
            s = link.start_node_name
            e = link.end_node_name
            if s in degree:
                degree[s] += 1
                adjacency[s].add(e)
            if e in degree:
                degree[e] += 1
                adjacency[e].add(s)

        isolated = [n for n, d in degree.items() if d == 0]
        if isolated:
            issues.append({
                'type': 'isolated_node',
                'severity': 'ERROR',
                'nodes': isolated,
                'message': f'{len(isolated)} nodes are not connected to any '
                           f'link. Fix: add a pipe to connect them, or '
                           f'remove via api.remove_node(node_id).',
            })

        # Connected component count via BFS
        visited = set()
        components = 0
        for start in wn.node_name_list:
            if start in visited or start in isolated:
                continue
            components += 1
            stack = [start]
            while stack:
                n = stack.pop()
                if n in visited:
                    continue
                visited.add(n)
                for neighbour in adjacency.get(n, ()):
                    if neighbour not in visited:
                        stack.append(neighbour)

        if components > 1:
            issues.append({
                'type': 'disconnected_subgraphs',
                'severity': 'ERROR',
                'count': components,
                'message': f'Network has {components} disconnected '
                           f'subgraphs. Fix: add pipes to link them, or '
                           f'analyse each separately.',
            })

        # Negative elevations — warn only
        neg_elev = []
        for jid in wn.junction_name_list:
            try:
                e = wn.get_node(jid).elevation
                if e < 0:
                    neg_elev.append({'node': jid, 'elevation_m': e})
            except Exception:
                pass
        if neg_elev:
            warnings.append({
                'type': 'negative_elevation',
                'severity': 'WARN',
                'nodes': neg_elev[:10],
                'count': len(neg_elev),
                'message': f'{len(neg_elev)} junctions have negative '
                           f'elevation. This is unusual — confirm datum '
                           f'(m AHD vs m below datum).',
            })

        # Pumps with no curve (POWER pumps are fine)
        bad_pumps = []
        for pmp_id in wn.pump_name_list:
            try:
                p = wn.get_link(pmp_id)
                if getattr(p, 'pump_type', '') == 'HEAD':
                    if getattr(p, 'pump_curve_name', None) is None:
                        bad_pumps.append(pmp_id)
            except Exception:
                pass
        if bad_pumps:
            issues.append({
                'type': 'pump_no_curve',
                'severity': 'ERROR',
                'pumps': bad_pumps,
                'message': f'{len(bad_pumps)} HEAD-type pumps missing curve. '
                           f'Fix: assign a pump curve, or switch to '
                           f'POWER pump type.',
            })

        # Duplicate IDs — WNTR rejects on load, but guard anyway
        all_ids = (wn.node_name_list + wn.pipe_name_list +
                   wn.pump_name_list + wn.valve_name_list)
        seen = set()
        dupes = set()
        for i in all_ids:
            if i in seen:
                dupes.add(i)
            seen.add(i)
        if dupes:
            issues.append({
                'type': 'duplicate_id',
                'severity': 'ERROR',
                'ids': sorted(dupes),
                'message': f'{len(dupes)} IDs are reused across nodes/links. '
                           f'Fix: rename duplicates — EPANET requires '
                           f'globally unique IDs.',
            })

        n_errors = sum(1 for i in issues if i['severity'] == 'ERROR')
        n_warnings = len(warnings)

        return {
            'is_valid': n_errors == 0,
            'n_errors': n_errors,
            'n_warnings': n_warnings,
            'errors': issues,
            'warnings': warnings,
            'inventory': {
                'nodes': len(wn.node_name_list),
                'pipes': len(wn.pipe_name_list),
                'pumps': len(wn.pump_name_list),
                'valves': len(wn.valve_name_list),
                'connected_components': components,
            },
            'note': (
                'Run validate_network() before run_steady_state() to catch '
                'common modelling errors early.'),
        }

    # =========================================================================
    # R5 — GIS EXPORT (GeoJSON)
    # =========================================================================

    def export_geojson(self, output_path, include_results=True, results=None):
        """
        Export the network to GeoJSON for GIS integration.

        Nodes become Point features, pipes become LineString features.
        If steady-state results are available and include_results=True,
        feature properties include pressure (nodes) and velocity/flow
        (pipes) plus WSAA compliance status.

        Parameters
        ----------
        output_path : str
            Destination .geojson path
        include_results : bool
            If True and steady-state results exist, attach them to features

        Returns dict with feature counts and output path. Shapely is NOT
        required — this uses pure JSON.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        import json as _json

        # If caller didn't pass a results dict, run steady-state now
        # to get a fresh results dict (self.steady_results holds the
        # raw WNTR object, not the API dict form).
        if include_results and results is None:
            try:
                results = self.run_steady_state(save_plot=False)
            except Exception:
                results = {}
        results = results if (include_results and isinstance(results, dict)) else {}
        pressures = results.get('pressures', {})
        flows = results.get('flows', {})

        wn = self.wn
        features = []

        wsaa_p_min = self.DEFAULTS['min_pressure_m']
        wsaa_p_max = self.DEFAULTS['max_pressure_m']
        wsaa_v_max = self.DEFAULTS['max_velocity_ms']

        # Node features
        for nid in wn.node_name_list:
            node = wn.get_node(nid)
            coords = getattr(node, 'coordinates', None)
            if coords is None:
                continue
            # Determine node kind
            if nid in wn.junction_name_list:
                kind = 'junction'
                elev = float(getattr(node, 'elevation', 0) or 0)
            elif nid in wn.reservoir_name_list:
                kind = 'reservoir'
                elev = float(getattr(node, 'base_head', 0) or 0)
            elif nid in wn.tank_name_list:
                kind = 'tank'
                elev = float(getattr(node, 'elevation', 0) or 0)
            else:
                kind = 'node'
                elev = 0.0

            props = {
                'id': nid,
                'type': kind,
                'elevation_m': round(elev, 2),
            }

            if nid in pressures:
                p_info = pressures[nid]
                p_avg = p_info.get('avg_m', 0)
                props['pressure_m'] = round(p_avg, 2)
                if kind == 'junction':
                    if p_avg < wsaa_p_min:
                        props['wsaa_status'] = 'FAIL_LOW'
                    elif p_avg > wsaa_p_max:
                        props['wsaa_status'] = 'FAIL_HIGH'
                    else:
                        props['wsaa_status'] = 'PASS'

            features.append({
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [float(coords[0]), float(coords[1])],
                },
                'properties': props,
            })

        # Pipe features
        for pid in wn.pipe_name_list:
            pipe = wn.get_link(pid)
            try:
                start_xy = wn.get_node(pipe.start_node_name).coordinates
                end_xy = wn.get_node(pipe.end_node_name).coordinates
            except Exception:
                continue
            if start_xy is None or end_xy is None:
                continue

            props = {
                'id': pid,
                'start': pipe.start_node_name,
                'end': pipe.end_node_name,
                'length_m': round(pipe.length, 1),
                'diameter_mm': int(round(pipe.diameter * 1000)),
                'roughness': round(pipe.roughness, 1),
            }

            if pid in flows:
                f_info = flows[pid]
                v_max = f_info.get('max_velocity_ms', 0)
                q_avg = f_info.get('avg_lps', 0)
                props['velocity_ms'] = round(v_max, 3)
                props['flow_lps'] = round(q_avg, 2)
                props['wsaa_status'] = ('FAIL' if v_max > wsaa_v_max
                                         else 'PASS')

            features.append({
                'type': 'Feature',
                'geometry': {
                    'type': 'LineString',
                    'coordinates': [
                        [float(start_xy[0]), float(start_xy[1])],
                        [float(end_xy[0]), float(end_xy[1])],
                    ],
                },
                'properties': props,
            })

        collection = {
            'type': 'FeatureCollection',
            'name': os.path.basename(self._inp_file or 'network'),
            'crs': {
                'type': 'name',
                'properties': {'name': 'urn:ogc:def:crs:EPSG::0'},
            },
            'features': features,
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            _json.dump(collection, f, indent=2)

        n_nodes = sum(1 for feat in features
                      if feat['geometry']['type'] == 'Point')
        n_pipes = sum(1 for feat in features
                      if feat['geometry']['type'] == 'LineString')

        return {
            'output_path': output_path,
            'n_features': len(features),
            'n_node_features': n_nodes,
            'n_pipe_features': n_pipes,
            'note': ('GeoJSON uses the .inp coordinate system (no reprojection). '
                     'Set the CRS explicitly in your GIS tool if needed.'),
        }

    # =========================================================================
    # I5 — ROOT CAUSE ANALYSIS
    # =========================================================================

    def root_cause_analysis(self, results=None, max_issues=10):
        """
        For each WSAA violation, trace the hydraulic root cause and
        suggest prioritised fixes with estimated costs.

        Parameters
        ----------
        results : dict or None
            Steady-state results. If None, runs analysis.
        max_issues : int
            Maximum number of violations to explain in detail.

        Returns dict with per-violation explanations and ranked fixes.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        if results is None:
            try:
                results = self.run_steady_state(save_plot=False)
            except Exception as e:
                return {'error': f'Analysis failed: {e}. '
                                 f'Fix: Run validate_network() to diagnose.'}

        pressures = results.get('pressures', {})
        flows = results.get('flows', {})

        wsaa_p_min = self.DEFAULTS['min_pressure_m']
        wsaa_p_max = self.DEFAULTS['max_pressure_m']
        wsaa_v_max = self.DEFAULTS['max_velocity_ms']

        wn = self.wn

        # Build adjacency so we can trace paths from source
        pipe_at_node = {nid: [] for nid in wn.node_name_list}
        for pid in wn.pipe_name_list:
            p = wn.get_link(pid)
            pipe_at_node[p.start_node_name].append(pid)
            pipe_at_node[p.end_node_name].append(pid)

        # Standard DN upsize ladder (mm)
        DN_LADDER = [50, 75, 100, 150, 200, 250, 300, 375, 450, 525, 600,
                     675, 750, 900, 1050, 1200]
        COST_PER_M_BY_DN = {
            50: 85, 75: 110, 100: 140, 150: 180, 200: 230, 250: 290,
            300: 360, 375: 440, 450: 530, 525: 620, 600: 720, 675: 820,
            750: 920, 900: 1150, 1050: 1400, 1200: 1700,
        }

        def _next_dn(dn_mm):
            for step in DN_LADDER:
                if step > dn_mm:
                    return step
            return dn_mm

        def _cost(length_m, dn_mm):
            unit = COST_PER_M_BY_DN.get(dn_mm, 200)
            return int(round(length_m * unit))

        explanations = []

        # Collect and sort low-pressure junctions
        low_p = sorted(
            [(n, p.get('avg_m', 0)) for n, p in pressures.items()
             if p.get('avg_m', 1e9) < wsaa_p_min],
            key=lambda x: x[1])

        for node_id, p_m in low_p[:max_issues]:
            # Find highest-headloss pipe connected to this node
            worst_pipe = None
            worst_v = 0
            for pid in pipe_at_node.get(node_id, []):
                v = flows.get(pid, {}).get('max_velocity_ms', 0)
                if v > worst_v:
                    worst_v = v
                    worst_pipe = pid

            fixes = []
            if worst_pipe:
                pipe_obj = wn.get_link(worst_pipe)
                dn = int(round(pipe_obj.diameter * 1000))
                length = pipe_obj.length
                q_lps = flows.get(worst_pipe, {}).get('avg_lps', 0)

                new_dn = _next_dn(dn)
                cost_upsize = _cost(length, new_dn)
                fixes.append({
                    'option': f'Upsize {worst_pipe} DN{dn} → DN{new_dn}',
                    'est_cost_aud': cost_upsize,
                    'effect': ('Lowers velocity and headloss on the '
                               'critical path, raising downstream pressure.'),
                })
                # Parallel main option (DN one smaller than upsize)
                parallel_dn = dn
                cost_parallel = _cost(length, parallel_dn)
                fixes.append({
                    'option': f'Parallel main alongside {worst_pipe} '
                              f'(DN{parallel_dn})',
                    'est_cost_aud': cost_parallel,
                    'effect': ('Halves carrying burden on existing pipe, '
                               'reduces headloss ~75% (Q^1.85 law).'),
                })

            explanations.append({
                'issue': 'low_pressure',
                'location': node_id,
                'measured_m': round(p_m, 1),
                'wsaa_limit_m': wsaa_p_min,
                'deficit_m': round(wsaa_p_min - p_m, 1),
                'root_cause': (
                    f'Pressure at {node_id} is {p_m:.1f} m (WSAA min '
                    f'{wsaa_p_min} m). '
                    + (f'Pipe {worst_pipe} carries '
                       f'{flows.get(worst_pipe, {}).get("avg_lps", 0):.1f} LPS '
                       f'at {worst_v:.2f} m/s through DN'
                       f'{int(round(wn.get_link(worst_pipe).diameter * 1000))}'
                       f' — this is the limiting segment.'
                       if worst_pipe else
                       'No single pipe dominates — review source head.')),
                'fixes': fixes,
            })

        # High-velocity pipes
        hi_v = sorted(
            [(pid, f.get('max_velocity_ms', 0)) for pid, f in flows.items()
             if f.get('max_velocity_ms', 0) > wsaa_v_max],
            key=lambda x: -x[1])

        for pid, v in hi_v[:max_issues]:
            pipe_obj = wn.get_link(pid)
            dn = int(round(pipe_obj.diameter * 1000))
            length = pipe_obj.length
            new_dn = _next_dn(dn)

            fixes = [{
                'option': f'Upsize {pid} DN{dn} → DN{new_dn}',
                'est_cost_aud': _cost(length, new_dn),
                'effect': (f'Velocity scales with 1/D^2 — DN{dn}→DN{new_dn} '
                           f'reduces v by '
                           f'~{(1 - (dn/new_dn)**2)*100:.0f}%.'),
            }]

            explanations.append({
                'issue': 'high_velocity',
                'location': pid,
                'measured_ms': round(v, 2),
                'wsaa_limit_ms': wsaa_v_max,
                'excess_ms': round(v - wsaa_v_max, 2),
                'root_cause': (
                    f'Pipe {pid} (DN{dn}, {length:.0f} m) carries '
                    f'{flows.get(pid, {}).get("avg_lps", 0):.1f} LPS at '
                    f'{v:.2f} m/s (WSAA max {wsaa_v_max} m/s). '
                    f'Undersized for the demand it serves.'),
                'fixes': fixes,
            })

        return {
            'n_issues': len(explanations),
            'explanations': explanations,
            'cost_assumptions': {
                'currency': 'AUD',
                'year': 2026,
                'cost_source': 'Rawlinsons Construction Cost Guide typical '
                               'unit rates for installed buried main, '
                               'ductile iron',
                'cost_source_edition': 'Rawlinsons 2026 (SEQ metro)',
                'uncertainty_pct': 15,
                'notes': (
                    'Unit rates are indicative for metropolitan '
                    'Brisbane/Sydney/Melbourne greenfield trenching. '
                    '+-15% typical variance. Adjust for: regional '
                    'freight (+10-25%), rock excavation (+30-60%), '
                    'urban reinstatement (+40-100%), wet trench '
                    'dewatering (+15-30%).'),
                'defensibility': (
                    'Cite this edition and apply local factors in the '
                    'design basis report. For tender-grade estimates, '
                    'obtain supplier quotes and trade-contractor pricing.'),
            },
            'note': (
                'Root cause identified from steady-state headloss. '
                'Costs are indicative unit rates — get quotes for '
                'project-specific ground conditions and reinstatement.'),
        }

    # =========================================================================
    # I3 — DEMAND PATTERN WIZARD
    # =========================================================================

    # 24-hour diurnal multipliers by network type (WSAA typical profiles)
    _DIURNAL_PATTERNS = {
        'residential': [0.35, 0.30, 0.28, 0.28, 0.35, 0.55, 0.95, 1.45,
                        1.55, 1.35, 1.20, 1.10, 1.05, 1.00, 0.95, 1.00,
                        1.20, 1.55, 1.75, 1.60, 1.35, 1.05, 0.75, 0.50],
        'commercial':  [0.30, 0.25, 0.25, 0.25, 0.30, 0.45, 0.80, 1.10,
                        1.40, 1.55, 1.60, 1.55, 1.50, 1.55, 1.50, 1.40,
                        1.30, 1.10, 0.85, 0.65, 0.55, 0.45, 0.40, 0.35],
        'industrial':  [0.70, 0.70, 0.70, 0.70, 0.75, 0.85, 1.05, 1.30,
                        1.35, 1.30, 1.25, 1.20, 1.05, 1.20, 1.25, 1.30,
                        1.30, 1.20, 1.00, 0.90, 0.85, 0.80, 0.75, 0.70],
    }

    def generate_demand_pattern(self, network_type='residential',
                                 daily_total_kL=None, peak_hour_lps=None):
        """
        Generate a 24-hour WSAA diurnal demand pattern.

        Parameters
        ----------
        network_type : str
            'residential', 'commercial', or 'industrial'
        daily_total_kL : float or None
            Total daily demand in kilolitres. If None, uses peak_hour_lps
            to reverse-compute daily total.
        peak_hour_lps : float or None
            Peak-hour demand in L/s. If None, uses daily_total_kL to
            compute it.

        Returns dict with 24-value pattern multipliers, base demand,
        and peak-hour indicator. The pattern sums to 24.0 (mean = 1.0)
        when unscaled — apply to base_demand to get hourly demand.
        """
        if network_type not in self._DIURNAL_PATTERNS:
            return {'error': f'Unknown network_type: {network_type}. '
                             f'Fix: use "residential", "commercial", '
                             f'or "industrial".'}
        if daily_total_kL is None and peak_hour_lps is None:
            return {'error': 'Must provide either daily_total_kL or '
                             'peak_hour_lps. Fix: pass at least one.'}

        multipliers = list(self._DIURNAL_PATTERNS[network_type])
        # Normalise so mean = 1.0 (sums to 24)
        mean_m = sum(multipliers) / 24.0
        multipliers = [m / mean_m for m in multipliers]

        peak_multiplier = max(multipliers)
        peak_hour = multipliers.index(peak_multiplier)

        if daily_total_kL is not None:
            # Average daily demand in L/s
            avg_demand_lps = daily_total_kL * 1000 / 86400
            peak_lps = avg_demand_lps * peak_multiplier
        else:
            # Reverse: derive average from peak
            avg_demand_lps = peak_hour_lps / peak_multiplier
            daily_total_kL = avg_demand_lps * 86400 / 1000
            peak_lps = peak_hour_lps

        # Per-hour demand in L/s for quick preview
        hourly_lps = [round(avg_demand_lps * m, 3) for m in multipliers]

        return {
            'network_type': network_type,
            'multipliers': [round(m, 3) for m in multipliers],
            'hourly_demand_lps': hourly_lps,
            'base_demand_lps': round(avg_demand_lps, 3),
            'peak_hour': peak_hour,
            'peak_multiplier': round(peak_multiplier, 3),
            'peak_demand_lps': round(peak_lps, 3),
            'daily_total_kL': round(daily_total_kL, 2),
            'reference': ('WSAA Water Supply Code WSA 03-2011 Table 2.2 '
                          'typical diurnal demand patterns'),
            'note': ('Multipliers are mean-normalised (sum=24). Apply '
                     'to junction base_demand to scale. Peak hour '
                     'identified for fire-flow overlay.'),
        }

    def apply_demand_pattern(self, pattern_multipliers, node_ids=None,
                              pattern_name='WIZARD_PATTERN'):
        """
        Apply a 24-hour demand pattern to selected junctions.

        Parameters
        ----------
        pattern_multipliers : list of float
            24 hourly multipliers (typically mean=1.0)
        node_ids : list of str or None
            Junctions to update. If None, applies to all junctions.
        pattern_name : str
            Name for the pattern in the WNTR model

        Returns dict with applied-node count.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}
        if len(pattern_multipliers) != 24:
            return {'error': f'Pattern must have 24 values, got '
                             f'{len(pattern_multipliers)}. Fix: call '
                             f'generate_demand_pattern() first.'}

        # Register pattern on the WN
        try:
            self.wn.add_pattern(pattern_name, list(pattern_multipliers))
        except Exception:
            # May already exist — silently overwrite attempt
            try:
                self.wn.remove_pattern(pattern_name)
                self.wn.add_pattern(pattern_name, list(pattern_multipliers))
            except Exception as e:
                return {'error': f'Could not add pattern: {e}. '
                                 f'Fix: rename pattern or restart API.'}

        targets = node_ids or list(self.wn.junction_name_list)
        applied = 0
        for nid in targets:
            try:
                junc = self.wn.get_node(nid)
                if junc.demand_timeseries_list:
                    junc.demand_timeseries_list[0].pattern_name = pattern_name
                    applied += 1
            except Exception:
                continue

        return {
            'pattern_name': pattern_name,
            'n_junctions_updated': applied,
            'pattern_length': len(pattern_multipliers),
            'note': ('Pattern applied. Run api.run_steady_state() for peak '
                     'or use EPS simulation to see hourly variation.'),
        }

    # =========================================================================
    # T3 — PUMP EFFICIENCY ANALYSIS
    # =========================================================================

    def pump_efficiency_analysis(self, electricity_price_aud_per_kwh=0.30,
                                   operating_hours_per_day=18):
        """
        Calculate efficiency, energy use, and annual cost for each pump.

        For each pump with a curve:
          - Derive operating point from steady-state flow
          - Estimate hydraulic power (kW) = rho * g * Q * H / 1000
          - Estimate efficiency from distance to BEP (simple parabolic
            model: eta = eta_max * (1 - k*(Q/Q_bep - 1)^2))
          - Compute electrical power = hydraulic power / efficiency
          - Annual energy and cost at the specified rate

        Parameters
        ----------
        electricity_price_aud_per_kwh : float
            Tariff for power cost estimate (default 0.30 AUD/kWh)
        operating_hours_per_day : float
            Duty cycle for annual energy calc (default 18 h/day)

        Returns dict with per-pump metrics and aggregate energy use.
        Ref: Karassik et al. Pump Handbook 4th ed.; API 610.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        # Typical centrifugal pump peak efficiency
        ETA_MAX = 0.82

        if not self.wn.pump_name_list:
            return {
                'n_pumps': 0,
                'pumps': [],
                'summary': {
                    'total_hydraulic_kw': 0.0,
                    'total_electrical_kw': 0.0,
                    'total_annual_kwh': 0.0,
                    'total_annual_cost_aud': 0.0,
                    'total_annual_saving_potential_aud': 0.0,
                },
                'assumptions': {
                    'electricity_price_aud_per_kwh':
                        electricity_price_aud_per_kwh,
                    'operating_hours_per_day': operating_hours_per_day,
                    'eta_max_assumption': ETA_MAX,
                    'bep_penalty_model':
                        'parabolic 0.80 * (Q/Q_bep - 1)^2',
                    'limitations': (
                        'Efficiency estimated from BEP distance; for '
                        'accurate values import manufacturer efficiency '
                        'curves.'),
                },
                'note': 'Network has no pumps.',
            }

        try:
            results = self.run_steady_state(save_plot=False)
        except Exception as e:
            return {'error': f'Analysis failed: {e}. '
                             f'Fix: Run validate_network() to diagnose.'}

        # Parabolic penalty: eta = ETA_MAX * (1 - K_PENALTY * (ratio - 1)^2)
        K_PENALTY = 0.80
        RHO_G = 1000.0 * 9.81  # kg/m³ × m/s² (water)

        pump_results = []
        total_hydraulic_kw = 0.0
        total_electrical_kw = 0.0

        for pump_id in self.wn.pump_name_list:
            op = self.compute_pump_operating_point(pump_id, results=results)
            if 'error' in op:
                pump_results.append({
                    'pump_id': pump_id,
                    'error': op['error'],
                })
                continue

            q_lps = op['operating_point']['flow_lps']
            h_m = op['operating_point']['head_m']
            bep = op.get('bep_flow_lps')

            # Hydraulic power (kW)
            q_m3s = q_lps / 1000.0
            hydraulic_kw = RHO_G * q_m3s * h_m / 1000.0

            # Efficiency from distance to BEP
            if bep and bep > 0 and q_lps > 0:
                ratio = q_lps / bep
                eta = ETA_MAX * max(0.30,
                                    (1 - K_PENALTY * (ratio - 1) ** 2))
            else:
                ratio = 1.0
                eta = ETA_MAX

            electrical_kw = hydraulic_kw / eta if eta > 0 else 0

            annual_kwh = electrical_kw * operating_hours_per_day * 365
            annual_cost = annual_kwh * electricity_price_aud_per_kwh

            # Flag if > 20% from BEP
            off_bep = abs(ratio - 1.0) > 0.20
            # Potential saving if re-selected to BEP
            hydraulic_at_bep_pct = ETA_MAX / eta if eta > 0 else 1.0
            saving_pct = max(0, (1 - eta / ETA_MAX)) * 100
            annual_saving_aud = annual_cost * (saving_pct / 100.0)

            recommendations = []
            if off_bep:
                recommendations.append(
                    f'Pump {pump_id} operating at {eta*100:.0f}% efficiency '
                    f'({ratio:.0%} of BEP flow). Reselect pump for ~'
                    f'{saving_pct:.0f}% energy saving '
                    f'(~${annual_saving_aud:,.0f}/yr).')
            if eta < 0.60:
                recommendations.append(
                    'Efficiency < 60% — strong candidate for VSD retrofit '
                    'or pump replacement.')

            pump_results.append({
                'pump_id': pump_id,
                'operating_flow_lps': q_lps,
                'operating_head_m': h_m,
                'bep_flow_lps': bep,
                'flow_to_bep_ratio': round(ratio, 2),
                'efficiency': round(eta, 3),
                'hydraulic_power_kw': round(hydraulic_kw, 2),
                'electrical_power_kw': round(electrical_kw, 2),
                'annual_energy_kwh': round(annual_kwh, 0),
                'annual_cost_aud': round(annual_cost, 0),
                'annual_saving_potential_aud': round(annual_saving_aud, 0),
                'off_bep': off_bep,
                'recommendations': recommendations,
            })

            total_hydraulic_kw += hydraulic_kw
            total_electrical_kw += electrical_kw

        total_annual_kwh = total_electrical_kw * operating_hours_per_day * 365
        total_annual_cost = total_annual_kwh * electricity_price_aud_per_kwh
        total_saving = sum(p.get('annual_saving_potential_aud', 0)
                           for p in pump_results)

        return {
            'n_pumps': len(pump_results),
            'pumps': pump_results,
            'summary': {
                'total_hydraulic_kw': round(total_hydraulic_kw, 2),
                'total_electrical_kw': round(total_electrical_kw, 2),
                'total_annual_kwh': round(total_annual_kwh, 0),
                'total_annual_cost_aud': round(total_annual_cost, 0),
                'total_annual_saving_potential_aud': round(total_saving, 0),
            },
            'assumptions': {
                'electricity_price_aud_per_kwh':
                    electricity_price_aud_per_kwh,
                'operating_hours_per_day': operating_hours_per_day,
                'eta_max_assumption': ETA_MAX,
                'bep_penalty_model': 'parabolic 0.80 × (Q/Q_bep - 1)^2',
                'limitations': (
                    'Efficiency estimated from BEP distance; for accurate '
                    'values import manufacturer efficiency curves.'),
            },
            'reference': 'Karassik et al. Pump Handbook 4th ed.; API 610',
        }

    # =========================================================================
    # T4 — AUTOMATED SENSITIVITY REPORT
    # =========================================================================

    def sensitivity_report(self, perturbation_pct=20, max_targets=10):
        """
        Rank parameters by how much they influence node pressures.

        For each pipe roughness and each junction demand, perturb by
        +/- perturbation_pct and record the pressure change at every
        node. Produces a ranked sensitivity table suitable for inclusion
        as a design-report appendix.

        Parameters
        ----------
        perturbation_pct : float
            Perturbation amount as a percentage (default 20 = +/- 20%)
        max_targets : int
            Max number of parameters to perturb (limits run-time on
            large networks)

        Returns dict with sensitivity matrix and ranked top drivers.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        try:
            base = self.run_steady_state(save_plot=False)
        except Exception as e:
            return {'error': f'Baseline failed: {e}. '
                             f'Fix: Run validate_network() to diagnose.'}
        base_p = {n: p.get('avg_m', 0)
                  for n, p in base.get('pressures', {}).items()}
        if not base_p:
            return {'error': 'No pressures in baseline. '
                             'Fix: ensure network has junctions.'}

        delta = perturbation_pct / 100.0
        wn = self.wn

        # Snapshot originals for restoration
        orig_c = {pid: wn.get_link(pid).roughness
                  for pid in wn.pipe_name_list}
        orig_d = {}
        for jid in wn.junction_name_list:
            try:
                orig_d[jid] = wn.get_node(jid).demand_timeseries_list[0].base_value
            except Exception:
                continue

        # Choose targets by size — largest pipes and highest-demand nodes
        # have the biggest hydraulic footprint, so they're natural candidates
        pipe_targets = sorted(
            wn.pipe_name_list,
            key=lambda p: wn.get_link(p).diameter * wn.get_link(p).length,
            reverse=True,
        )[:max_targets]
        demand_targets = sorted(
            orig_d.keys(), key=lambda j: orig_d[j], reverse=True)[:max_targets]

        sensitivities = []

        def _perturb_and_measure(label, apply_fn, revert_fn):
            apply_fn()
            try:
                res = self.run_steady_state(save_plot=False)
                pp = {n: p.get('avg_m', 0)
                      for n, p in res.get('pressures', {}).items()}
            except Exception:
                pp = base_p
            finally:
                revert_fn()
            # For each node, the absolute change in pressure
            per_node = {n: abs(pp.get(n, base_p.get(n, 0)) - base_p.get(n, 0))
                        for n in base_p}
            max_dp = max(per_node.values()) if per_node else 0
            worst_node = (max(per_node, key=per_node.get)
                          if per_node else None)
            mean_dp = (sum(per_node.values()) / len(per_node)
                       if per_node else 0)
            return {
                'parameter': label,
                'max_pressure_change_m': round(max_dp, 2),
                'most_sensitive_node': worst_node,
                'mean_pressure_change_m': round(mean_dp, 3),
            }

        # Roughness perturbations
        for pid in pipe_targets:
            base_val = orig_c[pid]
            label = f'roughness:{pid}'
            sens = _perturb_and_measure(
                label,
                apply_fn=lambda p=pid, v=base_val: setattr(
                    wn.get_link(p), 'roughness', v * (1 - delta)),
                revert_fn=lambda p=pid, v=base_val: setattr(
                    wn.get_link(p), 'roughness', v),
            )
            sensitivities.append(sens)

        # Demand perturbations
        for jid in demand_targets:
            base_val = orig_d[jid]
            label = f'demand:{jid}'
            def _apply(j=jid, v=base_val):
                wn.get_node(j).demand_timeseries_list[0].base_value = \
                    v * (1 + delta)
            def _revert(j=jid, v=base_val):
                wn.get_node(j).demand_timeseries_list[0].base_value = v
            sens = _perturb_and_measure(label, _apply, _revert)
            sensitivities.append(sens)

        # Final restoration (belt and braces)
        for pid, c in orig_c.items():
            try:
                wn.get_link(pid).roughness = c
            except Exception:
                pass
        for jid, d in orig_d.items():
            try:
                wn.get_node(jid).demand_timeseries_list[0].base_value = d
            except Exception:
                pass

        # Rank by max_pressure_change
        sensitivities.sort(key=lambda s: s['max_pressure_change_m'],
                            reverse=True)

        # Plain English summary lines
        summary_lines = []
        if sensitivities:
            top = sensitivities[0]
            summary_lines.append(
                f"Most sensitive: {top['parameter']} — "
                f"{top['max_pressure_change_m']:.1f} m pressure swing "
                f"at {top['most_sensitive_node']}.")
            bottom = sensitivities[-1]
            summary_lines.append(
                f"Least sensitive: {bottom['parameter']} — "
                f"{bottom['max_pressure_change_m']:.1f} m swing "
                f"at {bottom['most_sensitive_node']}.")

        return {
            'perturbation_pct': perturbation_pct,
            'n_parameters': len(sensitivities),
            'rankings': sensitivities,
            'top_5': sensitivities[:5],
            'summary_lines': summary_lines,
            'note': (
                'Sensitivity = max pressure change at any node for '
                f'+/- {perturbation_pct}% parameter change. Use to '
                'prioritise calibration effort and identify critical '
                'model parameters.'),
        }

    # =========================================================================
    # EMERGENCY RESPONSE — pipe burst at 2am (Innovation #3)
    # =========================================================================

    def emergency_pipe_burst(self, burst_pipe_id):
        """
        Rapid assessment for a burst pipe: who loses water, which valves
        to close, expected pressure impact, and priority restoration
        sequence.

        Intended for an operations engineer in the middle of the night
        who needs actionable information in 15 seconds.

        Parameters
        ----------
        burst_pipe_id : str
            The failed pipe

        Returns dict with:
            - impact: list of isolated junctions (no water)
            - pressure_drop_at_remaining_nodes
            - isolation_valves: pipes adjacent to burst to close
            - customers_affected: count of isolated junctions
            - immediate_actions: numbered action list
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        if burst_pipe_id not in self.wn.pipe_name_list:
            return {'error': f'Pipe {burst_pipe_id} not found. '
                             f'Fix: pass a valid pipe ID from '
                             f'api.wn.pipe_name_list.'}

        # Baseline pressures (pre-burst)
        try:
            base = self.run_steady_state(save_plot=False)
        except Exception as e:
            return {'error': f'Baseline failed: {e}. '
                             f'Fix: Run validate_network() to diagnose.'}
        base_p = {n: p.get('avg_m', 0)
                  for n, p in base.get('pressures', {}).items()}

        # Close the burst pipe (set initial_status to Closed) then re-solve
        burst = self.wn.get_link(burst_pipe_id)
        original_status = getattr(burst, 'initial_status', None)
        original_diam = burst.diameter
        try:
            # Simulate by setting diameter tiny — WNTR CLOSED status
            # sometimes creates convergence issues. Use a tiny diameter
            # instead (effectively severs hydraulic path).
            burst.diameter = 1e-6
            try:
                post = self.run_steady_state(save_plot=False)
            except Exception as e:
                post = {'pressures': {}, 'flows': {}, 'error': str(e)}
        finally:
            burst.diameter = original_diam

        post_p = {n: p.get('avg_m', 0)
                  for n, p in post.get('pressures', {}).items()}

        # Identify isolated junctions: unreachable from any source.
        # After closure, if a node's pressure collapsed to near-zero or
        # the solver couldn't converge for it, treat as isolated.
        isolated = []
        remaining = []
        for jid in self.wn.junction_name_list:
            p_after = post_p.get(jid, base_p.get(jid, 0))
            if p_after < 5.0 or jid not in post_p:
                isolated.append({
                    'node': jid,
                    'base_pressure_m': round(base_p.get(jid, 0), 1),
                    'post_burst_pressure_m': round(p_after, 1),
                })
            else:
                drop = base_p.get(jid, 0) - p_after
                remaining.append({
                    'node': jid,
                    'base_pressure_m': round(base_p.get(jid, 0), 1),
                    'post_burst_pressure_m': round(p_after, 1),
                    'pressure_drop_m': round(drop, 1),
                })

        # Rank remaining nodes by pressure drop
        remaining.sort(key=lambda x: -x['pressure_drop_m'])

        # Isolation valves: pipes at the end nodes of the burst pipe
        adjacent_pipes = set()
        burst_start = burst.start_node_name
        burst_end = burst.end_node_name
        for pid in self.wn.pipe_name_list:
            if pid == burst_pipe_id:
                continue
            p = self.wn.get_link(pid)
            if p.start_node_name in (burst_start, burst_end) or \
                    p.end_node_name in (burst_start, burst_end):
                adjacent_pipes.add(pid)

        # Nearest actual valves (if present)
        nearby_valves = []
        for vid in self.wn.valve_name_list:
            v = self.wn.get_link(vid)
            if v.start_node_name in (burst_start, burst_end) or \
                    v.end_node_name in (burst_start, burst_end):
                nearby_valves.append(vid)

        # Customer impact estimate (assume each junction = ~50 connections)
        customers_estimate = len(isolated) * 50

        # Immediate action list
        actions = [
            f'1. DISPATCH crew to pipe {burst_pipe_id} '
            f'(connects {burst_start} <-> {burst_end}, '
            f'{burst.length:.0f} m of DN'
            f'{int(round(original_diam * 1000))}).',
        ]
        if nearby_valves:
            actions.append(
                f'2. CLOSE valves: {", ".join(nearby_valves)} '
                f'to isolate the burst.')
        else:
            actions.append(
                f'2. ISOLATE by closing adjacent pipes: '
                f'{", ".join(sorted(adjacent_pipes)) or "(none adjacent)"}. '
                f'No inline valves found near burst — consider adding.')
        if isolated:
            actions.append(
                f'3. NOTIFY {len(isolated)} affected junction(s) '
                f'(~{customers_estimate} connections) of supply '
                f'interruption. Arrange tanker water if >4 hr restoration.')
        else:
            actions.append(
                '3. No customers isolated — redundant supply via '
                'alternate paths. Continue service.')
        if remaining:
            worst = remaining[0]
            actions.append(
                f'4. MONITOR pressure at {worst["node"]} '
                f'(dropped {worst["pressure_drop_m"]:.1f} m) and other '
                f'low-pressure nodes during repair.')
        actions.append(
            '5. LOG incident: pipe ID, time, cause if known, '
            'restoration time. Feed into break-rate data.')

        severity = ('HIGH' if len(isolated) > 5
                    else 'MEDIUM' if isolated
                    else 'LOW')

        return {
            'burst_pipe': burst_pipe_id,
            'burst_endpoints': [burst_start, burst_end],
            'burst_length_m': round(burst.length, 1),
            'burst_diameter_mm': int(round(original_diam * 1000)),
            'severity': severity,
            'n_isolated_junctions': len(isolated),
            'isolated': isolated[:20],
            'most_affected_remaining': remaining[:10],
            'customers_affected_estimate': customers_estimate,
            'isolation_valves_to_close': nearby_valves,
            'adjacent_pipes_to_close_if_no_valves': sorted(adjacent_pipes),
            'immediate_actions': actions,
            'note': (
                'Assessment uses instant-closure analysis. Actual impact '
                'depends on tank buffering, duration, and reroute capacity. '
                'For formal emergency protocol, consult network operations '
                'manual.'),
        }


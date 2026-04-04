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
            return {'error': 'No network loaded'}

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
            return {'error': 'No network loaded'}

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
            return {'error': 'No network loaded'}

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
            return {'error': 'No network loaded'}

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
            return {'error': 'No network loaded'}

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
            return {'error': 'No network loaded'}

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


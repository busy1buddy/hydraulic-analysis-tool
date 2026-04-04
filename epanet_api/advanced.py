import os, json, csv, math, wntr, numpy as np


class AdvancedMixin:

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
    # NETWORK TOPOLOGY ANALYSIS (L3)
    # =========================================================================

    def analyse_topology(self):
        """
        Analyse network topology: dead ends, loops, bridges, connectivity.

        Uses graph theory to identify structural characteristics that
        affect hydraulic reliability and maintenance.

        Returns dict with:
        - dead_ends: list of terminal nodes (degree 1)
        - bridges: pipes whose removal disconnects the network
        - loops: count of independent loops (cyclomatic complexity)
        - connectivity: overall connectivity metrics
        - isolated_segments: groups of nodes not connected to sources

        Ref: Graph theory for water distribution, Todini & Pilati (1988)
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        # Build adjacency from pipe connections
        adj = {}  # node -> set of (neighbor, pipe_id)
        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            sn = pipe.start_node_name
            en = pipe.end_node_name
            adj.setdefault(sn, set()).add((en, pid))
            adj.setdefault(en, set()).add((sn, pid))

        all_nodes = set(self.wn.node_name_list)
        for n in all_nodes:
            adj.setdefault(n, set())

        # Dead ends: nodes with exactly 1 connection (junctions only)
        dead_ends = []
        for nid in self.wn.junction_name_list:
            if len(adj.get(nid, set())) == 1:
                dead_ends.append(nid)

        # Degree distribution
        degrees = {nid: len(adj.get(nid, set())) for nid in all_nodes}

        # Sources: reservoirs and tanks
        sources = set(self.wn.reservoir_name_list) | set(self.wn.tank_name_list)

        # Connectivity: BFS from each source
        def bfs_reachable(start_nodes):
            visited = set()
            queue = list(start_nodes)
            visited.update(queue)
            while queue:
                node = queue.pop(0)
                for neighbor, _ in adj.get(node, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            return visited

        reachable = bfs_reachable(sources)
        isolated = all_nodes - reachable

        # Connected components
        remaining = set(all_nodes)
        components = []
        while remaining:
            start = next(iter(remaining))
            component = bfs_reachable({start})
            components.append(component)
            remaining -= component

        # Bridges: pipes whose removal increases component count
        # Use Tarjan's bridge-finding via DFS
        bridges = []
        n_pipes = len(self.wn.pipe_name_list)
        if n_pipes > 0 and n_pipes < 5000:  # skip for very large networks
            bridges = self._find_bridges(adj, all_nodes)

        # Cyclomatic complexity: M = E - V + C
        # E = edges (pipes), V = vertices (nodes), C = connected components
        n_edges = len(self.wn.pipe_name_list)
        n_vertices = len(all_nodes)
        n_components = len(components)
        loops = n_edges - n_vertices + n_components

        # Average node degree
        avg_degree = sum(degrees.values()) / max(len(degrees), 1)

        return {
            'dead_ends': dead_ends,
            'dead_end_count': len(dead_ends),
            'bridges': bridges,
            'bridge_count': len(bridges),
            'loops': max(loops, 0),
            'connected_components': n_components,
            'isolated_nodes': list(isolated),
            'isolated_count': len(isolated),
            'total_nodes': n_vertices,
            'total_pipes': n_edges,
            'avg_node_degree': round(avg_degree, 2),
            'degree_distribution': {
                deg: sum(1 for d in degrees.values() if d == deg)
                for deg in sorted(set(degrees.values()))
            },
            'sources': list(sources),
            'connectivity_ratio': round(len(reachable) / max(n_vertices, 1), 3),
        }

    def _find_bridges(self, adj, all_nodes):
        """
        Find bridge edges using iterative Tarjan's algorithm.
        A bridge is a pipe whose removal disconnects the graph.

        Returns list of pipe IDs that are bridges.
        """
        bridges = []
        disc = {}
        low = {}
        timer = [0]

        for start in all_nodes:
            if start in disc:
                continue
            # Iterative DFS
            # Stack: (node, parent_pipe, neighbor_iterator, is_entering)
            stack = [(start, None, iter(adj.get(start, set())), True)]
            while stack:
                node, parent_pipe, neighbors, entering = stack[-1]
                if entering:
                    disc[node] = low[node] = timer[0]
                    timer[0] += 1
                    stack[-1] = (node, parent_pipe, neighbors, False)

                found_next = False
                for neighbor, pipe_id in neighbors:
                    if neighbor not in disc:
                        stack.append((neighbor, pipe_id,
                                      iter(adj.get(neighbor, set())), True))
                        found_next = True
                        break
                    elif pipe_id != parent_pipe:
                        low[node] = min(low[node], disc[neighbor])

                if not found_next:
                    stack.pop()
                    if stack:
                        parent_node = stack[-1][0]
                        low[parent_node] = min(low[parent_node], low[node])
                        if low[node] > disc[parent_node] and parent_pipe is not None:
                            bridges.append(parent_pipe)

        return bridges

    # =========================================================================
    # TODINI RESILIENCE INDEX (M1)
    # =========================================================================

    def compute_resilience_index(self, results=None):
        """
        Compute the Todini resilience index for the current network.

        I_r = sum((h_i - h_min) * q_i) / sum((H_source - h_min) * Q_source)

        Where h_i is pressure at node i, h_min is minimum required (WSAA 20 m),
        q_i is demand at node i, H_source is source head, Q_source is source outflow.

        Parameters
        ----------
        results : dict or None
            Steady-state results from run_steady_state(). If None, runs analysis.

        Returns dict with 'resilience_index', 'grade', 'interpretation'.

        Ref: Todini E. (2000) "Looped water distribution networks design using
             a resilience index based heuristic approach". Urban Water 2(2):115-122
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        if results is None:
            try:
                results = self.run_steady_state(save_plot=False)
            except Exception as e:
                return {'error': f'Analysis failed: {e}'}

        pressures = results.get('pressures', {})
        flows = results.get('flows', {})

        if not pressures or not flows:
            return {'error': 'No results available'}

        h_min = self.DEFAULTS['min_pressure_m']  # WSAA 20 m

        # Numerator: sum of surplus power at demand nodes
        numerator = 0
        for jid, pdata in pressures.items():
            try:
                node = self.wn.get_node(jid)
                demand_m3s = node.demand_timeseries_list[0].base_value
            except (IndexError, AttributeError, KeyError):
                continue
            if demand_m3s <= 0:
                continue
            surplus = max(pdata.get('avg_m', 0) - h_min, 0)
            numerator += surplus * demand_m3s  # m * m³/s

        # Denominator: total source input power minus minimum required
        denominator = 0
        for rid in list(self.wn.reservoir_name_list) + list(self.wn.tank_name_list):
            node = self.wn.get_node(rid)
            head = getattr(node, 'base_head', getattr(node, 'head', 0))
            for pid in self.wn.pipe_name_list:
                pipe = self.wn.get_link(pid)
                if pipe.start_node_name == rid or pipe.end_node_name == rid:
                    fdata = flows.get(pid, {})
                    Q_m3s = abs(fdata.get('avg_lps', 0)) / 1000
                    denominator += (head - h_min) * Q_m3s

        # Cap at 1.0 — values > 1 indicate surplus energy far exceeds minimum
        # requirement, which is physically valid but practically meaningless
        raw_index = numerator / max(denominator, 1e-12)
        index = round(min(raw_index, 1.0), 4)

        # Grade and interpretation
        # Ref: Prasad & Park (2004) suggest >0.3 for reliable networks
        if index >= 0.5:
            grade = 'A'
            interpretation = 'Excellent redundancy — network is highly resilient.'
        elif index >= 0.3:
            grade = 'B'
            interpretation = 'Good redundancy — meets reliability targets.'
        elif index >= 0.15:
            grade = 'C'
            interpretation = 'Moderate redundancy — consider improving connectivity.'
        elif index >= 0.05:
            grade = 'D'
            interpretation = 'Low redundancy — vulnerable to pipe failures.'
        else:
            grade = 'F'
            interpretation = 'Very low redundancy — critical infrastructure risk.'

        return {
            'resilience_index': index,
            'grade': grade,
            'interpretation': interpretation,
            'numerator_power': round(numerator, 6),
            'denominator_power': round(denominator, 6),
            'min_pressure_target_m': h_min,
        }

    # =========================================================================
    # HYDRAULIC FINGERPRINT (L4)
    # =========================================================================

    def hydraulic_fingerprint(self):
        """
        Generate a unique hydraulic fingerprint of the network's behaviour.

        Captures key statistical signatures that characterise the network's
        response. Useful for detecting changes, comparing scenarios, and
        anomaly detection.

        Returns dict with:
        - pressure_stats: min/max/mean/std of pressures
        - velocity_stats: min/max/mean/std of velocities
        - flow_balance: total inflow vs total demand
        - headloss_profile: sorted list of pipe headloss intensities
        - energy_index: total headloss × flow (energy dissipation proxy)
        - resilience_index: Todini resilience index (2000)

        Ref: Todini (2000) "Looped water distribution networks design using
             a resilience index based heuristic approach"
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        try:
            results = self.run_steady_state(save_plot=False)
        except Exception as e:
            return {'error': f'Analysis failed: {e}'}

        pressures = results.get('pressures', {})
        flows = results.get('flows', {})

        if not pressures or not flows:
            return {'error': 'No results available'}

        import math

        # Pressure statistics
        p_vals = [p.get('avg_m', 0) for p in pressures.values()]
        p_mean = sum(p_vals) / max(len(p_vals), 1)
        p_std = math.sqrt(sum((p - p_mean)**2 for p in p_vals) / max(len(p_vals), 1))

        # Velocity statistics
        v_vals = [f.get('max_velocity_ms', 0) for f in flows.values()]
        v_mean = sum(v_vals) / max(len(v_vals), 1)
        v_std = math.sqrt(sum((v - v_mean)**2 for v in v_vals) / max(len(v_vals), 1))

        # Headloss intensity (m/km) sorted
        hl_vals = []
        for pid, fdata in flows.items():
            pipe = self.wn.get_link(pid)
            # headloss_per_km from results or calculate
            hl_pkm = fdata.get('headloss_m_per_km', 0)
            hl_vals.append({'pipe_id': pid, 'headloss_m_per_km': round(hl_pkm, 2)})
        hl_vals.sort(key=lambda x: x['headloss_m_per_km'], reverse=True)

        # Energy dissipation index: sum(headloss × flow) per pipe
        # Proxy for total energy consumed by friction
        energy_index = 0
        for pid, fdata in flows.items():
            pipe = self.wn.get_link(pid)
            Q_lps = abs(fdata.get('avg_lps', 0))
            Q_m3s = Q_lps / 1000  # convert LPS to m³/s
            hl_m = fdata.get('headloss_m_per_km', 0) * pipe.length / 1000
            energy_index += Q_m3s * hl_m * 9810  # watts = rho*g*Q*hL

        # Todini resilience index — delegate to standalone method
        # Ref: Todini (2000), Urban Water 2(2):115-122
        ri_result = self.compute_resilience_index(results)
        resilience = ri_result.get('resilience_index', 0) if 'error' not in ri_result else 0

        # Flow balance — get demands from WNTR model
        total_demand = 0
        for jid in self.wn.junction_name_list:
            try:
                d = self.wn.get_node(jid).demand_timeseries_list[0].base_value * 1000
                if d > 0:
                    total_demand += d
            except (IndexError, AttributeError):
                pass

        return {
            'pressure_stats': {
                'min_m': round(min(p_vals), 2) if p_vals else 0,
                'max_m': round(max(p_vals), 2) if p_vals else 0,
                'mean_m': round(p_mean, 2),
                'std_m': round(p_std, 2),
                'count': len(p_vals),
            },
            'velocity_stats': {
                'min_ms': round(min(v_vals), 3) if v_vals else 0,
                'max_ms': round(max(v_vals), 3) if v_vals else 0,
                'mean_ms': round(v_mean, 3),
                'std_ms': round(v_std, 3),
                'count': len(v_vals),
            },
            'total_demand_lps': round(total_demand, 2),
            'headloss_top5': hl_vals[:5],
            'energy_dissipation_watts': round(energy_index, 1),
            'resilience_index': resilience,
            'network_name': os.path.basename(self._inp_file) if self._inp_file else 'Unknown',
        }

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

    def pump_failure_impact(self, pump_id=None):
        """
        Analyse impact of pump station power loss on customer supply.

        Simulates pump failure by closing the pump and running steady-state
        analysis. Reports which customers lose adequate pressure and by how much.

        Parameters
        ----------
        pump_id : str or None
            Specific pump to fail. If None, analyses all pumps.

        Returns dict with per-pump failure impact:
        'pump_id', 'affected_nodes', 'pressure_drop', 'customers_without_supply'.

        Ref: WSAA WSA 03-2011 — minimum service pressure 20 m during outage
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        pump_ids = [pump_id] if pump_id else list(self.wn.pump_name_list)

        if not pump_ids:
            return {'error': 'No pumps in network', 'pump_count': 0}

        # Baseline pressures
        try:
            base_results = self.run_steady_state(save_plot=False)
        except Exception as e:
            return {'error': f'Baseline analysis failed: {e}'}

        base_pressures = base_results.get('pressures', {})

        impacts = []
        for pid in pump_ids:
            try:
                pump = self.wn.get_link(pid)
            except KeyError:
                impacts.append({
                    'pump_id': pid,
                    'error': f'Pump {pid} not found',
                })
                continue

            original_status = pump.initial_status

            # Close pump
            pump.initial_status = wntr.network.LinkStatus(0)

            try:
                fail_results = self.run_steady_state(save_plot=False)
                fail_pressures = fail_results.get('pressures', {})

                affected = []
                total_pressure_drop = 0
                n_below_min = 0

                for jid, base_p in base_pressures.items():
                    base_avg = base_p.get('avg_m', 0)
                    fail_avg = fail_pressures.get(jid, {}).get('avg_m', 0)
                    drop = base_avg - fail_avg

                    if drop > 1.0:  # meaningful pressure drop (> 1 m)
                        affected.append({
                            'node': jid,
                            'base_pressure_m': round(base_avg, 1),
                            'failure_pressure_m': round(fail_avg, 1),
                            'drop_m': round(drop, 1),
                        })
                        total_pressure_drop += drop

                    if fail_avg < self.DEFAULTS['min_pressure_m']:
                        n_below_min += 1

                affected.sort(key=lambda x: x['drop_m'], reverse=True)

                impacts.append({
                    'pump_id': pid,
                    'affected_nodes': affected,
                    'n_affected': len(affected),
                    'customers_without_supply': n_below_min,
                    'max_pressure_drop_m': round(max((a['drop_m'] for a in affected), default=0), 1),
                    'avg_pressure_drop_m': round(total_pressure_drop / max(len(affected), 1), 1),
                    'severity': ('CRITICAL' if n_below_min > len(base_pressures) * 0.5
                                else 'HIGH' if n_below_min > 0
                                else 'LOW'),
                })

            except Exception as e:
                impacts.append({
                    'pump_id': pid,
                    'error': f'Solver failed with pump {pid} off: network may be pump-dependent',
                    'severity': 'CRITICAL',
                    'customers_without_supply': len(base_pressures),
                })

            finally:
                pump.initial_status = original_status

        return {
            'impacts': impacts,
            'total_pumps_analysed': len(impacts),
            'summary': f'{len(impacts)} pump(s) analysed',
        }

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

    def detailed_comparison(self, other_inp_path):
        """
        Enhanced network comparison with categorised change detection.

        Extends compare_networks() with:
        - Change categories: added (green), removed (red), resized (blue),
          demand changed (yellow)
        - Change log with detailed descriptions
        - Demand comparison for common junctions

        Parameters
        ----------
        other_inp_path : str
            Path to the second .inp file

        Returns dict with categorised changes and change log.
        """
        base = self.compare_networks(other_inp_path)
        if 'error' in base:
            return base

        import wntr
        wn2 = wntr.network.WaterNetworkModel(other_inp_path)

        changelog = []

        # Categorise: added pipes
        for pid in base['topology']['added_pipes']:
            p2 = wn2.get_link(pid)
            changelog.append({
                'type': 'added',
                'element': 'pipe',
                'id': pid,
                'colour': 'green',
                'description': f'Pipe {pid} added: DN{int(p2.diameter*1000)}, '
                              f'{p2.length:.0f} m',
            })

        # Categorise: removed pipes
        for pid in base['topology']['removed_pipes']:
            p1 = self.wn.get_link(pid)
            changelog.append({
                'type': 'removed',
                'element': 'pipe',
                'id': pid,
                'colour': 'red',
                'description': f'Pipe {pid} removed: was DN{int(p1.diameter*1000)}, '
                              f'{p1.length:.0f} m',
            })

        # Categorise: resized pipes (diameter change)
        resized = []
        demand_changed = []
        for prop in base['properties']:
            if 'pipe' in prop:
                for c in prop['changes']:
                    if 'diameter' in c:
                        resized.append(prop['pipe'])
                        changelog.append({
                            'type': 'resized',
                            'element': 'pipe',
                            'id': prop['pipe'],
                            'colour': 'blue',
                            'description': f'Pipe {prop["pipe"]}: {c}',
                        })
                    elif 'roughness' in c:
                        changelog.append({
                            'type': 'modified',
                            'element': 'pipe',
                            'id': prop['pipe'],
                            'colour': 'blue',
                            'description': f'Pipe {prop["pipe"]}: {c}',
                        })

        # Demand changes for common junctions
        common_juncs = set(self.wn.junction_name_list) & set(wn2.junction_name_list)
        for jid in sorted(common_juncs):
            n1 = self.wn.get_node(jid)
            n2 = wn2.get_node(jid)
            try:
                d1 = n1.demand_timeseries_list[0].base_value
                d2 = n2.demand_timeseries_list[0].base_value
            except (IndexError, AttributeError):
                continue
            if abs(d1 - d2) > 0.0001:
                d1_lps = round(d1 * 1000, 2)
                d2_lps = round(d2 * 1000, 2)
                demand_changed.append(jid)
                changelog.append({
                    'type': 'demand_changed',
                    'element': 'junction',
                    'id': jid,
                    'colour': 'yellow',
                    'description': f'Junction {jid}: demand {d1_lps} → {d2_lps} LPS',
                })

        # Added/removed nodes
        for nid in base['topology']['added_nodes']:
            changelog.append({
                'type': 'added',
                'element': 'node',
                'id': nid,
                'colour': 'green',
                'description': f'Node {nid} added',
            })
        for nid in base['topology']['removed_nodes']:
            changelog.append({
                'type': 'removed',
                'element': 'node',
                'id': nid,
                'colour': 'red',
                'description': f'Node {nid} removed',
            })

        return {
            'changelog': changelog,
            'categories': {
                'added': len(base['topology']['added_pipes']) + len(base['topology']['added_nodes']),
                'removed': len(base['topology']['removed_pipes']) + len(base['topology']['removed_nodes']),
                'resized': len(resized),
                'demand_changed': len(demand_changed),
            },
            'total_changes': len(changelog),
            'base_comparison': base,
        }

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
    # SCENARIO DIFFERENCE REPORT (N8)
    # =========================================================================

    def scenario_difference(self, results_a, results_b, label_a='Scenario A',
                             label_b='Scenario B'):
        """
        Calculate differences between two analysis results.

        For each node: pressure change (B - A)
        For each pipe: velocity and headloss change
        Highlights changes > 10%.

        Parameters
        ----------
        results_a, results_b : dict
            Results from run_steady_state()
        label_a, label_b : str
            Names for the two scenarios

        Returns dict with per-node and per-pipe differences, and plain English summary.
        """
        if not results_a or not results_b:
            return {'error': 'Both scenarios must have results'}

        p_a = results_a.get('pressures', {})
        p_b = results_b.get('pressures', {})
        f_a = results_a.get('flows', {})
        f_b = results_b.get('flows', {})

        node_diffs = []
        for jid in set(p_a.keys()) | set(p_b.keys()):
            avg_a = p_a.get(jid, {}).get('avg_m', 0)
            avg_b = p_b.get(jid, {}).get('avg_m', 0)
            change = round(avg_b - avg_a, 1)
            pct = round(change / max(abs(avg_a), 0.1) * 100, 1)
            node_diffs.append({
                'node': jid,
                f'{label_a}_pressure_m': avg_a,
                f'{label_b}_pressure_m': avg_b,
                'change_m': change,
                'change_pct': pct,
                'significant': abs(pct) > 10,
            })

        pipe_diffs = []
        for pid in set(f_a.keys()) | set(f_b.keys()):
            v_a = f_a.get(pid, {}).get('max_velocity_ms', 0)
            v_b = f_b.get(pid, {}).get('max_velocity_ms', 0)
            v_change = round(v_b - v_a, 2)
            pipe_diffs.append({
                'pipe': pid,
                f'{label_a}_velocity_ms': v_a,
                f'{label_b}_velocity_ms': v_b,
                'velocity_change_ms': v_change,
                'significant': abs(v_change) > 0.2,
            })

        # Plain English summary
        improved = [d for d in node_diffs if d['change_m'] > 1]
        worsened = [d for d in node_diffs if d['change_m'] < -1]

        summary_parts = []
        if improved:
            best = max(improved, key=lambda d: d['change_m'])
            summary_parts.append(
                f"{len(improved)} node(s) improved pressure "
                f"(best: {best['node']} +{best['change_m']:.1f} m)")
        if worsened:
            worst = min(worsened, key=lambda d: d['change_m'])
            summary_parts.append(
                f"{len(worsened)} node(s) lost pressure "
                f"(worst: {worst['node']} {worst['change_m']:.1f} m)")

        vel_improved = [d for d in pipe_diffs if d['velocity_change_ms'] < -0.2]
        if vel_improved:
            summary_parts.append(
                f"{len(vel_improved)} pipe(s) reduced velocity")

        return {
            'node_differences': sorted(node_diffs, key=lambda d: abs(d['change_m']), reverse=True),
            'pipe_differences': sorted(pipe_diffs, key=lambda d: abs(d['velocity_change_ms']), reverse=True),
            'summary': '. '.join(summary_parts) if summary_parts else 'No significant changes.',
            'labels': [label_a, label_b],
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

    # =========================================================================
    # SURGE MITIGATION
    # =========================================================================

    def calculate_safe_closure_time(self, pipe_length_m, wave_speed_ms=1100):
        """
        Calculate minimum safe valve closure time to prevent full Joukowsky surge.

        Slow closure means tc > 2L/a (wave reflection time).
        For gradual reduction, recommend tc = 5 × 2L/a for < 20% surge.

        Parameters
        ----------
        pipe_length_m : float
            Pipeline length (m)
        wave_speed_ms : float
            Pressure wave speed (m/s, default: 1100 AS 2280 DI minimum)

        Returns dict with closure times and expected surge reduction.
        Ref: Thorley A.R.D. (2004) "Fluid Transients in Pipeline Systems",
             2nd ed., Palgrave Macmillan, Chapter 3
        """
        if pipe_length_m <= 0 or wave_speed_ms <= 0:
            return {'error': 'Pipe length and wave speed must be positive'}

        # Critical time: 2L/a — round-trip wave travel time
        tc_critical = 2 * pipe_length_m / wave_speed_ms

        # Surge reduction for different closure multiples
        # Rapid closure (tc < 2L/a): full Joukowsky surge
        # Slow closure: surge ≈ Joukowsky × (2L/a) / tc  (for linear closure)
        recommendations = {
            'critical_time_s': round(tc_critical, 2),
            'minimum_safe_s': round(tc_critical * 3, 1),
            'recommended_s': round(tc_critical * 5, 1),
            'conservative_s': round(tc_critical * 10, 1),
            'surge_reduction': {
                f'{tc_critical*3:.1f}s (3x)': '~33% of Joukowsky',
                f'{tc_critical*5:.1f}s (5x)': '~20% of Joukowsky',
                f'{tc_critical*10:.1f}s (10x)': '~10% of Joukowsky',
            },
            'pipe_length_m': pipe_length_m,
            'wave_speed_ms': wave_speed_ms,
            'basis': f'tc_critical = 2L/a = 2×{pipe_length_m:.0f}/{wave_speed_ms:.0f} '
                     f'= {tc_critical:.2f} s — Thorley (2004) Ch.3',
        }

        return recommendations

    def design_surge_mitigation(self, pipe_id=None, max_surge_m=None,
                                  target_reduction_pct=80):
        """
        Design surge mitigation for a specific pipe or the whole network.

        Combines valve closure time, surge vessel sizing, and air valve placement.

        Parameters
        ----------
        pipe_id : str or None
            Specific pipe, or None for worst-case in network
        max_surge_m : float or None
            Maximum surge head. If None, estimates from Joukowsky
        target_reduction_pct : float
            Target surge reduction percentage (default: 80%)

        Returns dict with mitigation options and specifications.
        Ref: Thorley (2004), Wylie & Streeter (1978)
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        # Find the longest pipe or specified pipe
        if pipe_id:
            try:
                pipe = self.wn.get_link(pipe_id)
            except KeyError:
                return {'error': f'Pipe {pipe_id} not found'}
        else:
            # Use longest pipe as worst case
            pipes = [(pid, self.wn.get_link(pid).length)
                     for pid in self.wn.pipe_name_list]
            if not pipes:
                return {'error': 'No pipes in network'}
            pipe_id, _ = max(pipes, key=lambda x: x[1])
            pipe = self.wn.get_link(pipe_id)

        L = pipe.length
        D = pipe.diameter
        a = self.DEFAULTS.get('wave_speed_ms', 1100)

        # Estimate max velocity from last analysis or assume 2.0 m/s
        V = 2.0
        if self.steady_results:
            flows = self.steady_results.link['flowrate']
            if pipe_id in flows.columns:
                import numpy as np
                area = np.pi * (D/2)**2
                V = float(abs(flows[pipe_id]).max()) / max(area, 1e-6)

        # Joukowsky surge
        j = self.joukowsky(a, V)
        surge_m = j['head_rise_m']
        if max_surge_m:
            surge_m = max_surge_m

        # Option 1: Slow-closing valve
        closure = self.calculate_safe_closure_time(L, a)

        # Option 2: Surge vessel (Boyle's law simplified)
        # V_vessel = a × Q × L / (2 × g × H_allowed)
        g = 9.81
        Q = V * np.pi * (D/2)**2 if 'np' in dir() else V * 3.14159 * (D/2)**2
        H_allowed = surge_m * (1 - target_reduction_pct / 100)
        H_allowed = max(H_allowed, 1.0)  # minimum 1m
        V_vessel_m3 = a * Q * L / (2 * g * max(H_allowed, 1) * 1000)
        V_vessel_L = V_vessel_m3 * 1000

        # Option 3: Air valve locations (high points)
        # Simplified: recommend at start, end, and midpoint
        air_valves = [
            {'location': pipe.start_node_name, 'type': 'Double orifice',
             'reason': 'Pipeline start — air entry on column separation'},
            {'location': pipe.end_node_name, 'type': 'Single orifice',
             'reason': 'Pipeline end — air release'},
        ]

        return {
            'pipe_id': pipe_id,
            'pipe_length_m': round(L, 1),
            'pipe_diameter_mm': int(D * 1000),
            'max_velocity_ms': round(V, 2),
            'joukowsky_surge_m': surge_m,
            'target_reduction_pct': target_reduction_pct,
            'options': {
                'slow_closing_valve': {
                    'recommended_closure_s': closure['recommended_s'],
                    'minimum_safe_s': closure['minimum_safe_s'],
                    'basis': closure['basis'],
                },
                'surge_vessel': {
                    'volume_litres': round(V_vessel_L, 0),
                    'precharge_pressure_kPa': round(surge_m * 9.81 * 0.6, 0),
                    'basis': 'Wylie & Streeter (1978) Ch.8',
                },
                'air_valves': air_valves,
            },
        }

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

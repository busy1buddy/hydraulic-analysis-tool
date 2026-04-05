"""Resilience mixin: Todini index, hydraulic fingerprint, reliability analysis."""
import os
import math
import wntr


class ResilienceMixin:

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
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        if results is None:
            try:
                results = self.run_steady_state(save_plot=False)
            except Exception as e:
                return {'error': f'Analysis failed: {e}'}

        pressures = results.get('pressures', {})
        flows = results.get('flows', {})

        if not pressures or not flows:
            return {'error': 'No analysis results available. Fix: Run api.run_steady_state() first.'}

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
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        try:
            results = self.run_steady_state(save_plot=False)
        except Exception as e:
            return {'error': f'Analysis failed: {e}'}

        pressures = results.get('pressures', {})
        flows = results.get('flows', {})

        if not pressures or not flows:
            return {'error': 'No analysis results available. Fix: Run api.run_steady_state() first.'}

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
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

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
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

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
    # WATER SECURITY VULNERABILITY ANALYSIS (O3)
    # =========================================================================

    def water_security_analysis(self, injection_duration_hrs=4):
        """
        Identify vulnerable points for contamination or attack.

        Uses source tracing to determine which nodes could be affected by
        contamination injected at each source candidate. Nodes with highest
        downstream impact score are the most critical vulnerabilities.

        Parameters
        ----------
        injection_duration_hrs : float
            Duration of hypothetical contamination event (hours)

        Returns dict with vulnerability ranking and security recommendations.
        Ref: USEPA (2004) "Water Security Analysis for Utilities";
             Davis & Janke (2008) "Importance of contaminant properties in
             water distribution system vulnerability"
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        # Build network graph for downstream analysis
        adj = {}
        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            sn = pipe.start_node_name
            en = pipe.end_node_name
            adj.setdefault(sn, set()).add(en)
            adj.setdefault(en, set()).add(sn)

        # For each junction, count how many downstream customers
        # (via BFS from injection point)
        all_junctions = list(self.wn.junction_name_list)

        def count_reachable(start):
            visited = {start}
            queue = [start]
            while queue:
                node = queue.pop(0)
                for neighbor in adj.get(node, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            # Count reachable junctions
            return len(visited & set(all_junctions))

        # Rank vulnerability by reachability
        vulnerabilities = []
        total_junctions = len(all_junctions)
        for jid in all_junctions:
            reachable = count_reachable(jid)
            try:
                demand = self.wn.get_node(jid).demand_timeseries_list[0].base_value * 1000
            except (IndexError, AttributeError):
                demand = 0

            # Vulnerability score: % of network reachable × demand weighting
            vulnerability = reachable / max(total_junctions, 1)
            vulnerabilities.append({
                'node': jid,
                'reachable_nodes': reachable,
                'reachable_pct': round(vulnerability * 100, 1),
                'node_demand_lps': round(demand, 2),
                'risk_level': ('CRITICAL' if vulnerability > 0.6
                              else 'HIGH' if vulnerability > 0.3
                              else 'MEDIUM' if vulnerability > 0.1
                              else 'LOW'),
            })

        # Sort by reachability descending (most critical first)
        vulnerabilities.sort(key=lambda v: v['reachable_nodes'], reverse=True)

        # Recommendations
        n_critical = sum(1 for v in vulnerabilities if v['risk_level'] == 'CRITICAL')
        recommendations = []
        if n_critical > 0:
            recommendations.append(
                f'{n_critical} nodes are CRITICAL vulnerabilities — '
                f'install water quality sensors at these points')
        recommendations.append(
            'Physical security at reservoirs and treatment plants')
        recommendations.append(
            'Consider real-time chlorine residual monitoring at top-10 critical nodes')
        recommendations.append(
            'Establish response protocols for contamination events')

        return {
            'vulnerabilities': vulnerabilities,
            'top_10_critical': vulnerabilities[:10],
            'summary': {
                'critical': n_critical,
                'high': sum(1 for v in vulnerabilities if v['risk_level'] == 'HIGH'),
                'medium': sum(1 for v in vulnerabilities if v['risk_level'] == 'MEDIUM'),
                'low': sum(1 for v in vulnerabilities if v['risk_level'] == 'LOW'),
            },
            'recommendations': recommendations,
            'injection_duration_hrs': injection_duration_hrs,
            'reference': 'USEPA (2004); Davis & Janke (2008)',
        }

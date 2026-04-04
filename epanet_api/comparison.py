"""Comparison mixin: network comparison and scenario difference reporting."""
import wntr


class ComparisonMixin:

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
    # O8 — CROSS-NETWORK (PORTFOLIO) ANALYSIS
    # =========================================================================

    def portfolio_analysis(self, inp_paths, labels=None):
        """
        Compare a portfolio of networks side-by-side.

        For consultants or utilities managing many networks, produces a single
        comparison table showing inventory, total length, pressure compliance,
        and grade for each network.

        Parameters
        ----------
        inp_paths : list of str
            Paths to .inp files to compare
        labels : list of str or None
            Optional labels (defaults to filenames)

        Returns dict with per-network summary and portfolio-wide aggregates.
        """
        import os as _os
        import wntr as _wntr

        if not inp_paths:
            return {'error': 'No networks provided'}

        if labels is None:
            labels = [_os.path.splitext(_os.path.basename(p))[0] for p in inp_paths]
        if len(labels) != len(inp_paths):
            return {'error': 'labels length must match inp_paths length'}

        # Preserve current state
        saved_wn = self.wn
        saved_inp = getattr(self, '_inp_file', None)

        networks = []
        try:
            for path, label in zip(inp_paths, labels):
                if not _os.path.exists(path):
                    networks.append({'label': label, 'path': path,
                                     'error': 'File not found'})
                    continue
                try:
                    wn = _wntr.network.WaterNetworkModel(path)
                    self.wn = wn
                    self._inp_file = path

                    total_len = sum(wn.get_link(p).length
                                    for p in wn.pipe_name_list)

                    try:
                        res = self.run_steady_state(save_plot=False)
                        compliance = res.get('compliance', [])
                        n_alerts = (len(compliance)
                                    if isinstance(compliance, list) else 0)
                        pressures = res.get('pressures', {})
                        if pressures:
                            p_vals = [p.get('avg_m', 0)
                                      for p in pressures.values()]
                            avg_p = sum(p_vals) / len(p_vals)
                            min_p = min(p_vals)
                        else:
                            avg_p, min_p = 0, 0
                    except Exception:
                        n_alerts, avg_p, min_p = None, None, None

                    if n_alerts is None:
                        grade = 'N/A'
                    elif n_alerts == 0:
                        grade = 'A'
                    elif n_alerts <= 3:
                        grade = 'B'
                    elif n_alerts <= 10:
                        grade = 'C'
                    else:
                        grade = 'D'

                    networks.append({
                        'label': label,
                        'path': path,
                        'n_junctions': len(wn.junction_name_list),
                        'n_pipes': len(wn.pipe_name_list),
                        'n_pumps': len(wn.pump_name_list),
                        'n_tanks': len(wn.tank_name_list),
                        'n_reservoirs': len(wn.reservoir_name_list),
                        'total_length_km': round(total_len / 1000, 2),
                        'n_alerts': n_alerts,
                        'avg_pressure_m': (round(avg_p, 1)
                                           if avg_p is not None else None),
                        'min_pressure_m': (round(min_p, 1)
                                           if min_p is not None else None),
                        'grade': grade,
                    })
                except Exception as e:
                    networks.append({'label': label, 'path': path,
                                     'error': f'Load failed: {e}'})
        finally:
            self.wn = saved_wn
            self._inp_file = saved_inp

        valid = [n for n in networks if 'error' not in n]
        portfolio_summary = {}
        if valid:
            portfolio_summary = {
                'n_networks': len(valid),
                'total_junctions': sum(n['n_junctions'] for n in valid),
                'total_pipes': sum(n['n_pipes'] for n in valid),
                'total_length_km': round(
                    sum(n['total_length_km'] for n in valid), 2),
                'total_alerts': sum((n['n_alerts'] or 0) for n in valid),
                'grade_distribution': {
                    g: sum(1 for n in valid if n['grade'] == g)
                    for g in ['A', 'B', 'C', 'D']
                },
            }

        return {
            'networks': networks,
            'portfolio_summary': portfolio_summary,
            'n_failed': len(networks) - len(valid),
        }

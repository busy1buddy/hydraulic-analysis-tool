"""Calibration mixin: sensitivity, Monte Carlo, auto-calibration, leakage analysis."""
import numpy as np


class CalibrationMixin:
    def set_field_measurement(self, node_id, pressure_m=None, flow_lps=None):
        """
        Store a field measurement for a specific node.
        """
        if not hasattr(self, '_field_data'):
            self._field_data = {}
            
        self._field_data[node_id] = {
            'pressure_m': pressure_m,
            'flow_lps': flow_lps
        }

    def get_calibration_residuals(self):
        """
        Compare the most recent model results with field data.
        """
        if self.wn is None:
            return {'error': 'No network loaded.'}
            
        if not hasattr(self, '_field_data') or not self._field_data:
            return {'error': 'No field measurements set.'}
            
        results = self.run_steady_state(save_plot=False)
        pressures = results.get('pressures', {})
        
        residuals = []
        errors_p = []
        
        for node_id, measured in self._field_data.items():
            model_p = pressures.get(node_id, {}).get('avg_m')
            
            if model_p is not None and measured['pressure_m'] is not None:
                error = model_p - measured['pressure_m']
                errors_p.append(error)
                residuals.append({
                    'node_id': node_id,
                    'measured_p': measured['pressure_m'],
                    'model_p': round(model_p, 2),
                    'error_p': round(error, 2),
                    'error_percent': round((error / measured['pressure_m']) * 100, 1) if measured['pressure_m'] != 0 else 0
                })
                
        # Aggregate stats
        stats = {
            'mae_p': round(float(np.mean(np.abs(errors_p))), 3) if errors_p else 0,
            'rmse_p': round(float(np.sqrt(np.mean(np.square(errors_p)))), 3) if errors_p else 0,
            'max_error_p': round(float(np.max(np.abs(errors_p))), 3) if errors_p else 0
        }
        
        return {
            'residuals': residuals,
            'stats': stats
        }

    def set_fire_flow_test(self, node_id, test_flow_lps, measured_pressure_m):
        """
        Record a fire flow test event for calibration.
        """
        if not hasattr(self, '_fire_tests'):
            self._fire_tests = []
            
        self._fire_tests.append({
            'node_id': node_id,
            'flow_lps': test_flow_lps,
            'measured_p': measured_pressure_m
        })

    def run_fire_test_verification(self):
        """
        Run the model for each fire test and calculate accuracy.
        """
        if not hasattr(self, '_fire_tests') or not self._fire_tests:
            return []
            
        results = []
        for test in self._fire_tests:
            node_id = test['node_id']
            # Save original demand
            junc = self.wn.get_node(node_id)
            orig_demand = junc.demand_timeseries_list[0].base_value
            
            # Apply test flow
            junc.demand_timeseries_list[0].base_value = (test['flow_lps'] / 1000.0)
            
            # Run
            try:
                sim_res = self.run_steady_state(save_plot=False)
                model_p = sim_res['pressures'].get(node_id, {}).get('avg_m', 0)
                results.append({
                    'node_id': node_id,
                    'test_flow_lps': test['flow_lps'],
                    'measured_p': test['measured_p'],
                    'model_p': round(model_p, 2),
                    'error_p': round(model_p - test['measured_p'], 2)
                })
            finally:
                # Restore
                junc.demand_timeseries_list[0].base_value = orig_demand
                
        return results

    def apply_global_demand_multiplier(self, multiplier):
        """
        Apply a multiplier to all junction base demands.
        Useful for matching total system inflow.
        """
        if self.wn is None:
            return
            
        for jid in self.wn.junction_name_list:
            junc = self.wn.get_node(jid)
            if junc.demand_timeseries_list:
                for ts in junc.demand_timeseries_list:
                    ts.base_value *= multiplier
                
        logger.info(f"Applied global demand multiplier: {multiplier}")

    def generate_calibration_report(self):
        """
        Generate a summary report of the calibration status.
        """
        residuals = self.get_calibration_residuals()
        fire_tests = self.run_fire_test_verification()
        
        report = {
            'summary': residuals.get('stats', {}),
            'node_residuals': residuals.get('residuals', []),
            'fire_test_results': fire_tests,
            'timestamp': str(np.datetime64('now')),
            'status': 'Calibrated' if residuals.get('stats', {}).get('rmse_p', 10) < 2.0 else 'Verification Required'
        }
        return report

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
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

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
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

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

    def auto_calibrate_roughness(self, measured_pressures=None, material_groups=None):
        """
        Automatically calibrate pipe roughness (Hazen-Williams C) by minimising
        pressure residuals using scipy.optimize.minimize.

        Groups pipes by material and adjusts C-factors to minimise the sum of
        squared pressure differences between modelled and measured values.

        Parameters
        ----------
        measured_pressures : dict or None
            {node_id: measured_pressure_m} — field measurements at junctions.
            If None, uses stored _field_data.
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
        import wntr

        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        if measured_pressures is None:
            if not hasattr(self, '_field_data'):
                return {'error': 'No field data provided for calibration.'}
            measured_pressures = {nid: d['pressure_m'] for nid, d in self._field_data.items() if d['pressure_m'] is not None}
            
        if not measured_pressures:
            return {'error': 'No measured pressure data available.'}

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
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

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

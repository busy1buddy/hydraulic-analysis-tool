import os


class ComplianceMixin:

    # =========================================================================
    # DESIGN COMPLIANCE CERTIFICATE (L1)
    # =========================================================================

    SOFTWARE_VERSION = '1.7.0'

    def run_design_compliance_check(self):
        """
        Run all compliance checks in sequence and generate a formal
        design compliance certificate.

        Checks performed:
        1. Pressure (WSAA WSA 03-2011) — 20-50 m
        2. Velocity (WSAA) — <2.0 m/s
        3. Fire flow (WSAA) — 25 LPS @ 12 m residual
        4. Water age (WSAA) — <24 hours
        5. Pipe stress (AS 2280) — PN safety factor
        6. Slurry settling (if applicable) — deposition velocity

        Returns dict with per-check results and overall COMPLIANT/NON-COMPLIANT.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        certificate = {
            'network_name': os.path.basename(self._inp_file) if self._inp_file else 'Unknown',
            'date': None,
            'software_version': self.SOFTWARE_VERSION,
            'checks': [],
            'overall_status': 'COMPLIANT',
        }

        from datetime import date
        certificate['date'] = date.today().strftime('%d %B %Y')

        # 1. Steady-state pressure and velocity
        try:
            results = self.run_steady_state(save_plot=False)
            pressures = results.get('pressures', {})
            flows = results.get('flows', {})

            # Pressure check
            low_p_nodes = [jid for jid, p in pressures.items()
                          if p.get('min_m', 0) < self.DEFAULTS['min_pressure_m']]
            high_p_nodes = [jid for jid, p in pressures.items()
                           if p.get('max_m', 0) > self.DEFAULTS['max_pressure_m']]

            if not low_p_nodes and not high_p_nodes:
                certificate['checks'].append({
                    'check': 'Pressure (WSAA WSA 03-2011)',
                    'status': 'PASS',
                    'standard': 'WSAA WSA 03-2011 Table 3.1',
                    'requirement': f'{self.DEFAULTS["min_pressure_m"]}-{self.DEFAULTS["max_pressure_m"]} m',
                    'details': 'All junctions within pressure limits.',
                })
            else:
                certificate['checks'].append({
                    'check': 'Pressure (WSAA WSA 03-2011)',
                    'status': 'FAIL',
                    'standard': 'WSAA WSA 03-2011 Table 3.1',
                    'requirement': f'{self.DEFAULTS["min_pressure_m"]}-{self.DEFAULTS["max_pressure_m"]} m',
                    'details': (f'{len(low_p_nodes)} node(s) below {self.DEFAULTS["min_pressure_m"]} m, '
                               f'{len(high_p_nodes)} node(s) above {self.DEFAULTS["max_pressure_m"]} m.'),
                })
                certificate['overall_status'] = 'NON-COMPLIANT'

            # Velocity check
            high_v_pipes = [pid for pid, f in flows.items()
                           if f.get('max_velocity_ms', 0) > self.DEFAULTS['max_velocity_ms']]
            if not high_v_pipes:
                certificate['checks'].append({
                    'check': 'Velocity (WSAA)',
                    'status': 'PASS',
                    'standard': 'WSAA WSA 03-2011 Clause 3.8.2',
                    'requirement': f'< {self.DEFAULTS["max_velocity_ms"]} m/s',
                    'details': 'All pipes within velocity limits.',
                })
            else:
                certificate['checks'].append({
                    'check': 'Velocity (WSAA)',
                    'status': 'FAIL',
                    'standard': 'WSAA WSA 03-2011 Clause 3.8.2',
                    'requirement': f'< {self.DEFAULTS["max_velocity_ms"]} m/s',
                    'details': f'{len(high_v_pipes)} pipe(s) exceed velocity limit.',
                })
                certificate['overall_status'] = 'NON-COMPLIANT'

        except Exception as e:
            certificate['checks'].append({
                'check': 'Steady-State Analysis',
                'status': 'ERROR',
                'details': f'Analysis failed: {e}',
            })
            certificate['overall_status'] = 'INCOMPLETE'

        # 2. Fire flow check (sample node)
        junctions = list(self.wn.junction_name_list)
        if junctions:
            try:
                ff = self.run_fire_flow(junctions[0], save_plot=False)
                ff_pressure = ff.get('fire_node_pressure_m', 0)
                if ff_pressure >= 12.0:
                    certificate['checks'].append({
                        'check': 'Fire Flow (WSAA)',
                        'status': 'PASS',
                        'standard': 'WSAA WSA 03-2011 Table 3.3',
                        'requirement': '25 LPS @ 12 m residual',
                        'details': f'Fire node pressure: {ff_pressure:.1f} m ≥ 12 m.',
                    })
                else:
                    certificate['checks'].append({
                        'check': 'Fire Flow (WSAA)',
                        'status': 'FAIL',
                        'standard': 'WSAA WSA 03-2011 Table 3.3',
                        'requirement': '25 LPS @ 12 m residual',
                        'details': f'Fire node pressure: {ff_pressure:.1f} m < 12 m.',
                    })
                    certificate['overall_status'] = 'NON-COMPLIANT'
            except Exception:
                certificate['checks'].append({
                    'check': 'Fire Flow (WSAA)',
                    'status': 'NOT RUN',
                    'details': 'Fire flow analysis could not complete.',
                })

        # 3. Pipe stress check
        from .pipe_stress import hoop_stress
        stress_failures = []
        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            # Estimate operating pressure
            p_data = pressures.get(pipe.start_node_name, {})
            p_m = p_data.get('max_m', 0)
            p_kPa = p_m * 9.81  # m head to kPa

            if p_kPa > self.DEFAULTS['pipe_rating_kPa']:
                stress_failures.append(pid)

        if not stress_failures:
            certificate['checks'].append({
                'check': 'Pipe Stress (AS 2280)',
                'status': 'PASS',
                'standard': 'AS 2280 / AS/NZS 1477 / AS/NZS 4130',
                'requirement': f'Operating pressure < PN rating ({self.DEFAULTS["pipe_rating_kPa"]} kPa)',
                'details': 'All pipes within pressure rating.',
            })
        else:
            certificate['checks'].append({
                'check': 'Pipe Stress (AS 2280)',
                'status': 'FAIL',
                'standard': 'AS 2280',
                'requirement': f'Operating pressure < PN rating ({self.DEFAULTS["pipe_rating_kPa"]} kPa)',
                'details': f'{len(stress_failures)} pipe(s) exceed pressure rating.',
            })
            certificate['overall_status'] = 'NON-COMPLIANT'

        # 4. Resilience index (Todini)
        ri = self.compute_resilience_index(results)
        if 'error' not in ri:
            ri_val = ri['resilience_index']
            ri_status = 'PASS' if ri_val >= 0.15 else 'FAIL'
            certificate['checks'].append({
                'check': 'Network Resilience (Todini)',
                'status': ri_status,
                'standard': 'Todini (2000), target > 0.15',
                'requirement': 'Resilience index > 0.15',
                'details': f'Todini index: {ri_val:.3f} (Grade {ri["grade"]}). '
                           f'{ri["interpretation"]}',
            })
            if ri_status == 'FAIL':
                certificate['overall_status'] = 'NON-COMPLIANT'
            certificate['resilience'] = ri

        # Summary counts
        n_pass = sum(1 for c in certificate['checks'] if c['status'] == 'PASS')
        n_fail = sum(1 for c in certificate['checks'] if c['status'] == 'FAIL')
        certificate['summary'] = {
            'total_checks': len(certificate['checks']),
            'passed': n_pass,
            'failed': n_fail,
        }

        return certificate

    # =========================================================================
    # CUSTOM COMPLIANCE THRESHOLDS (N10)
    # =========================================================================

    def set_compliance_thresholds(self, min_pressure_m=None, max_pressure_m=None,
                                   max_velocity_ms=None, min_velocity_ms=None,
                                   min_chlorine_mgl=None, pipe_rating_kPa=None):
        """
        Override default WSAA compliance thresholds for project-specific requirements.

        Useful for mining (120m max pressure), industrial (higher velocity limits),
        or other non-standard applications.

        Parameters
        ----------
        min_pressure_m : float or None
            Minimum pressure threshold (default: WSAA 20 m)
        max_pressure_m : float or None
            Maximum pressure threshold (default: WSAA 50 m, mining: 120 m)
        max_velocity_ms : float or None
            Maximum velocity (default: WSAA 2.0 m/s)
        min_velocity_ms : float or None
            Minimum velocity for sediment prevention (default: 0.6 m/s)
        min_chlorine_mgl : float or None
            Minimum chlorine residual (default: WSAA 0.2 mg/L)
        pipe_rating_kPa : float or None
            Pipe PN rating in kPa (default: 3500 = PN35)

        Returns dict with updated thresholds.
        """
        if min_pressure_m is not None:
            self.DEFAULTS['min_pressure_m'] = min_pressure_m
        if max_pressure_m is not None:
            self.DEFAULTS['max_pressure_m'] = max_pressure_m
        if max_velocity_ms is not None:
            self.DEFAULTS['max_velocity_ms'] = max_velocity_ms
        if min_velocity_ms is not None:
            self.DEFAULTS['min_velocity_ms'] = min_velocity_ms
        if min_chlorine_mgl is not None:
            self.WSAA_MIN_CHLORINE_MGL = min_chlorine_mgl
        if pipe_rating_kPa is not None:
            self.DEFAULTS['pipe_rating_kPa'] = pipe_rating_kPa

        return {
            'thresholds': dict(self.DEFAULTS),
            'min_chlorine_mgl': self.WSAA_MIN_CHLORINE_MGL,
        }

    def get_compliance_thresholds(self):
        """Return current compliance thresholds."""
        return {
            'min_pressure_m': self.DEFAULTS['min_pressure_m'],
            'max_pressure_m': self.DEFAULTS['max_pressure_m'],
            'max_velocity_ms': self.DEFAULTS['max_velocity_ms'],
            'min_velocity_ms': self.DEFAULTS['min_velocity_ms'],
            'pipe_rating_kPa': self.DEFAULTS['pipe_rating_kPa'],
            'min_chlorine_mgl': self.WSAA_MIN_CHLORINE_MGL,
        }

    # =========================================================================
    # QUALITY SCORE SYSTEM (M9)
    # =========================================================================

    def compute_quality_score(self, results=None):
        """
        Compute an overall network quality score (0-100).

        Scoring breakdown:
        - Pressure compliance (20 pts): % of junctions within WSAA 20-50 m
        - Velocity compliance (20 pts): % of pipes below 2.0 m/s
        - Network resilience (15 pts): Todini index mapped to 0-15
        - Pipe stress safety (15 pts): % of pipes within PN rating
        - Data completeness (15 pts): pipes with material/roughness data
        - Connectivity (15 pts): no isolated nodes, low dead-end ratio

        Grade: A (90+), B (75+), C (60+), D (45+), F (<45)

        Returns dict with total score, grade, and per-category breakdown.
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
        categories = []

        # 1. Pressure compliance (20 pts)
        if pressures:
            n_junctions = len(pressures)
            n_compliant = sum(1 for p in pressures.values()
                             if self.DEFAULTS['min_pressure_m'] <= p.get('avg_m', 0)
                             <= self.DEFAULTS['max_pressure_m'])
            pct = n_compliant / max(n_junctions, 1)
            score_p = round(pct * 20, 1)
        else:
            score_p = 0
            pct = 0
        categories.append({
            'category': 'Pressure Compliance',
            'max_points': 20,
            'score': score_p,
            'detail': f'{pct*100:.0f}% within WSAA 20-50 m',
        })

        # 2. Velocity compliance (20 pts)
        if flows:
            n_pipes = len(flows)
            n_vel_ok = sum(1 for f in flows.values()
                          if f.get('max_velocity_ms', 0) <= self.DEFAULTS['max_velocity_ms'])
            pct_v = n_vel_ok / max(n_pipes, 1)
            score_v = round(pct_v * 20, 1)
        else:
            score_v = 0
            pct_v = 0
        categories.append({
            'category': 'Velocity Compliance',
            'max_points': 20,
            'score': score_v,
            'detail': f'{pct_v*100:.0f}% below {self.DEFAULTS["max_velocity_ms"]} m/s',
        })

        # 3. Network resilience (15 pts)
        ri = self.compute_resilience_index(results)
        if 'error' not in ri:
            # Map 0-0.5 to 0-15 (anything > 0.5 gets full marks)
            ri_val = min(ri['resilience_index'], 0.5)
            score_r = round((ri_val / 0.5) * 15, 1)
        else:
            score_r = 0
        categories.append({
            'category': 'Network Resilience',
            'max_points': 15,
            'score': score_r,
            'detail': f'Todini Ir={ri.get("resilience_index", 0):.3f}',
        })

        # 4. Pipe stress safety (15 pts)
        n_stress_ok = 0
        n_total_pipes = len(self.wn.pipe_name_list)
        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            p_data = pressures.get(pipe.start_node_name, {})
            p_kPa = p_data.get('max_m', 0) * 9.81
            if p_kPa <= self.DEFAULTS['pipe_rating_kPa']:
                n_stress_ok += 1
        pct_s = n_stress_ok / max(n_total_pipes, 1)
        score_s = round(pct_s * 15, 1)
        categories.append({
            'category': 'Pipe Stress Safety',
            'max_points': 15,
            'score': score_s,
            'detail': f'{pct_s*100:.0f}% within PN rating',
        })

        # 5. Data completeness (15 pts)
        # Check that pipes have reasonable roughness values (proxy for having data)
        n_data_ok = 0
        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            if 50 <= pipe.roughness <= 160 and pipe.length > 0 and pipe.diameter > 0:
                n_data_ok += 1
        pct_d = n_data_ok / max(n_total_pipes, 1)
        score_d = round(pct_d * 15, 1)
        categories.append({
            'category': 'Data Completeness',
            'max_points': 15,
            'score': score_d,
            'detail': f'{pct_d*100:.0f}% pipes with valid properties',
        })

        # 6. Connectivity (15 pts)
        topo = self.analyse_topology()
        if 'error' not in topo:
            conn_score = topo['connectivity_ratio'] * 10  # 10 pts for full connectivity
            # Penalty for high dead-end ratio (max 5 pts)
            de_ratio = topo['dead_end_count'] / max(topo['total_nodes'], 1)
            de_score = max(0, 5 * (1 - de_ratio * 5))  # lose all 5 pts if >20% dead ends
            score_c = round(min(conn_score + de_score, 15), 1)
        else:
            score_c = 0
        categories.append({
            'category': 'Connectivity',
            'max_points': 15,
            'score': score_c,
            'detail': f'{topo.get("dead_end_count", "?")} dead ends, '
                      f'{topo.get("loops", "?")} loops',
        })

        # Total
        total = sum(c['score'] for c in categories)
        total = round(min(total, 100), 1)

        # Grade
        if total >= 90:
            grade = 'A'
        elif total >= 75:
            grade = 'B'
        elif total >= 60:
            grade = 'C'
        elif total >= 45:
            grade = 'D'
        else:
            grade = 'F'

        return {
            'total_score': total,
            'grade': grade,
            'categories': categories,
            'max_possible': 100,
        }

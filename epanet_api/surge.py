"""Surge mixin: surge protection design, water hammer sizing, surge mitigation."""
import math
import numpy as np


class SurgeMixin:

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
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

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
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

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

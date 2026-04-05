import os


class SlurryMixin:

    # =========================================================================
    # SLURRY PIPELINE DESIGN REPORT (M6)
    # =========================================================================

    def slurry_design_report(self, d_particle_mm=0.5, rho_solid=2650,
                              concentration_vol=0.15, rho_fluid=1000,
                              mu_fluid=0.001):
        """
        Generate a comprehensive slurry pipeline design report.

        Analyses every pipe for critical deposition velocity (Durand and Wasp),
        settling risk, and pump derating.

        Parameters
        ----------
        d_particle_mm : float
            Median particle diameter d50 (mm)
        rho_solid : float
            Solid particle density (kg/m³)
        concentration_vol : float
            Volumetric solids concentration (0-1)
        rho_fluid : float
            Carrier fluid density (kg/m³)
        mu_fluid : float
            Dynamic viscosity (Pa·s)

        Returns dict with per-pipe analysis and overall recommendations.
        Ref: Wilson, Addie & Clift (2006); Durand (1952); Wasp et al. (1977)
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        from slurry_solver import (critical_deposition_velocity,
                                    wasp_critical_velocity,
                                    settling_velocity,
                                    derate_pump_for_slurry)

        # Run steady-state to get actual velocities
        try:
            results = self.run_steady_state(save_plot=False)
        except Exception as e:
            return {'error': f'Analysis failed: {e}'}

        flows = results.get('flows', {})

        # Settling velocity for particles
        ws = settling_velocity(d_particle_mm, rho_solid, rho_fluid, mu_fluid)

        # Mixture properties
        S_m = 1 + concentration_vol * (rho_solid / rho_fluid - 1)

        pipe_analysis = []
        n_at_risk = 0
        n_below_critical = 0

        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            dn_mm = int(pipe.diameter * 1000)  # convert WNTR m to mm
            fdata = flows.get(pid, {})
            v_actual = fdata.get('max_velocity_ms', 0)

            # Durand critical velocity
            durand = critical_deposition_velocity(
                d_particle_mm, dn_mm, rho_solid, rho_fluid, concentration_vol)

            # Wasp critical velocity
            wasp = wasp_critical_velocity(
                d_particle_mm, dn_mm, rho_solid, rho_fluid,
                concentration_vol, mu_fluid)

            # Use the higher of the two as design critical velocity
            v_crit_durand = durand.get('velocity_ms', 0)
            v_crit_wasp = wasp.get('velocity_ms', 0)
            v_crit = max(v_crit_durand, v_crit_wasp)

            # Safety margin
            if v_crit > 0:
                safety_margin = (v_actual - v_crit) / v_crit * 100
            else:
                safety_margin = 100  # no risk if critical velocity is 0

            status = 'OK'
            if v_actual < v_crit:
                status = 'BELOW CRITICAL'
                n_below_critical += 1
            elif safety_margin < 20:
                status = 'AT RISK'
                n_at_risk += 1

            pipe_analysis.append({
                'pipe_id': pid,
                'diameter_mm': dn_mm,
                'length_m': round(pipe.length, 1),
                'actual_velocity_ms': round(v_actual, 2),
                'critical_velocity_durand_ms': v_crit_durand,
                'critical_velocity_wasp_ms': v_crit_wasp,
                'design_critical_ms': round(v_crit, 2),
                'safety_margin_pct': round(safety_margin, 1),
                'status': status,
            })

        # Sort by safety margin (most at-risk first)
        pipe_analysis.sort(key=lambda x: x['safety_margin_pct'])

        return {
            'carrier_fluid': {
                'density_kgm3': rho_fluid,
                'viscosity_Pa_s': mu_fluid,
            },
            'solids': {
                'd50_mm': d_particle_mm,
                'density_kgm3': rho_solid,
                'concentration_vol': concentration_vol,
                'settling_velocity_ms': ws['velocity_ms'],
                'settling_regime': ws.get('regime', 'unknown'),
            },
            'mixture': {
                'density_kgm3': round(S_m * rho_fluid, 1),
                'specific_gravity': round(S_m, 3),
            },
            'pipe_analysis': pipe_analysis,
            'summary': {
                'total_pipes': len(pipe_analysis),
                'below_critical': n_below_critical,
                'at_risk': n_at_risk,
                'safe': len(pipe_analysis) - n_below_critical - n_at_risk,
            },
        }

"""Forecasting mixin: demand forecasting."""
import math


class ForecastingMixin:

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

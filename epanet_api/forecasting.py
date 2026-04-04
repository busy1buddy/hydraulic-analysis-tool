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

    # =========================================================================
    # CLIMATE CHANGE DEMAND PROJECTION (O2)
    # =========================================================================

    def climate_demand_projection(self, base_year=2026, target_years=None,
                                    climate_scenario='medium'):
        """
        Project demand under climate change scenarios.

        Combines population growth with climate-driven per-capita demand changes.
        Australian research (CSIRO, BoM) shows warming → increased water demand.

        Parameters
        ----------
        base_year : int
            Current year (default 2026)
        target_years : list of int or None
            Years to project to (default: [2030, 2040, 2050, 2070])
        climate_scenario : str
            'low' (RCP 2.6), 'medium' (RCP 4.5), 'high' (RCP 8.5)

        Returns dict with per-year demand multipliers and confidence bounds.
        Ref: CSIRO Climate Change in Australia (2015); IPCC AR6 RCP scenarios;
             BoM State of Climate Report 2020
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        if target_years is None:
            target_years = [2030, 2040, 2050, 2070]

        # Climate multipliers per year (annual compounded rates)
        # Based on CSIRO projections for Southern Australia per-capita demand
        # Low (RCP 2.6): +0.3% per year per-capita increase
        # Medium (RCP 4.5): +0.6% per year
        # High (RCP 8.5): +1.0% per year
        climate_rates = {
            'low': 0.003,
            'medium': 0.006,
            'high': 0.010,
        }

        if climate_scenario not in climate_rates:
            return {'error': f'Unknown scenario: {climate_scenario}. '
                             f'Use low/medium/high.'}

        climate_rate = climate_rates[climate_scenario]
        # Population growth assumption: 1.5% (ABS Australian average)
        pop_rate = 0.015

        projections = {}
        for year in target_years:
            years_elapsed = year - base_year
            if years_elapsed < 0:
                continue

            # Combined multiplier = (1 + climate)^n × (1 + population)^n
            climate_mult = (1 + climate_rate) ** years_elapsed
            pop_mult = (1 + pop_rate) ** years_elapsed
            combined = climate_mult * pop_mult

            # Confidence bounds (±30% uncertainty on climate rate)
            low_mult = (1 + climate_rate * 0.7) ** years_elapsed * pop_mult
            high_mult = (1 + climate_rate * 1.3) ** years_elapsed * pop_mult

            projections[year] = {
                'total_multiplier': round(combined, 3),
                'climate_multiplier': round(climate_mult, 3),
                'population_multiplier': round(pop_mult, 3),
                'low_bound': round(low_mult, 3),
                'high_bound': round(high_mult, 3),
                'years_from_base': years_elapsed,
            }

        # Current total demand
        total_base_lps = 0
        for jid in self.wn.junction_name_list:
            try:
                d = self.wn.get_node(jid).demand_timeseries_list[0].base_value
                total_base_lps += d * 1000
            except (IndexError, AttributeError):
                pass

        return {
            'scenario': climate_scenario,
            'base_year': base_year,
            'base_demand_lps': round(total_base_lps, 1),
            'climate_rate_pct_per_year': round(climate_rate * 100, 2),
            'population_rate_pct_per_year': round(pop_rate * 100, 2),
            'projections': projections,
            'reference': 'CSIRO Climate Change in Australia (2015); '
                         'IPCC AR6 RCP scenarios',
        }

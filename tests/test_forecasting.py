"""
Unit tests for ``epanet_api/forecasting.py``.

Recommendation #4 from the multi-agent review plan: ForecastingMixin had no
dedicated test file. These tests cover:

- The error contract when no network is loaded
- Linear / exponential / logistic growth multipliers (mathematical sanity)
- Monotonicity: higher growth_rate cannot delay first_failure_year
- Climate-demand projection: scenario rates, confidence bounds, error contract
"""

from __future__ import annotations

import math

import pytest


# ---------------------------------------------------------------------------
# forecast_demand
# ---------------------------------------------------------------------------

def test_forecast_demand_no_network_returns_error(api_instance):
    """Documented contract: returns {'error': ...} when no network is loaded."""
    result = api_instance.forecast_demand()
    assert isinstance(result, dict)
    assert 'error' in result


def test_forecast_demand_linear_growth_monotonic(loaded_network):
    """Linear growth: multiplier increases monotonically with year."""
    out = loaded_network.forecast_demand(
        growth_model='linear', growth_rate=0.02, base_year=2026,
        forecast_years=[2030, 2040, 2050],
    )
    forecasts = out['forecasts']
    multipliers = [forecasts[y]['multiplier'] for y in sorted(forecasts)]
    assert multipliers == sorted(multipliers), (
        f"linear growth produced non-monotonic multipliers: {multipliers}"
    )
    # 2030 = base + 4 yr × 2% = 1.080
    assert math.isclose(forecasts[2030]['multiplier'], 1.080, abs_tol=1e-3)


def test_forecast_demand_exponential_growth_compounds(loaded_network):
    """Exponential growth: (1+r)^dt; should exceed linear after several years."""
    lin = loaded_network.forecast_demand(
        growth_model='linear', growth_rate=0.02, base_year=2026,
        forecast_years=[2050],
    )
    exp = loaded_network.forecast_demand(
        growth_model='exponential', growth_rate=0.02, base_year=2026,
        forecast_years=[2050],
    )
    lin_m = lin['forecasts'][2050]['multiplier']
    exp_m = exp['forecasts'][2050]['multiplier']
    assert exp_m > lin_m, (
        f"24-year exponential ({exp_m}) should exceed linear ({lin_m})"
    )
    # 24-year exponential at 2% = 1.608
    assert math.isclose(exp_m, 1.608, abs_tol=1e-2)


def test_forecast_demand_logistic_bounded_by_carrying_capacity(loaded_network):
    """Logistic growth has K=2.0 carrying capacity — multiplier must approach 2."""
    out = loaded_network.forecast_demand(
        growth_model='logistic', growth_rate=0.10, base_year=2026,
        forecast_years=[2200],  # far future — should saturate near K=2
    )
    mult = out['forecasts'][2200]['multiplier']
    assert 1.5 < mult <= 2.0, (
        f"logistic at very long horizon should be near K=2 carrying capacity, got {mult}"
    )


def test_forecast_demand_higher_growth_advances_first_failure(loaded_network):
    """Sanity: doubling growth rate cannot delay first_failure_year."""
    slow = loaded_network.forecast_demand(
        growth_model='linear', growth_rate=0.01, base_year=2026,
        forecast_years=[2030, 2040, 2050, 2070, 2100],
    )
    fast = loaded_network.forecast_demand(
        growth_model='linear', growth_rate=0.10, base_year=2026,
        forecast_years=[2030, 2040, 2050, 2070, 2100],
    )

    slow_year = slow['first_failure_year']
    fast_year = fast['first_failure_year']

    # Either slow doesn't fail (None) and fast does, OR fast fails earlier-or-equal
    if slow_year is None and fast_year is None:
        pytest.skip("Network never fails under either growth — no signal")
    if slow_year is None:
        return  # fast fails, slow doesn't — that's exactly the expected ordering
    if fast_year is None:
        pytest.fail(
            f"slow (1%/yr) failed in {slow_year} but fast (10%/yr) reported no failure"
        )

    assert fast_year <= slow_year, (
        f"fast (10%/yr) first_failure_year {fast_year} should not be after "
        f"slow (1%/yr) first_failure_year {slow_year}"
    )


def test_forecast_demand_unknown_model_falls_back_to_linear(loaded_network):
    """Unknown model name silently falls back to linear (per current code)."""
    linear = loaded_network.forecast_demand(
        growth_model='linear', growth_rate=0.02, base_year=2026,
        forecast_years=[2050],
    )
    unknown = loaded_network.forecast_demand(
        growth_model='gompertz_typo', growth_rate=0.02, base_year=2026,
        forecast_years=[2050],
    )
    assert math.isclose(
        linear['forecasts'][2050]['multiplier'],
        unknown['forecasts'][2050]['multiplier'],
        abs_tol=1e-3,
    )


def test_forecast_demand_restores_original_demands(loaded_network):
    """After forecast_demand returns, base_demand on every junction is restored."""
    before = {}
    for jid in loaded_network.wn.junction_name_list:
        junc = loaded_network.wn.get_node(jid)
        if junc.demand_timeseries_list:
            before[jid] = junc.demand_timeseries_list[0].base_value

    loaded_network.forecast_demand(
        growth_model='exponential', growth_rate=0.05,
        base_year=2026, forecast_years=[2050, 2100],
    )

    for jid, base in before.items():
        junc = loaded_network.wn.get_node(jid)
        assert math.isclose(junc.demand_timeseries_list[0].base_value, base, rel_tol=1e-9), (
            f"forecast_demand left junction {jid} with mutated base_demand"
        )


# ---------------------------------------------------------------------------
# climate_demand_projection
# ---------------------------------------------------------------------------

def test_climate_projection_no_network_returns_error(api_instance):
    result = api_instance.climate_demand_projection()
    assert isinstance(result, dict)
    assert 'error' in result


def test_climate_projection_unknown_scenario_returns_error(loaded_network):
    result = loaded_network.climate_demand_projection(climate_scenario='extreme')
    assert 'error' in result
    assert 'low/medium/high' in result['error']


def test_climate_projection_scenarios_ordered(loaded_network):
    """High-emissions scenario must give a larger total multiplier than low for the same year."""
    low = loaded_network.climate_demand_projection(
        climate_scenario='low', target_years=[2050])
    high = loaded_network.climate_demand_projection(
        climate_scenario='high', target_years=[2050])

    low_m = low['projections'][2050]['total_multiplier']
    high_m = high['projections'][2050]['total_multiplier']
    assert high_m > low_m, (
        f"High scenario ({high_m}) should exceed low scenario ({low_m})"
    )


def test_climate_projection_confidence_bounds_bracket_central(loaded_network):
    """For each year: low_bound <= total_multiplier <= high_bound."""
    out = loaded_network.climate_demand_projection(
        climate_scenario='medium', target_years=[2030, 2050, 2070])
    for year, p in out['projections'].items():
        assert p['low_bound'] <= p['total_multiplier'] <= p['high_bound'], (
            f"year {year}: bounds {p['low_bound']}/{p['total_multiplier']}/{p['high_bound']} not ordered"
        )


def test_climate_projection_metadata_present(loaded_network):
    out = loaded_network.climate_demand_projection(climate_scenario='medium')
    meta = out.get('scenario_metadata', {})
    # The function cites CSIRO/BoM and IPCC AR6 — confirm metadata fields exist
    assert meta.get('rcp') == 'RCP 4.5'
    assert meta.get('warming_2100_c') == pytest.approx(2.4, abs=0.1)
    assert 'CSIRO' in meta.get('source', '')

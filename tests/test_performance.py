"""
Performance gate tests — wrap ``scripts/benchmark_steady_state.py`` budgets
under pytest so CI fails when the solver, EPS, or water-quality runs cross
the documented thresholds.

Phase-5 deliverable from the multi-agent review plan. Marked ``slow`` so the
default fast suite skips them; CI runs them via ``-m slow``.

Budgets (sourced from existing performance baselines):
- 1000-node steady-state ........ 250 ms (per benchmark_steady_state.py:59)
- 24 h EPS on simple_loop ........ 10 s
- 48 h water-quality (AGE) ....... 30 s

Budgets are intentionally generous (≈2× current measured time) so transient
hardware noise or test-runner overhead does not cause spurious failures.
"""

from __future__ import annotations

import os
import time

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.slow
def test_steady_state_1000_node_budget(api_instance):
    """1000-node linear network steady-state must complete < 250 ms average."""
    api_instance.create_network("perf_steady")
    api_instance.add_reservoir("R1", head_m=200.0)
    api_instance.add_junction("J0", elevation=150.0)
    api_instance.add_pipe("P0", "R1", "J0", length=100)
    for i in range(1, 1000):
        prev = f"J{i-1}"
        curr = f"J{i}"
        api_instance.add_junction(curr, elevation=max(0, 150.0 - i * 0.1))
        api_instance.set_node_demand(curr, 0.5)
        api_instance.add_pipe(f"P{i}", prev, curr, length=100,
                               diameter_m=0.3, roughness=130)

    # Warmup
    api_instance.run_steady_state(save_plot=False)

    runs = 5
    total = 0.0
    for _ in range(runs):
        t0 = time.perf_counter()
        res = api_instance.run_steady_state(save_plot=False)
        total += time.perf_counter() - t0
        assert 'error' not in res, f"steady-state failed: {res.get('error')}"

    avg_ms = (total / runs) * 1000.0
    assert avg_ms < 250.0, (
        f"1000-node steady-state averaged {avg_ms:.1f} ms, budget 250 ms — "
        f"the live what-if panel will feel laggy. Profile recent solver / "
        f"post-processing changes."
    )


@pytest.mark.slow
def test_eps_24h_simple_loop_budget(loaded_network):
    """24 h EPS on the simple_loop tutorial must complete < 10 s."""
    loaded_network.set_simulation_options(
        duration_hrs=24,
        hydraulic_timestep_s=300,
        pattern_timestep_s=300,
    )
    t0 = time.perf_counter()
    res = loaded_network.run_steady_state(save_plot=False)
    elapsed = time.perf_counter() - t0
    assert 'error' not in res, f"EPS failed: {res.get('error')}"
    assert elapsed < 10.0, (
        f"24 h EPS took {elapsed:.2f} s on australian_network, budget 10 s. "
        f"Investigate pattern handling or solver-loop changes."
    )


@pytest.mark.slow
def test_water_quality_48h_age_budget(loaded_network):
    """48 h water-quality (AGE) must complete < 30 s on a small network."""
    loaded_network.set_simulation_options(
        duration_hrs=48,
        hydraulic_timestep_s=600,
        pattern_timestep_s=600,
        quality_timestep_s=600,
    )
    loaded_network.set_water_quality_mode('AGE')
    t0 = time.perf_counter()
    res = loaded_network.run_water_quality_analysis()
    elapsed = time.perf_counter() - t0
    assert 'error' not in res, f"WQ failed: {res.get('error')}"
    assert elapsed < 30.0, (
        f"48 h water-quality run took {elapsed:.2f} s, budget 30 s. "
        f"User-visible quality_review path will appear frozen."
    )

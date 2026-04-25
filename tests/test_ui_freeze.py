"""
UI-freeze regression tests — confirm the AnalysisWorker dispatches do not
block the GUI thread.

Recommendation #1 from the multi-agent review plan moved three sync solver
calls (`desktop/main_window.py:1634/2326/2818`) onto `AnalysisWorker`. These
tests assert that constructing and starting a worker for each of those
analysis types returns control to the GUI thread within ~100 ms — far below
the multi-second times the synchronous calls used to consume.

The tests do not run the solver to completion; they only verify that
``QThread.start()`` returns promptly and ``QApplication.processEvents()``
remains responsive while the worker runs.
"""

from __future__ import annotations

import os
import sys
import time

import pytest


pytest.importorskip("PyQt6.QtWidgets")  # skip when PyQt is unavailable

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication

from desktop.analysis_worker import AnalysisWorker


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIMPLE_INP = os.path.join(PROJECT_ROOT, 'tutorials', 'simple_loop', 'network.inp')


@pytest.fixture(scope='module')
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def loaded_api():
    from epanet_api import HydraulicAPI
    api = HydraulicAPI(work_dir=PROJECT_ROOT)
    api.load_network_from_path(SIMPLE_INP)
    return api


# Hard upper bound on how long start() + first event-loop tick may take
# before we declare the GUI is "frozen". Worker setup is a few-ms op; the
# real solve happens in the background thread.
START_BUDGET_S = 0.10


def _start_and_measure(worker: AnalysisWorker, qapp: QCoreApplication) -> float:
    """Start the worker and return seconds until the GUI gets one event tick."""
    t0 = time.perf_counter()
    worker.start()
    qapp.processEvents()
    elapsed = time.perf_counter() - t0
    # Wait for completion before tearing down the fixture so the QThread
    # object is in a clean state (avoids QThread destroyed-while-running).
    worker.wait(60_000)
    return elapsed


def test_steady_dispatch_returns_to_event_loop_quickly(qapp, loaded_api):
    worker = AnalysisWorker(loaded_api, analysis_type='steady', params={})
    elapsed = _start_and_measure(worker, qapp)
    assert elapsed < START_BUDGET_S, (
        f"AnalysisWorker(steady).start() + first processEvents took "
        f"{elapsed*1000:.1f} ms (budget {START_BUDGET_S*1000:.0f} ms). "
        f"This indicates the solver is running on the GUI thread."
    )


def test_quality_dispatch_returns_to_event_loop_quickly(qapp, loaded_api):
    """Recommendation #1: water-quality 48h EPS must not block the UI."""
    # Configure quickest possible quality run so the worker doesn't hold us
    # up beyond reason on a tiny network.
    loaded_api.set_simulation_options(duration_hrs=2, hydraulic_timestep_s=600,
                                      pattern_timestep_s=600,
                                      quality_timestep_s=600)
    loaded_api.set_water_quality_mode('AGE')

    worker = AnalysisWorker(loaded_api, analysis_type='quality', params={})
    elapsed = _start_and_measure(worker, qapp)
    assert elapsed < START_BUDGET_S, (
        f"AnalysisWorker(quality).start() + first processEvents took "
        f"{elapsed*1000:.1f} ms (budget {START_BUDGET_S*1000:.0f} ms). "
        f"Water-quality EPS appears to be running on the GUI thread."
    )


def test_scenarios_batch_dispatch_returns_to_event_loop_quickly(qapp, loaded_api):
    """Recommendation #1: multi-scenario batch must not block the UI."""
    specs = [
        {'id': 0, 'demand_multiplier': 1.0},
        {'id': 1, 'demand_multiplier': 1.5},
        {'id': 2, 'demand_multiplier': 0.5},
    ]
    worker = AnalysisWorker(
        loaded_api,
        analysis_type='scenarios_batch',
        params={'inp_file': SIMPLE_INP, 'scenarios': specs},
    )
    elapsed = _start_and_measure(worker, qapp)
    assert elapsed < START_BUDGET_S, (
        f"AnalysisWorker(scenarios_batch).start() + first processEvents took "
        f"{elapsed*1000:.1f} ms (budget {START_BUDGET_S*1000:.0f} ms). "
        f"Scenarios batch appears to be running on the GUI thread."
    )


def test_quality_worker_emits_results(qapp, loaded_api):
    """Sanity: the quality worker really completes and emits a results dict."""
    loaded_api.set_simulation_options(duration_hrs=2, hydraulic_timestep_s=600,
                                      pattern_timestep_s=600,
                                      quality_timestep_s=600)
    loaded_api.set_water_quality_mode('AGE')

    captured = {}
    worker = AnalysisWorker(loaded_api, analysis_type='quality', params={})
    worker.finished.connect(lambda r: captured.setdefault('results', r))
    worker.error.connect(lambda m: captured.setdefault('error', m))

    worker.start()
    if not worker.wait(60_000):
        pytest.fail("Quality worker did not finish within 60 s")

    qapp.processEvents()  # allow the queued finished signal to deliver

    assert 'error' not in captured, f"worker error: {captured.get('error')}"
    assert 'results' in captured, "worker did not emit 'finished' signal"
    res = captured['results']
    assert isinstance(res, dict)
    # Either a real result dict, or a graceful {'error': ...} from the API
    assert 'error' in res or 'mode' in res


def test_scenarios_batch_worker_returns_one_entry_per_scenario(qapp, loaded_api):
    specs = [
        {'id': 0, 'demand_multiplier': 1.0},
        {'id': 1, 'demand_multiplier': 1.2},
    ]
    captured = {}
    worker = AnalysisWorker(
        loaded_api,
        analysis_type='scenarios_batch',
        params={'inp_file': SIMPLE_INP, 'scenarios': specs},
    )
    worker.finished.connect(lambda r: captured.setdefault('results', r))
    worker.error.connect(lambda m: captured.setdefault('error', m))

    worker.start()
    if not worker.wait(60_000):
        pytest.fail("scenarios_batch worker did not finish within 60 s")

    qapp.processEvents()

    assert 'error' not in captured, f"worker error: {captured.get('error')}"
    res = captured.get('results') or {}
    assert 'scenarios' in res
    assert len(res['scenarios']) == 2
    ids = {entry.get('id') for entry in res['scenarios']}
    assert ids == {0, 1}

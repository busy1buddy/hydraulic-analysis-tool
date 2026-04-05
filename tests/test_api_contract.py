"""
API Contract Tests (P4)
========================
Every public method on HydraulicAPI must:
  - Have a docstring
  - Handle wn=None gracefully (return error dict or raise clear exception)
  - Return a dict (or structured value) — never None silently

Auto-discovered to catch drift as new methods are added.
"""

import inspect
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI

# Methods that legitimately take no arguments but don't need a network, or
# return a non-dict container (list, str, number).
_METHODS_RETURNING_LIST = {
    'prioritize_rehabilitation',  # returns list
    'get_node_list',
    'get_link_list',
}

# Methods that don't need a loaded network (pure helpers / class utilities)
_NETWORK_FREE = {
    'joukowsky',              # pure calc
    'get_compliance_thresholds',
    'set_compliance_thresholds',
    'get_pipe_conditions',    # returns dict (possibly empty)
    'knowledge_base',          # static KB query
    'search_knowledge_base',
    'create_network',
    'load_network',
    'load_network_from_path',
    'portfolio_analysis',      # takes paths list
    'climate_demand_projection',  # still errors correctly, tested via public
    # Getters that return structured values without needing wn loaded:
    'get_pattern_library',     # static library of patterns
    'get_pressure_zones',      # current zone registry (may be empty)
    'get_steady_results',      # returns results or None (stored state)
    'get_transient_model',     # returns model or None (stored state)
    'list_networks',           # returns list of .inp files in models/
}

# Getters whose "no state" response is None rather than error dict.
# Document them here — contract explicitly allows None for stored-state getters.
_STATE_GETTERS = {
    'get_steady_results', 'get_transient_model',
}

# Methods that require specific arguments beyond what we can auto-supply
_SKIP_AUTO_CALL = {
    'create_network', 'load_network', 'load_network_from_path',
    'import_from_excel', 'import_pipe_conditions_csv',
    'generate_field_template', 'write_inp',
    'assign_pressure_zone', 'compare_networks', 'detailed_comparison',
    'scenario_difference', 'portfolio_analysis',
    'add_junction', 'update_junction', 'remove_junction',
    'add_pipe', 'update_pipe', 'remove_pipe',
    'remove_node', 'remove_link', 'get_node', 'get_link',
    'set_pipe_condition', 'get_pattern', 'export_results_csv',
    'generate_scada_trace',
}


def _public_methods():
    """Yield (name, method) for every public callable on HydraulicAPI."""
    for name in dir(HydraulicAPI):
        if name.startswith('_'):
            continue
        attr = getattr(HydraulicAPI, name)
        if callable(attr) and not isinstance(attr, type):
            yield name, attr


def test_all_public_methods_have_docstrings():
    """Every public method on HydraulicAPI must be documented."""
    undocumented = []
    for name, method in _public_methods():
        if not inspect.getdoc(method):
            undocumented.append(name)
    assert not undocumented, (
        f'{len(undocumented)} public methods lack docstrings: {undocumented}')


def test_methods_return_dict_on_no_network():
    """Calling an analysis method with no network loaded must return
    an error dict (not None, not raise AttributeError)."""
    api = HydraulicAPI()  # fresh instance, wn is None

    failed = []
    for name, _ in _public_methods():
        if name in _NETWORK_FREE or name in _SKIP_AUTO_CALL:
            continue
        method = getattr(api, name)
        sig = inspect.signature(method)
        # Only try methods with no required args
        required_params = [
            p for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind not in (inspect.Parameter.VAR_POSITIONAL,
                                inspect.Parameter.VAR_KEYWORD)
        ]
        if required_params:
            continue

        try:
            result = method()
        except Exception as e:
            failed.append(f'{name}: raised {type(e).__name__}: {e}')
            continue

        if result is None:
            failed.append(f'{name}: returned None')
            continue
        if name in _METHODS_RETURNING_LIST:
            if not isinstance(result, (list, tuple, dict)):
                failed.append(
                    f'{name}: returned {type(result).__name__}')
            continue
        if not isinstance(result, dict):
            failed.append(
                f'{name}: returned {type(result).__name__}, expected dict')
            continue
        # With no network, expect an 'error' key
        if 'error' not in result:
            failed.append(
                f'{name}: returned dict without "error" key: '
                f'{list(result.keys())[:5]}')

    assert not failed, (
        'API contract violations (no-network behaviour):\n  ' +
        '\n  '.join(failed))


def test_public_method_count_stable():
    """Regression guard: public method count should only grow.
    If it shrinks unexpectedly, a public method was accidentally removed."""
    n_methods = sum(1 for _ in _public_methods())
    # Baseline captured at v2.3.0 (97 methods after mixin split)
    # Increases are fine. Sudden decreases indicate accidental removal.
    assert n_methods >= 90, (
        f'Public method count dropped to {n_methods} — was 90+ at v2.3.0. '
        f'Did something get accidentally removed?')

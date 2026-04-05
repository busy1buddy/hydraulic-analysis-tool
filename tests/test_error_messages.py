"""
Error Message Consistency Tests (Q1)
=====================================
Every error message returned by the API must include 'Fix:' guidance
so that users know what action to take. This test enforces that contract.
"""

import inspect
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI

# Methods that need specific positional args — skip auto-discovery for these
# (they're exercised by other tests).
_SKIP = {
    'create_network', 'load_network', 'load_network_from_path',
    'import_from_excel', 'import_pipe_conditions_csv',
    'generate_field_template', 'write_inp',
    'assign_pressure_zone', 'compare_networks', 'detailed_comparison',
    'scenario_difference', 'portfolio_analysis',
    'add_junction', 'update_junction', 'remove_junction',
    'add_pipe', 'update_pipe', 'remove_pipe',
    'remove_node', 'remove_link', 'get_node', 'get_link',
    'set_pipe_condition', 'get_pattern', 'export_results_csv',
    'generate_scada_trace', 'joukowsky', 'set_compliance_thresholds',
}


def test_no_network_errors_include_fix():
    """Every analysis method called with no network must return
    an error that includes 'Fix:' actionable guidance."""
    api = HydraulicAPI()
    violations = []

    for name in dir(HydraulicAPI):
        if name.startswith('_') or name in _SKIP:
            continue
        attr = getattr(HydraulicAPI, name)
        if not callable(attr):
            continue
        method = getattr(api, name)
        sig = inspect.signature(method)
        required = [
            p for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind not in (inspect.Parameter.VAR_POSITIONAL,
                                inspect.Parameter.VAR_KEYWORD)
        ]
        if required:
            continue

        try:
            result = method()
        except Exception:
            continue
        if not isinstance(result, dict):
            continue
        if 'error' not in result:
            continue

        msg = str(result['error'])
        if 'Fix:' not in msg:
            violations.append(f'{name}: "{msg}"')

    assert not violations, (
        f'{len(violations)} error messages lack "Fix:" guidance:\n  ' +
        '\n  '.join(violations))


def test_error_message_format_examples():
    """Spot-check specific methods return properly formatted errors."""
    api = HydraulicAPI()

    for method_name in ('run_steady_state', 'run_water_quality',
                        'slurry_design_report', 'network_health_summary',
                        'operations_dashboard'):
        result = getattr(api, method_name)()
        assert 'error' in result, f'{method_name}: no error returned'
        assert 'Fix:' in result['error'], (
            f'{method_name}: error "{result["error"]}" missing Fix:')

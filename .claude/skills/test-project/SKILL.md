---
name: Test Project
description: Use when the user asks to run tests, check quality, validate the project, or verify that things work correctly. Runs pytest test suite and performs health checks.
---

# Testing the EPANET Toolkit

## Running Tests

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_api_core.py -v

# Run with coverage report
pytest tests/ --cov=epanet_api --cov-report=term-missing

# Run only correctness tests
pytest tests/test_api_core.py tests/test_api_steady.py tests/test_api_transient.py tests/test_compliance.py -v

# Run only usability/integration tests
pytest tests/test_usability.py tests/test_server.py -v
```

## Quick Health Checks

```bash
# Verify packages
python -c "import wntr; import tsnet; import epyt; print('All packages OK')"

# Verify API
python -c "
from epanet_api import HydraulicAPI
api = HydraulicAPI()
s = api.load_network('australian_network.inp')
assert s['junctions'] == 7
r = api.run_steady_state(save_plot=False)
assert 'pressures' in r
print('API self-test PASSED')
"

# Verify server starts
python -c "from server import app; print('Server imports OK')"
```

## Test Structure
- `tests/conftest.py` - Shared fixtures (isolated API instances, pre-loaded networks)
- `tests/test_api_core.py` - Core API methods (load, create, list, joukowsky, export)
- `tests/test_api_steady.py` - Steady-state analysis results validation
- `tests/test_api_transient.py` - Transient analysis results validation
- `tests/test_server.py` - REST endpoint integration tests
- `tests/test_compliance.py` - WSAA Australian standards compliance logic
- `tests/test_usability.py` - End-to-end workflow tests

## If Tests Fail
1. Read the failure output carefully - it shows expected vs actual values
2. Check if model files exist in `models/` directory
3. Check for Windows encoding issues (UTF-8 wrapper needed)
4. For transient test failures, check TSNet version compatibility with WNTR

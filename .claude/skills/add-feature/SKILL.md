---
name: Add Feature
description: Use when adding new analysis types, capabilities, or features to the EPANET toolkit. Defines the three-layer pattern for consistent feature development.
---

# Adding Features to the EPANET Toolkit

Every new feature follows a **three-layer pattern**:

## Layer 1: API Method (epanet_api.py)

Add a new method to the `HydraulicAPI` class:

```python
def run_new_analysis(self, param1, param2, save_plot=True):
    """Description of what this analysis does."""
    if self.wn is None:
        return {'error': 'No network loaded'}

    # Run analysis logic using self.wn (WNTR network model)
    # ...

    results = {
        'key_metric': value,
        'compliance': [],  # List of {'type': 'OK'/'WARNING'/'CRITICAL', 'message': '...'}
    }

    if save_plot:
        results['plot'] = self._plot_new_analysis()

    return results
```

**Rules:**
- Always check `self.wn is None` at the start
- Return a dict with results and a `compliance` list
- Handle numpy types in results (safe_json handles this in the server layer)
- Use `self.output_dir` for saving plots and exports
- Use `self.model_dir` for saving/loading .inp files
- Add compliance checks using `self.DEFAULTS` thresholds

## Layer 2: REST Endpoint (server.py)

```python
# Add Pydantic request model if POST
class NewAnalysisRequest(BaseModel):
    inp_file: str = "network.inp"
    param1: float = 1.0

# Add endpoint
@app.post("/api/new-analysis")  # or @app.get for simple queries
async def run_new_analysis(req: NewAnalysisRequest):
    try:
        api_instance = HydraulicAPI(WORK_DIR)
        api_instance.load_network(req.inp_file)
        result = api_instance.run_new_analysis(req.param1)
        return safe_json(result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
```

**Rules:**
- Create a fresh `HydraulicAPI(WORK_DIR)` per request (thread safety)
- Always wrap with `safe_json()` for numpy type serialization
- Catch exceptions and return 400 with detail message

## Layer 3: UI Page (app/pages/ for NiceGUI, or dashboard.html for legacy)

For NiceGUI:
```python
# app/pages/new_analysis.py
from nicegui import ui
from epanet_api import HydraulicAPI

def create_page(api: HydraulicAPI):
    # Input controls
    # Run button with callback
    # Results display (charts, compliance, metrics)
```

## Testing

Add tests in `tests/test_new_feature.py`:
- Test the API method returns expected structure
- Test with known network and verify values
- Test error cases (no network loaded, invalid params)
- Test the endpoint via TestClient

## Checklist
- [ ] API method in epanet_api.py with docstring
- [ ] Endpoint in server.py with Pydantic model
- [ ] UI page or section
- [ ] Tests in tests/
- [ ] Update docs/USER_GUIDE.md

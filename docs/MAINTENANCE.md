# Maintenance Guide

How to maintain, update, troubleshoot, and extend the EPANET Hydraulic Analysis Toolkit.

---

## 1. Routine Maintenance

### Updating Python Packages

Check for updates periodically:
```bash
pip list --outdated | grep -i -E "wntr|epyt|tsnet|fastapi|uvicorn"
```

Update specific packages:
```bash
pip install --upgrade wntr epyt tsnet
```

Update all project dependencies:
```bash
pip install --upgrade -r requirements.txt
```

**Important version notes:**
- **WNTR** updates may change API signatures. Check the [WNTR changelog](https://github.com/USEPA/WNTR/releases) before upgrading.
- **TSNet** is research-grade software with infrequent updates. Test thoroughly after any upgrade.
- **EPyT** tracks the EPANET C library version. Updates may add new EPANET features.

### Cleaning Output Files

Generated plots and JSON accumulate in `output/`. Clean periodically:
```bash
# Remove all output files
rm output/*.png output/*.json

# Or keep recent files only (Linux/Mac)
find output/ -mtime +30 -delete
```

### Cleaning EPANET Temp Files

EPANET creates temporary `.bin`, `.rpt` files during simulation. These are cleaned automatically but may persist if a simulation crashes:
```bash
rm -f models/*.bin models/*.rpt
```

---

## 2. Troubleshooting

### Common Issues

#### "UnicodeEncodeError: 'charmap' codec can't encode"
**Cause:** Windows default encoding (cp1252) can't handle Unicode characters.
**Fix:** All scripts include `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')`. If you create new scripts, add this at the top before any print statements.

#### "ENSyntaxError: syntax error at line X"
**Cause:** The .inp file contains a section WNTR doesn't recognize.
**Fix:** Remove unsupported sections. Known unsupported sections include `[ROUGHNESS]`. Stick to standard EPANET sections listed in the User Guide.

#### "AttributeError: 'Pipe' object has no attribute 'initial_head'"
**Cause:** TSNet's `MOCSimulator` was called without running `Initializer` first.
**Fix:** Always call `tsnet.simulation.Initializer(tm, 0, engine='DD')` before `tsnet.simulation.MOCSimulator(tm)`. The `epanet_api.py` handles this automatically.

#### "'V1' not found" or similar valve errors
**Cause:** The selected .inp file doesn't contain the specified valve element.
**Fix:** Ensure the network file has a `[VALVES]` section with the valve ID. For transient analysis, use `transient_network.inp` which has valve V1.

#### Dashboard shows "Disconnected"
**Cause:** The FastAPI server isn't running.
**Fix:** Start it with `python server.py`. Verify it's running: `curl http://localhost:8765/api/networks`

#### Transient analysis gives "Initial condition discrepancy"
**Cause:** TSNet's EPANET initialization produces slightly different results at valve nodes. This is a known TSNet issue with TCV valves.
**Impact:** Minor - the transient simulation still runs correctly. Results are valid for engineering assessment.

### Verifying the Installation

Run the built-in verification:
```bash
python -c "
import wntr; print(f'WNTR {wntr.__version__}')
import tsnet; print('TSNet OK')
import epyt; print('EPyT OK')
import fastapi; print(f'FastAPI {fastapi.__version__}')
print('All packages verified.')
"
```

Run the API self-test:
```bash
python -c "
from epanet_api import HydraulicAPI
api = HydraulicAPI()
s = api.load_network('australian_network.inp')
assert s['junctions'] == 7, 'Network load failed'
r = api.run_steady_state(save_plot=False)
assert 'pressures' in r, 'Steady-state failed'
print('Self-test PASSED')
"
```

---

## 3. Extending the Toolkit

### Adding a New Analysis Type

1. Add the method to `epanet_api.py` in the `HydraulicAPI` class
2. Add a corresponding endpoint in `server.py`
3. Add a UI section in `dashboard.html`

Example - adding a water quality analysis:
```python
# In epanet_api.py
def run_water_quality(self, source_node, quality_type='age'):
    """Run water quality simulation."""
    self.wn.options.quality.parameter = quality_type
    # ... configure and run
```

### Adding a New Network Model

1. Create the `.inp` file (manually or via `api.create_network()`)
2. Save to `models/` directory
3. It appears automatically in the dashboard dropdown

### Adding New Compliance Standards

Edit the `DEFAULTS` dict in `epanet_api.py`:
```python
DEFAULTS = {
    'min_pressure_m': 20,       # Change for different standards
    'max_pressure_m': 50,
    'max_velocity_ms': 2.0,
    'pipe_rating_kPa': 3500,    # Change for different pipe class
    ...
}
```

### Supporting Other Pipe Materials

Update wave speeds in the Joukowsky calculator and transient defaults:
```python
WAVE_SPEEDS = {
    'ductile_iron': 1000,
    'steel': 1100,
    'pvc': 400,
    'pe_hdpe': 300,
    'concrete': 1200,
}
```

---

## 4. Architecture Reference

### Data Flow

```
User / Claude Code
       |
       v
  epanet_api.py (HydraulicAPI)
       |
  +----+----+----+
  |    |         |
WNTR  EPyT    TSNet
  |              |
EPANET        MOC Solver
(C lib)     (Python/NumPy)
  |              |
  v              v
.inp files   Transient
(models/)    time-series
  |              |
  +------+-------+
         |
    JSON results
    PNG plots
   (output/)
```

### Dashboard Architecture

```
Browser (dashboard.html + Plotly.js)
       |
       | HTTP/JSON
       v
  FastAPI (server.py, port 8765)
       |
       v
  HydraulicAPI (epanet_api.py)
       |
       v
  WNTR / TSNet solvers
```

### Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `epanet_api.py` | ~530 | Core API - all analysis logic |
| `server.py` | ~160 | FastAPI server wrapping the API |
| `dashboard.html` | ~650 | Single-page web dashboard |
| `run_hydraulic_analysis.py` | ~270 | Standalone steady-state script |
| `run_transient_analysis.py` | ~425 | Standalone transient script |

---

## 5. Known Limitations

| Limitation | Detail | Workaround |
|-----------|--------|------------|
| TSNet accuracy | Research-grade, not commercially validated | Cross-check critical results with Bentley HAMMER or Hytran |
| No pump transients | TSNet pump shutdown not implemented in this toolkit | Add pump_closure() calls manually via TSNet API |
| Single-period patterns | Dashboard creates 24-element patterns only | Edit .inp files directly for multi-day patterns |
| No water quality | Quality simulation not exposed in dashboard | Use WNTR directly: `wn.options.quality.parameter = 'age'` |
| No fire flow analysis | Not automated | Manually set fire flow demands and re-run |
| Wave speed uniform | Same speed set for all pipes | Edit per-pipe wave speeds via TSNet API |

---

## 6. Useful References

- [WNTR Documentation](https://usepa.github.io/WNTR/)
- [WNTR GitHub](https://github.com/USEPA/WNTR)
- [EPyT Documentation](https://epanet-python-toolkit-epyt.readthedocs.io/)
- [TSNet Documentation](https://tsnet.readthedocs.io/)
- [EPANET User Manual](https://www.epa.gov/water-research/epanet)
- [WSAA Design Standards](https://www.wsaa.asn.au/)
- [AS/NZS 2566 - Buried Flexible Pipelines](https://www.standards.org.au/)

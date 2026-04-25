# PyQt6 UI Conventions — Reference

Extended rules for `desktop/` code. Loaded into context when `pyqt-architect` skill activates.

## Dialog Skeleton

Every new QDialog should follow this structure:

```python
"""
Short Dialog Title — One-line purpose.
================================================
What this dialog does in 2-3 sentences. Cite the WSAA / AS-NZS reference
if it implements a compliance check.
"""

import logging

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QDoubleSpinBox,
    QDialogButtonBox, QMessageBox,
)
from PyQt6.QtCore import Qt


class MyAnalysisDialog(QDialog):
    """Brief description of what the dialog returns."""

    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api  # HydraulicAPI — never wntr/tsnet directly

        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            self.reject()
            return

        self.setWindowTitle("My Analysis")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.flow_spin = QDoubleSpinBox()
        self.flow_spin.setRange(0.0, 1000.0)
        self.flow_spin.setValue(25.0)
        self.flow_spin.setDecimals(1)
        self.flow_spin.setSuffix(" LPS")  # always include unit
        form.addRow("Required flow:", self.flow_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
```

## Threading — AnalysisWorker

For anything that can take more than ~50 ms (any solver call), use `desktop/analysis_worker.py:AnalysisWorker`:

```python
from desktop.analysis_worker import AnalysisWorker

self._worker = AnalysisWorker(self.api, analysis_type='steady', params={})
self._worker.progress.connect(self.progress_bar.setValue)
self._worker.finished.connect(self._on_done)
self._worker.error.connect(self._on_error)
self._worker.start()
```

If you need a new `analysis_type`, extend `AnalysisWorker.run()` rather than writing a parallel QThread.

## Unit Suffixes (always required)

| Field type | QDoubleSpinBox suffix |
|---|---|
| Pressure | `" m"` |
| Pressure (PN) | `" kPa"` |
| Velocity | `" m/s"` |
| Flow | `" LPS"` |
| Diameter | `" mm"` |
| Length | `" m"` |
| Stress | `" MPa"` |
| Wave speed | `" m/s"` |
| Time | `" h"` or `" s"` or `" min"` |
| Roughness | none — show as `"C=140"` label |

## Decimal Precision

```python
spin.setDecimals(1)   # pressure
spin.setDecimals(2)   # velocity, safety factors
spin.setDecimals(0)   # diameter (integer mm)
```

In display labels (QLabel), use f-strings:

```python
self.pressure_label.setText(f"{p_m:.1f} m")
self.velocity_label.setText(f"{v_ms:.2f} m/s")
self.diameter_label.setText(f"{int(round(d_m * 1000))} mm")  # WNTR stores in m
```

## State Guards

Every menu slot that touches the network must guard:

```python
def _on_my_action(self):
    if self.api.wn is None:
        QMessageBox.warning(self, "No Network",
            "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
        return
    # ... rest of the slot
```

## Compliance Colours

Use `desktop/colourmap_widget.py` constants:

- Green = PASS / within WSAA limits
- Amber = WARNING / approaching limit
- Red = CRITICAL / exceeds limit
- Grey = NO DATA

Never use red-only or red-vs-green — accessibility. Pair every colour with text.

## Crash Dialog

For unhandled exceptions (last resort), `main_app.py` already wires `sys.excepthook` to `desktop/crash_dialog.py:CrashDialog`. New dialogs should still wrap their own `try/except` and surface a `QMessageBox.critical` rather than letting CrashDialog be the front-line response.

## Forbidden in `desktop/`

```python
# layer-purity violations:
import wntr                                  # use api method
import tsnet                                 # use api method
from epanet_api.slurry_solver import ...     # use api.compute_slurry_headloss()
from epanet_api.pipe_stress import ...       # use api.compute_pipe_stress()

# direct mutation violations:
api.wn.options.time.duration = ...           # use api.set_simulation_options(...)
api.wn.options.quality.parameter = ...       # use api.set_water_quality_mode(...)
api.wn.add_pipe(...)                         # use api.add_pipe(...)
```

## Allowed in `desktop/`

```python
from epanet_api import HydraulicAPI         # the only API import you need
api.wn.junction_name_list                    # read-only WNTR access OK
api.wn.get_link(name)                        # read-only WNTR access OK
api.wn.options.quality.parameter             # read OK; mutation NOT OK
```

## Signal/Slot Naming

- Slots: `_on_<action>` (e.g. `_on_run_steady`, `_on_open_file`)
- Worker signals: `progress` (int 0-100), `finished` (dict), `error` (str)
- Internal helpers: `_<verb>_<thing>` (e.g. `_populate_explorer`, `_update_status_bar`)

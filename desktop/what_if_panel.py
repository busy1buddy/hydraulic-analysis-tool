"""
What-If Sensitivity Panel (I4)
================================
Live sliders for demand, roughness, and source pressure. Each change
triggers a re-analysis and emits the result so the canvas and results
view can refresh.
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton,
    QGroupBox, QFormLayout, QSizePolicy,
)


class WhatIfPanel(QWidget):
    """Dockable What-If panel for live sensitivity sliders."""

    # Emitted after a re-analysis completes with the new results dict.
    analysis_updated = pyqtSignal(dict)

    # Emitted on any error during re-analysis.
    analysis_failed = pyqtSignal(str)

    def __init__(self, api=None, parent=None):
        super().__init__(parent)
        self.api = api
        self._original_demands = None
        self._original_roughness = None
        self._original_source_heads = None

        # Debounce re-analysis so sliders feel responsive
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(150)
        self._debounce.timeout.connect(self._run_analysis)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        box = QGroupBox("What If...")
        form = QFormLayout(box)

        # Demand multiplier: 50%..200% (slider 50..200)
        self.demand_slider, self.demand_label = self._make_slider(
            50, 200, 100, fmt='{:d}%')
        self.demand_slider.setToolTip(
            "Scale all junction demands by this multiplier.\n"
            "50% = off-peak, 100% = design, 200% = peak demand stress test.")
        form.addRow("Demand:", self._combine(self.demand_slider,
                                              self.demand_label))

        # Roughness multiplier: 50%..150% (slider 50..150)
        self.rough_slider, self.rough_label = self._make_slider(
            50, 150, 100, fmt='{:d}%')
        self.rough_slider.setToolTip(
            "Scale all pipe Hazen-Williams C-factors by this multiplier.\n"
            "50% = heavily tuberculated old pipe, 100% = design, "
            "150% = new smooth pipe.")
        form.addRow("Roughness:", self._combine(self.rough_slider,
                                                 self.rough_label))

        # Source pressure: -20..+20 m
        self.source_slider, self.source_label = self._make_slider(
            -20, 20, 0, fmt='{:+d} m')
        self.source_slider.setToolTip(
            "Add/subtract this head from every reservoir.\n"
            "Simulates reservoir drawdown (-) or pump boost (+).")
        form.addRow("Source head:", self._combine(self.source_slider,
                                                   self.source_label))

        layout.addWidget(box)

        btn_row = QHBoxLayout()
        self.reset_btn = QPushButton("Reset to baseline")
        self.reset_btn.setToolTip("Return all sliders to 100% / 0 m.")
        self.reset_btn.clicked.connect(self._on_reset)
        btn_row.addWidget(self.reset_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status_label = QLabel("(adjust a slider to run analysis)")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch()

        # Wire slider changes
        self.demand_slider.valueChanged.connect(self._on_any_change)
        self.rough_slider.valueChanged.connect(self._on_any_change)
        self.source_slider.valueChanged.connect(self._on_any_change)

    def _make_slider(self, low, high, initial, fmt='{}'):
        sld = QSlider(Qt.Orientation.Horizontal)
        sld.setRange(low, high)
        sld.setValue(initial)
        sld.setTickPosition(QSlider.TickPosition.TicksBelow)
        sld.setTickInterval(max(1, (high - low) // 10))
        sld.setMinimumWidth(150)
        lbl = QLabel(fmt.format(initial))
        lbl.setMinimumWidth(44)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        sld._fmt = fmt
        sld._label = lbl
        sld.valueChanged.connect(lambda v, s=sld: s._label.setText(s._fmt.format(v)))
        return sld, lbl

    def _combine(self, slider, label):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(slider)
        h.addWidget(label)
        return w

    # -------- Public --------
    def set_api(self, api):
        self.api = api
        self._capture_baseline()
        self._on_reset()

    def _capture_baseline(self):
        """Snapshot current demands/roughness/source heads."""
        if self.api is None or self.api.wn is None:
            return
        wn = self.api.wn
        self._original_demands = {}
        for jid in wn.junction_name_list:
            try:
                d = wn.get_node(jid).demand_timeseries_list[0].base_value
                self._original_demands[jid] = d
            except Exception:
                continue
        self._original_roughness = {
            pid: wn.get_link(pid).roughness for pid in wn.pipe_name_list
        }
        self._original_source_heads = {}
        for rid in wn.reservoir_name_list:
            try:
                self._original_source_heads[rid] = \
                    wn.get_node(rid).base_head
            except Exception:
                continue

    def _on_reset(self):
        self.demand_slider.setValue(100)
        self.rough_slider.setValue(100)
        self.source_slider.setValue(0)

    def restore_baseline(self):
        """Write the originally-captured demands/roughness/source heads
        back to the network model. Call this before the panel is destroyed
        so any consumer of `api.wn` sees the original model state."""
        if self.api is None or self.api.wn is None:
            return
        wn = self.api.wn
        if self._original_demands:
            for jid, base in self._original_demands.items():
                try:
                    wn.get_node(jid).demand_timeseries_list[0].base_value = base
                except Exception:
                    pass
        if self._original_roughness:
            for pid, base_c in self._original_roughness.items():
                try:
                    wn.get_link(pid).roughness = base_c
                except Exception:
                    pass
        if self._original_source_heads:
            for rid, base_h in self._original_source_heads.items():
                try:
                    wn.get_node(rid).base_head = base_h
                except Exception:
                    pass

    def closeEvent(self, event):
        """Restore baseline state when the panel is closed so the
        underlying network model is not left in a mutated state."""
        self.restore_baseline()
        super().closeEvent(event)

    def _on_any_change(self):
        if self.api is None or self.api.wn is None:
            return
        if self._original_demands is None:
            self._capture_baseline()
        self._debounce.start()

    # -------- Analysis --------
    def _run_analysis(self):
        if self.api is None or self.api.wn is None:
            return
        wn = self.api.wn
        dm = self.demand_slider.value() / 100.0
        rm = self.rough_slider.value() / 100.0
        sh = self.source_slider.value()

        # Apply multipliers
        for jid, base in self._original_demands.items():
            try:
                wn.get_node(jid).demand_timeseries_list[0].base_value = \
                    base * dm
            except Exception:
                pass
        for pid, base_c in self._original_roughness.items():
            try:
                wn.get_link(pid).roughness = base_c * rm
            except Exception:
                pass
        for rid, base_h in self._original_source_heads.items():
            try:
                wn.get_node(rid).base_head = base_h + sh
            except Exception:
                pass

        try:
            results = self.api.run_steady_state(save_plot=False)
        except Exception as e:
            self.status_label.setText(f"Analysis failed: {e}")
            self.analysis_failed.emit(str(e))
            return

        if 'error' in results:
            self.status_label.setText(results['error'])
            self.analysis_failed.emit(results['error'])
            return

        # Summarise pressures/velocities for status label
        p_vals = [p.get('avg_m', 0)
                  for p in results.get('pressures', {}).values()]
        v_vals = [f.get('max_velocity_ms', 0)
                  for f in results.get('flows', {}).values()]
        p_min = min(p_vals) if p_vals else 0
        v_max = max(v_vals) if v_vals else 0
        self.status_label.setText(
            f"Updated: min pressure {p_min:.1f} m, max velocity "
            f"{v_max:.2f} m/s ({self.demand_slider.value()}% demand, "
            f"{self.rough_slider.value()}% C, {sh:+d} m source)")
        self.analysis_updated.emit(results)

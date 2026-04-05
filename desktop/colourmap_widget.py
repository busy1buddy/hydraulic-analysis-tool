"""
ColourMap Widget — FEA-style continuous colour scale for hydraulic variables
=============================================================================
Provides ColourMapWidget (dropdown, min/max, log scale) and ColourBar
(vertical gradient strip with tick labels).

Matplotlib colourmap lookups are used for perceptually-uniform mapping.
"""

import numpy as np
import matplotlib.cm as mpl_cm
import matplotlib.colors as mpl_colors

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QDoubleSpinBox, QCheckBox, QPushButton, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont, QColor, QPainter, QLinearGradient, QPen


# Supported colourmap names (matplotlib identifiers)
COLOURMAPS = ["viridis", "plasma", "RdYlGn", "RdBu", "jet"]
COLOURMAP_LABELS = ["Viridis", "Plasma", "RdYlGn", "RdBu", "Jet"]


class ColourMapWidget(QWidget):
    """
    Controls for the continuous colour mapping applied to result overlays.

    Signals
    -------
    colour_map_changed : emitted whenever any setting changes
    """

    colour_map_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vmin = 0.0
        self._vmax = 100.0
        self._data_vmin = 0.0
        self._data_vmax = 100.0
        self._unit = ""
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        font = QFont("Consolas", 9)

        # Colourmap selector
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Map:"))
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(COLOURMAP_LABELS)
        self.cmap_combo.setFont(font)
        self.cmap_combo.currentIndexChanged.connect(self._emit_changed)
        self.cmap_combo.setToolTip(
            "Colour map palette for results overlay.\n"
            "Viridis is colour-blind friendly and print-safe.")
        row1.addWidget(self.cmap_combo)
        layout.addLayout(row1)

        # Min / Max spin boxes
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Min:"))
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(-1e9, 1e9)
        self.min_spin.setDecimals(2)
        self.min_spin.setValue(self._vmin)
        self.min_spin.setFont(font)
        self.min_spin.valueChanged.connect(self._on_spin_changed)
        self.min_spin.setToolTip(
            "Minimum value for colour scale.\n"
            "Values below this map to the lowest colour.")
        row2.addWidget(self.min_spin)

        row2.addWidget(QLabel("Max:"))
        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(-1e9, 1e9)
        self.max_spin.setDecimals(2)
        self.max_spin.setValue(self._vmax)
        self.max_spin.setFont(font)
        self.max_spin.valueChanged.connect(self._on_spin_changed)
        self.max_spin.setToolTip(
            "Maximum value for colour scale.\n"
            "Values above this map to the highest colour.")
        row2.addWidget(self.max_spin)
        layout.addLayout(row2)

        # Log scale + Reset
        row3 = QHBoxLayout()
        self.log_check = QCheckBox("Log scale")
        self.log_check.setFont(font)
        self.log_check.stateChanged.connect(self._emit_changed)
        self.log_check.setToolTip(
            "Use log10 scale for colour mapping.\n"
            "Useful when values span several orders of magnitude.")
        row3.addWidget(self.log_check)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setFont(font)
        self.reset_btn.setFixedWidth(55)
        self.reset_btn.clicked.connect(self._on_reset)
        row3.addWidget(self.reset_btn)
        layout.addLayout(row3)

        # Percentile clip
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Clip:"))
        self.clip_spin = QDoubleSpinBox()
        self.clip_spin.setRange(0, 10)
        self.clip_spin.setDecimals(1)
        self.clip_spin.setValue(0.0)
        self.clip_spin.setSuffix(" %")
        self.clip_spin.setFont(font)
        self.clip_spin.setToolTip(
            "Percentile clip — ignore top/bottom N% of values when\n"
            "setting colour range. Prevents outliers from washing out\n"
            "the colour scale. Set to 0 for no clipping."
        )
        self.clip_spin.valueChanged.connect(self._on_clip_changed)
        row4.addWidget(self.clip_spin)
        row4.addStretch()
        layout.addLayout(row4)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_range(self, vmin: float, vmax: float):
        """Set both the data range and the current display range."""
        self._data_vmin = vmin
        self._data_vmax = vmax
        self._vmin = vmin
        self._vmax = vmax
        # Block signals to avoid double-emit during programmatic update
        self.min_spin.blockSignals(True)
        self.max_spin.blockSignals(True)
        self.min_spin.setValue(vmin)
        self.max_spin.setValue(vmax)
        self.min_spin.blockSignals(False)
        self.max_spin.blockSignals(False)
        self.colour_map_changed.emit()

    def set_unit(self, text: str):
        """Set the unit label text (propagated to ColourBar)."""
        self._unit = text
        self.colour_map_changed.emit()

    def map_value(self, v: float) -> QColor:
        """
        Map a scalar value to a QColor using the selected colourmap.

        Values outside [vmin, vmax] are clamped.
        If log scale is enabled, values are log10-transformed before mapping.
        """
        vmin = self._vmin
        vmax = self._vmax

        if self.log_check.isChecked():
            # Guard against non-positive values when log scale is active
            safe_v = max(v, 1e-12)
            safe_min = max(vmin, 1e-12)
            safe_max = max(vmax, 1e-12)
            if safe_max <= safe_min:
                t = 0.0
            else:
                t = (np.log10(safe_v) - np.log10(safe_min)) / (
                    np.log10(safe_max) - np.log10(safe_min)
                )
        else:
            if vmax == vmin:
                t = 0.0
            else:
                t = (v - vmin) / (vmax - vmin)

        t = float(np.clip(t, 0.0, 1.0))

        cmap_name = COLOURMAPS[self.cmap_combo.currentIndex()]
        # matplotlib >= 3.7 exposes colormaps registry; fall back to get_cmap
        if hasattr(mpl_cm, 'colormaps'):
            cmap = mpl_cm.colormaps[cmap_name]
        else:
            cmap = mpl_cm.get_cmap(cmap_name)  # type: ignore[attr-defined]
        r, g, b, a = cmap(t)
        return QColor(int(r * 255), int(g * 255), int(b * 255), int(a * 255))

    @property
    def vmin(self) -> float:
        return self._vmin

    @property
    def vmax(self) -> float:
        return self._vmax

    @property
    def unit(self) -> str:
        return self._unit

    @property
    def log_scale(self) -> bool:
        return self.log_check.isChecked()

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_spin_changed(self):
        self._vmin = self.min_spin.value()
        self._vmax = self.max_spin.value()
        self.colour_map_changed.emit()

    def _on_reset(self):
        self.clip_spin.setValue(0.0)
        self.set_range(self._data_vmin, self._data_vmax)

    def _on_clip_changed(self, pct):
        """Apply percentile clip to the data range."""
        if not hasattr(self, '_raw_values') or self._raw_values is None:
            return
        if pct <= 0 or len(self._raw_values) < 3:
            self.set_range(self._data_vmin, self._data_vmax)
            return
        clipped_min = float(np.percentile(self._raw_values, pct))
        clipped_max = float(np.percentile(self._raw_values, 100 - pct))
        self.set_range(clipped_min, clipped_max)

    def set_data_values(self, values):
        """
        Store raw data values for percentile clip computation.

        Parameters
        ----------
        values : list or np.ndarray
            All data values currently displayed on the canvas
        """
        self._raw_values = np.array(values) if values else None
        # Update full range
        if self._raw_values is not None and len(self._raw_values) > 0:
            self._data_vmin = float(self._raw_values.min())
            self._data_vmax = float(self._raw_values.max())

    def _emit_changed(self):
        self.colour_map_changed.emit()


# ---------------------------------------------------------------------------


class ColourBar(QWidget):
    """
    Vertical gradient strip with tick labels showing the current colourmap.

    Fixed size: 30 px wide × 200 px tall gradient strip plus text labels.
    Connect to ColourMapWidget.colour_map_changed to auto-refresh.
    """

    # Number of tick labels on the gradient
    N_TICKS = 5

    def __init__(self, colourmap_widget: ColourMapWidget, parent=None):
        super().__init__(parent)
        self._cw = colourmap_widget
        self._cw.colour_map_changed.connect(self.update)

        # Fixed width; height grows with labels
        self.setFixedWidth(90)
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        font = QFont("Consolas", 8)
        painter.setFont(font)
        fm = painter.fontMetrics()

        # Dimensions
        w = self.width()
        top_margin = 18   # space for unit label
        bottom_margin = 4
        bar_width = 20
        label_left = bar_width + 4
        bar_h = self.height() - top_margin - bottom_margin

        # Unit label at top
        painter.setPen(QPen(QColor(180, 180, 200)))
        painter.drawText(0, 0, w, top_margin, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         self._cw.unit)

        # Gradient strip (top = vmax, bottom = vmin — conventional FEA orientation)
        bar_top = top_margin
        n_steps = max(bar_h, 1)
        for i in range(n_steps):
            # i=0 → top of bar → vmax
            t = 1.0 - i / n_steps
            v = self._cw.vmin + t * (self._cw.vmax - self._cw.vmin)
            color = self._cw.map_value(v)
            painter.setPen(QPen(color))
            painter.drawLine(0, bar_top + i, bar_width, bar_top + i)

        # Border around the bar
        painter.setPen(QPen(QColor(80, 80, 100)))
        painter.drawRect(0, bar_top, bar_width, bar_h)

        # Tick labels — evenly spaced, N_TICKS marks
        painter.setPen(QPen(QColor(180, 180, 200)))
        for j in range(self.N_TICKS):
            # j=0 → top (vmax), j=N_TICKS-1 → bottom (vmin)
            frac = j / (self.N_TICKS - 1) if self.N_TICKS > 1 else 0
            v = self._cw.vmax - frac * (self._cw.vmax - self._cw.vmin)
            y_px = bar_top + int(frac * bar_h)
            # Format: for values in typical hydraulic range, avoid
            # scientific notation (e.g. show "100", not "1e+02").
            av = abs(v)
            if av >= 1000 or (0 < av < 0.01):
                label = f"{v:.2g}"
            elif av >= 10:
                label = f"{v:.0f}"
            else:
                label = f"{v:.1f}"
            text_y = max(y_px, bar_top + fm.ascent())
            text_y = min(text_y, bar_top + bar_h)
            painter.drawText(label_left, text_y, label)

        painter.end()

"""
Demand Pattern Editor
======================
Dialog for editing 24-hour demand patterns with preset options,
bar chart preview, and apply-to controls.
"""

import numpy as np
import pyqtgraph as pg

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QPushButton,
    QRadioButton, QButtonGroup, QLabel, QDialogButtonBox,
    QGroupBox, QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


# WSAA WSA 03-2011 typical residential diurnal demand pattern
RESIDENTIAL_PATTERN = [
    0.4, 0.3, 0.3, 0.3, 0.4, 0.6, 1.0, 1.8, 1.6, 1.4, 1.2, 1.0,
    1.0, 0.9, 0.9, 1.0, 1.1, 1.4, 1.8, 1.5, 1.2, 1.0, 0.8, 0.5,
]

COMMERCIAL_PATTERN = [
    0.2, 0.2, 0.2, 0.2, 0.2, 0.3, 0.5, 1.0, 1.5, 1.5, 1.5, 1.5,
    1.3, 1.5, 1.5, 1.5, 1.5, 1.2, 0.8, 0.5, 0.3, 0.2, 0.2, 0.2,
]

INDUSTRIAL_PATTERN = [
    0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 1.0, 1.2, 1.2, 1.2, 1.2, 1.2,
    1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.0, 0.8, 0.8, 0.8, 0.8, 0.8,
]

FLAT_PATTERN = [1.0] * 24

PRESETS = {
    'Residential (WSAA)': RESIDENTIAL_PATTERN,
    'Commercial': COMMERCIAL_PATTERN,
    'Industrial': INDUSTRIAL_PATTERN,
    'Flat (1.0)': FLAT_PATTERN,
}


class PatternEditorDialog(QDialog):
    """Dialog for editing a 24-hour demand multiplier pattern."""

    def __init__(self, api, junction_id=None, parent=None):
        super().__init__(parent)
        self.api = api
        self.junction_id = junction_id
        self.setWindowTitle("Demand Pattern Editor")
        self.setMinimumSize(600, 550)

        layout = QVBoxLayout(self)

        # Presets
        preset_group = QGroupBox("Presets")
        preset_layout = QHBoxLayout()
        for name in PRESETS:
            btn = QPushButton(name)
            btn.setFont(QFont("Consolas", 8))
            btn.clicked.connect(lambda checked, n=name: self._load_preset(n))
            preset_layout.addWidget(btn)
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        # Table
        self.table = QTableWidget(24, 2)
        self.table.setHorizontalHeaderLabels(["Hour", "Multiplier"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setFont(QFont("Consolas", 10))
        self.table.verticalHeader().setVisible(False)
        for h in range(24):
            hour_item = QTableWidgetItem(f"{h:02d}:00")
            hour_item.setFlags(hour_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(h, 0, hour_item)
            self.table.setItem(h, 1, QTableWidgetItem("1.0"))
        self.table.cellChanged.connect(self._on_table_changed)
        layout.addWidget(self.table)

        # Chart preview
        self.chart = pg.PlotWidget()
        self.chart.setBackground('#1e1e2e')
        self.chart.setMaximumHeight(150)
        self.chart.setLabel('bottom', 'Hour')
        self.chart.setLabel('left', 'Multiplier')
        self.bar_item = pg.BarGraphItem(x=list(range(24)), height=[1.0]*24,
                                         width=0.8, brush='#89b4fa')
        self.chart.addItem(self.bar_item)
        layout.addWidget(self.chart)

        # Apply-to radio buttons
        apply_group = QGroupBox("Apply To")
        apply_layout = QHBoxLayout()
        self.apply_this = QRadioButton("This junction only")
        self.apply_all = QRadioButton("All junctions")
        self.apply_this.setChecked(True)
        if junction_id is None:
            self.apply_all.setChecked(True)
            self.apply_this.setEnabled(False)
        apply_layout.addWidget(self.apply_this)
        apply_layout.addWidget(self.apply_all)
        apply_group.setLayout(apply_layout)
        layout.addWidget(apply_group)

        # Sum label
        self.sum_label = QLabel("Sum: 24.0 (day total)")
        self.sum_label.setFont(QFont("Consolas", 9))
        layout.addWidget(self.sum_label)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Load current pattern if exists
        self._load_preset('Residential (WSAA)')

    def _load_preset(self, name):
        pattern = PRESETS.get(name, FLAT_PATTERN)
        self.table.blockSignals(True)
        for h in range(24):
            self.table.setItem(h, 1, QTableWidgetItem(f"{pattern[h]:.1f}"))
        self.table.blockSignals(False)
        self._update_chart()

    def _on_table_changed(self, row, col):
        if col == 1:
            self._update_chart()

    def get_pattern(self):
        """Return the 24-element multiplier list."""
        pattern = []
        for h in range(24):
            try:
                val = float(self.table.item(h, 1).text())
            except (ValueError, AttributeError):
                val = 1.0
            pattern.append(max(0.0, val))
        return pattern

    def _update_chart(self):
        pattern = self.get_pattern()
        self.bar_item.setOpts(height=pattern)
        total = sum(pattern)
        self.sum_label.setText(f"Sum: {total:.1f} (day total)")

    def _on_accept(self):
        """Apply the pattern to the WNTR network model."""
        pattern = self.get_pattern()

        if self.api.wn is None:
            self.accept()
            return

        wn = self.api.wn

        # Create or update the pattern in WNTR
        pat_name = 'diurnal'
        if pat_name in wn.pattern_name_list:
            pat = wn.get_pattern(pat_name)
            pat.multipliers = pattern
        else:
            wn.add_pattern(pat_name, pattern)

        # Apply to junctions
        if self.apply_all.isChecked():
            for jid in wn.junction_name_list:
                junc = wn.get_node(jid)
                if junc.demand_timeseries_list:
                    junc.demand_timeseries_list[0].pattern_name = pat_name
        elif self.junction_id:
            try:
                junc = wn.get_node(self.junction_id)
                if junc.demand_timeseries_list:
                    junc.demand_timeseries_list[0].pattern_name = pat_name
            except Exception:
                pass

        self.accept()

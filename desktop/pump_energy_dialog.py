"""
Pump Energy Analysis Dialog
============================
Displays pump energy consumption and time-of-use tariff cost breakdown.
"""

import logging

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QGroupBox,
    QFormLayout, QDoubleSpinBox,
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


class PumpEnergyDialog(QDialog):
    """Dialog showing pump energy analysis with TOU tariff breakdown."""

    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Pump Energy & Cost Analysis")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Pump Energy Analysis — Time-of-Use Tariff")
        header.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        layout.addWidget(header)

        # Parameters
        param_group = QGroupBox("Operating Parameters")
        param_layout = QFormLayout()
        self.hours_spin = QDoubleSpinBox()
        self.hours_spin.setRange(1, 24)
        self.hours_spin.setValue(18)
        self.hours_spin.setSuffix(" hrs/day")
        param_layout.addRow("Operating hours:", self.hours_spin)
        param_group.setLayout(param_layout)
        layout.addWidget(param_group)

        # Tariff info
        tariff_label = QLabel(
            "Tariff:  Peak $0.35/kWh (7am-9pm weekdays)  |  "
            "Shoulder $0.25/kWh (7am-10pm weekends)  |  "
            "Off-peak $0.15/kWh (other)")
        tariff_label.setFont(QFont("Consolas", 9))
        tariff_label.setWordWrap(True)
        layout.addWidget(tariff_label)

        # Results table
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Pump", "Flow (LPS)", "Head (m)", "Efficiency",
            "Power (kW)", "Annual (kWh)",
            "TOU Cost ($)", "Optimised ($)", "Saving ($)"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setFont(QFont("Consolas", 9))
        for col in range(8):
            self.table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        # Summary label
        self.summary_label = QLabel("")
        self.summary_label.setFont(QFont("Consolas", 10))
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        # Buttons
        btn_layout = QHBoxLayout()
        run_btn = QPushButton("Calculate")
        run_btn.setFont(QFont("Consolas", 10))
        run_btn.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        run_btn.clicked.connect(self._run_analysis)
        btn_layout.addWidget(run_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # Auto-run if results available
        self._run_analysis()

    def _run_analysis(self):
        """Run pump energy TOU analysis and populate table."""
        hours = self.hours_spin.value()
        try:
            result = self.api.pump_energy_tou(
                operating_hours_per_day=hours)
        except (AttributeError, KeyError, ValueError) as e:
            logger.error("Pump energy analysis failed: %s", e)
            self.summary_label.setText(f"Error: {e}")
            return

        if 'error' in result:
            self.summary_label.setText(result['error'])
            return

        pumps = result.get('pumps', [])
        self.table.setRowCount(0)

        for pump in pumps:
            row = self.table.rowCount()
            self.table.insertRow(row)

            if 'error' in pump:
                self.table.setItem(row, 0, QTableWidgetItem(
                    pump.get('pump_id', '--')))
                err_item = QTableWidgetItem(pump['error'])
                err_item.setForeground(QColor(243, 139, 168))
                self.table.setItem(row, 1, err_item)
                continue

            tou = pump.get('tou_breakdown', {})
            items = [
                pump.get('pump_id', '--'),
                f"{pump.get('operating_flow_lps', 0):.1f}",
                f"{pump.get('operating_head_m', 0):.1f}",
                f"{pump.get('efficiency', 0):.1%}",
                f"{pump.get('electrical_power_kw', 0):.1f}",
                f"{pump.get('annual_energy_kwh', 0):,.0f}",
                f"${pump.get('tou_total_aud', 0):,.0f}",
                f"${pump.get('optimised_annual_aud', 0):,.0f}",
                f"${pump.get('optimised_saving_aud', 0):,.0f}",
            ]

            for col, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                # Highlight savings > $1000
                if col == 8:
                    saving = pump.get('optimised_saving_aud', 0)
                    if saving > 1000:
                        item.setForeground(QColor(166, 227, 161))
                # Highlight low efficiency
                if col == 3 and pump.get('efficiency', 1) < 0.60:
                    item.setForeground(QColor(243, 139, 168))
                self.table.setItem(row, col, item)

        # Summary
        tou_sum = result.get('tou_summary', {})
        total_cost = tou_sum.get('total_annual_cost_tou_aud', 0)
        optimised = tou_sum.get('optimised_annual_cost_aud', 0)
        saving = tou_sum.get('potential_saving_aud', 0)
        n = result.get('n_pumps', 0)

        self.summary_label.setText(
            f"Total: {n} pump(s)  |  "
            f"Annual TOU cost: ${total_cost:,.0f}  |  "
            f"Optimised (all off-peak): ${optimised:,.0f}  |  "
            f"Potential saving: ${saving:,.0f}/yr")

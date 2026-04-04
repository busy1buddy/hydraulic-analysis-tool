"""
Fire Flow Wizard Dialog
========================
Specify a junction, required flow, and residual pressure.
Runs fire flow analysis and shows results with WSAA compliance.
Can also sweep all junctions to build a fire flow availability map.
"""

import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QDoubleSpinBox, QPushButton, QLabel,
    QDialogButtonBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


class FireFlowDialog(QDialog):
    """Fire flow analysis wizard — WSAA WSA 03-2011."""

    def __init__(self, api, canvas=None, parent=None):
        super().__init__(parent)
        self.api = api
        self.canvas = canvas
        self._results = None
        self._sweep_results = {}
        self.setWindowTitle("Fire Flow Analysis — WSAA")
        self.setMinimumSize(650, 550)

        layout = QVBoxLayout(self)

        # --- Parameters ---
        params_group = QGroupBox("Fire Flow Parameters")
        params_layout = QFormLayout()

        self.node_combo = QComboBox()
        self.node_combo.setFont(QFont("Consolas", 10))
        for jid in sorted(api.get_node_list('junction')):
            self.node_combo.addItem(jid)
        params_layout.addRow("Fire Node:", self.node_combo)

        self.flow_spin = QDoubleSpinBox()
        self.flow_spin.setRange(1, 200)
        self.flow_spin.setValue(25.0)
        self.flow_spin.setSuffix(" LPS")
        self.flow_spin.setFont(QFont("Consolas", 10))
        params_layout.addRow("Required Flow:", self.flow_spin)

        self.pressure_spin = QDoubleSpinBox()
        self.pressure_spin.setRange(0, 100)
        self.pressure_spin.setValue(12.0)
        self.pressure_spin.setSuffix(" m")
        self.pressure_spin.setFont(QFont("Consolas", 10))
        params_layout.addRow("Min Residual Pressure:", self.pressure_spin)

        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        # --- Standard reference ---
        ref = QLabel("Reference: WSAA WSA 03-2011 — 25 LPS at 12 m residual pressure")
        ref.setFont(QFont("Consolas", 8))
        ref.setStyleSheet("color: #a6adc8;")
        layout.addWidget(ref)

        # --- Buttons ---
        btn_layout = QHBoxLayout()

        self.run_btn = QPushButton("Run at Selected Node")
        self.run_btn.setFont(QFont("Consolas", 10))
        self.run_btn.clicked.connect(self._on_run_single)
        btn_layout.addWidget(self.run_btn)

        self.sweep_btn = QPushButton("Sweep All Nodes")
        self.sweep_btn.setFont(QFont("Consolas", 10))
        self.sweep_btn.clicked.connect(self._on_run_sweep)
        btn_layout.addWidget(self.sweep_btn)

        layout.addLayout(btn_layout)

        # --- Progress ---
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # --- Results table ---
        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels([
            "Junction", "Residual Pressure (m)", "Required (m)", "Status"
        ])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setFont(QFont("Consolas", 9))
        self.results_table.verticalHeader().setVisible(False)
        layout.addWidget(self.results_table)

        # --- Summary ---
        self.summary_label = QLabel("")
        self.summary_label.setFont(QFont("Consolas", 10))
        layout.addWidget(self.summary_label)

        # --- Close ---
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _on_run_single(self):
        """Run fire flow at the selected node."""
        node_id = self.node_combo.currentText()
        flow = self.flow_spin.value()
        pressure = self.pressure_spin.value()

        self.run_btn.setEnabled(False)
        self.sweep_btn.setEnabled(False)

        try:
            results = self.api.run_fire_flow(
                node_id=node_id,
                flow_lps=flow,
                min_pressure_m=pressure,
                save_plot=False,
            )
            self._results = results
            self._show_single_results(results, pressure)
        except Exception as e:
            self.summary_label.setText(f"Error: {e}")
            self.summary_label.setStyleSheet("color: #f38ba8;")
        finally:
            self.run_btn.setEnabled(True)
            self.sweep_btn.setEnabled(True)

    def _on_run_sweep(self):
        """Run fire flow at every junction — build availability map."""
        flow = self.flow_spin.value()
        pressure = self.pressure_spin.value()
        junctions = sorted(self.api.get_node_list('junction'))

        self.run_btn.setEnabled(False)
        self.sweep_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setMaximum(len(junctions))

        self._sweep_results = {}
        self.results_table.setRowCount(0)

        for i, jid in enumerate(junctions):
            self.progress.setValue(i)
            try:
                results = self.api.run_fire_flow(
                    node_id=jid, flow_lps=flow,
                    min_pressure_m=pressure, save_plot=False,
                )
                # Get fire node residual pressure
                fire_p = results.get('fire_node_pressure_m', 0)
                self._sweep_results[jid] = fire_p
            except Exception:
                self._sweep_results[jid] = None

        self.progress.setVisible(False)
        self._show_sweep_results(pressure)

        self.run_btn.setEnabled(True)
        self.sweep_btn.setEnabled(True)

    def _show_single_results(self, results, min_pressure):
        """Populate table with single-node fire flow results."""
        self.results_table.setRowCount(0)
        residuals = results.get('residual_pressures', {})

        pass_count = 0
        fail_count = 0

        for jid in sorted(residuals.keys()):
            p = residuals[jid]
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)

            status = "PASS" if p >= min_pressure else "FAIL"
            if status == "PASS":
                pass_count += 1
            else:
                fail_count += 1

            items = [jid, f"{p:.1f}", f"{min_pressure:.1f}", status]
            for col, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                if col == 3 and val == "FAIL":
                    item.setForeground(QColor(243, 139, 168))
                elif col == 3:
                    item.setForeground(QColor(166, 227, 161))
                self.results_table.setItem(row, col, item)

        fire_node = results.get('fire_node', '?')
        fire_p = results.get('fire_node_pressure_m', 0)
        if fail_count == 0:
            self.summary_label.setText(
                f"PASS — Fire flow at {fire_node}: {fire_p:.1f} m residual. "
                f"All {pass_count} junctions above {min_pressure:.0f} m.")
            self.summary_label.setStyleSheet("color: #a6e3a1;")
        else:
            self.summary_label.setText(
                f"FAIL — {fail_count} junction(s) below {min_pressure:.0f} m "
                f"with fire flow at {fire_node} ({fire_p:.1f} m residual).")
            self.summary_label.setStyleSheet("color: #f38ba8;")

    def _show_sweep_results(self, min_pressure):
        """Populate table with sweep results — one row per fire location."""
        self.results_table.setRowCount(0)
        self.results_table.setHorizontalHeaderLabels([
            "Fire Location", "Residual at Node (m)", "Required (m)", "Status"
        ])

        pass_count = 0
        fail_count = 0

        for jid in sorted(self._sweep_results.keys()):
            p = self._sweep_results[jid]
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)

            if p is None:
                status = "ERROR"
                p_str = "--"
            elif p >= min_pressure:
                status = "PASS"
                p_str = f"{p:.1f}"
                pass_count += 1
            else:
                status = "FAIL"
                p_str = f"{p:.1f}"
                fail_count += 1

            items = [jid, p_str, f"{min_pressure:.1f}", status]
            for col, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                if col == 3 and val == "FAIL":
                    item.setForeground(QColor(243, 139, 168))
                elif col == 3 and val == "PASS":
                    item.setForeground(QColor(166, 227, 161))
                self.results_table.setItem(row, col, item)

        total = pass_count + fail_count
        self.summary_label.setText(
            f"Sweep complete: {pass_count}/{total} nodes can supply "
            f"{self.flow_spin.value():.0f} LPS at {min_pressure:.0f} m residual.")
        if fail_count == 0:
            self.summary_label.setStyleSheet("color: #a6e3a1;")
        else:
            self.summary_label.setStyleSheet("color: #f38ba8;")

        # Update canvas with fire flow availability map if available
        if self.canvas and self._sweep_results:
            self.canvas.set_variable(
                "Fire Flow Residual (m)",
                {k: v for k, v in self._sweep_results.items() if v is not None}
            )

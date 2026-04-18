"""
LCC Dialog — Lifecycle Cost and NPV Comparison
==============================================
Compares different engineering scenarios based on total cost of ownership.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView, QPushButton, QGroupBox, QFormLayout, QLineEdit
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg

class LCCDialog(QDialog):
    def __init__(self, api, scenario_results, parent=None):
        """
        scenario_results: list of dicts from api.calculate_pipeline_lcc()
        """
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Lifecycle Cost Analysis (NPV)")
        self.setMinimumSize(700, 500)
        
        self.layout = QVBoxLayout(self)
        
        # 1. Summary Table
        self.table = QTableWidget(len(scenario_results), 5)
        self.table.setHorizontalHeaderLabels([
            "Scenario", "CAPEX (AUD)", "Annual OPEX", "NPV (Total Cost)", "ROI / Margin"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        for i, res in enumerate(scenario_results):
            self.table.setItem(i, 0, QTableWidgetItem(res.get('name', f"Scenario {i+1}")))
            self.table.setItem(i, 1, QTableWidgetItem(f"${res['capex']:,.0f}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"${res['annual_opex']:,.0f}"))
            self.table.setItem(i, 3, QTableWidgetItem(f"${res['npv']:,.0f}"))
            self.table.setItem(i, 4, QTableWidgetItem("-"))
            
        self.layout.addWidget(self.table)
        
        # 2. Charts
        self.chart_group = QGroupBox("Cost Comparison")
        self.chart_layout = QVBoxLayout(self.chart_group)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#1e1e2e')
        self.plot_widget.setLabel('left', 'Total NPV (AUD)')
        self.chart_layout.addWidget(self.plot_widget)
        self.layout.addWidget(self.chart_group)
        
        self._draw_chart(scenario_results)
        
        # 3. Parameters
        self.param_group = QGroupBox("Analysis Parameters")
        self.param_layout = QFormLayout(self.param_group)
        
        self.discount_input = QLineEdit("0.07")
        self.inflation_input = QLineEdit("0.03")
        self.years_input = QLineEdit("25")
        
        self.param_layout.addRow("Discount Rate (7% = 0.07):", self.discount_input)
        self.param_layout.addRow("Inflation Rate (3% = 0.03):", self.inflation_input)
        self.param_layout.addRow("Analysis Period (Years):", self.years_input)
        
        self.recalc_btn = QPushButton("Recalculate NPV")
        self.recalc_btn.clicked.connect(self._on_recalculate)
        self.param_layout.addRow(self.recalc_btn)
        
        self.layout.addWidget(self.param_group)
        
        # 4. Close
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        self.layout.addWidget(self.close_btn)

    def _draw_chart(self, results):
        x = np.arange(len(results))
        y_npv = [r['npv'] for r in results]
        y_capex = [r['capex'] for r in results]
        
        # NPV Bars
        bg1 = pg.BarGraphItem(x=x, height=y_npv, width=0.6, brush='#89b4fa', name="Total NPV")
        self.plot_widget.addItem(bg1)
        
        # CAPEX portion
        bg2 = pg.BarGraphItem(x=x, height=y_capex, width=0.4, brush='#a6e3a1', name="CAPEX")
        self.plot_widget.addItem(bg2)
        
        self.plot_widget.getAxis('bottom').setTicks([[(i, r.get('name', f"S{i+1}")) for i, r in enumerate(results)]])

    def _on_recalculate(self):
        try:
            dr = float(self.discount_input.text())
            ir = float(self.inflation_input.text())
            yr = int(self.years_input.text())
            
            # Recalculate for current design
            res = self.api.calculate_pipeline_lcc(years=yr, discount_rate=dr, inflation_rate=ir)
            res['name'] = "Current Design"
            
            # Update table
            self.table.setRowCount(1)
            self.table.setItem(0, 0, QTableWidgetItem(res['name']))
            self.table.setItem(0, 1, QTableWidgetItem(f"${res['capex']:,.0f}"))
            self.table.setItem(0, 2, QTableWidgetItem(f"${res['annual_opex']:,.0f}"))
            self.table.setItem(0, 3, QTableWidgetItem(f"${res['npv']:,.0f}"))
            
            # Update chart
            self.plot_widget.clear()
            self._draw_chart([res])
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Recalculation Failed", str(e))

import numpy as np

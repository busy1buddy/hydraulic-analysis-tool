"""
Sensitivity Analysis Dialog — Identifying Critical Calibration Parameters
========================================================================
Analyzes which pipes or junctions have the most impact on system pressure.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView, QPushButton, QComboBox, QGroupBox
)
from PyQt6.QtCore import Qt

class SensitivityDialog(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Roughness & Demand Sensitivity")
        self.setMinimumSize(600, 500)
        
        self.layout = QVBoxLayout(self)
        
        # 1. Config
        self.config_group = QGroupBox("Analysis Settings")
        self.config_layout = QHBoxLayout(self.config_group)
        self.param_combo = QComboBox()
        self.param_combo.addItems(["roughness", "demand"])
        self.config_layout.addWidget(QLabel("Parameter:"))
        self.config_layout.addWidget(self.param_combo)
        
        self.run_btn = QPushButton("Run Analysis")
        self.run_btn.clicked.connect(self._on_run)
        self.config_layout.addWidget(self.run_btn)
        self.layout.addWidget(self.config_group)
        
        # 2. Results Table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Element ID", "Base Value", "Pressure Impact (m)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.layout.addWidget(self.table)
        
        # 3. Actions
        self.highlight_btn = QPushButton("Highlight Top 10 on Canvas")
        self.highlight_btn.clicked.connect(self._on_highlight)
        self.layout.addWidget(self.highlight_btn)
        
        self.results = []

    def _on_run(self):
        param = self.param_combo.currentText()
        self.results = self.api.sensitivity_analysis(parameter=param)
        
        if 'error' in self.results:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Analysis Failed", self.results['error'])
            return
            
        self.table.setRowCount(len(self.results))
        for i, r in enumerate(self.results):
            self.table.setItem(i, 0, QTableWidgetItem(r['element']))
            self.table.setItem(i, 1, QTableWidgetItem(str(r['base_value'])))
            self.table.setItem(i, 2, QTableWidgetItem(f"{r['pressure_change_m']:.3f}"))

    def _on_highlight(self):
        if not self.results:
            return
            
        top_ids = [r['element'] for r in self.results[:10]]
        self.parent().canvas.highlight_elements(top_ids)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Highlighted", "Top 10 most sensitive elements highlighted on canvas.")

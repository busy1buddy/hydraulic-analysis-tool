"""
Calibration Data Dialog — Field Measurement Entry
================================================
Allows users to enter or import pressure/flow data from field tests.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView, QPushButton, QGroupBox, QFileDialog
)
from PyQt6.QtCore import Qt

class CalibrationDataDialog(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Field Calibration Data")
        self.setMinimumSize(500, 400)
        
        self.layout = QVBoxLayout(self)
        
        # 1. Instructions
        self.layout.addWidget(QLabel("Enter field measurements for model verification:"))
        
        # 2. Table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Node ID", "Measured Pressure (m)", "Measured Flow (LPS)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._load_existing_data()
        self.layout.addWidget(self.table)
        
        # 3. Buttons
        btn_layout = QHBoxLayout()
        self.add_row_btn = QPushButton("Add Row")
        self.add_row_btn.clicked.connect(self._on_add_row)
        self.import_btn = QPushButton("Import CSV...")
        self.import_btn.clicked.connect(self._on_import_csv)
        
        btn_layout.addWidget(self.add_row_btn)
        btn_layout.addWidget(self.import_btn)
        btn_layout.addStretch()
        self.layout.addLayout(btn_layout)
        
        # 4. Actions
        self.apply_btn = QPushButton("Apply & Close")
        self.apply_btn.clicked.connect(self._on_apply)
        self.apply_btn.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold;")
        self.layout.addWidget(self.apply_btn)

    def _load_existing_data(self):
        if hasattr(self.api, '_field_data'):
            self.table.setRowCount(len(self.api._field_data))
            for i, (nid, data) in enumerate(self.api._field_data.items()):
                self.table.setItem(i, 0, QTableWidgetItem(nid))
                self.table.setItem(i, 1, QTableWidgetItem(str(data['pressure_m']) if data['pressure_m'] else ""))
                self.table.setItem(i, 2, QTableWidgetItem(str(data['flow_lps']) if data['flow_lps'] else ""))

    def _on_add_row(self):
        self.table.insertRow(self.table.rowCount())

    def _on_import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Field Data CSV", "", "CSV Files (*.csv)")
        if path:
            import pandas as pd
            try:
                df = pd.read_csv(path)
                # Expecting columns: node_id, pressure, flow
                for _, row in df.iterrows():
                    r = self.table.rowCount()
                    self.table.insertRow(r)
                    self.table.setItem(r, 0, QTableWidgetItem(str(row.get('node_id', ''))))
                    self.table.setItem(r, 1, QTableWidgetItem(str(row.get('pressure', ''))))
                    self.table.setItem(r, 2, QTableWidgetItem(str(row.get('flow', ''))))
            except Exception as e:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Import Error", f"Failed to import CSV: {e}")

    def _on_apply(self):
        self.api._field_data = {} # Reset
        for i in range(self.table.rowCount()):
            nid = self.table.item(i, 0).text() if self.table.item(i, 0) else None
            if not nid: continue
            
            p_text = self.table.item(i, 1).text() if self.table.item(i, 1) else ""
            f_text = self.table.item(i, 2).text() if self.table.item(i, 2) else ""
            
            p = float(p_text) if p_text else None
            f = float(f_text) if f_text else None
            
            self.api.set_field_measurement(nid, p, f)
            
        self.accept()

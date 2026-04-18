"""
Calibration Residuals Dialog — Model Accuracy Assessment
======================================================
Displays discrepancies between field data and model results.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView, QPushButton, QGroupBox
)
from PyQt6.QtCore import Qt

class CalibrationResidualDialog(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Model Calibration Residuals")
        self.setMinimumSize(600, 500)
        
        self.layout = QVBoxLayout(self)
        
        # 1. Summary Stats
        self.stats_group = QGroupBox("Accuracy Metrics")
        self.stats_layout = QHBoxLayout(self.stats_group)
        self.mae_label = QLabel("MAE: -")
        self.rmse_label = QLabel("RMSE: -")
        self.stats_layout.addWidget(self.mae_label)
        self.stats_layout.addWidget(self.rmse_label)
        self.layout.addWidget(self.stats_group)
        
        # 2. Residuals Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Node ID", "Measured (m)", "Model (m)", "Error (m)", "% Error"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.layout.addWidget(self.table)
        
        # 3. Actions
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Recalculate Residuals")
        self.refresh_btn.clicked.connect(self._refresh_data)
        self.calibrate_btn = QPushButton("Run Auto-Calibration...")
        self.calibrate_btn.clicked.connect(self._on_auto_calibrate)
        self.calibrate_btn.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold;")
        
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.calibrate_btn)
        self.layout.addLayout(btn_layout)
        
        self._refresh_data()

    def _refresh_data(self):
        res = self.api.get_calibration_residuals()
        if 'error' in res:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Data", res['error'])
            return
            
        stats = res['stats']
        self.mae_label.setText(f"MAE: {stats['mae_p']:.3f} m")
        self.rmse_label.setText(f"RMSE: {stats['rmse_p']:.3f} m")
        
        residuals = res['residuals']
        self.table.setRowCount(len(residuals))
        for i, r in enumerate(residuals):
            self.table.setItem(i, 0, QTableWidgetItem(r['node_id']))
            self.table.setItem(i, 1, QTableWidgetItem(f"{r['measured_p']:.2f}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{r['model_p']:.2f}"))
            self.table.setItem(i, 3, QTableWidgetItem(f"{r['error_p']:.2f}"))
            self.table.setItem(i, 4, QTableWidgetItem(f"{r['error_percent']:.1f}%"))
            
            # Color coding for errors
            if abs(r['error_p']) > 2.0: # 2m error threshold
                self.table.item(i, 3).setForeground(Qt.GlobalColor.red)

    def _on_auto_calibrate(self):
        # We'll use the existing CalibrationDialog which handles the optimization UI
        from desktop.calibration_dialog import CalibrationDialog
        dlg = CalibrationDialog(self.api, self)
        if dlg.exec():
            self._refresh_data()

"""
Calibration Dashboard — Model Validation Visualization
======================================================
Visualizes the goodness-of-fit between model and field data.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QPushButton
)
import pyqtgraph as pg
import numpy as np

class CalibrationDashboard(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Hydraulic Model Calibration Dashboard")
        self.setMinimumSize(800, 600)
        
        self.layout = QVBoxLayout(self)
        
        # 1. Stats Cards
        self.stats_layout = QHBoxLayout()
        self.layout.addLayout(self.stats_layout)
        self.r2_card = self._create_card("Coefficient of Determination (R2)", "0.000")
        self.mae_card = self._create_card("Mean Absolute Error (MAE)", "0.00 m")
        self.rmse_card = self._create_card("Root Mean Square Error (RMSE)", "0.00 m")
        
        self.stats_layout.addWidget(self.r2_card)
        self.stats_layout.addWidget(self.mae_card)
        self.stats_layout.addWidget(self.rmse_card)
        
        # 2. Scatter Plot
        self.plot_group = QGroupBox("Model vs Measured Pressure")
        self.plot_layout = QVBoxLayout(self.plot_group)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#1e1e2e')
        self.plot_widget.setLabel('left', 'Model Pressure (m)')
        self.plot_widget.setLabel('bottom', 'Measured Pressure (m)')
        self.plot_layout.addWidget(self.plot_widget)
        self.layout.addWidget(self.plot_group)
        
        # 3. Actions
        self.refresh_btn = QPushButton("Refresh Verification")
        self.refresh_btn.clicked.connect(self._refresh_data)
        self.layout.addWidget(self.refresh_btn)
        
        self._refresh_data()

    def _create_card(self, title, value):
        from PyQt6.QtWidgets import QFrame
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet("background-color: #313244; border-radius: 10px; color: #cdd6f4;")
        layout = QVBoxLayout(card)
        t_label = QLabel(title)
        t_label.setStyleSheet("font-size: 12px; color: #bac2de;")
        v_label = QLabel(value)
        v_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #a6e3a1;")
        v_label.setObjectName("value_label")
        layout.addWidget(t_label)
        layout.addWidget(v_label)
        return card

    def _refresh_data(self):
        res = self.api.get_calibration_residuals()
        if 'error' in res:
            return
            
        stats = res['stats']
        residuals = res['residuals']
        
        x_meas = [r['measured_p'] for r in residuals]
        y_mod = [r['model_p'] for r in residuals]
        
        # Calculate R2
        r2 = 0
        if len(x_meas) > 1:
            from desktop.calibration_dialog import compute_r2
            r2 = compute_r2(x_meas, y_mod)
            
        # Update cards
        self.r2_card.findChild(QLabel, "value_label").setText(f"{r2:.3f}")
        self.mae_card.findChild(QLabel, "value_label").setText(f"{stats['mae_p']:.2f} m")
        self.rmse_card.findChild(QLabel, "value_label").setText(f"{stats['rmse_p']:.2f} m")
        
        # Plot
        self.plot_widget.clear()
        
        # 1:1 Line
        m = max(max(x_meas), max(y_mod)) if x_meas else 100
        self.plot_widget.plot([0, m], [0, m], pen=pg.mkPen('#bac2de', style=Qt.PenStyle.DashLine))
        
        # Scatter
        scatter = pg.ScatterPlotItem(size=12, pen=pg.mkPen('#11111b', width=0.5), brush='#89b4fa')
        scatter.addPoints(x_meas, y_mod)
        self.plot_widget.addItem(scatter)

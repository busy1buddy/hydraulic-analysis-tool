"""
Pump Panel — Pump Curve and System Curve Analysis
=================================================
Visualizes pump curves, system curves, and operating points.
Allows selection of pumps from the database and matching against 
real-time system requirements.
"""

import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QGroupBox, QFormLayout, QPushButton, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import numpy as np

from data.pump_curves import PUMP_DATABASE, get_pump_head, get_pump_efficiency

class PumpPanel(QWidget):
    """Widget for pump performance analysis."""
    
    pump_selected = pyqtSignal(str) # pump_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        
        # Header / Control Area
        self.controls = QHBoxLayout()
        
        # Pump Selection
        self.pump_combo = QComboBox()
        self.pump_combo.addItem("--- Select Pump ---", None)
        for pid, pdata in PUMP_DATABASE.items():
            self.pump_combo.addItem(f"{pdata['manufacturer']} {pdata['model']}", pid)
        self.pump_combo.currentIndexChanged.connect(self._on_pump_changed)
        self.controls.addWidget(QLabel("Pump:"))
        self.controls.addWidget(self.pump_combo)
        
        # Speed Slider
        self.controls.addWidget(QLabel("Speed:"))
        self.speed_spin = QComboBox() # Using combo for common speeds or just spinbox
        from PyQt6.QtWidgets import QSpinBox
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(30, 120)
        self.speed_spin.setValue(100)
        self.speed_spin.setSuffix("%")
        self.speed_spin.valueChanged.connect(self._on_speed_changed)
        self.controls.addWidget(self.speed_spin)
        
        self.controls.addStretch()
        
        self.show_hgl_check = QCheckBox("Show Efficiency")
        self.show_hgl_check.setChecked(True)
        self.controls.addWidget(self.show_hgl_check)
        
        self.layout.addLayout(self.controls)
        
        # Splitter or Grid for Plot and Stats
        self.main_content = QHBoxLayout()
        
        # Plot Widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#1e1e2e')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', 'Head', units='m')
        self.plot_widget.setLabel('bottom', 'Flow', units='L/s')
        self.plot_widget.addLegend(offset=(30, 30))
        self.main_content.addWidget(self.plot_widget, 3)
        
        # Stats Panel
        self.stats_group = QGroupBox("Operating Point")
        self.stats_layout = QFormLayout(self.stats_group)
        self.stats_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        self.flow_val = QLabel("-")
        self.head_val = QLabel("-")
        self.eff_val = QLabel("-")
        self.power_val = QLabel("-")
        self.bep_status = QLabel("-")
        self.npsha_val = QLabel("-")
        self.cavitation_status = QLabel("-")
        self.annual_cost = QLabel("-")
        
        self.stats_layout.addRow("Flow:", self.flow_val)
        self.stats_layout.addRow("Head:", self.head_val)
        self.stats_layout.addRow("Efficiency:", self.eff_val)
        self.stats_layout.addRow("Power (Est):", self.power_val)
        self.stats_layout.addRow("BEP Status:", self.bep_status)
        self.stats_layout.addRow("NPSHa:", self.npsha_val)
        self.stats_layout.addRow("Cavitation:", self.cavitation_status)
        self.stats_layout.addRow("Annual Cost:", self.annual_cost)
        
        self.main_content.addWidget(self.stats_group, 1)
        
        self.layout.addLayout(self.main_content)
        
        # Data Items
        self.pump_curve_item = self.plot_widget.plot(
            pen=pg.mkPen('#fab387', width=2),
            name="Pump Curve"
        )
        self.system_curve_item = self.plot_widget.plot(
            pen=pg.mkPen('#89b4fa', width=2, style=Qt.PenStyle.DashLine),
            name="System Curve"
        )
        self.duty_point_item = pg.ScatterPlotItem(
            size=15, brush=pg.mkBrush('#f38ba8'),
            pen=pg.mkPen('#1e1e2e', width=1),
            name="Duty Point"
        )
        self.plot_widget.addItem(self.duty_point_item)
        
        self.current_system_curve = []
        self.current_pump_id = None

    def set_system_curve(self, curve_data):
        """
        Set the system curve data [(flow, head), ...].
        """
        self.current_system_curve = curve_data
        if curve_data:
            fx = [p[0] for p in curve_data]
            fy = [p[1] for p in curve_data]
            self.system_curve_item.setData(fx, fy)
            self._update_operating_point()

    def _on_pump_changed(self, index):
        self.current_pump_id = self.pump_combo.itemData(index)
        self._update_pump_curve()
        self._update_operating_point()

    def _on_speed_changed(self, val):
        self._update_pump_curve()
        self._update_operating_point()

    def _update_pump_curve(self):
        if not self.current_pump_id:
            self.pump_curve_item.setData([], [])
            return
            
        pdata = PUMP_DATABASE[self.current_pump_id]
        flows = [p[0] for p in pdata['curve_points']]
        speed = self.speed_spin.value()
        
        # Smooth interpolation for plotting
        fx = np.linspace(0, flows[-1] * (speed/100.0) * 1.2, 100)
        fy = [get_pump_head(self.current_pump_id, q, speed) for q in fx]
        
        self.pump_curve_item.setData(fx, fy)

    def _update_operating_point(self):
        if not self.current_pump_id or not self.current_system_curve:
            return
            
        # Try to use parent's API for precision solver
        res = None
        speed = self.speed_spin.value()
        if hasattr(self.parent(), 'api') and self.parent().api:
            res = self.parent().api.solve_operating_point(
                self.current_pump_id, self.current_system_curve, speed_pct=speed)
        
        if res:
            best_q = res['flow_lps']
            best_h = res['head_m']
            eff = res['efficiency_pct']
            
            self.duty_point_item.setData([best_q], [best_h])
            self.flow_val.setText(f"{best_q:.1f} L/s")
            self.head_val.setText(f"{best_h:.1f} m")
            self.eff_val.setText(f"{eff:.1f} %")
            
            # Power estimate
            q_m3s = best_q / 1000.0
            power = (q_m3s * best_h * 1000 * 9.81) / (eff/100.0) if eff > 0 else 0
            self.power_val.setText(f"{power/1000.0:.1f} kW")
            
            # BEP Status
            if hasattr(self.parent(), 'api') and self.parent().api:
                bep = self.parent().api.analyze_bep_proximity(self.current_pump_id, best_q)
                if bep:
                    self.bep_status.setText(bep['status'])
                    self.bep_status.setStyleSheet(f"color: {bep['color']}; font-weight: bold;")
                
                # NPSHa
                npsha = self.parent().api.calculate_npsha(self.current_pump_id, best_q)
                if npsha is not None:
                    self.npsha_val.setText(f"{npsha:.2f} m")
                    
                    # Cavitation check
                    cav = self.parent().api.check_cavitation_risk(self.current_pump_id, npsha)
                    if cav:
                        self.cavitation_status.setText(cav['status'])
                        self.cavitation_status.setStyleSheet(f"color: {cav['color']}; font-weight: bold;")
                
                # Energy Cost
                cost_res = self.parent().api.calculate_energy_cost(power/1000.0)
                if cost_res:
                    self.annual_cost.setText(f"${cost_res['annual_cost_aud']:,.0f} AUD")
        else:
            self.duty_point_item.setData([], [])
            self.flow_val.setText("No Match")
            self.head_val.setText("-")
            self.eff_val.setText("-")
            self.power_val.setText("-")
            self.bep_status.setText("-")
            self.npsha_val.setText("-")
            self.cavitation_status.setText("-")
            self.annual_cost.setText("-")

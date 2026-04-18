"""
TCO Dashboard — Total Cost of Ownership Visualization
=====================================================
Visualizes the long-term economic impact of design decisions.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QFrame
)
import pyqtgraph as pg
import numpy as np

class TCODashboard(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Total Cost of Ownership (TCO) Dashboard")
        self.setMinimumSize(800, 600)
        
        self.layout = QVBoxLayout(self)
        
        # 1. Headline Metrics
        self.headline_layout = QHBoxLayout()
        self.layout.addLayout(self.headline_layout)
        
        self.npv_card = self._create_card("Total NPV (25yr)", "$0")
        self.capex_card = self._create_card("Total CAPEX", "$0")
        self.opex_card = self._create_card("Annual OPEX", "$0")
        self.carbon_card = self._create_card("Carbon Footprint", "0 tCO2")
        
        self.headline_layout.addWidget(self.npv_card)
        self.headline_layout.addWidget(self.capex_card)
        self.headline_layout.addWidget(self.opex_card)
        self.headline_layout.addWidget(self.carbon_card)
        
        # 2. Charts
        self.charts_layout = QHBoxLayout()
        self.layout.addLayout(self.charts_layout)
        
        # A. Cost Breakdown (Bar)
        self.breakdown_group = QGroupBox("Lifecycle Cost Breakdown")
        self.breakdown_layout = QVBoxLayout(self.breakdown_group)
        self.breakdown_plot = pg.PlotWidget()
        self.breakdown_plot.setBackground('#1e1e2e')
        self.breakdown_layout.addWidget(self.breakdown_plot)
        self.charts_layout.addWidget(self.breakdown_group)
        
        # B. Cumulative Cost (Line)
        self.cumulative_group = QGroupBox("Cumulative Total Cost (50 Year Projection)")
        self.cumulative_layout = QVBoxLayout(self.cumulative_group)
        self.cumulative_plot = pg.PlotWidget()
        self.cumulative_plot.setBackground('#1e1e2e')
        self.cumulative_layout.addWidget(self.cumulative_plot)
        self.charts_layout.addWidget(self.cumulative_group)
        
        self._refresh_data()

    def _create_card(self, title, value):
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet("background-color: #313244; border-radius: 10px; color: #cdd6f4;")
        layout = QVBoxLayout(card)
        t_label = QLabel(title)
        t_label.setStyleSheet("font-size: 14px; color: #bac2de;")
        v_label = QLabel(value)
        v_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #89b4fa;")
        v_label.setObjectName("value_label")
        layout.addWidget(t_label)
        layout.addWidget(v_label)
        return card

    def _refresh_data(self):
        if not self.api.wn:
            return
            
        lcc = self.api.calculate_pipeline_lcc()
        if not lcc:
            return
            
        # Update cards
        self.npv_card.findChild(QLabel, "value_label").setText(f"${lcc['npv']:,.0f}")
        self.capex_card.findChild(QLabel, "value_label").setText(f"${lcc['capex']:,.0f}")
        self.opex_card.findChild(QLabel, "value_label").setText(f"${lcc['annual_opex']:,.0f}")
        
        carbon = self.api.calculate_carbon_footprint()
        if carbon:
            self.carbon_card.findChild(QLabel, "value_label").setText(f"{carbon:,.0f} tCO2")
        
        # Draw Breakdown
        # We estimate Maint vs Energy
        maint = lcc['annual_opex'] * 0.7 # Placeholder ratio
        energy = lcc['annual_opex'] * 0.3
        
        x = [0, 1, 2]
        y = [lcc['capex'], maint * 25, energy * 25] # 25yr totals
        bg = pg.BarGraphItem(x=x, height=y, width=0.6, brush=['#a6e3a1', '#f9e2af', '#fab387'])
        self.breakdown_plot.addItem(bg)
        self.breakdown_plot.getAxis('bottom').setTicks([[ (0, 'CAPEX'), (1, 'Maint'), (2, 'Energy') ]])
        
        # Draw Cumulative
        years = np.arange(51)
        # Simplified linear model: Cost = CAPEX + Year * OPEX
        costs = lcc['capex'] + years * lcc['annual_opex']
        self.cumulative_plot.plot(years, costs, pen=pg.mkPen('#89b4fa', width=3))
        self.cumulative_plot.setLabel('bottom', 'Years')
        self.cumulative_plot.setLabel('left', 'Cumulative Cost (AUD)')

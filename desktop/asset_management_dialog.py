"""
Asset Management Dialog — Maintenance and Renewal Planning
==========================================================
Configures pipe conditions, maintenance rates, and renewal strategies.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView, QPushButton, QGroupBox, QFileDialog
)
from PyQt6.QtCore import Qt

class AssetManagementDialog(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Asset Management & Maintenance")
        self.setMinimumWidth(600)
        
        self.layout = QVBoxLayout(self)
        
        # 1. Condition Import
        self.import_group = QGroupBox("Asset Condition Data")
        self.import_layout = QHBoxLayout(self.import_group)
        self.import_btn = QPushButton("Import Condition CSV...")
        self.import_btn.clicked.connect(self._on_import_csv)
        self.import_layout.addWidget(self.import_btn)
        self.layout.addWidget(self.import_group)
        
        # 2. Maintenance Rates
        self.rate_group = QGroupBox("Maintenance Rates (AUD/km/year)")
        self.rate_layout = QVBoxLayout(self.rate_group)
        self.rate_table = QTableWidget(6, 2)
        self.rate_table.setHorizontalHeaderLabels(["Material", "Rate"])
        self.rate_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._populate_rates()
        self.rate_layout.addWidget(self.rate_table)
        self.layout.addWidget(self.rate_group)
        
        # 3. Renewal Strategy
        self.renewal_group = QGroupBox("Renewal Suggestions (10 Year Horizon)")
        self.renewal_layout = QVBoxLayout(self.renewal_group)
        self.suggest_btn = QPushButton("Calculate Renewal Priorities")
        self.suggest_btn.clicked.connect(self._on_calculate_renewal)
        self.renewal_table = QTableWidget(0, 3)
        self.renewal_table.setHorizontalHeaderLabels(["Pipe ID", "Priority Reason", "Est. Cost"])
        self.renewal_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.renewal_layout.addWidget(self.suggest_btn)
        self.renewal_layout.addWidget(self.renewal_table)
        self.layout.addWidget(self.renewal_group)
        
        # 4. Close
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        self.layout.addWidget(self.close_btn)

    def _populate_rates(self):
        from data.asset_costs import MAINTENANCE_RATES
        for i, (mat, rate) in enumerate(MAINTENANCE_RATES.items()):
            self.rate_table.setItem(i, 0, QTableWidgetItem(mat))
            self.rate_table.setItem(i, 1, QTableWidgetItem(str(rate)))

    def _on_import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Condition CSV", "", "CSV Files (*.csv)")
        if path:
            count = self.api.import_pipe_conditions_csv(path)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Import Complete", f"Imported condition data for {count} pipes.")

    def _on_calculate_renewal(self):
        suggestions = self.api.suggest_replacements()
        self.renewal_table.setRowCount(len(suggestions))
        for i, s in enumerate(suggestions):
            self.renewal_table.setItem(i, 0, QTableWidgetItem(s['pipe_id']))
            self.renewal_table.setItem(i, 1, QTableWidgetItem(s['reason']))
            self.renewal_table.setItem(i, 2, QTableWidgetItem(f"${s['cost']:,.0f}"))

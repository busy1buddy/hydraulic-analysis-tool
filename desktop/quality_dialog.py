"""
Quality Dialog — Water Quality Analysis Configuration
====================================================
Configures chlorine decay, age of water, and source concentrations.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QGroupBox, QFormLayout, QRadioButton,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt

class QualityDialog(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Water Quality Configuration")
        self.setMinimumWidth(400)
        
        self.layout = QVBoxLayout(self)
        
        # 1. Mode Selection
        self.mode_group = QGroupBox("Analysis Mode")
        self.mode_layout = QHBoxLayout(self.mode_group)
        
        self.none_rb = QRadioButton("None")
        self.age_rb = QRadioButton("Water Age")
        self.chem_rb = QRadioButton("Chemical Decay")
        
        self.mode_layout.addWidget(self.none_rb)
        self.mode_layout.addWidget(self.age_rb)
        self.mode_layout.addWidget(self.chem_rb)
        
        self.layout.addWidget(self.mode_group)
        
        # 2. Reaction Coefficients
        self.coeff_group = QGroupBox("Reaction Coefficients")
        self.coeff_layout = QFormLayout(self.coeff_group)
        
        self.bulk_input = QLineEdit("-0.5")
        self.wall_input = QLineEdit("-0.1")
        
        self.coeff_layout.addRow("Bulk Coeff (1/day):", self.bulk_input)
        self.coeff_layout.addRow("Wall Coeff (m/day):", self.wall_input)
        
        self.layout.addWidget(self.coeff_group)
        
        # 3. Source Concentrations
        self.source_group = QGroupBox("Source Concentrations (mg/L)")
        self.source_layout = QVBoxLayout(self.source_group)
        
        self.source_table = QTableWidget(0, 2)
        self.source_table.setHorizontalHeaderLabels(["Node", "Concentration"])
        self.source_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.source_layout.addWidget(self.source_table)
        
        self.opt_layout = QHBoxLayout()
        self.target_input = QLineEdit("0.2")
        self.target_input.setFixedWidth(50)
        self.opt_btn = QPushButton("Auto-Optimize Dose")
        self.opt_btn.clicked.connect(self._on_optimize)
        self.opt_layout.addWidget(QLabel("Target Min (mg/L):"))
        self.opt_layout.addWidget(self.target_input)
        self.opt_layout.addWidget(self.opt_btn)
        self.source_layout.addLayout(self.opt_layout)
        
        self.booster_btn = QPushButton("Suggest Booster Placements")
        self.booster_btn.clicked.connect(self._on_suggest_boosters)
        self.source_layout.addWidget(self.booster_btn)
        
        self.layout.addWidget(self.source_group)
        
        # 4. Buttons
        self.buttons = QHBoxLayout()
        self.ok_btn = QPushButton("Apply")
        self.cancel_btn = QPushButton("Cancel")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.buttons.addWidget(self.ok_btn)
        self.buttons.addWidget(self.cancel_btn)
        self.layout.addLayout(self.buttons)
        
        self._populate()

    def _populate(self):
        if not self.api.wn:
            return
            
        # Set current mode
        mode = self.api.wn.options.quality.parameter
        if mode == 'NONE': self.none_rb.setChecked(True)
        elif mode == 'AGE': self.age_rb.setChecked(True)
        elif mode == 'CHEMICAL': self.chem_rb.setChecked(True)
        
        # Set coefficients
        self.bulk_input.setText(str(self.api.wn.options.reaction.bulk_coeff))
        self.wall_input.setText(str(self.api.wn.options.reaction.wall_coeff))
        
        # Set sources
        sources = self.api.wn.reservoir_name_list + self.api.wn.tank_name_list
        self.source_table.setRowCount(len(sources))
        for i, name in enumerate(sources):
            self.source_table.setItem(i, 0, QTableWidgetItem(name))
            
            # Find existing concentration if any
            conc = "1.0"
            for sname, source in self.api.wn.sources():
                if source.node_name == name:
                    conc = str(source.strength_timeseries.base_value)
                    break
            self.source_table.setItem(i, 1, QTableWidgetItem(conc))

    def _on_optimize(self):
        try:
            target = float(self.target_input.text())
            best_dose = self.api.optimize_source_dose(target)
            if best_dose:
                for i in range(self.source_table.rowCount()):
                    self.source_table.setItem(i, 1, QTableWidgetItem(str(best_dose)))
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Optimization Complete", f"Optimal dose found: {best_dose} mg/L")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Optimization Failed", str(e))

            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Optimization Failed", str(e))

    def _on_suggest_boosters(self):
        try:
            target = float(self.target_input.text())
            boosters = self.api.suggest_booster_stations(target)
            if boosters:
                msg = "Suggested Booster Locations:\n\n"
                for b in boosters:
                    msg += f"- {b['node_id']}: Residual {b['residual']} mg/L. ({b['reason']})\n"
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Booster Suggestions", msg)
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Booster Suggestions", "No boosters required. All nodes meet target.")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Analysis Failed", str(e))

    def get_config(self):
        mode = 'NONE'
        if self.age_rb.isChecked(): mode = 'AGE'
        elif self.chem_rb.isChecked(): mode = 'CHEMICAL'
        
        sources = {}
        for i in range(self.source_table.rowCount()):
            name = self.source_table.item(i, 0).text()
            try:
                conc = float(self.source_table.item(i, 1).text())
                sources[name] = conc
            except Exception:
                pass
                
        return {
            'mode': mode,
            'bulk': float(self.bulk_input.text()),
            'wall': float(self.wall_input.text()),
            'sources': sources
        }

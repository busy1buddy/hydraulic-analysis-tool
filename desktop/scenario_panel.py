"""
Scenario Panel — Scenario Management and Comparison
=====================================================
Manages multiple scenarios for side-by-side what-if analysis.
Each scenario stores demand multipliers, pipe modifications, etc.
All mutations route through HydraulicAPI.
"""

import copy
import json
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTreeWidget, QTreeWidgetItem, QDialog, QLineEdit,
    QDoubleSpinBox, QComboBox, QFormLayout, QDialogButtonBox,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont, QColor


class ScenarioData:
    """Data container for a single scenario."""

    def __init__(self, name, demand_multiplier=1.0, modifications=None):
        self.name = name
        self.demand_multiplier = demand_multiplier
        self.modifications = modifications or []
        self.results = None

    def to_dict(self):
        return {
            'name': self.name,
            'demand_multiplier': self.demand_multiplier,
            'modifications': self.modifications,
        }


class ScenarioDialog(QDialog):
    """Dialog for creating/editing a scenario."""

    def __init__(self, parent=None, scenario=None):
        super().__init__(parent)
        self.setWindowTitle("Scenario" if scenario is None else f"Edit: {scenario.name}")
        self.setMinimumWidth(350)

        layout = QFormLayout(self)

        self.name_input = QLineEdit()
        self.name_input.setText(scenario.name if scenario else "New Scenario")
        layout.addRow("Name:", self.name_input)

        self.demand_spin = QDoubleSpinBox()
        self.demand_spin.setRange(0.1, 5.0)
        self.demand_spin.setSingleStep(0.1)
        self.demand_spin.setValue(scenario.demand_multiplier if scenario else 1.0)
        self.demand_spin.setSuffix("x")
        layout.addRow("Demand Multiplier:", self.demand_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_scenario(self):
        return ScenarioData(
            name=self.name_input.text().strip(),
            demand_multiplier=self.demand_spin.value(),
        )


class ScenarioComparisonTable(QWidget):
    """Table comparing results across scenarios."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Scenario", "Demand (x)", "Min P (m)", "Max P (m)",
            "Max V (m/s)", "WSAA Issues"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setFont(QFont("Consolas", 9))
        layout.addWidget(self.table)

    def update_scenarios(self, scenarios):
        """Update table with scenario results."""
        self.table.setRowCount(0)

        for sc in scenarios:
            row = self.table.rowCount()
            self.table.insertRow(row)

            items = [sc.name, f"{sc.demand_multiplier:.1f}"]

            if sc.results:
                pressures = sc.results.get('pressures', {})
                flows = sc.results.get('flows', {})
                compliance = sc.results.get('compliance', [])

                all_p = [p.get('avg_m', 0) for p in pressures.values()]
                all_v = [f.get('max_velocity_ms', 0) for f in flows.values()]

                min_p = min(all_p) if all_p else 0
                max_p = max(all_p) if all_p else 0
                max_v = max(all_v) if all_v else 0
                issues = sum(1 for c in compliance
                             if c.get('type') in ('WARNING', 'CRITICAL'))

                items.extend([
                    f"{min_p:.1f}", f"{max_p:.1f}",
                    f"{max_v:.2f}", str(issues),
                ])
            else:
                items.extend(["--", "--", "--", "--"])

            for col, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                # Color WSAA issues column
                if col == 5 and val != "--" and int(val) > 0:
                    item.setForeground(QColor(243, 139, 168))
                elif col == 5 and val == "0":
                    item.setForeground(QColor(166, 227, 161))
                self.table.setItem(row, col, item)


class ScenarioPanel(QWidget):
    """Panel for managing scenarios."""

    scenario_selected = pyqtSignal(str)  # scenario name
    run_scenario = pyqtSignal(object)    # ScenarioData
    run_all = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scenarios = [ScenarioData("Base", 1.0)]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Buttons
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.add_btn.setFont(QFont("Consolas", 9))
        self.add_btn.clicked.connect(self._on_add)
        btn_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setFont(QFont("Consolas", 9))
        self.edit_btn.clicked.connect(self._on_edit)
        btn_layout.addWidget(self.edit_btn)

        self.dup_btn = QPushButton("Duplicate")
        self.dup_btn.setFont(QFont("Consolas", 9))
        self.dup_btn.clicked.connect(self._on_duplicate)
        btn_layout.addWidget(self.dup_btn)

        self.del_btn = QPushButton("Delete")
        self.del_btn.setFont(QFont("Consolas", 9))
        self.del_btn.clicked.connect(self._on_delete)
        btn_layout.addWidget(self.del_btn)

        self.run_all_btn = QPushButton("Run All")
        self.run_all_btn.setFont(QFont("Consolas", 9))
        self.run_all_btn.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        self.run_all_btn.clicked.connect(self._on_run_all)
        btn_layout.addWidget(self.run_all_btn)

        layout.addLayout(btn_layout)

        # Scenario tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Scenarios"])
        self.tree.setFont(QFont("Consolas", 10))
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)

        # Comparison table
        self.comparison = ScenarioComparisonTable()
        layout.addWidget(self.comparison)

        self._refresh_tree()

    def _refresh_tree(self):
        self.tree.clear()
        for sc in self.scenarios:
            status = "done" if sc.results else "pending"
            item = QTreeWidgetItem(self.tree,
                                   [f"{sc.name} ({sc.demand_multiplier:.1f}x) [{status}]"])
            item.setData(0, Qt.ItemDataRole.UserRole, sc.name)

    def _get_selected_scenario(self):
        item = self.tree.currentItem()
        if item is None:
            return None
        name = item.data(0, Qt.ItemDataRole.UserRole)
        for sc in self.scenarios:
            if sc.name == name:
                return sc
        return None

    def _on_add(self):
        dialog = ScenarioDialog(self)
        if dialog.exec():
            sc = dialog.get_scenario()
            if any(s.name == sc.name for s in self.scenarios):
                QMessageBox.warning(self, "Duplicate", f"Scenario '{sc.name}' already exists.")
                return
            self.scenarios.append(sc)
            self._refresh_tree()

    def _on_edit(self):
        sc = self._get_selected_scenario()
        if sc is None:
            return
        dialog = ScenarioDialog(self, sc)
        if dialog.exec():
            new = dialog.get_scenario()
            sc.name = new.name
            sc.demand_multiplier = new.demand_multiplier
            self._refresh_tree()

    def _on_duplicate(self):
        sc = self._get_selected_scenario()
        if sc is None:
            return
        new_sc = ScenarioData(
            name=f"{sc.name} (copy)",
            demand_multiplier=sc.demand_multiplier,
            modifications=copy.deepcopy(sc.modifications),
        )
        self.scenarios.append(new_sc)
        self._refresh_tree()

    def _on_delete(self):
        sc = self._get_selected_scenario()
        if sc is None:
            return
        if sc.name == "Base":
            QMessageBox.warning(self, "Cannot Delete", "Cannot delete the Base scenario.")
            return
        self.scenarios.remove(sc)
        self._refresh_tree()

    def _on_item_clicked(self, item, column):
        name = item.data(0, Qt.ItemDataRole.UserRole)
        self.scenario_selected.emit(name)

    def _on_run_all(self):
        self.run_all.emit()

    def update_comparison(self):
        self.comparison.update_scenarios(self.scenarios)
        self._refresh_tree()

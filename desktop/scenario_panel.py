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
from collections import defaultdict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTreeWidget, QTreeWidgetItem, QDialog, QLineEdit,
    QDoubleSpinBox, QComboBox, QFormLayout, QDialogButtonBox,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QFileDialog
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont, QColor


class ScenarioData:
    """Data container for a single scenario."""

    def __init__(self, name, demand_multiplier=1.0, modifications=None, metal_age=0, plastic_age=0):
        self.name = name
        self.demand_multiplier = demand_multiplier
        self.metal_age = metal_age
        self.plastic_age = plastic_age
        self.modifications = modifications or []
        self.results = None

    def to_dict(self):
        return {
            'name': self.name,
            'demand_multiplier': self.demand_multiplier,
            'modifications': self.modifications,
            'metal_age': self.metal_age,
            'plastic_age': self.plastic_age,
        }

    @classmethod
    def from_dict(cls, data):
        name = data.get('name', 'Unknown')
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"'name' must be a non-empty string, got {type(name).__name__}")
        name = name.strip()
            
        demand_multiplier = data.get('demand_multiplier', 1.0)
        if isinstance(demand_multiplier, bool) or not isinstance(demand_multiplier, (int, float)):
            raise ValueError(f"'demand_multiplier' must be a number, got {type(demand_multiplier).__name__}")
        if demand_multiplier <= 0:
            raise ValueError(f"'demand_multiplier' must be positive, got {demand_multiplier}")
            
        modifications = data.get('modifications', [])
        if not isinstance(modifications, list):
            raise ValueError(f"'modifications' must be a list, got {type(modifications).__name__}")
        cleaned_modifications = []
        for j, mod in enumerate(modifications):
            if not isinstance(mod, dict):
                raise ValueError(f"'modifications[{j}]' must be a dict, got {type(mod).__name__}")
            if 'type' not in mod:
                raise ValueError(f"'modifications[{j}]' is missing required key: 'type'")
            if not isinstance(mod.get('type'), str) or not mod['type'].strip():
                raise ValueError(f"'modifications[{j}']['type'] must be a non-empty string")
            
            # Deeper schema validation for specific modification types
            if mod['type'] == "roughness_override":
                if not isinstance(mod.get('pipe_id'), str) or not mod['pipe_id'].strip():
                    raise ValueError(f"'modifications[{j}]' missing 'pipe_id'")
                if "value" not in mod:
                    raise ValueError(f"'modifications[{j}]' missing 'value' for roughness_override")
                if isinstance(mod.get('value'), bool) or not isinstance(mod.get('value'), (int, float)):
                    raise ValueError(f"'modifications[{j}]['value'] must be a number")
            elif mod['type'] == "status_toggle":
                if not isinstance(mod.get('pipe_id'), str) or not mod['pipe_id'].strip():
                    raise ValueError(f"'modifications[{j}]' missing 'pipe_id'")
                if "status" not in mod:
                    raise ValueError(f"'modifications[{j}]' missing 'status' for status_toggle")

                status_val = mod.get('status')
                if not isinstance(status_val, str) or status_val.lower() not in ["open", "closed"]:
                    raise ValueError(f"'modifications[{j}]['status'] must be 'open' or 'closed' (string)")
            else:
                # Skip unknown types for forward compatibility
                continue

            # Sanitize without mutating original
            sanitized_mod = dict(mod)
            sanitized_mod['type'] = mod['type'].strip()
            if 'pipe_id' in sanitized_mod and isinstance(sanitized_mod['pipe_id'], str):
                sanitized_mod['pipe_id'] = sanitized_mod['pipe_id'].strip()
            if 'status' in sanitized_mod and isinstance(sanitized_mod['status'], str):
                sanitized_mod['status'] = sanitized_mod['status'].lower()
            cleaned_modifications.append(sanitized_mod)
                
        metal_age = data.get('metal_age', 0)
        if isinstance(metal_age, bool) or not isinstance(metal_age, (int, float)):
            raise ValueError(f"'metal_age' must be a number, got {type(metal_age).__name__}")
        if metal_age < 0:
            raise ValueError(f"'metal_age' must be non-negative, got {metal_age}")
            
        plastic_age = data.get('plastic_age', 0)
        if isinstance(plastic_age, bool) or not isinstance(plastic_age, (int, float)):
            raise ValueError(f"'plastic_age' must be a number, got {type(plastic_age).__name__}")
        if plastic_age < 0:
            raise ValueError(f"'plastic_age' must be non-negative, got {plastic_age}")
            
        return cls(
            name=name,
            demand_multiplier=demand_multiplier,
            modifications=cleaned_modifications,
            metal_age=metal_age,
            plastic_age=plastic_age
        )


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

        from PyQt6.QtWidgets import QSpinBox
        self.metal_spin = QSpinBox()
        self.metal_spin.setRange(0, 100)
        self.metal_spin.setValue(scenario.metal_age if scenario else 0)
        self.metal_spin.setSuffix(" yrs")
        layout.addRow("Metal Age:", self.metal_spin)

        self.plastic_spin = QSpinBox()
        self.plastic_spin.setRange(0, 100)
        self.plastic_spin.setValue(scenario.plastic_age if scenario else 0)
        self.plastic_spin.setSuffix(" yrs")
        layout.addRow("Plastic Age:", self.plastic_spin)

        # Modifications Table
        self.mod_table = QTableWidget(0, 3)
        self.mod_table.setHorizontalHeaderLabels(["Pipe ID", "Type", "Value/Status"])
        self.mod_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mod_table.setMinimumHeight(150)
        layout.addRow("Pipe Modifications:", self.mod_table)

        mod_btn_layout = QHBoxLayout()
        self.add_mod_btn = QPushButton("Add Mod")
        self.add_mod_btn.clicked.connect(lambda: self._add_mod_row())
        mod_btn_layout.addWidget(self.add_mod_btn)

        self.del_mod_btn = QPushButton("Remove Mod")
        self.del_mod_btn.clicked.connect(self._remove_mod_row)
        mod_btn_layout.addWidget(self.del_mod_btn)
        layout.addRow("", mod_btn_layout)

        if scenario and scenario.modifications:
            for mod in scenario.modifications:
                self._add_mod_row(mod)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._validated_scenario = None

    def accept(self):
        # Validate scenario before closing
        sc = self.get_scenario()
        if sc is not None:
            self._validated_scenario = sc
            super().accept()

    def _add_mod_row(self, mod=None):
        row = self.mod_table.rowCount()
        self.mod_table.insertRow(row)
        
        pid = mod.get('pipe_id', '') if mod else ''
        m_type = mod.get('type', 'roughness_override') if mod else 'roughness_override'
        val = ""
        if mod:
            if m_type == 'roughness_override':
                val = str(mod.get('value', ''))
            else:
                val = str(mod.get('status', 'Open'))
                
        self.mod_table.setItem(row, 0, QTableWidgetItem(pid))
        
        type_combo = QComboBox()
        type_combo.addItems(["roughness_override", "status_toggle"])
        type_combo.setCurrentText(m_type)
        type_combo.currentTextChanged.connect(self._on_mod_type_changed)
        self.mod_table.setCellWidget(row, 1, type_combo)
        
        if m_type == "status_toggle":
            val_combo = QComboBox()
            val_combo.addItems(["Open", "Closed"])
            if val:
                val_combo.setCurrentText(val.capitalize())
            self.mod_table.setCellWidget(row, 2, val_combo)
        else:
            self.mod_table.setItem(row, 2, QTableWidgetItem(val))

    def _on_mod_type_changed(self, text):
        sender = self.sender()
        if not sender:
            return
        # Find which row this sender belongs to
        for row in range(self.mod_table.rowCount()):
            if self.mod_table.cellWidget(row, 1) is sender:
                if text == "status_toggle":
                    val_combo = QComboBox()
                    val_combo.addItems(["Open", "Closed"])
                    self.mod_table.setCellWidget(row, 2, val_combo)
                else:
                    self.mod_table.removeCellWidget(row, 2)
                    self.mod_table.setItem(row, 2, QTableWidgetItem(""))
                break

    def _remove_mod_row(self):
        row = self.mod_table.currentRow()
        if row >= 0:
            self.mod_table.removeRow(row)

    def get_scenario(self):
        mods = []
        errors = []
        
        name = self.name_input.text().strip()
        if not name:
            errors.append("Scenario name cannot be empty.")

        for row in range(self.mod_table.rowCount()):
            pid_item = self.mod_table.item(row, 0)
            if not pid_item:
                continue
                
            pid = pid_item.text().strip()
            if not pid:
                continue

            m_type = self.mod_table.cellWidget(row, 1).currentText()
            
            if m_type == "roughness_override":
                val_item = self.mod_table.item(row, 2)
                val_text = val_item.text().strip() if val_item else ""
                try:
                    val = float(val_text)
                    if val > 0:
                        mods.append({'type': m_type, 'pipe_id': pid, 'value': val})
                    else:
                        errors.append(f"Row {row+1}: Roughness must be > 0")
                except ValueError:
                    errors.append(f"Row {row+1}: Roughness must be a number")
            elif m_type == "status_toggle":
                val_widget = self.mod_table.cellWidget(row, 2)
                if isinstance(val_widget, QComboBox):
                    status = val_widget.currentText().lower()
                    mods.append({'type': m_type, 'pipe_id': pid, 'status': status})

        if errors:
            QMessageBox.warning(self, "Validation Errors", "\n".join(errors))
            return None

        return ScenarioData(
            name=name,
            demand_multiplier=self.demand_spin.value(),
            metal_age=self.metal_spin.value(),
            plastic_age=self.plastic_spin.value(),
            modifications=mods
        )


class ScenarioComparisonTable(QWidget):
    """Table comparing results across scenarios."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Scenario", "Demand", "Metal Age", "Plast Age",
            "Min P (m)", "Max P (m)", "Max V (m/s)", "Issues"
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

            items = [sc.name, f"{sc.demand_multiplier:.1f}x", f"{sc.metal_age}", f"{sc.plastic_age}"]

            if sc.results:
                pressures = sc.results.get('pressures', {})
                flows = sc.results.get('flows', {})
                compliance = sc.results.get('compliance', [])

                # Use actual min/max across all timesteps, not averages
                all_p_min = [p.get('min_m', 0) for p in pressures.values()]
                all_p_max = [p.get('max_m', 0) for p in pressures.values()]
                # Use slurry velocity if available
                slurry_data = sc.results.get('slurry', {})
                all_v = []
                for pid, f in flows.items():
                    sd = slurry_data.get(pid)
                    v = sd.get('velocity_ms', f.get('max_velocity_ms', 0)) if sd else f.get('max_velocity_ms', 0)
                    all_v.append(v)

                min_p = min(all_p_min) if all_p_min else 0
                max_p = max(all_p_max) if all_p_max else 0
                max_v = max(all_v) if all_v else 0
                issues = sum(1 for c in compliance
                             if c.get('type') in ('WARNING', 'CRITICAL'))

                items.extend([
                    f"{min_p:.1f} m", f"{max_p:.1f} m",
                    f"{max_v:.2f} m/s", str(issues),
                ])
            else:
                items.extend(["--", "--", "--", "--"])

            for col, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                # Color WSAA issues column
                if col == 7 and val != "--" and int(val) > 0:
                    item.setForeground(QColor(243, 139, 168))
                elif col == 7 and val == "0":
                    item.setForeground(QColor(166, 227, 161))
                self.table.setItem(row, col, item)


class ScenarioPanel(QWidget):
    """Panel for managing scenarios."""

    scenario_selected = pyqtSignal(str)  # scenario name
    scenarios_changed = pyqtSignal()     # emitted when list changes (add/del/load)
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

        self.export_btn = QPushButton("Export")
        self.export_btn.setFont(QFont("Consolas", 9))
        self.export_btn.setStyleSheet("color: #89b4fa; font-weight: bold;")
        self.export_btn.clicked.connect(self._on_export_report)
        btn_layout.addWidget(self.export_btn)

        layout.addLayout(btn_layout)

        # Scenario tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Scenarios"])
        self.tree.setFont(QFont("Consolas", 10))
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)

        # File IO buttons
        io_layout = QHBoxLayout()
        self.load_btn = QPushButton("Load from JSON")
        self.load_btn.setFont(QFont("Consolas", 9))
        self.load_btn.clicked.connect(self._on_load)
        io_layout.addWidget(self.load_btn)

        self.save_btn = QPushButton("Save to JSON")
        self.save_btn.setFont(QFont("Consolas", 9))
        self.save_btn.clicked.connect(self._on_save)
        io_layout.addWidget(self.save_btn)
        layout.addLayout(io_layout)

        # Comparison table
        self.comparison = ScenarioComparisonTable()
        layout.addWidget(self.comparison)

        self._refresh_tree()

    def _refresh_tree(self):
        self.tree.clear()
        for sc in self.scenarios:
            status = "done" if sc.results else "pending"
            item = QTreeWidgetItem(self.tree,
                                   [f"{sc.name} ({sc.demand_multiplier:.1f}x, {sc.metal_age}y/{sc.plastic_age}y) [{status}]"])
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
            sc = dialog._validated_scenario
            if sc is None:
                return
            if any(s.name.lower() == sc.name.lower() for s in self.scenarios):
                QMessageBox.warning(self, "Duplicate", f"Scenario '{sc.name}' already exists.")
                return
            self.scenarios.append(sc)
            self._refresh_tree()
            self.update_comparison()
            self.scenarios_changed.emit()

    def _on_edit(self):
        sc = self._get_selected_scenario()
        if sc is None:
            return
        dialog = ScenarioDialog(self, sc)
        if dialog.exec():
            new = dialog._validated_scenario
            if new is None:
                return
            # Check for duplicate names (exclude the scenario being edited)
            if new.name.lower() != sc.name.lower() and any(s.name.lower() == new.name.lower() for s in self.scenarios):
                QMessageBox.warning(self, "Duplicate", f"Scenario '{new.name}' already exists.")
                return
            old_name = sc.name
            sc.name = new.name
            sc.demand_multiplier = new.demand_multiplier
            sc.metal_age = new.metal_age
            sc.plastic_age = new.plastic_age
            sc.modifications = new.modifications
            sc.results = None
            
            # If this scenario was the one being viewed, refresh the canvas/results
            current_item = self.tree.currentItem()
            was_selected = current_item and current_item.data(0, Qt.ItemDataRole.UserRole) == old_name
            
            self._refresh_tree()
            self.update_comparison()
            self.scenarios_changed.emit()
            
            if was_selected:
                self.scenario_selected.emit(sc.name)

    def _on_duplicate(self):
        sc = self._get_selected_scenario()
        if sc is None:
            return
        base_name = sc.name + " Copy"
        name = base_name
        counter = 2
        existing = {s.name.lower() for s in self.scenarios}
        while name.lower() in existing:
            name = f"{base_name} {counter}"
            counter += 1
        new_sc = ScenarioData(
            name=name,
            demand_multiplier=sc.demand_multiplier,
            modifications=copy.deepcopy(sc.modifications),
            metal_age=sc.metal_age,
            plastic_age=sc.plastic_age,
        )
        self.scenarios.append(new_sc)
        self._refresh_tree()
        self.update_comparison()
        self.scenarios_changed.emit()

    def _on_delete(self):
        sc = self._get_selected_scenario()
        if sc is None:
            return
        if sc.name == "Base":
            QMessageBox.warning(self, "Cannot Delete", "Cannot delete the Base scenario.")
            return
        self.scenarios.remove(sc)
        self._refresh_tree()
        self.update_comparison()
        self.scenarios_changed.emit()

    def _on_item_clicked(self, item, column):
        name = item.data(0, Qt.ItemDataRole.UserRole)
        self.scenario_selected.emit(name)

    def _on_run_all(self):
        self.run_all.emit()

    def update_comparison(self):
        self.comparison.update_scenarios(self.scenarios)
        self._refresh_tree()

    def _on_save(self):
        if not self.scenarios:
            QMessageBox.warning(self, "Nothing to Save", "There are no scenarios to save.")
            return
            
        path, _ = QFileDialog.getSaveFileName(self, "Save Scenarios", "", "JSON Files (*.json)")
        if not path:
            return
            
        if not path.lower().endswith('.json'):
            path += '.json'
            
        data = [sc.to_dict() for sc in self.scenarios]
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            QMessageBox.information(self, "Saved", f"Saved {len(data)} scenarios to {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save scenarios: {e}")

    def _on_load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Scenarios", "", "JSON Files (*.json)")
        if not path:
            return
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, list):
                raise ValueError(f"Expected a list of scenarios, got {type(data).__name__}")

            new_scenarios = []
            for i, d in enumerate(data):
                if not isinstance(d, dict):
                    raise ValueError(f"Item {i} is not a dict: {type(d).__name__}")
                new_scenarios.append(ScenarioData.from_dict(d))

            if not new_scenarios:
                QMessageBox.warning(self, "Empty File", "The selected file contains no scenarios.")
                return

            names = [s.name for s in new_scenarios]
            if len(names) != len(set(n.lower() for n in names)):
                grouped = defaultdict(list)
                for n in names:
                    grouped[n.lower()].append(n)
                dupes = [n for group in grouped.values() if len(group) > 1 for n in group]
                raise ValueError(f"Duplicate scenario names (case-insensitive): {', '.join(sorted(set(dupes)))}")
                
            if self.scenarios:
                reply = QMessageBox.question(
                    self, "Replace Scenarios",
                    f"This will replace your {len(self.scenarios)} current scenario(s). Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            self.scenarios = new_scenarios
            self.update_comparison()
            self.scenarios_changed.emit()
            if self.tree.topLevelItemCount() > 0:
                first_item = self.tree.topLevelItem(0)
                self.tree.setCurrentItem(first_item)
                name = first_item.data(0, Qt.ItemDataRole.UserRole)
                if name:
                    self.scenario_selected.emit(name)
            
            QMessageBox.information(self, "Loaded", f"Loaded {len(self.scenarios)} scenarios from {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load scenarios: {e}")

    def _on_export_report(self):
        """Generate and save a comparative analysis report."""
        if not self.scenarios:
            QMessageBox.warning(self, "No Data", "No scenarios to export.")
            return
            
        # Check if at least one scenario has results
        if not any(sc.results for sc in self.scenarios):
            QMessageBox.warning(self, "No Results", "Please run analysis first (Run All) before exporting.")
            return
            
        path, file_filter = QFileDialog.getSaveFileName(
            self, "Export Comparison Report", "", 
            "PDF Report (*.pdf);;Excel Spreadsheet (*.xlsx);;CSV Data (*.csv)"
        )
        if not path:
            return
            
        from epanet_api.reporting import ReportingEngine
        engine = ReportingEngine(self.scenarios)
        
        try:
            ext = os.path.splitext(path)[1].lower()
            if not ext:
                if "pdf" in file_filter.lower():
                    ext = ".pdf"
                elif "xlsx" in file_filter.lower():
                    ext = ".xlsx"
                else:
                    ext = ".csv"
                path += ext

            if ext == ".pdf":
                engine.export_pdf(path)
            elif ext == ".xlsx":
                engine.export_excel(path)
            else:
                engine.export_csv(path)
                
            QMessageBox.information(self, "Export Successful", f"Report saved to:\n{os.path.basename(path)}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Export Error", f"Failed to generate report: {e}")

"""
Pressure Zone Management Dialog
================================
Allows engineers to define pressure zones, assign nodes, view zone balance
statistics, and identify PRV requirements per WSAA WSA 03-2011.
"""

import logging

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QMessageBox, QComboBox, QColorDialog, QAbstractItemView, QHeaderView,
    QSplitter,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

# Zone palette — distinct colours for up to 8 zones
ZONE_PALETTE = [
    '#89b4fa', '#a6e3a1', '#f9e2af', '#f38ba8',
    '#cba6f7', '#94e2d5', '#fab387', '#74c7ec',
]


class PressureZoneDialog(QDialog):
    """Dialog for managing pressure zones and viewing zone balance report."""

    def __init__(self, api, canvas=None, parent=None):
        super().__init__(parent)
        self.api = api
        self.canvas = canvas
        self.setWindowTitle("Pressure Zone Management")
        self.setMinimumSize(900, 600)
        self._setup_ui()
        self._refresh_zones()
        self._refresh_available_nodes()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left: Zone Definition ---
        left = QGroupBox("Zone Definition")
        left_layout = QVBoxLayout(left)

        # Zone name + colour
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Zone Name:"))
        self.zone_name_edit = QLineEdit()
        self.zone_name_edit.setPlaceholderText("e.g., Zone A — High Level")
        self.zone_name_edit.setFont(QFont("Consolas", 10))
        name_row.addWidget(self.zone_name_edit)
        self.color_btn = QPushButton("Colour")
        self.color_btn.setFont(QFont("Consolas", 9))
        self._current_color = ZONE_PALETTE[0]
        self.color_btn.setStyleSheet(f"background-color: {self._current_color};")
        self.color_btn.clicked.connect(self._pick_color)
        name_row.addWidget(self.color_btn)
        left_layout.addLayout(name_row)

        # Available nodes
        left_layout.addWidget(QLabel("Available Junctions:"))
        self.available_list = QListWidget()
        self.available_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.available_list.setFont(QFont("Consolas", 9))
        left_layout.addWidget(self.available_list)

        # Buttons
        btn_row = QHBoxLayout()
        self.add_zone_btn = QPushButton("Create Zone with Selected")
        self.add_zone_btn.setFont(QFont("Consolas", 10))
        self.add_zone_btn.clicked.connect(self._on_create_zone)
        btn_row.addWidget(self.add_zone_btn)

        self.auto_zone_btn = QPushButton("Auto-Detect Zones by Elevation")
        self.auto_zone_btn.setFont(QFont("Consolas", 10))
        self.auto_zone_btn.clicked.connect(self._on_auto_detect)
        btn_row.addWidget(self.auto_zone_btn)
        left_layout.addLayout(btn_row)

        # Existing zones list
        left_layout.addWidget(QLabel("Defined Zones:"))
        self.zones_list = QListWidget()
        self.zones_list.setFont(QFont("Consolas", 9))
        self.zones_list.currentRowChanged.connect(self._on_zone_selected)
        left_layout.addWidget(self.zones_list)

        # Delete zone button
        del_row = QHBoxLayout()
        self.del_zone_btn = QPushButton("Delete Zone")
        self.del_zone_btn.setFont(QFont("Consolas", 10))
        self.del_zone_btn.clicked.connect(self._on_delete_zone)
        del_row.addWidget(self.del_zone_btn)
        del_row.addStretch()
        left_layout.addLayout(del_row)

        splitter.addWidget(left)

        # --- Right: Zone Balance Report ---
        right = QGroupBox("Zone Balance Report")
        right_layout = QVBoxLayout(right)

        self.report_table = QTableWidget(0, 8)
        self.report_table.setHorizontalHeaderLabels([
            "Zone", "Nodes", "Demand (LPS)", "Min P (m)",
            "Max P (m)", "Avg P (m)", "WSAA", "PRV"
        ])
        self.report_table.horizontalHeader().setStretchLastSection(True)
        self.report_table.setFont(QFont("Consolas", 9))
        self.report_table.verticalHeader().setVisible(False)
        self.report_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        right_layout.addWidget(self.report_table)

        self.analyze_btn = QPushButton("Run Zone Analysis")
        self.analyze_btn.setFont(QFont("Consolas", 10))
        self.analyze_btn.clicked.connect(self._on_analyze)
        right_layout.addWidget(self.analyze_btn)

        # Apply zone colours to canvas
        self.apply_btn = QPushButton("Apply Zone Colours to Canvas")
        self.apply_btn.setFont(QFont("Consolas", 10))
        self.apply_btn.clicked.connect(self._on_apply_to_canvas)
        right_layout.addWidget(self.apply_btn)

        splitter.addWidget(right)
        splitter.setSizes([450, 450])

        layout.addWidget(splitter)

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self._current_color), self, "Zone Colour")
        if color.isValid():
            self._current_color = color.name()
            self.color_btn.setStyleSheet(f"background-color: {self._current_color};")

    def _refresh_available_nodes(self):
        """Show junctions not yet assigned to any zone."""
        self.available_list.clear()
        if self.api.wn is None:
            return

        zones = self.api.get_pressure_zones()
        assigned = set()
        for z in zones.values():
            assigned.update(z['nodes'])

        for jid in self.api.get_node_list('junction'):
            if jid not in assigned:
                self.available_list.addItem(jid)

    def _refresh_zones(self):
        """Refresh the defined zones list."""
        self.zones_list.clear()
        zones = self.api.get_pressure_zones()
        for name, z in zones.items():
            item = QListWidgetItem(f"{name} ({len(z['nodes'])} nodes)")
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setForeground(QColor(z['color']))
            self.zones_list.addItem(item)

    def _on_create_zone(self):
        name = self.zone_name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Enter a zone name.")
            return

        selected = self.available_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Nodes",
                                "Select junctions from the available list.")
            return

        node_ids = [item.text() for item in selected]
        self.api.assign_pressure_zone(name, node_ids, self._current_color)

        # Auto-advance colour
        zones = self.api.get_pressure_zones()
        idx = len(zones) % len(ZONE_PALETTE)
        self._current_color = ZONE_PALETTE[idx]
        self.color_btn.setStyleSheet(f"background-color: {self._current_color};")

        self.zone_name_edit.clear()
        self._refresh_zones()
        self._refresh_available_nodes()

    def _on_delete_zone(self):
        item = self.zones_list.currentItem()
        if item is None:
            return
        zone_name = item.data(Qt.ItemDataRole.UserRole)
        self.api.remove_pressure_zone(zone_name)
        self._refresh_zones()
        self._refresh_available_nodes()

    def _on_zone_selected(self, row):
        """Highlight zone nodes on canvas when a zone is selected."""
        if row < 0 or self.canvas is None:
            return
        item = self.zones_list.item(row)
        if item is None:
            return
        zone_name = item.data(Qt.ItemDataRole.UserRole)
        zones = self.api.get_pressure_zones()
        zone = zones.get(zone_name)
        if zone:
            # Use canvas variable data to highlight zone nodes
            zone_data = {nid: 1.0 for nid in zone['nodes']}
            self.canvas.set_variable_overlay("Zone: " + zone_name, zone_data)

    def _on_auto_detect(self):
        """Auto-detect pressure zones by elevation bands."""
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network", "Load a network first.")
            return

        # Collect elevations
        elevations = {}
        for jid in self.api.get_node_list('junction'):
            node = self.api.get_node(jid)
            elevations[jid] = node.elevation

        if not elevations:
            return

        # Split into 3 bands: low, mid, high
        elev_vals = sorted(elevations.values())
        n = len(elev_vals)
        low_thresh = elev_vals[n // 3]
        high_thresh = elev_vals[2 * n // 3]

        low_nodes = [n for n, e in elevations.items() if e <= low_thresh]
        mid_nodes = [n for n, e in elevations.items() if low_thresh < e <= high_thresh]
        high_nodes = [n for n, e in elevations.items() if e > high_thresh]

        # Clear existing zones
        for zname in list(self.api.get_pressure_zones().keys()):
            self.api.remove_pressure_zone(zname)

        if low_nodes:
            self.api.assign_pressure_zone(
                f"Low Zone (≤{low_thresh:.0f} m)", low_nodes, ZONE_PALETTE[0])
        if mid_nodes:
            self.api.assign_pressure_zone(
                f"Mid Zone ({low_thresh:.0f}-{high_thresh:.0f} m)", mid_nodes, ZONE_PALETTE[1])
        if high_nodes:
            self.api.assign_pressure_zone(
                f"High Zone (>{high_thresh:.0f} m)", high_nodes, ZONE_PALETTE[2])

        self._refresh_zones()
        self._refresh_available_nodes()

    def _on_analyze(self):
        """Run zone balance analysis and populate report table."""
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network", "Load a network first.")
            return

        zones = self.api.get_pressure_zones()
        if not zones:
            QMessageBox.warning(self, "No Zones",
                                "Define at least one pressure zone first.")
            return

        try:
            report = self.api.analyze_pressure_zones()
        except (OSError, ValueError, RuntimeError) as e:
            QMessageBox.critical(self, "Analysis Error", str(e))
            return

        self.report_table.setRowCount(0)
        for zone_name, data in report.items():
            if zone_name == '_unassigned':
                continue
            row = self.report_table.rowCount()
            self.report_table.insertRow(row)

            items = [
                zone_name,
                str(data['node_count']),
                f"{data['total_demand_lps']:.1f} LPS",
                f"{data['min_pressure_m']:.1f} m",
                f"{data['max_pressure_m']:.1f} m",
                f"{data['avg_pressure_m']:.1f} m",
                "PASS" if data['wsaa_compliant'] else "FAIL",
                "Yes" if data['prv_recommended'] else "No",
            ]
            for col, val in enumerate(items):
                ti = QTableWidgetItem(val)
                if col == 0:
                    ti.setForeground(QColor(data.get('color', '#cdd6f4')))
                elif col == 6:
                    if val == "PASS":
                        ti.setForeground(QColor(166, 227, 161))
                    else:
                        ti.setForeground(QColor(243, 139, 168))
                elif col == 7 and val == "Yes":
                    ti.setForeground(QColor(243, 139, 168))
                self.report_table.setItem(row, col, ti)

        # Show unassigned count
        unassigned = report.get('_unassigned', {})
        if unassigned:
            row = self.report_table.rowCount()
            self.report_table.insertRow(row)
            ti = QTableWidgetItem(f"Unassigned ({unassigned['node_count']} nodes)")
            ti.setForeground(QColor(108, 112, 134))
            self.report_table.setItem(row, 0, ti)
            self.report_table.setItem(row, 1,
                                       QTableWidgetItem(str(unassigned['node_count'])))

    def _on_apply_to_canvas(self):
        """Push zone colours to the canvas as a custom variable overlay."""
        if self.canvas is None:
            return

        zones = self.api.get_pressure_zones()
        if not zones:
            return

        # Build zone_data: {node_id: zone_index} for colour lookup
        zone_colors = {}  # {node_id: color_hex}
        for zone_name, z in zones.items():
            for nid in z['nodes']:
                zone_colors[nid] = z['color']

        self.canvas.set_zone_overlay(zone_colors)

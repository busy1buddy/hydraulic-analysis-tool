"""
Main Window — PyQt6 Desktop Application
=========================================
QMainWindow with menu bar, dock panels, status bar, and central widget.
All network data accessed through HydraulicAPI only.
"""

import os
import json

from PyQt6.QtWidgets import (
    QMainWindow, QMenuBar, QMenu, QStatusBar, QDockWidget,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QLabel, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog,
    QMessageBox, QHeaderView, QSplitter,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QFont

from epanet_api import HydraulicAPI


class MainWindow(QMainWindow):
    """Main application window for Hydraulic Analysis Tool."""

    def __init__(self):
        super().__init__()
        self.api = HydraulicAPI()
        self._current_file = None
        self._hap_file = None

        self.setWindowTitle("Hydraulic Analysis Tool")
        self.setMinimumSize(QSize(1200, 800))
        self.resize(1400, 900)

        self._setup_menus()
        self._setup_central_widget()
        self._setup_dock_panels()
        self._setup_status_bar()

    # =====================================================================
    # MENUS
    # =====================================================================

    def _setup_menus(self):
        menubar = self.menuBar()

        # --- File ---
        file_menu = menubar.addMenu("&File")

        new_act = QAction("&New", self)
        new_act.setShortcut("Ctrl+N")
        new_act.triggered.connect(self._on_new)
        file_menu.addAction(new_act)

        open_act = QAction("&Open (.inp)...", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._on_open_inp)
        file_menu.addAction(open_act)

        file_menu.addSeparator()

        save_act = QAction("&Save", self)
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self._on_save)
        file_menu.addAction(save_act)

        saveas_act = QAction("Save &As (.hap)...", self)
        saveas_act.setShortcut("Ctrl+Shift+S")
        saveas_act.triggered.connect(self._on_save_as)
        file_menu.addAction(saveas_act)

        file_menu.addSeparator()

        exit_act = QAction("E&xit", self)
        exit_act.setShortcut("Ctrl+Q")
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        # --- Analysis ---
        analysis_menu = menubar.addMenu("&Analysis")

        steady_act = QAction("Run &Steady State", self)
        steady_act.setShortcut("F5")
        steady_act.triggered.connect(self._on_run_steady)
        analysis_menu.addAction(steady_act)

        transient_act = QAction("Run &Transient", self)
        transient_act.setShortcut("F6")
        transient_act.triggered.connect(self._on_run_transient)
        analysis_menu.addAction(transient_act)

        analysis_menu.addSeparator()

        self.slurry_act = QAction("Slurry &Mode", self)
        self.slurry_act.setCheckable(True)
        self.slurry_act.toggled.connect(self._on_slurry_toggle)
        analysis_menu.addAction(self.slurry_act)

        # --- Tools ---
        tools_menu = menubar.addMenu("&Tools")

        quality_act = QAction("&Quality Review", self)
        quality_act.triggered.connect(self._on_quality_review)
        tools_menu.addAction(quality_act)

        settings_act = QAction("&Settings", self)
        settings_act.triggered.connect(self._on_settings)
        tools_menu.addAction(settings_act)

        # --- Reports ---
        reports_menu = menubar.addMenu("&Reports")

        docx_act = QAction("Generate Report (&DOCX)", self)
        docx_act.triggered.connect(self._on_report_docx)
        reports_menu.addAction(docx_act)

        pdf_act = QAction("Generate Report (&PDF)", self)
        pdf_act.triggered.connect(self._on_report_pdf)
        reports_menu.addAction(pdf_act)

        # --- View ---
        view_menu = menubar.addMenu("&View")

        reset_act = QAction("&Reset Layout", self)
        reset_act.triggered.connect(self._on_reset_layout)
        view_menu.addAction(reset_act)

        view_menu.addSeparator()

        self.toggle_explorer_act = QAction("Project &Explorer", self)
        self.toggle_explorer_act.setCheckable(True)
        self.toggle_explorer_act.setChecked(True)
        view_menu.addAction(self.toggle_explorer_act)

        self.toggle_properties_act = QAction("&Properties", self)
        self.toggle_properties_act.setCheckable(True)
        self.toggle_properties_act.setChecked(True)
        view_menu.addAction(self.toggle_properties_act)

        self.toggle_results_act = QAction("&Results", self)
        self.toggle_results_act.setCheckable(True)
        self.toggle_results_act.setChecked(True)
        view_menu.addAction(self.toggle_results_act)

        # --- Help ---
        help_menu = menubar.addMenu("&Help")

        about_act = QAction("&About", self)
        about_act.triggered.connect(self._on_about)
        help_menu.addAction(about_act)

    # =====================================================================
    # CENTRAL WIDGET
    # =====================================================================

    def _setup_central_widget(self):
        """Placeholder for the network canvas (replaced in Phase 2)."""
        self.central_label = QLabel("Network View")
        self.central_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.central_label.setFont(QFont("Arial", 24))
        self.central_label.setStyleSheet(
            "background-color: #1e1e2e; color: #6c7086; border: 1px solid #313244;"
        )
        self.setCentralWidget(self.central_label)

    # =====================================================================
    # DOCK PANELS
    # =====================================================================

    def _setup_dock_panels(self):
        # --- Left: Project Explorer ---
        self.explorer_dock = QDockWidget("Project Explorer", self)
        self.explorer_dock.setMinimumWidth(220)
        self.explorer_tree = QTreeWidget()
        self.explorer_tree.setHeaderLabels(["Element"])
        self.explorer_tree.setFont(QFont("Consolas", 10))
        self.explorer_dock.setWidget(self.explorer_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.explorer_dock)
        self.toggle_explorer_act.toggled.connect(self.explorer_dock.setVisible)
        self.explorer_dock.visibilityChanged.connect(self.toggle_explorer_act.setChecked)

        # --- Right: Properties ---
        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setMinimumWidth(250)
        self.properties_table = QTableWidget(0, 2)
        self.properties_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.properties_table.horizontalHeader().setStretchLastSection(True)
        self.properties_table.setFont(QFont("Consolas", 10))
        self.properties_dock.setWidget(self.properties_table)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
        self.toggle_properties_act.toggled.connect(self.properties_dock.setVisible)
        self.properties_dock.visibilityChanged.connect(self.toggle_properties_act.setChecked)

        # --- Bottom: Results ---
        self.results_dock = QDockWidget("Results", self)
        self.results_dock.setMinimumHeight(180)
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(4, 4, 4, 4)

        self.node_results_table = QTableWidget(0, 5)
        self.node_results_table.setHorizontalHeaderLabels(
            ["ID", "Elevation (m)", "Pressure (m)", "Head (m)", "WSAA Status"]
        )
        self.node_results_table.horizontalHeader().setStretchLastSection(True)
        self.node_results_table.setFont(QFont("Consolas", 9))

        self.pipe_results_table = QTableWidget(0, 5)
        self.pipe_results_table.setHorizontalHeaderLabels(
            ["ID", "Diameter (DN)", "Length (m)", "Velocity (m/s)", "Headloss (m/km)"]
        )
        self.pipe_results_table.horizontalHeader().setStretchLastSection(True)
        self.pipe_results_table.setFont(QFont("Consolas", 9))

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.node_results_table)
        splitter.addWidget(self.pipe_results_table)
        results_layout.addWidget(splitter)

        self.results_dock.setWidget(results_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.results_dock)
        self.toggle_results_act.toggled.connect(self.results_dock.setVisible)
        self.results_dock.visibilityChanged.connect(self.toggle_results_act.setChecked)

        # Wire tree selection
        self.explorer_tree.itemClicked.connect(self._on_tree_item_clicked)

    # =====================================================================
    # STATUS BAR
    # =====================================================================

    def _setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.analysis_label = QLabel("Analysis: None")
        self.nodes_label = QLabel("Nodes: 0")
        self.pipes_label = QLabel("Pipes: 0")
        self.wsaa_label = QLabel("WSAA: --")

        for lbl in (self.analysis_label, self.nodes_label,
                    self.pipes_label, self.wsaa_label):
            lbl.setFont(QFont("Consolas", 9))
            self.status_bar.addPermanentWidget(lbl)

    def _update_status_bar(self):
        summary = self.api.get_network_summary()
        if 'error' in summary:
            return
        n_nodes = summary['junctions'] + summary.get('reservoirs', 0) + summary.get('tanks', 0)
        n_pipes = summary['pipes']
        self.nodes_label.setText(f"Nodes: {n_nodes}")
        self.pipes_label.setText(f"Pipes: {n_pipes}")

        if self.slurry_act.isChecked():
            self.analysis_label.setText("Analysis: Slurry (Bingham Plastic)")
        else:
            self.analysis_label.setText("Analysis: Hydraulic")

    # =====================================================================
    # FILE ACTIONS
    # =====================================================================

    def _on_new(self):
        self.api = HydraulicAPI()
        self._current_file = None
        self._hap_file = None
        self.explorer_tree.clear()
        self.properties_table.setRowCount(0)
        self.node_results_table.setRowCount(0)
        self.pipe_results_table.setRowCount(0)
        self.central_label.setText("Network View")
        self._update_status_bar()
        self.setWindowTitle("Hydraulic Analysis Tool")

    def _on_open_inp(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open EPANET Network", "",
            "EPANET Files (*.inp);;All Files (*)"
        )
        if not path:
            return

        try:
            # Load directly from the full path
            self.api.wn = None
            self.api._inp_file = path
            import wntr as _wntr
            self.api.wn = _wntr.network.WaterNetworkModel(path)
            self._current_file = path
            self._populate_explorer()
            self._update_status_bar()
            self.setWindowTitle(f"Hydraulic Analysis Tool — {os.path.basename(path)}")
            self.central_label.setText(f"Loaded: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error",
                                f"Could not load network file.\n\n{type(e).__name__}: {e}")

    def _on_save(self):
        if self._hap_file:
            self._save_hap(self._hap_file)
        elif self._current_file:
            try:
                self.api.write_inp(self._current_file)
                self.status_bar.showMessage(f"Saved to {self._current_file}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Save Error", str(e))
        else:
            self._on_save_as()

    def _on_save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "",
            "Hydraulic Analysis Project (*.hap);;All Files (*)"
        )
        if path:
            self._hap_file = path
            self._save_hap(path)

    def _save_hap(self, path):
        """Save project state as .hap JSON file."""
        project = {
            'inp_path': self._current_file or '',
            'scenarios': [],
            'last_run': {},
            'settings': {
                'slurry_mode': self.slurry_act.isChecked(),
            },
        }
        try:
            with open(path, 'w') as f:
                json.dump(project, f, indent=2)
            self.status_bar.showMessage(f"Saved to {path}", 3000)
            self.setWindowTitle(f"Hydraulic Analysis Tool — {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    # =====================================================================
    # PROJECT EXPLORER
    # =====================================================================

    def _populate_explorer(self):
        self.explorer_tree.clear()
        summary = self.api.get_network_summary()
        if 'error' in summary:
            return

        model_name = os.path.basename(self._current_file or "Network")
        root = QTreeWidgetItem(self.explorer_tree, [model_name])
        root.setExpanded(True)

        # Junctions
        juncs_item = QTreeWidgetItem(root, [f"Junctions ({summary['junctions']})"])
        for jid in self.api.get_node_list('junction'):
            QTreeWidgetItem(juncs_item, [jid])

        # Reservoirs
        res_count = summary.get('reservoirs', 0)
        if res_count:
            res_item = QTreeWidgetItem(root, [f"Reservoirs ({res_count})"])
            for rid in self.api.get_node_list('reservoir'):
                QTreeWidgetItem(res_item, [rid])

        # Tanks
        tank_count = summary.get('tanks', 0)
        if tank_count:
            tank_item = QTreeWidgetItem(root, [f"Tanks ({tank_count})"])
            for tid in self.api.get_node_list('tank'):
                QTreeWidgetItem(tank_item, [tid])

        # Pipes
        pipes_item = QTreeWidgetItem(root, [f"Pipes ({summary['pipes']})"])
        for pid in self.api.get_link_list('pipe'):
            QTreeWidgetItem(pipes_item, [pid])

        # Pumps
        pump_list = self.api.get_link_list('pump')
        if pump_list:
            pumps_item = QTreeWidgetItem(root, [f"Pumps ({len(pump_list)})"])
            for pid in pump_list:
                QTreeWidgetItem(pumps_item, [pid])

        # Valves
        valve_list = self.api.get_link_list('valve')
        if valve_list:
            valves_item = QTreeWidgetItem(root, [f"Valves ({len(valve_list)})"])
            for vid in valve_list:
                QTreeWidgetItem(valves_item, [vid])

        # Scenarios
        QTreeWidgetItem(root, ["Scenarios (Base)"])

        # Results
        QTreeWidgetItem(root, ["Results (none)"])

    def _on_tree_item_clicked(self, item, column):
        """Show properties for selected element."""
        element_id = item.text(0)
        parent = item.parent()
        if parent is None:
            return

        parent_text = parent.text(0)
        self.properties_table.setRowCount(0)

        try:
            if parent_text.startswith("Junctions"):
                node = self.api.get_node(element_id)
                self._show_node_properties(element_id, node)
            elif parent_text.startswith("Reservoirs"):
                node = self.api.get_node(element_id)
                self._show_reservoir_properties(element_id, node)
            elif parent_text.startswith("Pipes"):
                link = self.api.get_link(element_id)
                self._show_pipe_properties(element_id, link)
            elif parent_text.startswith("Pumps"):
                link = self.api.get_link(element_id)
                self._show_pump_properties(element_id, link)
            elif parent_text.startswith("Valves"):
                link = self.api.get_link(element_id)
                self._show_valve_properties(element_id, link)
        except Exception:
            pass

    def _add_property_row(self, key, value):
        row = self.properties_table.rowCount()
        self.properties_table.insertRow(row)
        self.properties_table.setItem(row, 0, QTableWidgetItem(key))
        self.properties_table.setItem(row, 1, QTableWidgetItem(str(value)))

    def _show_node_properties(self, nid, node):
        self._add_property_row("Type", "Junction")
        self._add_property_row("ID", nid)
        self._add_property_row("Elevation", f"{node.elevation:.1f} m")
        demand = 0
        if node.demand_timeseries_list:
            demand = node.demand_timeseries_list[0].base_value * 1000
        self._add_property_row("Base Demand", f"{demand:.2f} LPS")
        x, y = node.coordinates
        self._add_property_row("X", f"{x:.1f}")
        self._add_property_row("Y", f"{y:.1f}")

    def _show_reservoir_properties(self, rid, node):
        self._add_property_row("Type", "Reservoir")
        self._add_property_row("ID", rid)
        self._add_property_row("Head", f"{node.base_head:.1f} m")

    def _show_pipe_properties(self, pid, pipe):
        self._add_property_row("Type", "Pipe")
        self._add_property_row("ID", pid)
        self._add_property_row("Start Node", pipe.start_node_name)
        self._add_property_row("End Node", pipe.end_node_name)
        self._add_property_row("Length", f"{pipe.length:.1f} m")
        self._add_property_row("Diameter", f"{int(pipe.diameter * 1000)} mm")
        self._add_property_row("Roughness (C)", f"{pipe.roughness:.0f}")

    def _show_pump_properties(self, pid, pump):
        self._add_property_row("Type", "Pump")
        self._add_property_row("ID", pid)
        self._add_property_row("Start Node", pump.start_node_name)
        self._add_property_row("End Node", pump.end_node_name)

    def _show_valve_properties(self, vid, valve):
        self._add_property_row("Type", "Valve")
        self._add_property_row("ID", vid)
        self._add_property_row("Start Node", valve.start_node_name)
        self._add_property_row("End Node", valve.end_node_name)
        self._add_property_row("Valve Type", str(valve.valve_type))

    # =====================================================================
    # ANALYSIS ACTIONS (stubs — wired in Phase 3)
    # =====================================================================

    def _on_run_steady(self):
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network", "Load a network first.")
            return
        self.status_bar.showMessage("Running steady-state analysis...")

    def _on_run_transient(self):
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network", "Load a network first.")
            return
        self.status_bar.showMessage("Running transient analysis...")

    def _on_slurry_toggle(self, checked):
        self._update_status_bar()

    # =====================================================================
    # TOOLS / REPORTS / VIEW (stubs)
    # =====================================================================

    def _on_quality_review(self):
        self.status_bar.showMessage("Quality review not yet implemented.", 3000)

    def _on_settings(self):
        self.status_bar.showMessage("Settings not yet implemented.", 3000)

    def _on_report_docx(self):
        self.status_bar.showMessage("DOCX report generation not yet implemented.", 3000)

    def _on_report_pdf(self):
        self.status_bar.showMessage("PDF report generation not yet implemented.", 3000)

    def _on_reset_layout(self):
        self.explorer_dock.setVisible(True)
        self.properties_dock.setVisible(True)
        self.results_dock.setVisible(True)

    def _on_about(self):
        QMessageBox.about(
            self, "About Hydraulic Analysis Tool",
            "Hydraulic Analysis Tool v1.0\n\n"
            "Professional hydraulic analysis for Australian\n"
            "water supply and mining engineers.\n\n"
            "Standards: WSAA, AS/NZS 1477, AS 2280,\n"
            "AS/NZS 4130, AS 4058\n\n"
            "Powered by WNTR + TSNet"
        )

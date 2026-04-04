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
    QMessageBox, QHeaderView, QSplitter, QProgressBar, QPushButton,
)
from PyQt6.QtCore import Qt, QSize, QByteArray, QEvent
from PyQt6.QtGui import QAction, QFont, QColor

from epanet_api import HydraulicAPI
from desktop.network_canvas import NetworkCanvas
from desktop.analysis_worker import AnalysisWorker
from desktop.scenario_panel import ScenarioPanel, ScenarioData
from desktop.report_dialog import ReportDialog
from desktop.audit_trail import AuditTrail
from desktop.pipe_stress_panel import PipeStressPanel
from desktop.canvas_editor import CanvasEditor


class MainWindow(QMainWindow):
    """Main application window for Hydraulic Analysis Tool."""

    def __init__(self):
        super().__init__()
        self.api = HydraulicAPI()
        self.audit = AuditTrail()
        self._current_file = None
        self._hap_file = None
        self._last_results = None

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

        # --- Edit ---
        edit_menu = menubar.addMenu("&Edit")

        self.undo_act = QAction("&Undo", self)
        self.undo_act.setShortcut("Ctrl+Z")
        self.undo_act.triggered.connect(self._on_undo)
        edit_menu.addAction(self.undo_act)

        self.redo_act = QAction("&Redo", self)
        self.redo_act.setShortcut("Ctrl+Y")
        self.redo_act.triggered.connect(self._on_redo)
        edit_menu.addAction(self.redo_act)

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
        """Network canvas with PyQtGraph 2D view."""
        self.canvas = NetworkCanvas()
        self.canvas.element_selected.connect(self._on_canvas_element_selected)
        self.setCentralWidget(self.canvas)

        # Canvas editor (manages Edit Mode interactions)
        self.editor = CanvasEditor(self.canvas, self)
        self.canvas._editor = self.editor

        # Add Edit Mode button to canvas toolbar
        self.canvas.edit_btn = QPushButton("Edit")
        self.canvas.edit_btn.setCheckable(True)
        self.canvas.edit_btn.setFont(QFont("Consolas", 9))
        self.canvas.edit_btn.toggled.connect(self._on_edit_mode_toggled)
        # Insert into the canvas toolbar layout (after Labels button)
        toolbar_layout = self.canvas.layout().itemAt(0).layout()
        toolbar_layout.insertWidget(4, self.canvas.edit_btn)

    # =====================================================================
    # DOCK PANELS
    # =====================================================================

    def _setup_dock_panels(self):
        # Dock features: movable and floatable, but NOT closable
        _dock_features = (QDockWidget.DockWidgetFeature.DockWidgetMovable |
                          QDockWidget.DockWidgetFeature.DockWidgetFloatable)

        # --- Left: Project Explorer ---
        self.explorer_dock = QDockWidget("Project Explorer", self)
        self.explorer_dock.setObjectName("explorer_dock")
        self.explorer_dock.setFeatures(_dock_features)
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
        self.properties_dock.setObjectName("properties_dock")
        self.properties_dock.setFeatures(_dock_features)
        self.properties_dock.setMinimumWidth(220)
        self.properties_table = QTableWidget(0, 2)
        self.properties_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.properties_table.horizontalHeader().setStretchLastSection(True)
        self.properties_table.setMinimumWidth(220)
        self.properties_table.setFont(QFont("Consolas", 10))
        self.properties_table.verticalHeader().setVisible(False)
        self.properties_dock.setWidget(self.properties_table)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
        self.properties_dock.setVisible(True)
        self.toggle_properties_act.toggled.connect(self.properties_dock.setVisible)
        self.properties_dock.visibilityChanged.connect(self.toggle_properties_act.setChecked)

        # --- Bottom: Results ---
        self.results_dock = QDockWidget("Results", self)
        self.results_dock.setObjectName("results_dock")
        self.results_dock.setFeatures(_dock_features)
        self.results_dock.setMinimumHeight(300)
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(4, 4, 4, 4)

        self.node_results_table = QTableWidget(0, 5)
        self.node_results_table.setHorizontalHeaderLabels(
            ["ID", "Elevation (m)", "Pressure (m)", "Head (m)", "WSAA Status"]
        )
        self.node_results_table.horizontalHeader().setStretchLastSection(True)
        self.node_results_table.setFont(QFont("Consolas", 9))
        self.node_results_table.setMinimumHeight(120)
        self.node_results_table.verticalHeader().setVisible(False)

        self.pipe_results_table = QTableWidget(0, 5)
        self.pipe_results_table.setHorizontalHeaderLabels(
            ["ID", "Diameter (DN)", "Length (m)", "Velocity (m/s)", "Headloss (m/km)"]
        )
        self.pipe_results_table.horizontalHeader().setStretchLastSection(True)
        self.pipe_results_table.setFont(QFont("Consolas", 9))
        self.pipe_results_table.setMinimumHeight(120)
        self.pipe_results_table.verticalHeader().setVisible(False)

        self.pipe_stress_panel = PipeStressPanel()

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.node_results_table)
        splitter.addWidget(self.pipe_results_table)
        splitter.addWidget(self.pipe_stress_panel)
        # Give each panel roughly equal initial space
        splitter.setSizes([200, 200, 200])
        results_layout.addWidget(splitter)

        self.results_dock.setWidget(results_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.results_dock)
        self.toggle_results_act.toggled.connect(self.results_dock.setVisible)
        self.results_dock.visibilityChanged.connect(self.toggle_results_act.setChecked)

        # --- Scenario Panel (tabbed with explorer on left) ---
        self.scenario_dock = QDockWidget("Scenarios", self)
        self.scenario_dock.setObjectName("scenario_dock")
        self.scenario_dock.setFeatures(_dock_features)
        self.scenario_dock.setMinimumWidth(250)
        self.scenario_panel = ScenarioPanel()
        self.scenario_panel.run_all.connect(self._on_run_all_scenarios)
        self.scenario_dock.setWidget(self.scenario_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.scenario_dock)
        # Tab scenario behind explorer so explorer is the visible tab
        self.tabifyDockWidget(self.scenario_dock, self.explorer_dock)

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

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(150)
        self.progress_bar.setMaximumHeight(16)
        self.progress_bar.setVisible(False)
        self.status_bar.addWidget(self.progress_bar)

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
        self.canvas.set_api(None)  # clear canvas
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
            self.api.load_network_from_path(path)
            self._current_file = path
            self._populate_explorer()
            self._update_status_bar()
            self.setWindowTitle(f"Hydraulic Analysis Tool — {os.path.basename(path)}")
            self.canvas.set_api(self.api)
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

    def _on_canvas_element_selected(self, element_id, element_type):
        """Handle element selection from the canvas."""
        self.properties_table.setRowCount(0)
        try:
            if element_type == 'junction':
                node = self.api.get_node(element_id)
                self._show_node_properties(element_id, node)
                # Show analysis results if available
                if self._last_results:
                    pdata = self._last_results.get('pressures', {}).get(element_id)
                    if pdata:
                        self._add_property_row("--- Results ---", "")
                        self._add_property_row("Min Pressure", f"{pdata['min_m']:.1f} m")
                        self._add_property_row("Avg Pressure", f"{pdata['avg_m']:.1f} m")
                        self._add_property_row("Max Pressure", f"{pdata['max_m']:.1f} m")
            elif element_type in ('reservoir', 'tank'):
                node = self.api.get_node(element_id)
                self._show_reservoir_properties(element_id, node)
            elif element_type == 'pipe':
                link = self.api.get_link(element_id)
                self._show_pipe_properties(element_id, link)
                # Show analysis results if available
                if self._last_results:
                    fdata = self._last_results.get('flows', {}).get(element_id)
                    if fdata:
                        self._add_property_row("--- Results ---", "")
                        self._add_property_row("Avg Flow", f"{fdata['avg_lps']:.2f} LPS")
                        self._add_property_row("Max Velocity", f"{fdata['max_velocity_ms']:.2f} m/s")
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
    # ANALYSIS ACTIONS
    # =====================================================================

    def _on_run_steady(self):
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network", "Load a network first.")
            return
        atype = 'slurry' if self.slurry_act.isChecked() else 'steady'
        params = {}
        if atype == 'slurry':
            params['slurry'] = {
                'yield_stress': 10.0,
                'plastic_viscosity': 0.01,
                'density': 1500,
            }
        self._run_analysis(atype, params)

    def _on_run_transient(self):
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network", "Load a network first.")
            return
        self._run_analysis('transient')

    def _run_analysis(self, analysis_type, params=None):
        """Launch analysis in background thread."""
        self._worker = AnalysisWorker(self.api, analysis_type, params)
        self._worker.started_signal.connect(self._on_analysis_started)
        self._worker.progress.connect(self._on_analysis_progress)
        self._worker.finished.connect(self._on_analysis_finished)
        self._worker.error.connect(self._on_analysis_error)
        self._worker.start()

    def _on_analysis_started(self):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Running analysis...")

    def _on_analysis_progress(self, value):
        self.progress_bar.setValue(value)

    def _on_analysis_finished(self, results):
        self.progress_bar.setVisible(False)
        self._last_results = results

        # Update canvas colors
        self.canvas.set_results(results)

        # Populate results tables
        self._populate_node_results(results)
        self._populate_pipe_results(results)

        # Update WSAA status
        compliance = results.get('compliance', [])
        fails = sum(1 for c in compliance if c.get('type') in ('WARNING', 'CRITICAL'))
        if fails == 0:
            self.wsaa_label.setText("WSAA: PASS")
            self.wsaa_label.setStyleSheet("color: #a6e3a1;")
        else:
            self.wsaa_label.setText(f"WSAA: {fails} issue(s)")
            self.wsaa_label.setStyleSheet("color: #f38ba8;")

        analysis_type = "Slurry" if self.slurry_act.isChecked() else "Hydraulic"
        if 'junctions' in results and 'max_surge_m' in results:
            analysis_type = "Transient"
        self.analysis_label.setText(f"Analysis: {analysis_type}")

        # Update pipe stress panel
        self.pipe_stress_panel.update_results(self.api, results)

        # Log to audit trail
        try:
            self.audit.log_run(
                self._current_file or '',
                {'analysis_type': analysis_type.lower()},
                results,
                analysis_type=analysis_type.lower(),
            )
        except Exception:
            pass  # Audit trail failure is non-critical

        self.status_bar.showMessage("Analysis complete.", 5000)

    def _on_analysis_error(self, msg):
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Analysis Error", msg)
        self.status_bar.showMessage("Analysis failed.", 5000)

    def _on_run_all_scenarios(self):
        """Run all scenarios sequentially and update comparison table."""
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network", "Load a network first.")
            return

        self.status_bar.showMessage("Running all scenarios...")
        self.progress_bar.setVisible(True)

        for i, sc in enumerate(self.scenario_panel.scenarios):
            self.progress_bar.setValue(int((i / len(self.scenario_panel.scenarios)) * 100))

            # Reset to original network via API
            self.api.load_network_from_path(self.api._inp_file)

            # Apply demand multiplier
            if sc.demand_multiplier != 1.0:
                for jname in self.api.get_node_list('junction'):
                    junc = self.api.get_node(jname)
                    if junc.demand_timeseries_list:
                        junc.demand_timeseries_list[0].base_value *= sc.demand_multiplier

            try:
                sc.results = self.api.run_steady_state(save_plot=False)
            except Exception as e:
                sc.results = {'error': str(e), 'pressures': {}, 'flows': {}, 'compliance': []}

        # Restore original via API
        self.api.load_network_from_path(self.api._inp_file)

        self.progress_bar.setVisible(False)
        self.scenario_panel.update_comparison()

        # Show base scenario results on canvas
        base = self.scenario_panel.scenarios[0]
        if base.results and 'error' not in base.results:
            self.canvas.set_results(base.results)
            self._populate_node_results(base.results)
            self._populate_pipe_results(base.results)

        self.status_bar.showMessage(
            f"All {len(self.scenario_panel.scenarios)} scenarios complete.", 5000
        )

    def _populate_node_results(self, results):
        """Fill the node results table."""
        pressures = results.get('pressures', {})
        self.node_results_table.setRowCount(0)

        for jid, pdata in pressures.items():
            row = self.node_results_table.rowCount()
            self.node_results_table.insertRow(row)

            try:
                node = self.api.get_node(jid)
                elev = f"{node.elevation:.1f}"
            except Exception:
                elev = "--"

            avg_p = pdata.get('avg_m', 0)
            max_p = pdata.get('max_m', 0)
            head = node.elevation + avg_p if elev != "--" else avg_p

            # WSAA compliance check — WSAA WSA 03-2011 Table 3.1
            if avg_p < 20.0:
                status = "FAIL (<20 m)"
            elif avg_p > 50.0:
                status = "FAIL (>50 m)"
            else:
                status = "PASS"

            items = [jid, elev, f"{avg_p:.1f}", f"{head:.1f}", status]
            for col, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                if "FAIL" in str(val):
                    item.setForeground(QColor(243, 139, 168))  # red
                elif val == "PASS":
                    item.setForeground(QColor(166, 227, 161))  # green
                self.node_results_table.setItem(row, col, item)

    def _populate_pipe_results(self, results):
        """Fill the pipe results table."""
        flows = results.get('flows', {})
        self.pipe_results_table.setRowCount(0)

        for pid, fdata in flows.items():
            row = self.pipe_results_table.rowCount()
            self.pipe_results_table.insertRow(row)

            try:
                pipe = self.api.get_link(pid)
                dn = f"{int(pipe.diameter * 1000)} mm"
                length = f"{pipe.length:.1f}"
            except Exception:
                dn = "--"
                length = "--"

            v = fdata.get('max_velocity_ms', 0)
            # Headloss per km approximation
            avg_lps = abs(fdata.get('avg_lps', 0))
            try:
                pipe = self.api.get_link(pid)
                if pipe.length > 0 and pipe.diameter > 0:
                    # Hazen-Williams headloss per km
                    Q_m3s = avg_lps / 1000
                    hl_per_m = (10.67 * Q_m3s ** 1.852) / (
                        pipe.roughness ** 1.852 * pipe.diameter ** 4.87)
                    hl_per_km = hl_per_m * 1000
                else:
                    hl_per_km = 0
            except Exception:
                hl_per_km = 0

            items = [pid, dn, length, f"{v:.2f}", f"{hl_per_km:.1f}"]
            for col, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                # Flag velocity > 2.0 m/s — WSAA WSA 03-2011
                if col == 3 and v > 2.0:
                    item.setForeground(QColor(243, 139, 168))
                self.pipe_results_table.setItem(row, col, item)

    def _on_slurry_toggle(self, checked):
        self._update_status_bar()

    # =====================================================================
    # EDIT MODE / UNDO / REDO
    # =====================================================================

    def _on_edit_mode_toggled(self, checked):
        self.editor.edit_mode = checked

    def _on_undo(self):
        if hasattr(self, 'editor'):
            self.editor.undo()

    def _on_redo(self):
        if hasattr(self, 'editor'):
            self.editor.redo()

    def keyPressEvent(self, event):
        """Handle Escape to cancel pipe creation in edit mode."""
        if event.key() == Qt.Key.Key_Escape and hasattr(self, 'editor') and self.editor.edit_mode:
            self.editor.cancel_pipe_start()
        else:
            super().keyPressEvent(event)

    # =====================================================================
    # TOOLS / REPORTS / VIEW
    # =====================================================================

    def _on_quality_review(self):
        self.status_bar.showMessage("Quality review triggered.", 3000)

    def _on_settings(self):
        self.status_bar.showMessage("Settings not yet implemented.", 3000)

    def _on_report_docx(self):
        if self._last_results is None:
            QMessageBox.warning(self, "No Results",
                                "Run an analysis first before generating a report.")
            return
        dialog = ReportDialog(self.api, self._last_results, self)
        dialog.exec()

    def _on_report_pdf(self):
        if self._last_results is None:
            QMessageBox.warning(self, "No Results",
                                "Run an analysis first before generating a report.")
            return
        dialog = ReportDialog(self.api, self._last_results, self)
        dialog.exec()

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

    # =====================================================================
    # WINDOW STATE PRESERVATION
    # =====================================================================

    def showEvent(self, event):
        """Save dock layout once the window is first shown, and restore on subsequent shows."""
        super().showEvent(event)
        if not hasattr(self, '_initial_state'):
            # First show — capture the good layout
            self._initial_state = self.saveState()
        else:
            # Subsequent shows (e.g. restore from minimise) — restore layout
            self._restore_layout()

    def changeEvent(self, event):
        """Handle window state changes (minimise/restore/focus)."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            # Save state before any state change
            if not self.isMinimized():
                self._saved_state = self.saveState()
            # If we just restored from minimised, restore the layout
            if hasattr(self, '_was_minimized') and self._was_minimized and not self.isMinimized():
                self._restore_layout()
            self._was_minimized = self.isMinimized()

    def _restore_layout(self):
        """Restore dock layout and re-ensure canvas interactivity."""
        # Restore dock geometry from saved state
        state = getattr(self, '_saved_state', None) or getattr(self, '_initial_state', None)
        if state:
            self.restoreState(state)

        # Force all docks visible
        self.explorer_dock.setVisible(True)
        self.properties_dock.setVisible(True)
        self.results_dock.setVisible(True)
        self.scenario_dock.setVisible(True)

        # Re-ensure canvas scene click handler is connected
        self.canvas.ensure_scene_connected()

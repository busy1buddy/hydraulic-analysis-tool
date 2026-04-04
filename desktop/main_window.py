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
from desktop.colourmap_widget import ColourMapWidget, ColourBar
from desktop.animation_panel import AnimationPanel
from desktop.pattern_editor import PatternEditorDialog
from desktop.eps_dialog import EPSConfigDialog
from desktop.fire_flow_dialog import FireFlowDialog
from desktop.water_quality_dialog import WaterQualityDialog
from desktop.probe_tooltip import ProbeTooltip
from desktop.calibration_dialog import CalibrationDialog
from desktop.statistics_panel import StatisticsPanel
from desktop.preferences import load_preferences, save_preferences
from desktop.pressure_zone_dialog import PressureZoneDialog
from desktop.rehab_dialog import RehabDialog


class MainWindow(QMainWindow):
    """Main application window for Hydraulic Analysis Tool."""

    def __init__(self):
        super().__init__()
        self.api = HydraulicAPI()
        self.audit = AuditTrail()
        self._current_file = None
        self._hap_file = None
        self._last_results = None
        self._probe_tooltip = None  # Created lazily

        self.setWindowTitle("Hydraulic Analysis Tool")
        self.setMinimumSize(QSize(1200, 800))
        self.resize(1400, 900)

        self._setup_menus()
        self._setup_central_widget()
        self._setup_dock_panels()
        self._setup_status_bar()

        # Enable drag-and-drop of .inp files onto the main window
        self.setAcceptDrops(True)

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

        tutorial_act = QAction("Open &Tutorial...", self)
        tutorial_act.triggered.connect(self._on_open_tutorial)
        file_menu.addAction(tutorial_act)

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

        eps_act = QAction("Run &Extended Period (EPS)", self)
        eps_act.setShortcut("F7")
        eps_act.triggered.connect(self._on_run_eps)
        analysis_menu.addAction(eps_act)

        fire_act = QAction("&Fire Flow Wizard...", self)
        fire_act.setShortcut("F8")
        fire_act.triggered.connect(self._on_fire_flow)
        analysis_menu.addAction(fire_act)

        # --- Water Quality submenu ---
        wq_menu = QMenu("&Water Quality", self)
        analysis_menu.addMenu(wq_menu)

        wq_age_act = QAction("Water &Age...", self)
        wq_age_act.triggered.connect(self._on_water_quality_age)
        wq_menu.addAction(wq_age_act)

        wq_cl_act = QAction("&Chlorine Decay...", self)
        wq_cl_act.triggered.connect(self._on_water_quality_chlorine)
        wq_menu.addAction(wq_cl_act)

        wq_trace_act = QAction("&Trace...", self)
        wq_trace_act.triggered.connect(self._on_water_quality_trace)
        wq_menu.addAction(wq_trace_act)

        analysis_menu.addSeparator()

        calibration_act = QAction("&Calibration...", self)
        calibration_act.triggered.connect(self._on_calibration)
        analysis_menu.addAction(calibration_act)

        pattern_act = QAction("&Demand Patterns...", self)
        pattern_act.triggered.connect(self._on_demand_patterns)
        analysis_menu.addAction(pattern_act)

        self.slurry_act = QAction("Slurry &Mode", self)
        self.slurry_act.setCheckable(True)
        self.slurry_act.toggled.connect(self._on_slurry_toggle)
        analysis_menu.addAction(self.slurry_act)

        # --- Tools ---
        tools_menu = menubar.addMenu("&Tools")

        quality_act = QAction("&Quality Review", self)
        quality_act.triggered.connect(self._on_quality_review)
        tools_menu.addAction(quality_act)

        zones_act = QAction("&Pressure Zones...", self)
        zones_act.triggered.connect(self._on_pressure_zones)
        tools_menu.addAction(zones_act)

        rehab_act = QAction("&Rehabilitation Prioritisation...", self)
        rehab_act.triggered.connect(self._on_rehabilitation)
        tools_menu.addAction(rehab_act)

        tools_menu.addSeparator()

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

        self.scale_pipes_act = QAction("Scale Pipes by DN", self)
        self.scale_pipes_act.setCheckable(True)
        self.scale_pipes_act.toggled.connect(self._on_scale_pipes_toggled)
        view_menu.addAction(self.scale_pipes_act)

        self.scale_nodes_act = QAction("Scale Nodes by Demand", self)
        self.scale_nodes_act.setCheckable(True)
        self.scale_nodes_act.toggled.connect(self._on_scale_nodes_toggled)
        view_menu.addAction(self.scale_nodes_act)

        self.basemap_act = QAction("GIS &Basemap (OpenStreetMap)", self)
        self.basemap_act.setCheckable(True)
        self.basemap_act.toggled.connect(self._on_basemap_toggled)
        view_menu.addAction(self.basemap_act)

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

        shortcuts_act = QAction("&Keyboard Shortcuts", self)
        shortcuts_act.setShortcut("F1")
        shortcuts_act.triggered.connect(self._on_keyboard_shortcuts)
        help_menu.addAction(shortcuts_act)

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
        self.canvas.edit_btn.setToolTip(
            "Edit Mode — add/move/delete nodes and pipes on the canvas"
        )
        self.canvas.edit_btn.toggled.connect(self._on_edit_mode_toggled)
        # Insert into the canvas toolbar layout (after Labels button)
        toolbar_layout = self.canvas.layout().itemAt(0).layout()

        # Add tooltips to the existing canvas toolbar buttons
        self.canvas.fit_btn.setToolTip("Fit — zoom to show all network elements (Ctrl+F)")
        self.canvas.labels_btn.setToolTip("Labels — toggle node/pipe ID labels on the canvas")

        toolbar_layout.insertWidget(4, self.canvas.edit_btn)

        # Values overlay toggle
        self.values_btn = QPushButton("Values")
        self.values_btn.setCheckable(True)
        self.values_btn.setFont(QFont("Consolas", 9))
        self.values_btn.setToolTip(
            "Values — show numeric pressure/velocity labels on every element"
        )
        self.values_btn.toggled.connect(self._on_values_toggled)
        toolbar_layout.insertWidget(5, self.values_btn)

        # Probe tool button
        self.probe_btn = QPushButton("Probe")
        self.probe_btn.setCheckable(True)
        self.probe_btn.setFont(QFont("Consolas", 9))
        self.probe_btn.setToolTip(
            "Probe — click any element to inspect all hydraulic result variables"
        )
        self.probe_btn.toggled.connect(self._on_probe_mode_toggled)
        toolbar_layout.insertWidget(6, self.probe_btn)

        # Wire probe signal from canvas
        self.canvas.probe_requested.connect(self._on_probe_requested)

        # ColourBar widget (fixed sidebar next to canvas)
        self._colourmap_widget = ColourMapWidget()
        self._colourmap_widget.colour_map_changed.connect(self._on_colourmap_changed)
        self._colour_bar = ColourBar(self._colourmap_widget)

        # Embed ColourMap + ColourBar into a small vertical widget
        cmap_container = QWidget()
        cmap_vlayout = QVBoxLayout(cmap_container)
        cmap_vlayout.setContentsMargins(2, 2, 2, 2)
        cmap_vlayout.addWidget(self._colourmap_widget)
        cmap_vlayout.addWidget(self._colour_bar)
        cmap_vlayout.addStretch()

        # Place it in the canvas area using a horizontal wrapper
        canvas_wrapper = QWidget()
        canvas_h = QHBoxLayout(canvas_wrapper)
        canvas_h.setContentsMargins(0, 0, 0, 0)
        canvas_h.setSpacing(0)
        # The real canvas is already set as central — rebuild with wrapper
        # We replace the central widget with a wrapper containing both
        self.setCentralWidget(canvas_wrapper)
        canvas_h.addWidget(self.canvas)
        canvas_h.addWidget(cmap_container)

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
            ["ID", "Elevation (m)", "Min Pressure (m)", "Head (m)", "WSAA Status"]
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
        self.statistics_panel = StatisticsPanel()

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.node_results_table)
        splitter.addWidget(self.pipe_results_table)
        splitter.addWidget(self.pipe_stress_panel)
        splitter.addWidget(self.statistics_panel)
        # Give each panel roughly equal initial space
        splitter.setSizes([200, 200, 150, 150])
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

        # --- Bottom: Animation (tabbed with Results) ---
        self.animation_dock = QDockWidget("Animation", self)
        self.animation_dock.setObjectName("animation_dock")
        self.animation_dock.setFeatures(_dock_features)
        self.animation_panel = AnimationPanel()
        self.animation_panel.frame_changed.connect(self._on_animation_frame)
        self.animation_dock.setWidget(self.animation_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.animation_dock)
        # Tab animation alongside results
        self.tabifyDockWidget(self.results_dock, self.animation_dock)
        # Show results as the initially visible bottom tab
        self.results_dock.raise_()

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

        self.wsaa_label.setToolTip(
            "WSAA Compliance — PASS: all nodes 20–50 m pressure, all pipes <2.0 m/s velocity.\n"
            "FAIL: one or more elements outside WSAA WSA 03-2011 Table 3.1 limits.\n"
            "Run Analysis > Steady State (F5) to compute WSAA status."
        )

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
        self._add_property_row("X (m)", f"{x:.1f}")
        self._add_property_row("Y (m)", f"{y:.1f}")

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
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
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
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
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
        infos = sum(1 for c in compliance if c.get('type') == 'INFO')
        if fails == 0 and infos == 0:
            self.wsaa_label.setText("WSAA: PASS")
            self.wsaa_label.setStyleSheet("color: #a6e3a1;")
        elif fails == 0:
            self.wsaa_label.setText(f"WSAA: PASS ({infos} info)")
            self.wsaa_label.setStyleSheet("color: #a6e3a1;")
        else:
            info_str = f", {infos} info" if infos > 0 else ""
            self.wsaa_label.setText(f"WSAA: {fails} issue(s){info_str}")
            self.wsaa_label.setStyleSheet("color: #f38ba8;")

        analysis_type = "Slurry" if self.slurry_act.isChecked() else "Hydraulic"
        if 'junctions' in results and 'max_surge_m' in results:
            analysis_type = "Transient"
        self.analysis_label.setText(f"Analysis: {analysis_type}")

        # Update pipe stress panel
        self.pipe_stress_panel.update_results(self.api, results)

        # Update network statistics panel
        self.statistics_panel.update_statistics(self.api, results)

        # Populate animation panel if transient data present
        # Transient results include 'junctions' key with head arrays
        if 'junctions' in results and isinstance(results['junctions'], dict):
            self._populate_animation_panel(results)

        # EPS results: populate animation from raw WNTR data if multi-timestep
        raw = self.api.get_steady_results()
        if raw is not None and 'pressures' in results:
            import numpy as np
            n_timesteps = len(raw.node['pressure'].index)
            if n_timesteps > 1:
                self._populate_eps_animation(raw)

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

    def _populate_animation_panel(self, results):
        """Load transient data into the AnimationPanel."""
        import numpy as np

        junctions = results.get('junctions', {})
        # Build timestamps from the first junction's head array length
        # HydraulicAPI transient results store head as ndarray per node
        sample_node = next(iter(junctions.values()), None)
        if sample_node is None:
            return

        head_arr = sample_node.get('head')
        if head_arr is None or len(head_arr) == 0:
            return

        n_steps = len(head_arr)
        # Use 'timestamps' from results if available, else synthesise from dt
        if 'timestamps' in results:
            timestamps = np.asarray(results['timestamps'])
        else:
            dt = results.get('dt', 0.1)
            timestamps = np.arange(n_steps) * dt

        # node_data: {node_id: {'head': np.ndarray}}
        node_data = {nid: {'head': np.asarray(v['head'])}
                     for nid, v in junctions.items()
                     if 'head' in v}

        # pipe_data: best-effort from 'pipes_transient' key
        pipe_data = results.get('pipes_transient', {})

        self.animation_panel.set_transient_data(timestamps, node_data, pipe_data)
        # Raise the animation dock so the user can see it
        self.animation_dock.raise_()

    def _populate_eps_animation(self, raw_results):
        """Load EPS multi-timestep data into AnimationPanel."""
        import numpy as np

        pressures = raw_results.node['pressure']
        flows = raw_results.link['flowrate']
        velocities = raw_results.link.get('velocity')

        timestamps = np.array(pressures.index, dtype=float)
        n_steps = len(timestamps)
        if n_steps < 2:
            return

        # node_data: head = pressure + elevation
        node_data = {}
        for nid in pressures.columns:
            try:
                elev = self.api.get_node(nid).elevation
            except Exception:
                elev = 0
            head_arr = np.array(pressures[nid].values, dtype=float) + elev
            node_data[nid] = {'head': head_arr}

        # pipe_data: velocity and flow
        pipe_data = {}
        for lid in flows.columns:
            pd = {'start_node_flowrate': np.array(flows[lid].values, dtype=float)}
            if velocities is not None and lid in velocities.columns:
                pd['start_node_velocity'] = np.array(velocities[lid].values, dtype=float)
            pipe_data[lid] = pd

        self.animation_panel.set_transient_data(timestamps, node_data, pipe_data)
        self.animation_dock.raise_()

    def _on_animation_frame(self, frame: int):
        """
        Handle AnimationPanel.frame_changed — extract a single-frame snapshot
        and push it to the canvas as if it were steady-state results.
        """
        node_data = self.animation_panel.node_data
        pipe_data = self.animation_panel.pipe_data
        if not node_data:
            return

        # Build a pressures snapshot matching the steady-state dict format:
        # {'node_id': {'avg_m': float, 'min_m': float, 'max_m': float}}
        pressures = {}
        for nid, nd in node_data.items():
            head_arr = nd.get('head')
            if head_arr is not None and frame < len(head_arr):
                try:
                    node = self.api.get_node(nid)
                    elev = node.elevation
                except Exception:
                    elev = 0.0
                p = float(head_arr[frame]) - elev
                pressures[nid] = {'avg_m': p, 'min_m': p, 'max_m': p}

        # Build a flows snapshot
        flows = {}
        for pid, pd in pipe_data.items():
            vel_arr = pd.get('start_node_velocity')
            if vel_arr is None:
                vel_arr = pd.get('velocity')
            flow_arr = pd.get('start_node_flowrate')
            if flow_arr is None:
                flow_arr = pd.get('flowrate')
            v = float(vel_arr[frame]) if vel_arr is not None and frame < len(vel_arr) else 0.0
            q = float(flow_arr[frame]) if flow_arr is not None and frame < len(flow_arr) else 0.0
            flows[pid] = {
                'avg_lps': q * 1000,
                'max_velocity_ms': abs(v),
                'min_velocity_ms': abs(v),
            }

        snapshot = {
            'pressures': pressures,
            'flows': flows,
            'compliance': [],
        }
        self.canvas.set_results(snapshot)

    def _on_colourmap_changed(self):
        """Re-apply canvas colours when colourmap settings change."""
        self.canvas.set_colourmap(self._colourmap_widget)

    def _on_values_toggled(self, checked: bool):
        """Toggle numeric value overlay on canvas elements."""
        self.canvas.set_values_visible(checked)

    def _on_scale_pipes_toggled(self, checked: bool):
        """Toggle pipe width scaling by DN."""
        self.canvas.set_pipe_scaling(checked)

    def _on_scale_nodes_toggled(self, checked: bool):
        """Toggle node size scaling by demand."""
        self.canvas.set_node_scaling(checked)

    def _on_basemap_toggled(self, checked: bool):
        """Toggle GIS basemap overlay."""
        self.canvas.toggle_basemap(checked)

    def _on_analysis_error(self, msg):
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Analysis Error", msg)
        self.status_bar.showMessage("Analysis failed.", 5000)

    def _on_run_all_scenarios(self):
        """Run all scenarios sequentially and update comparison table."""
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
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

            min_p = pdata.get('min_m', 0)
            avg_p = pdata.get('avg_m', 0)
            max_p = pdata.get('max_m', 0)
            head = node.elevation + avg_p if elev != "--" else avg_p

            # WSAA compliance uses MINIMUM pressure across all timesteps
            # — WSAA WSA 03-2011 Table 3.1: if pressure drops below 20m
            # at any time (e.g., 7am peak demand), it fails
            wsaa_p = min_p
            if wsaa_p < 20.0:
                status = "FAIL (<20 m)"
            elif max_p > 50.0:
                status = "FAIL (>50 m)"
            else:
                status = "PASS"

            items = [jid, elev, f"{min_p:.1f} m", f"{head:.1f} m", status]
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
    # DEMAND PATTERNS / EPS
    # =====================================================================

    def _on_calibration(self):
        """Open the Calibration Tools dialog."""
        dialog = CalibrationDialog(self.api, canvas=self.canvas, parent=self)
        dialog.exec()

    def _on_fire_flow(self):
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
        dialog = FireFlowDialog(self.api, canvas=self.canvas, parent=self)
        dialog.exec()

    # =====================================================================
    # WATER QUALITY ACTIONS
    # =====================================================================

    def _open_water_quality_dialog(self, mode):
        """Open WaterQualityDialog in the specified mode."""
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
        dialog = WaterQualityDialog(
            self.api, canvas=self.canvas, mode=mode, parent=self
        )
        dialog.exec()

    def _on_water_quality_age(self):
        self._open_water_quality_dialog('age')

    def _on_water_quality_chlorine(self):
        self._open_water_quality_dialog('chlorine')

    def _on_water_quality_trace(self):
        self._open_water_quality_dialog('trace')

    def _on_demand_patterns(self):
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
        dialog = PatternEditorDialog(self.api, parent=self)
        dialog.exec()

    def _on_run_eps(self):
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return

        dialog = EPSConfigDialog(self)
        if not dialog.exec():
            return

        duration_hrs = dialog.get_duration_hours()
        timestep_s = dialog.get_timestep_seconds()

        # Configure WNTR model
        self.api.wn.options.time.duration = duration_hrs * 3600
        self.api.wn.options.time.hydraulic_timestep = timestep_s
        self.api.wn.options.time.pattern_timestep = timestep_s

        self.status_bar.showMessage(f"Running EPS ({duration_hrs}h, {timestep_s}s step)...")

        # Run steady state (which is actually EPS when duration > 0)
        self._run_analysis('steady')

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
        """Handle Escape to cancel pipe creation in edit mode or hide probe tooltip."""
        if event.key() == Qt.Key.Key_Escape:
            if self._probe_tooltip and self._probe_tooltip.isVisible():
                self._probe_tooltip.hide()
            if hasattr(self, 'editor') and self.editor.edit_mode:
                self.editor.cancel_pipe_start()
        else:
            super().keyPressEvent(event)

    # =====================================================================
    # TOOLS / REPORTS / VIEW
    # =====================================================================

    def _on_quality_review(self):
        self.status_bar.showMessage("Quality review triggered.", 3000)

    def _on_pressure_zones(self):
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
        dialog = PressureZoneDialog(self.api, canvas=self.canvas, parent=self)
        dialog.exec()

    def _on_rehabilitation(self):
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
        dialog = RehabDialog(self.api, parent=self)
        dialog.exec()

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
        self.animation_dock.setVisible(True)

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
    # PROBE TOOL
    # =====================================================================

    def _on_probe_mode_toggled(self, checked: bool):
        """Enable/disable probe mode on the canvas."""
        self.canvas.set_probe_mode(checked)
        if not checked and self._probe_tooltip:
            self._probe_tooltip.hide()

    def _on_probe_requested(self, element_id: str, element_type: str, gx: int, gy: int):
        """Show ProbeTooltip for the clicked element."""
        # Lazy-create the tooltip
        if self._probe_tooltip is None:
            self._probe_tooltip = ProbeTooltip()

        # Hide first so geometry is recalculated after content changes
        self._probe_tooltip.hide()

        try:
            if element_type == 'junction':
                node = self.api.get_node(element_id)
                pdata = (self._last_results or {}).get('pressures', {}).get(element_id)
                self._probe_tooltip.show_junction(element_id, node, pdata)
            elif element_type == 'reservoir':
                node = self.api.get_node(element_id)
                self._probe_tooltip.show_reservoir(element_id, node)
            elif element_type == 'tank':
                node = self.api.get_node(element_id)
                self._probe_tooltip.show_tank(element_id, node)
            elif element_type == 'pipe':
                pipe = self.api.get_link(element_id)
                fdata = (self._last_results or {}).get('flows', {}).get(element_id)
                self._probe_tooltip.show_pipe(element_id, pipe, fdata)
            else:
                return
        except Exception:
            return

        self._probe_tooltip.move_near(gx, gy)

    # =====================================================================
    # TUTORIAL / SHORTCUTS
    # =====================================================================

    def _on_open_tutorial(self):
        """Open a file dialog starting in the tutorials/ directory."""
        tutorials_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tutorials"
        )
        if not os.path.isdir(tutorials_dir):
            tutorials_dir = ""

        path, _ = QFileDialog.getOpenFileName(
            self, "Open Tutorial Network", tutorials_dir,
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
                                 f"Could not load tutorial file.\n\n{type(e).__name__}: {e}")

    def _on_keyboard_shortcuts(self):
        """Show all keyboard shortcuts in a QMessageBox."""
        shortcuts = (
            "Keyboard Shortcuts\n"
            "==================\n\n"
            "File\n"
            "  Ctrl+N          New project\n"
            "  Ctrl+O          Open .inp file\n"
            "  Ctrl+S          Save\n"
            "  Ctrl+Shift+S    Save As (.hap)\n"
            "  Ctrl+Q          Exit\n\n"
            "Edit\n"
            "  Ctrl+Z          Undo\n"
            "  Ctrl+Y          Redo\n"
            "  Escape          Cancel pipe creation / hide probe tooltip\n\n"
            "Analysis\n"
            "  F5              Run Steady State\n"
            "  F6              Run Transient\n"
            "  F7              Run Extended Period (EPS)\n"
            "  F8              Fire Flow Wizard\n\n"
            "Help\n"
            "  F1              Keyboard Shortcuts (this dialog)\n"
        )
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts)

    # =====================================================================
    # DRAG AND DROP
    # =====================================================================

    def dragEnterEvent(self, event):
        """Accept drag if it contains .inp file URLs."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith('.inp') for u in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        """Load the first .inp file dropped onto the window."""
        urls = event.mimeData().urls()
        for url in urls:
            path = url.toLocalFile()
            if path.lower().endswith('.inp'):
                try:
                    self.api.load_network_from_path(path)
                    self._current_file = path
                    self._populate_explorer()
                    self._update_status_bar()
                    self.setWindowTitle(f"Hydraulic Analysis Tool — {os.path.basename(path)}")
                    self.canvas.set_api(self.api)
                    event.acceptProposedAction()
                    self.status_bar.showMessage(f"Loaded {os.path.basename(path)}", 3000)
                except Exception as e:
                    QMessageBox.critical(self, "Load Error",
                                         f"Could not load dropped file.\n\n{type(e).__name__}: {e}")
                return
        event.ignore()

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
        self.animation_dock.setVisible(True)

        # Re-ensure canvas scene click handler is connected
        self.canvas.ensure_scene_connected()

    def closeEvent(self, event):
        """Save preferences on window close."""
        prefs = {
            'last_file': self._current_file or '',
            'window_width': self.width(),
            'window_height': self.height(),
            'slurry_mode': self.slurry_act.isChecked(),
            'colour_mode': self.canvas.color_mode_combo.currentText(),
        }
        save_preferences(prefs)
        super().closeEvent(event)

    def _restore_session(self):
        """Restore last session from preferences."""
        prefs = load_preferences()
        last_file = prefs.get('last_file', '')
        if last_file and os.path.exists(last_file):
            try:
                self.api.load_network_from_path(last_file)
                self._current_file = last_file
                self._populate_explorer()
                self._update_status_bar()
                self.canvas.set_api(self.api)
                self.setWindowTitle(
                    f"Hydraulic Analysis Tool — {os.path.basename(last_file)}")
            except Exception:
                pass
        w = prefs.get('window_width')
        h = prefs.get('window_height')
        if w and h:
            self.resize(w, h)
        if prefs.get('slurry_mode'):
            self.slurry_act.setChecked(True)
        cm = prefs.get('colour_mode')
        if cm and cm in self.canvas.COLOR_MODES:
            self.canvas.color_mode_combo.setCurrentText(cm)

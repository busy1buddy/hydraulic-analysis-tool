"""
Main Window — PyQt6 Desktop Application
=========================================
QMainWindow with menu bar, dock panels, status bar, and central widget.
All network data accessed through HydraulicAPI only.
"""

import os
import json

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMenuBar, QMenu, QStatusBar, QDockWidget,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QLabel, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog,
    QMessageBox, QHeaderView, QSplitter, QProgressBar, QPushButton,
)
from PyQt6.QtCore import Qt, QSize, QByteArray, QEvent
from PyQt6.QtGui import QAction, QFont, QColor, QShortcut, QKeySequence

import logging

from epanet_api import HydraulicAPI

logger = logging.getLogger(__name__)
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
from desktop.split_canvas import SplitCanvas
from desktop.surge_wizard import SurgeWizard
from desktop.view_3d import View3D
from desktop.report_scheduler import ReportSchedulerDialog
from desktop.pipe_profile_dialog import PipeProfileDialog
from desktop.dashboard_widget import DashboardWidget
from desktop.what_if_panel import WhatIfPanel


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
        # Slurry params persist across runs; user edits via Analysis > Slurry.
        # Defaults match the "Iron ore tailings" preset in slurry_params_dialog.
        self._slurry_params = {
            'yield_stress': 15.0,
            'plastic_viscosity': 0.05,
            'density': 1800.0,
        }

        self.setWindowTitle("Hydraulic Analysis Tool — v2.9.0")
        self.setMinimumSize(QSize(1400, 900))
        # Default to 85% of the primary screen so the canvas gets real estate
        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.resize(int(geo.width() * 0.85), int(geo.height() * 0.85))
        else:
            self.resize(1600, 1000)

        self._setup_menus()
        self._setup_central_widget()
        self._setup_dock_panels()
        self._setup_status_bar()

        # Initial prompt — tells the user what to do first
        self.status_bar.showMessage(
            "Ready — open a network (File > Open, Ctrl+O) or "
            "Help > Run Demo to start.", 0)

        # Enable drag-and-drop of .inp files onto the main window
        self.setAcceptDrops(True)

        # NOTE: _restore_session() is NOT called here. The production entry
        # point (main_app.py) calls it after constructing the window so the
        # feature works for end users, while tests that instantiate
        # MainWindow directly start with a clean empty state.

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

        export_bundle_act = QAction("Export Project &Bundle...", self)
        export_bundle_act.triggered.connect(self._on_export_bundle)
        file_menu.addAction(export_bundle_act)

        import_bundle_act = QAction("&Import Project Bundle...", self)
        import_bundle_act.triggered.connect(self._on_import_bundle)
        file_menu.addAction(import_bundle_act)

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

        profile_act = QAction("&Pipe Profile...", self)
        profile_act.triggered.connect(self._on_pipe_profile)
        analysis_menu.addAction(profile_act)

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

        slurry_params_act = QAction("Slurry &Parameters...", self)
        slurry_params_act.triggered.connect(self._on_edit_slurry_params)
        slurry_params_act.setToolTip(
            "Edit Bingham-plastic parameters: yield stress, plastic "
            "viscosity, density")
        analysis_menu.addAction(slurry_params_act)

        analysis_menu.addSeparator()
        design_check_act = QAction("&Design Compliance Check...", self)
        design_check_act.setShortcut("F9")
        design_check_act.setToolTip("Run all WSAA compliance checks and generate certificate")
        design_check_act.triggered.connect(self._on_design_compliance_check)
        analysis_menu.addAction(design_check_act)

        safety_case_act = QAction("&Safety Case Report...", self)
        safety_case_act.setToolTip(
            "Generate formal pipeline safety case for regulatory submission.")
        safety_case_act.triggered.connect(self._on_safety_case)
        analysis_menu.addAction(safety_case_act)

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

        schedule_act = QAction("&Schedule Reports...", self)
        schedule_act.triggered.connect(self._on_schedule_reports)
        tools_menu.addAction(schedule_act)

        assess_act = QAction("&Quick Assessment...", self)
        assess_act.setShortcut("F10")
        assess_act.setToolTip("Generate comprehensive quick assessment of network health")
        assess_act.triggered.connect(self._on_quick_assessment)
        tools_menu.addAction(assess_act)

        diag_act = QAction("&Network Diagnostics...", self)
        diag_act.setToolTip("Diagnose common network problems and suggest fixes")
        diag_act.triggered.connect(self._on_diagnostics)
        tools_menu.addAction(diag_act)

        topo_act = QAction("&Topology Analysis...", self)
        topo_act.setToolTip("Analyse dead ends, loops, bridges, connectivity")
        topo_act.triggered.connect(self._on_topology)
        tools_menu.addAction(topo_act)

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

        split_act = QAction("Split &Screen (Compare Scenarios)", self)
        split_act.triggered.connect(self._on_split_screen)
        view_menu.addAction(split_act)

        view_3d_act = QAction("&3D View", self)
        view_3d_act.triggered.connect(self._on_3d_view)
        view_menu.addAction(view_3d_act)

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

        self.toggle_what_if_act = QAction("&What-If Panel", self)
        self.toggle_what_if_act.setCheckable(True)
        self.toggle_what_if_act.setChecked(True)
        view_menu.addAction(self.toggle_what_if_act)

        # --- Help ---
        help_menu = menubar.addMenu("&Help")

        about_act = QAction("&About", self)
        about_act.triggered.connect(self._on_about)
        help_menu.addAction(about_act)

        shortcuts_act = QAction("&Keyboard Shortcuts", self)
        shortcuts_act.setShortcut("F1")
        shortcuts_act.triggered.connect(self._on_keyboard_shortcuts)
        help_menu.addAction(shortcuts_act)

        help_menu.addSeparator()
        demo_act = QAction("&Run Demo", self)
        demo_act.setToolTip(
            "Guided tour: loads demo network, runs analysis, shows "
            "violations and recommended fixes.")
        demo_act.triggered.connect(self._on_run_demo)
        help_menu.addAction(demo_act)

    # =====================================================================
    # CENTRAL WIDGET
    # =====================================================================

    def _setup_central_widget(self):
        """Network canvas with PyQtGraph 2D view."""
        self.canvas = NetworkCanvas()
        self.canvas.element_selected.connect(self._on_canvas_element_selected)
        # NOTE: setCentralWidget is called ONCE at the end of this method, after
        # the wrapper is built. Previously we set canvas as central here, then
        # replaced it with a wrapper below — Qt deletes the previous central
        # widget via deleteLater(), which on Windows could destroy the PlotWidget's
        # ViewBox before the reparent-via-addWidget completed, causing
        # "wrapped C/C++ object of type ViewBox has been deleted" on next render.

        # Canvas editor (manages Edit Mode interactions)
        self.editor = CanvasEditor(self.canvas, self)
        self.canvas._editor = self.editor

        # Add Edit Mode button to canvas toolbar. Every toolbar button gets
        # a minimum width or the layout clips the label at 1400 px (observed
        # "Labels" -> ".abel:" on live UX walkthrough).
        self.canvas.edit_btn = QPushButton("Edit")
        self.canvas.edit_btn.setCheckable(True)
        self.canvas.edit_btn.setFont(QFont("Consolas", 9))
        self.canvas.edit_btn.setMinimumWidth(55)
        self.canvas.edit_btn.setToolTip(
            "Edit Mode — add/move/delete nodes and pipes on the canvas"
        )
        self.canvas.edit_btn.toggled.connect(self._on_edit_mode_toggled)
        # Insert into the canvas toolbar layout (after Labels button)
        toolbar_layout = self.canvas.layout().itemAt(0).layout()

        # Add tooltips to the existing canvas toolbar buttons
        self.canvas.fit_btn.setToolTip("Fit — zoom to show all network elements (Ctrl+F)")
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.canvas._fit_view)
        self.canvas.labels_btn.setToolTip("Labels — toggle node/pipe ID labels on the canvas")

        # NOTE: NetworkCanvas adds combo + Fit + Labels (3 items) -- we append
        # Edit/Values/Probe using addWidget. insertWidget(4, ...) used to be
        # correct before the "Color:" label and a trailing stretch were
        # removed, and left a "QBoxLayout::insert: index N out of range"
        # warning printed on every launch.
        toolbar_layout.addWidget(self.canvas.edit_btn)

        # Values overlay toggle
        self.values_btn = QPushButton("Values")
        self.values_btn.setCheckable(True)
        self.values_btn.setFont(QFont("Consolas", 9))
        self.values_btn.setMinimumWidth(62)
        self.values_btn.setToolTip(
            "Values — show numeric pressure/velocity labels on every element"
        )
        self.values_btn.toggled.connect(self._on_values_toggled)
        toolbar_layout.addWidget(self.values_btn)

        # Probe tool button
        self.probe_btn = QPushButton("Probe")
        self.probe_btn.setCheckable(True)
        self.probe_btn.setFont(QFont("Consolas", 9))
        self.probe_btn.setMinimumWidth(60)
        self.probe_btn.setToolTip(
            "Probe — click any element to inspect all hydraulic result variables"
        )
        self.probe_btn.toggled.connect(self._on_probe_mode_toggled)
        toolbar_layout.addWidget(self.probe_btn)

        # Wire probe signal from canvas
        self.canvas.probe_requested.connect(self._on_probe_requested)

        # ColourMap controls: horizontal row, appended to canvas toolbar.
        # The ColourBar (gradient legend) stays as a thin strip next to
        # the canvas so users can read the scale.
        self._colourmap_widget = ColourMapWidget(horizontal=True)
        self._colourmap_widget.colour_map_changed.connect(self._on_colourmap_changed)
        self._colour_bar = ColourBar(self._colourmap_widget)
        # Wire the canvas to the colourmap immediately so _push_colourmap_range
        # has a widget reference when results arrive, not only after the user
        # first touches the colourmap controls. Assign the attribute directly
        # (set_colourmap() calls _apply_colors which needs _pipe_segments,
        # which is not populated until a network is rendered).
        self.canvas._colourmap_widget = self._colourmap_widget

        toolbar_layout.addSpacing(12)
        toolbar_layout.addWidget(self._colourmap_widget, 1)

        # Place ColourBar in the canvas area using a horizontal wrapper.
        # Build the wrapper with canvas inside BEFORE calling setCentralWidget,
        # so Qt never deletes a previous central widget holding self.canvas.
        canvas_wrapper = QWidget()
        canvas_h = QHBoxLayout(canvas_wrapper)
        canvas_h.setContentsMargins(0, 0, 0, 0)
        canvas_h.setSpacing(0)
        canvas_h.addWidget(self.canvas)
        canvas_h.addWidget(self._colour_bar)
        self.setCentralWidget(canvas_wrapper)

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
        self.explorer_dock.setMinimumWidth(200)
        self.explorer_tree = QTreeWidget()
        self.explorer_tree.setHeaderLabels(["Element"])
        self.explorer_tree.setFont(QFont("Consolas", 10))
        self.explorer_dock.setWidget(self.explorer_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.explorer_dock)
        self.toggle_explorer_act.toggled.connect(self.explorer_dock.setVisible)
        self.explorer_dock.visibilityChanged.connect(self.toggle_explorer_act.setChecked)

        # --- Right: Properties (narrow collapsible sidebar) ---
        # Kept in the Right dock area (collapsible via View > Properties)
        # but narrow so the canvas owns the horizontal real estate.
        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setObjectName("properties_dock")
        self.properties_dock.setFeatures(_dock_features)
        self.properties_dock.setMinimumWidth(180)
        self.properties_table = QTableWidget(0, 2)
        self.properties_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.properties_table.horizontalHeader().setStretchLastSection(True)
        self.properties_table.setMinimumWidth(180)
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
        self.results_dock.setMinimumHeight(180)
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(4, 4, 4, 4)

        # Observed in live UX walkthrough: default column widths were clipping
        # the headers ("Min Pressure (m)" -> "in Pressure (m",
        # "Velocity (m/s)" -> "/elocity (m/s)"). ResizeToContents on the
        # fixed-width columns guarantees the header text fits; the last
        # column stretches to fill the remaining space.
        from PyQt6.QtWidgets import QHeaderView

        self.node_results_table = QTableWidget(0, 5)
        self.node_results_table.setHorizontalHeaderLabels(
            ["ID", "Elevation (m)", "Min Pressure (m)", "Head (m)", "WSAA Status"]
        )
        node_hdr = self.node_results_table.horizontalHeader()
        for c in range(4):
            node_hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        node_hdr.setStretchLastSection(True)
        self.node_results_table.setFont(QFont("Consolas", 9))
        self.node_results_table.setMinimumHeight(120)
        self.node_results_table.verticalHeader().setVisible(False)

        self.pipe_results_table = QTableWidget(0, 5)
        self.pipe_results_table.setHorizontalHeaderLabels(
            ["ID", "Diameter (DN)", "Length (m)", "Velocity (m/s)", "Headloss (m/km)"]
        )
        pipe_hdr = self.pipe_results_table.horizontalHeader()
        for c in range(4):
            pipe_hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        pipe_hdr.setStretchLastSection(True)
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
        # Force a repaint when the Results tab is selected -- without this,
        # Qt sometimes draws the dock blank until the user Alt-Tabs away
        # and back, because the tab-switch doesn't propagate a paint event
        # to the child table widgets.
        self.results_dock.visibilityChanged.connect(
            lambda v: self.results_dock.widget().update() if v else None
        )

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
        # --- Bottom: Dashboard (tabbed with Results) ---
        self.dashboard_dock = QDockWidget("Dashboard", self)
        self.dashboard_dock.setObjectName("dashboard_dock")
        self.dashboard_dock.setFeatures(_dock_features)
        self.dashboard_widget = DashboardWidget()
        self.dashboard_dock.setWidget(self.dashboard_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dashboard_dock)

        # Tab animation and dashboard alongside results
        self.tabifyDockWidget(self.results_dock, self.animation_dock)
        self.tabifyDockWidget(self.results_dock, self.dashboard_dock)

        # --- What-If Sensitivity Panel (tabbed with Explorer/Scenarios on the left) ---
        # The Right-area tabify is fragile (Qt silently drops the tab-group
        # when docks have differing minimum widths), but the Left-area tab
        # group already holds Explorer+Scenarios and merges correctly.
        self.what_if_dock = QDockWidget("What-If", self)
        self.what_if_dock.setObjectName("what_if_dock")
        self.what_if_dock.setFeatures(_dock_features)
        self.what_if_dock.setMinimumWidth(220)
        self.what_if_panel = WhatIfPanel(api=self.api)
        self.what_if_panel.analysis_updated.connect(self._on_analysis_finished)
        self.what_if_panel.analysis_failed.connect(
            lambda msg: self.status_bar.showMessage(f"What-If: {msg}", 5000)
        )
        self.what_if_dock.setWidget(self.what_if_panel)
        # Floating-by-default: What-If is a power-user tool, not always-on.
        # It still registers with the left dock area so Qt knows where it
        # belongs if the user drags it back onto the main window.
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.what_if_dock)
        self.what_if_dock.setFloating(True)
        self.what_if_dock.resize(360, 420)
        self.what_if_dock.setVisible(False)
        self.toggle_what_if_act.toggled.connect(self.what_if_dock.setVisible)
        self.what_if_dock.visibilityChanged.connect(self.toggle_what_if_act.setChecked)
        # Show results as the initially visible bottom tab
        self.results_dock.raise_()

        # Apply preferred dock proportions after the initial show so the
        # canvas gets the majority of horizontal/vertical space.
        from PyQt6.QtCore import QTimer as _QTimer
        def _apply_dock_sizes():
            # Left panel: 260 px, right: 180 px, bottom: ~25% window height
            self.resizeDocks(
                [self.explorer_dock, self.properties_dock],
                [260, 180],
                Qt.Orientation.Horizontal,
            )
            bh = max(200, int(self.height() * 0.25))
            self.resizeDocks([self.results_dock], [bh], Qt.Orientation.Vertical)
        _QTimer.singleShot(0, _apply_dock_sizes)

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
        self.resilience_label = QLabel("Ir: --")
        self.quality_label = QLabel("Score: --")

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
        self.resilience_label.setToolTip(
            "Todini Resilience Index: 0.0 = no redundancy, 1.0 = full redundancy.\n"
            "Target > 0.3 for reliable distribution networks.\n"
            "Ref: Todini (2000), Urban Water 2(2):115-122"
        )
        self.quality_label.setToolTip(
            "Network Quality Score (0-100):\n"
            "Pressure (20) + Velocity (20) + Resilience (15) +\n"
            "Pipe Stress (15) + Data (15) + Connectivity (15)\n"
            "Grade: A (90+), B (75+), C (60+), D (45+), F (<45)"
        )

        for lbl in (self.analysis_label, self.nodes_label,
                    self.pipes_label, self.wsaa_label, self.resilience_label,
                    self.quality_label):
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
        self.what_if_panel.set_api(self.api)
        self._update_status_bar()
        self.setWindowTitle("Hydraulic Analysis Tool — v2.9.0")

    def _on_open_inp(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open EPANET Network", "",
            "EPANET Files (*.inp);;Project Files (*.hap);;All Files (*)"
        )
        if not path:
            return

        # Delegate .hap files to the project loader
        if path.lower().endswith('.hap'):
            self._load_hap(path)
            return

        try:
            self.api.load_network_from_path(path)
            self._current_file = path
            # Clear stale results from previous network
            self._last_results = None
            self.node_results_table.setRowCount(0)
            self.pipe_results_table.setRowCount(0)
            self._populate_explorer()
            self._update_status_bar()
            self.setWindowTitle(f"Hydraulic Analysis Tool v2.9.0 — {os.path.basename(path)}")
            self.canvas.set_api(self.api)
            self.dashboard_widget.update_dashboard(self.api)
            self.what_if_panel.set_api(self.api)
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
        """Save full project state as .hap JSON file."""
        # Serialize scenarios
        scenarios = []
        if hasattr(self, 'scenario_panel'):
            scenarios = [s.to_dict() for s in self.scenario_panel.scenarios]

        # Serialize last analysis results (pressures, flows, compliance)
        last_run = {}
        if self._last_results is not None:
            last_run = {
                'pressures': self._last_results.get('pressures', {}),
                'flows': self._last_results.get('flows', {}),
                'compliance': self._last_results.get('compliance', []),
            }
            # Include slurry data if present
            if self._last_results.get('slurry'):
                last_run['slurry'] = self._last_results['slurry']

        # Serialize slurry parameters
        slurry_params = dict(self._slurry_params) if hasattr(self, '_slurry_params') else {}

        # Store inp_path relative to .hap file for portability
        inp_abs = self._current_file or ''
        hap_dir = os.path.dirname(os.path.abspath(path))
        try:
            inp_rel = os.path.relpath(inp_abs, hap_dir)
        except ValueError:
            inp_rel = inp_abs  # Different drive on Windows

        # Capture .inp file modification time for stale detection
        inp_mtime = 0
        if inp_abs and os.path.exists(inp_abs):
            inp_mtime = os.path.getmtime(inp_abs)

        project = {
            'version': '3.3.0',
            'inp_path': inp_abs,
            'inp_path_relative': inp_rel,
            'inp_mtime': inp_mtime,
            'scenarios': scenarios,
            'last_run': last_run,
            'slurry_params': slurry_params,
            'settings': {
                'slurry_mode': self.slurry_act.isChecked(),
                'colour_mode': self.canvas.color_mode_combo.currentText(),
            },
        }
        try:
            with open(path, 'w') as f:
                json.dump(project, f, indent=2)
            self.status_bar.showMessage(f"Saved to {path}", 3000)
            self.setWindowTitle(f"Hydraulic Analysis Tool v2.9.0 — {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _load_hap(self, path):
        """Load full project state from .hap JSON file."""
        try:
            with open(path) as f:
                project = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Load Error",
                                 f"Could not read project file.\n\n{e}")
            return

        # Resolve .inp network path (try absolute, then relative to .hap)
        inp_path = project.get('inp_path', '')
        hap_dir = os.path.dirname(os.path.abspath(path))
        if not inp_path or not os.path.exists(inp_path):
            # Try relative path stored in .hap
            inp_rel = project.get('inp_path_relative', '')
            if inp_rel:
                inp_path = os.path.join(hap_dir, inp_rel)
            if not os.path.exists(inp_path):
                # Last resort: basename next to .hap
                inp_path = os.path.join(hap_dir, os.path.basename(
                    project.get('inp_path', '')))
            if not os.path.exists(inp_path):
                QMessageBox.warning(self, "Missing Network",
                    f"Network file not found: {project.get('inp_path', '')}")
                return

        # Warn if .inp was modified since the project was saved
        saved_mtime = project.get('inp_mtime', 0)
        if saved_mtime > 0:
            current_mtime = os.path.getmtime(inp_path)
            if abs(current_mtime - saved_mtime) > 1.0:
                QMessageBox.information(self, "Network Modified",
                    "The .inp file has been modified since this project was saved.\n"
                    "Saved results may not match the current network.\n"
                    "Consider re-running analysis (F5) to update.")

        try:
            self.api.load_network_from_path(inp_path)
        except Exception as e:
            QMessageBox.critical(self, "Load Error",
                                 f"Could not load network.\n\n{e}")
            return

        self._current_file = inp_path
        self._hap_file = path
        self._last_results = None
        self.node_results_table.setRowCount(0)
        self.pipe_results_table.setRowCount(0)
        self._populate_explorer()
        self.canvas.set_api(self.api)
        self.dashboard_widget.update_dashboard(self.api)
        self.what_if_panel.set_api(self.api)

        # Restore analysis results to tables without re-running
        last_run = project.get('last_run', {})
        if last_run and last_run.get('pressures'):
            self._last_results = last_run
            self._on_analysis_finished(last_run)

        # Restore scenarios
        from desktop.scenario_panel import ScenarioData
        scenarios_data = project.get('scenarios', [])
        if scenarios_data and hasattr(self, 'scenario_panel'):
            self.scenario_panel.scenarios = [
                ScenarioData(s['name'], s.get('demand_multiplier', 1.0),
                             s.get('modifications', []))
                for s in scenarios_data
            ]

        # Restore slurry parameters
        slurry_params = project.get('slurry_params', {})
        if slurry_params:
            self._slurry_params = slurry_params

        # Restore settings
        settings = project.get('settings', {})
        if settings.get('slurry_mode', False):
            self.slurry_act.setChecked(True)
        cm = settings.get('colour_mode')
        if cm and cm in self.canvas.COLOR_MODES:
            self.canvas.color_mode_combo.setCurrentText(cm)

        self._update_status_bar()
        self.setWindowTitle(f"Hydraulic Analysis Tool v2.9.0 — {os.path.basename(path)}")
        self.status_bar.showMessage(f"Loaded project {os.path.basename(path)}", 3000)

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

        # Results (tracked so _on_analysis_finished can update the label)
        self._results_tree_item = QTreeWidgetItem(root, ["Results (none)"])

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
        except (KeyError, AttributeError) as e:
            logger.debug("Could not show properties for %s: %s", element_id, e)

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
        except (KeyError, AttributeError) as e:
            logger.debug("Canvas element properties error: %s", e)

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
            # Use stored slurry params, or default them. User can edit
            # via Analysis > Slurry Mode toggle (which prompts the dialog).
            params['slurry'] = self._slurry_params
        self._run_analysis(atype, params)

    def _on_run_transient(self):
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
        self._run_analysis('transient')

    def _run_analysis(self, analysis_type, params=None):
        """Launch analysis in background thread."""
        # Guard against concurrent analysis runs
        if hasattr(self, '_worker') and self._worker is not None and self._worker.isRunning():
            self.status_bar.showMessage(
                "Analysis already running. Please wait for it to finish.", 5000)
            return
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

        # Update Project Explorer Results label
        if getattr(self, '_results_tree_item', None) is not None:
            worker = getattr(self, '_worker', None)
            atype = getattr(worker, 'analysis_type', 'steady') if worker else 'steady'
            label_map = {
                'steady': 'Steady State',
                'transient': 'Transient',
                'slurry': 'Slurry (Bingham)',
            }
            label = label_map.get(atype, str(atype).replace('_', ' ').title())
            self._results_tree_item.setText(0, f"Results ({label})")

        # Update canvas colors
        self.canvas.set_results(results)

        # Populate results tables
        self._populate_node_results(results)
        self._populate_pipe_results(results)

        # Update WSAA status
        compliance = results.get('compliance', [])
        fails = sum(1 for c in compliance if c.get('type') in ('WARNING', 'CRITICAL'))
        infos = sum(1 for c in compliance if c.get('type') == 'INFO')
        # Compact format to fit the status-bar slot:
        #   "WSAA: PASS", "WSAA: PASS 2i", "WSAA: 8! 7i"
        if fails == 0 and infos == 0:
            self.wsaa_label.setText("WSAA: PASS")
            self.wsaa_label.setStyleSheet("color: #a6e3a1;")
        elif fails == 0:
            self.wsaa_label.setText(f"WSAA: PASS {infos}i")
            self.wsaa_label.setStyleSheet("color: #a6e3a1;")
        else:
            info_str = f" {infos}i" if infos > 0 else ""
            self.wsaa_label.setText(f"WSAA: {fails}!{info_str}")
            self.wsaa_label.setStyleSheet("color: #f38ba8;")
        self.wsaa_label.setToolTip(
            f"WSAA: {fails} issue(s), {infos} info — {'PASS' if fails == 0 else 'FAIL'}"
        )

        # Update resilience index
        ri = self.api.compute_resilience_index(results)
        if 'error' not in ri:
            ri_val = ri['resilience_index']
            self.resilience_label.setText(f"Ir: {ri_val:.3f} ({ri['grade']})")
            if ri_val >= 0.3:
                self.resilience_label.setStyleSheet("color: #a6e3a1;")
            elif ri_val >= 0.15:
                self.resilience_label.setStyleSheet("color: #f9e2af;")
            else:
                self.resilience_label.setStyleSheet("color: #f38ba8;")

        # Update quality score
        qs = self.api.compute_quality_score(results)
        if 'error' not in qs:
            self.quality_label.setText(f"Score: {qs['total_score']:.0f}/100 ({qs['grade']})")
            if qs['total_score'] >= 75:
                self.quality_label.setStyleSheet("color: #a6e3a1;")
            elif qs['total_score'] >= 60:
                self.quality_label.setStyleSheet("color: #f9e2af;")
            else:
                self.quality_label.setStyleSheet("color: #f38ba8;")

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
        except (OSError, ValueError) as e:
            logger.warning("Audit trail write failed: %s", e)

        # Update dashboard
        self.dashboard_widget.update_dashboard(self.api, results)

        # Raise the Results dock so the engineer sees the numeric results they
        # just computed. _populate_eps_animation() above raises the Animation
        # dock when multi-timestep EPS data is present — that hides Results
        # unless we raise it again here. Force a repaint too: without it, Qt
        # sometimes leaves the dock's child tables blank until the user
        # Alt-Tabs away and back.
        self.results_dock.raise_()
        self.results_dock.widget().update()
        QApplication.processEvents()

        self.status_bar.showMessage("Analysis complete.", 5000)

        # Show surge protection wizard if transient surge > 30 m
        if results.get('max_surge_m', 0) > 30:
            wizard = SurgeWizard(self.api, results, parent=self)
            wizard.exec()

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
        # NOTE: intentionally NOT calling animation_dock.raise_() here.
        # Transient analysis populates the Animation panel but the engineer
        # wants to see the Results tables first. They can click the Animation
        # tab to scrub through frames when they want.

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
            except (KeyError, AttributeError):
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
        # Do NOT raise animation_dock — leave Results visible. User switches
        # to the Animation tab manually.

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
                except (KeyError, AttributeError):
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

    def _on_3d_view(self):
        """Open 3D network visualisation."""
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
        view = View3D(self.api, results=self._last_results, parent=self)
        view.show()

    def _on_basemap_toggled(self, checked: bool):
        """Toggle GIS basemap overlay."""
        self.canvas.toggle_basemap(checked)

    def _on_split_screen(self):
        """Open split-screen scenario comparison."""
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
        scenarios = self.scenario_panel.scenarios
        if len(scenarios) < 2:
            QMessageBox.warning(self, "Insufficient Scenarios",
                "Create at least 2 scenarios and run them before comparing.\n\n"
                "Go to the Scenarios panel, create scenarios with different\n"
                "demand multipliers, then click 'Run All'.")
            return
        has_results = sum(1 for sc in scenarios if sc.results)
        if has_results < 2:
            QMessageBox.warning(self, "No Results",
                "Run all scenarios first (click 'Run All' in the Scenarios panel).")
            return

        split = SplitCanvas(self.api, parent=self)
        split.set_scenarios(scenarios)
        split.closed.connect(split.deleteLater)
        split.show()

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
            except (KeyError, AttributeError):
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
        """Fill the pipe results table.

        In slurry mode (results contains 'slurry'), the headloss column
        shows Bingham-plastic headloss from slurry_solver -- NOT the
        Hazen-Williams water value -- and the table grows two columns
        (Regime, Re_B). Previously the table always showed the water
        headloss, which was a ~10x accuracy bug for slurry users.
        """
        flows = results.get('flows', {})
        slurry_data = results.get('slurry')  # {pid: {headloss_m, regime, reynolds, ...}} or None
        is_slurry = bool(slurry_data)

        # Reconfigure columns depending on mode
        if is_slurry:
            hdr = ["ID", "Diameter (DN)", "Length (m)", "Velocity (m/s)",
                   "Headloss Slurry (m/km)", "Regime", "Re_B"]
        else:
            hdr = ["ID", "Diameter (DN)", "Length (m)", "Velocity (m/s)",
                   "Headloss (m/km)"]
        if self.pipe_results_table.columnCount() != len(hdr):
            self.pipe_results_table.setColumnCount(len(hdr))
            for c in range(len(hdr) - 1):
                self.pipe_results_table.horizontalHeader().setSectionResizeMode(
                    c, QHeaderView.ResizeMode.ResizeToContents)
            self.pipe_results_table.horizontalHeader().setStretchLastSection(True)
        self.pipe_results_table.setHorizontalHeaderLabels(hdr)
        self.pipe_results_table.setRowCount(0)

        for pid, fdata in flows.items():
            row = self.pipe_results_table.rowCount()
            self.pipe_results_table.insertRow(row)

            try:
                pipe = self.api.get_link(pid)
                dn = f"{int(pipe.diameter * 1000)} mm"
                length = f"{pipe.length:.1f}"
                pipe_length = pipe.length
                pipe_diameter = pipe.diameter
                pipe_roughness = pipe.roughness
            except (KeyError, AttributeError):
                dn = "--"
                length = "--"
                pipe_length = 0
                pipe_diameter = 0
                pipe_roughness = 130

            v = fdata.get('max_velocity_ms', 0)
            avg_lps = abs(fdata.get('avg_lps', 0))

            if is_slurry and pid in slurry_data:
                # Use slurry-solver headloss and velocity
                sd = slurry_data[pid]
                # Use slurry velocity, not water velocity
                v_display = sd.get('velocity_ms', v)
                if pipe_length > 0:
                    hl_per_km = sd.get('headloss_m', 0) / pipe_length * 1000
                else:
                    hl_per_km = 0
                regime = sd.get('regime', '--')
                re_b = sd.get('reynolds', 0)
                items = [pid, dn, length, f"{v_display:.2f}",
                         f"{hl_per_km:.1f}", regime, f"{re_b:.0f}"]
            else:
                # Read headloss from solver results (not recalculated)
                hl_per_km = fdata.get('headloss_per_km', 0)
                if is_slurry:
                    # Zero-flow pipe in slurry mode — fill extra columns
                    items = [pid, dn, length, f"{v:.2f}", f"{hl_per_km:.1f}",
                             "--", "0"]
                else:
                    items = [pid, dn, length, f"{v:.2f}", f"{hl_per_km:.1f}"]

            # Determine actual displayed velocity for WSAA flagging
            v_check = v_display if (is_slurry and pid in slurry_data) else v
            for col, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                # Flag velocity > 2.0 m/s — WSAA WSA 03-2011
                if col == 3 and v_check > 2.0:
                    item.setForeground(QColor(243, 139, 168))
                self.pipe_results_table.setItem(row, col, item)

    def _on_slurry_toggle(self, checked):
        # Toggle only flips the mode -- parameters are edited through
        # Analysis > Slurry Parameters... Previously the dialog was popped
        # from here, which froze headless tests and made the toggle modal.
        if checked:
            p = self._slurry_params
            self.status_bar.showMessage(
                f"Slurry mode ON (tau_y={p['yield_stress']:.1f} Pa, "
                f"mu_p={p['plastic_viscosity']:.3f} Pa.s, "
                f"rho={p['density']:.0f} kg/m3). "
                f"Edit via Analysis > Slurry Parameters...", 5000)
        self._update_status_bar()

    def _on_edit_slurry_params(self):
        """Open the slurry parameter editor dialog."""
        from desktop.slurry_params_dialog import SlurryParamsDialog
        dlg = SlurryParamsDialog(initial=self._slurry_params, parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._slurry_params = dlg.params()
            p = self._slurry_params
            self.status_bar.showMessage(
                f"Slurry parameters updated: tau_y={p['yield_stress']:.1f} Pa, "
                f"mu_p={p['plastic_viscosity']:.3f} Pa.s, "
                f"rho={p['density']:.0f} kg/m3", 5000)

    # =====================================================================
    # DEMAND PATTERNS / EPS
    # =====================================================================

    def _on_pipe_profile(self):
        """Open pipe profile longitudinal section dialog."""
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
        dialog = PipeProfileDialog(self.api, results=self._last_results, parent=self)
        dialog.exec()

    def _on_safety_case(self):
        """Open the Safety Case Report dialog."""
        if self.api.wn is None:
            QMessageBox.warning(
                self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
        from desktop.safety_case_dialog import SafetyCaseDialog
        dialog = SafetyCaseDialog(self.api, parent=self)
        dialog.exec()

    def _on_design_compliance_check(self):
        """Run all compliance checks and show certificate."""
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
        from desktop.compliance_dialog import ComplianceDialog
        dialog = ComplianceDialog(self.api, parent=self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()

    def _on_quick_assessment(self):
        """Run quick assessment and show results."""
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
        result = self.api.quick_assessment()
        if 'error' in result:
            QMessageBox.warning(self, "Error", result['error'])
            return

        lines = [f"Quick Assessment: {result['network_name']}\n"]

        s = result.get('summary', {})
        lines.append(f"Network: {s.get('junctions', 0)} junctions, "
                     f"{s.get('pipes', 0)} pipes, {s.get('pumps', 0)} pumps")

        t = result.get('topology', {})
        if 'error' not in t:
            lines.append(f"Topology: {t.get('loops', 0)} loops, "
                        f"{t.get('dead_end_count', 0)} dead ends, "
                        f"{t.get('bridge_count', 0)} bridges")

        ri = result.get('resilience', {})
        if 'error' not in ri:
            lines.append(f"Resilience: {ri.get('resilience_index', 0):.3f} "
                        f"(Grade {ri.get('grade', '?')})")

        qs = result.get('quality_score', {})
        if 'error' not in qs:
            lines.append(f"Quality: {qs.get('total_score', 0):.0f}/100 "
                        f"(Grade {qs.get('grade', '?')})")

        # Materials
        mats = result.get('material_inventory', {})
        if mats:
            lines.append(f"\nMaterials: " + ", ".join(
                f"{k}: {v}" for k, v in mats.items() if v > 0))

        # Recommendations
        recs = result.get('recommendations', [])
        if recs:
            lines.append(f"\nRecommendations:")
            for r in recs:
                lines.append(f"  - {r}")

        QMessageBox.information(self, "Quick Assessment", '\n'.join(lines))

    def _on_diagnostics(self):
        """Run network diagnostics."""
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
        result = self.api.diagnose_network()
        if 'error' in result:
            QMessageBox.warning(self, "Error", result['error'])
            return
        # Build readable report
        lines = [f"Network Diagnostics: {result['summary']}\n"]
        for issue in result['issues']:
            lines.append(f"[{issue['severity']}] {issue['message']}")
            lines.append(f"  Suggestion: {issue['suggestion']}\n")
        if not result['issues']:
            lines.append("No issues detected — network appears healthy.")
        QMessageBox.information(self, "Network Diagnostics", '\n'.join(lines))

    def _on_topology(self):
        """Run topology analysis."""
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
        result = self.api.analyse_topology()
        if 'error' in result:
            QMessageBox.warning(self, "Error", result['error'])
            return
        lines = [
            f"Nodes: {result['total_nodes']}  |  Pipes: {result['total_pipes']}",
            f"Dead ends: {result['dead_end_count']}  |  Bridges: {result['bridge_count']}",
            f"Independent loops: {result['loops']}  |  Components: {result['connected_components']}",
            f"Connectivity ratio: {result['connectivity_ratio']}",
            f"Avg node degree: {result['avg_node_degree']}",
            f"Sources: {', '.join(result['sources'])}",
        ]
        if result['isolated_count'] > 0:
            lines.append(f"\nIsolated nodes ({result['isolated_count']}): "
                        f"{', '.join(result['isolated_nodes'][:10])}")
        if result['dead_end_count'] > 0:
            lines.append(f"\nDead ends: {', '.join(result['dead_ends'][:10])}")
        QMessageBox.information(self, "Topology Analysis", '\n'.join(lines))

    def _on_calibration(self):
        """Open the Calibration Tools dialog."""
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
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

    def _on_export_bundle(self):
        """Export project as .hydraulic bundle."""
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Open a network first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Project Bundle", "",
            "Hydraulic Bundle (*.hydraulic);;All Files (*)")
        if not path:
            return
        try:
            self.api.export_bundle(
                path, inp_path=self._current_file,
                hap_data={'settings': {'slurry_mode': self.slurry_act.isChecked()}},
            )
            QMessageBox.information(self, "Export Complete",
                f"Project bundle saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _on_import_bundle(self):
        """Import a .hydraulic project bundle."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Project Bundle", "",
            "Hydraulic Bundle (*.hydraulic);;ZIP Files (*.zip);;All Files (*)")
        if not path:
            return
        try:
            result = self.api.import_bundle(path)
            inp = result.get('inp_path')
            if inp and os.path.exists(inp):
                self.api.load_network_from_path(inp)
                self._current_file = inp
                self._populate_explorer()
                self._update_status_bar()
                self.canvas.set_api(self.api)
                self.what_if_panel.set_api(self.api)
                self.setWindowTitle(
                    f"Hydraulic Analysis Tool v2.9.0 — {os.path.basename(inp)}")
                QMessageBox.information(self, "Import Complete",
                    f"Loaded network from bundle:\n{os.path.basename(inp)}")
            else:
                QMessageBox.warning(self, "No Network in Bundle",
                    "The bundle did not contain an .inp network file.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

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

    def _on_schedule_reports(self):
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network",
                "No network loaded. Use File > Open (Ctrl+O) to load an .inp file.")
            return
        dialog = ReportSchedulerDialog(self.api, parent=self)
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

    def _on_run_demo(self):
        """One-click guided demo: load demo network → steady → show violations."""
        import os
        from PyQt6.QtCore import QTimer

        demo_inp = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'tutorials', 'demo_network', 'network.inp')
        if not os.path.exists(demo_inp):
            QMessageBox.warning(
                self, "Demo Network Missing",
                "Demo network not found at tutorials/demo_network/network.inp.\n"
                "Fix: reinstall or check the tutorials/ directory.")
            return

        steps = []
        def _step1():
            self.statusBar().showMessage(
                "Demo step 1/4: Loading demo network...")
            self.api.load_network(demo_inp)
            if hasattr(self, '_refresh_after_load'):
                self._refresh_after_load()
            elif hasattr(self, 'load_network_file'):
                try:
                    self.load_network_file(demo_inp)
                except (OSError, ValueError) as e:
                    logger.warning("Demo load fallback failed: %s", e)

        def _step2():
            self.statusBar().showMessage(
                "Demo step 2/4: Running steady-state analysis...")
            try:
                self._demo_results = self.api.run_steady_state(save_plot=False)
            except Exception as e:
                self.statusBar().showMessage(
                    f"Demo analysis failed: {e}")
                return

        def _step3():
            if not hasattr(self, '_demo_results'):
                return
            n_violations = len(self._demo_results.get('compliance', []))
            self.statusBar().showMessage(
                f"Demo step 3/4: Found {n_violations} WSAA violations. "
                f"See Learning Mode for explanations.")

        def _step4():
            # Present summary and root-cause
            summary = self.api.network_health_summary()
            rc = self.api.root_cause_analysis(self._demo_results)
            lines = [summary.get('summary_paragraph', '')]
            lines.append('')
            lines.append(f"Root cause analysis found {rc['n_issues']} issues:")
            for exp in rc['explanations'][:3]:
                lines.append(f"  - {exp['issue'].replace('_', ' ').title()} "
                             f"at {exp['location']}")
                if exp['fixes']:
                    lines.append(f"    Fix 1: {exp['fixes'][0]['option']} "
                                 f"(~${exp['fixes'][0]['est_cost_aud']:,})")
            self.statusBar().showMessage(
                "Demo step 4/4: Complete. See message for details.")
            QMessageBox.information(
                self, "Demo — Analysis Summary", '\n'.join(lines))

        # Chain steps with 500ms delays
        self._demo_step_num = 0
        self._demo_steps = [_step1, _step2, _step3, _step4]

        def _run_next():
            if self._demo_step_num >= len(self._demo_steps):
                return
            self._demo_steps[self._demo_step_num]()
            self._demo_step_num += 1
            if self._demo_step_num < len(self._demo_steps):
                QTimer.singleShot(500, _run_next)

        _run_next()

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
        except (KeyError, AttributeError):
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
            self.setWindowTitle(f"Hydraulic Analysis Tool v2.9.0 — {os.path.basename(path)}")
            self.canvas.set_api(self.api)
            self.what_if_panel.set_api(self.api)
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
                    self.setWindowTitle(f"Hydraulic Analysis Tool v2.9.0 — {os.path.basename(path)}")
                    self.canvas.set_api(self.api)
                    self.what_if_panel.set_api(self.api)
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
        """Save preferences and clean up running workers on close."""
        # Stop any running analysis worker to avoid dangling threads
        if hasattr(self, '_worker') and self._worker is not None and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(1000)
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
                self.what_if_panel.set_api(self.api)
                self.setWindowTitle(
                    f"Hydraulic Analysis Tool v2.9.0 — {os.path.basename(last_file)}")
            except (OSError, ValueError) as e:
                logger.info("Could not restore last session: %s", e)
        w = prefs.get('window_width')
        h = prefs.get('window_height')
        if w and h:
            self.resize(w, h)
        if prefs.get('slurry_mode'):
            self.slurry_act.setChecked(True)
        cm = prefs.get('colour_mode')
        if cm and cm in self.canvas.COLOR_MODES:
            self.canvas.color_mode_combo.setCurrentText(cm)

    def show_welcome_if_needed(self):
        """Show welcome dialog on first launch when no network is loaded."""
        if self.api.wn is not None:
            return  # Network already loaded from session restore
        from desktop.preferences import get_pref, set_pref
        if get_pref('skip_welcome', False):
            return

        from desktop.welcome_dialog import WelcomeDialog
        dlg = WelcomeDialog(parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            if dlg.skip_next_time():
                set_pref('skip_welcome', True)
            if dlg.choice == WelcomeDialog.DEMO:
                demo_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'tutorials', 'demo_network', 'network.inp')
                if os.path.exists(demo_path):
                    self.api.load_network_from_path(demo_path)
                    self._current_file = demo_path
                    self._last_results = None
                    self._populate_explorer()
                    self._update_status_bar()
                    self.canvas.set_api(self.api)
                    self.dashboard_widget.update_dashboard(self.api)
                    self.what_if_panel.set_api(self.api)
                    self.setWindowTitle(
                        f"Hydraulic Analysis Tool v2.9.0 — network.inp")
            elif dlg.choice == WelcomeDialog.OPEN:
                self._on_open_inp()
            elif dlg.choice == WelcomeDialog.TUTORIALS:
                tut_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'tutorials')
                if os.path.isdir(tut_dir):
                    import subprocess
                    subprocess.Popen(['explorer', tut_dir])

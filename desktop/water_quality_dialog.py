"""
Water Quality Modelling Dialog
================================
Three-tab dialog for WNTR-based water quality analysis:
  - Water Age   : AGE simulation, flags > 24 hrs stagnation
  - Chlorine    : CHEMICAL decay simulation, WSAA min 0.2 mg/L compliance
  - Trace       : TRACE simulation from a selected source reservoir

All analyses run through HydraulicAPI — UI code never imports WNTR directly.
Results are reported in SI units: hours for age, mg/L for chlorine, % for trace.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTabWidget, QWidget, QLabel, QPushButton, QComboBox,
    QDoubleSpinBox, QTableWidget, QTableWidgetItem,
    QGroupBox, QApplication, QProgressBar, QHeaderView,
    QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


# ---------------------------------------------------------------------------
# Colour constants (Catppuccin-style, matching existing dialogs)
# ---------------------------------------------------------------------------
_COL_PASS = QColor("#a6e3a1")    # green
_COL_WARN = QColor("#f9e2af")    # yellow
_COL_FAIL = QColor("#f38ba8")    # red
_COL_INFO = QColor("#89b4fa")    # blue

_MONO_FONT = QFont("Consolas", 9)
_HEADER_FONT = QFont("Consolas", 10)


class WaterQualityDialog(QDialog):
    """
    Water Quality Modelling Dialog.

    Parameters
    ----------
    api : HydraulicAPI
        Loaded API instance (api.wn must not be None).
    canvas : NetworkCanvas or None
        If supplied, results can be projected as a colour variable.
    mode : str
        Opening tab — 'age', 'chlorine', or 'trace'.
    parent : QWidget or None
    """

    MODES = ('age', 'chlorine', 'trace')

    def __init__(self, api, canvas=None, mode='age', parent=None):
        super().__init__(parent)
        self.api = api
        self.canvas = canvas
        self._results = None

        self.setWindowTitle("Water Quality Analysis")
        self.setMinimumSize(720, 580)
        self.resize(760, 640)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ---- Tab widget --------------------------------------------------
        self.tabs = QTabWidget()
        self.tabs.setFont(_HEADER_FONT)

        self._age_tab = self._build_age_tab()
        self._chlorine_tab = self._build_chlorine_tab()
        self._trace_tab = self._build_trace_tab()

        self.tabs.addTab(self._age_tab, "Water Age")
        self.tabs.addTab(self._chlorine_tab, "Chlorine Decay")
        self.tabs.addTab(self._trace_tab, "Trace")
        layout.addWidget(self.tabs)

        # ---- Progress bar ------------------------------------------------
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)   # indeterminate
        self.progress.setMaximumHeight(14)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # ---- Summary label -----------------------------------------------
        self.summary_label = QLabel("")
        self.summary_label.setFont(_HEADER_FONT)
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        # ---- Results table -----------------------------------------------
        self.results_table = QTableWidget(0, 4)
        self.results_table.setFont(_MONO_FONT)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.results_table, stretch=1)

        # ---- Bottom buttons ----------------------------------------------
        btn_row = QHBoxLayout()

        self.run_btn = QPushButton("Run Analysis")
        self.run_btn.setFont(_HEADER_FONT)
        self.run_btn.setMinimumHeight(32)
        self.run_btn.clicked.connect(self._on_run)
        btn_row.addWidget(self.run_btn)

        self.show_canvas_btn = QPushButton("Show on Canvas")
        self.show_canvas_btn.setFont(_HEADER_FONT)
        self.show_canvas_btn.setEnabled(False)
        self.show_canvas_btn.clicked.connect(self._on_show_canvas)
        btn_row.addWidget(self.show_canvas_btn)

        close_btn = QPushButton("Close")
        close_btn.setFont(_HEADER_FONT)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

        # Select initial tab
        try:
            idx = self.MODES.index(mode)
        except ValueError:
            idx = 0
        self.tabs.setCurrentIndex(idx)

    # ======================================================================
    # Tab construction
    # ======================================================================

    def _build_age_tab(self):
        """Water Age tab — parameters + reference."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)

        params_group = QGroupBox("Simulation Parameters")
        form = QFormLayout()

        self.age_duration_spin = QDoubleSpinBox()
        self.age_duration_spin.setRange(1, 720)
        self.age_duration_spin.setValue(72)
        self.age_duration_spin.setSuffix(" hrs")
        self.age_duration_spin.setFont(_MONO_FONT)
        form.addRow("Simulation Duration:", self.age_duration_spin)

        params_group.setLayout(form)
        layout.addWidget(params_group)

        ref = QLabel(
            "Reference: WSAA — water age > 24 hrs indicates stagnation risk.\n"
            "A 72-hour simulation allows the network to reach a repeating "
            "daily cycle; maximum age at each junction is reported."
        )
        ref.setFont(_MONO_FONT)
        ref.setStyleSheet("color: #a6adc8;")
        ref.setWordWrap(True)
        layout.addWidget(ref)
        layout.addStretch()
        return tab

    def _build_chlorine_tab(self):
        """Chlorine Decay tab — initial concentration, bulk/wall coefficients."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)

        params_group = QGroupBox("Chlorine Decay Parameters")
        form = QFormLayout()

        self.cl_init_spin = QDoubleSpinBox()
        self.cl_init_spin.setRange(0.0, 10.0)
        self.cl_init_spin.setDecimals(2)
        self.cl_init_spin.setValue(0.5)
        self.cl_init_spin.setSuffix(" mg/L")
        self.cl_init_spin.setFont(_MONO_FONT)
        form.addRow("Initial Concentration:", self.cl_init_spin)

        self.cl_bulk_spin = QDoubleSpinBox()
        self.cl_bulk_spin.setRange(-50.0, 0.0)
        self.cl_bulk_spin.setDecimals(3)
        self.cl_bulk_spin.setValue(-0.5)
        self.cl_bulk_spin.setSuffix(" /hr")
        self.cl_bulk_spin.setFont(_MONO_FONT)
        form.addRow("Bulk Decay Coefficient:", self.cl_bulk_spin)

        self.cl_wall_spin = QDoubleSpinBox()
        self.cl_wall_spin.setRange(-10.0, 0.0)
        self.cl_wall_spin.setDecimals(4)
        self.cl_wall_spin.setValue(-0.01)
        self.cl_wall_spin.setSuffix(" m/hr")
        self.cl_wall_spin.setFont(_MONO_FONT)
        form.addRow("Wall Decay Coefficient:", self.cl_wall_spin)

        self.cl_duration_spin = QDoubleSpinBox()
        self.cl_duration_spin.setRange(1, 720)
        self.cl_duration_spin.setValue(72)
        self.cl_duration_spin.setSuffix(" hrs")
        self.cl_duration_spin.setFont(_MONO_FONT)
        form.addRow("Simulation Duration:", self.cl_duration_spin)

        params_group.setLayout(form)
        layout.addWidget(params_group)

        ref = QLabel(
            "Reference: WSAA WSA 03-2011 — minimum chlorine residual 0.2 mg/L.\n"
            "Negative coefficients indicate first-order decay. "
            "Bulk applies throughout the water volume; wall applies at pipe surfaces."
        )
        ref.setFont(_MONO_FONT)
        ref.setStyleSheet("color: #a6adc8;")
        ref.setWordWrap(True)
        layout.addWidget(ref)
        layout.addStretch()
        return tab

    def _build_trace_tab(self):
        """Trace tab — source node selection."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)

        params_group = QGroupBox("Trace Parameters")
        form = QFormLayout()

        self.trace_source_combo = QComboBox()
        self.trace_source_combo.setFont(_MONO_FONT)
        # Populate with all reservoirs and tanks as valid trace sources
        for rid in sorted(self.api.wn.reservoir_name_list if self.api.wn else []):
            self.trace_source_combo.addItem(f"{rid} (reservoir)")
        for tid in sorted(self.api.wn.tank_name_list if self.api.wn else []):
            self.trace_source_combo.addItem(f"{tid} (tank)")
        form.addRow("Source Node:", self.trace_source_combo)

        self.trace_duration_spin = QDoubleSpinBox()
        self.trace_duration_spin.setRange(1, 720)
        self.trace_duration_spin.setValue(72)
        self.trace_duration_spin.setSuffix(" hrs")
        self.trace_duration_spin.setFont(_MONO_FONT)
        form.addRow("Simulation Duration:", self.trace_duration_spin)

        params_group.setLayout(form)
        layout.addWidget(params_group)

        ref = QLabel(
            "Trace analysis shows what percentage of water at each junction "
            "originates from the selected source. "
            "Useful for blended supply or mixing zone studies."
        )
        ref.setFont(_MONO_FONT)
        ref.setStyleSheet("color: #a6adc8;")
        ref.setWordWrap(True)
        layout.addWidget(ref)
        layout.addStretch()
        return tab

    # ======================================================================
    # Run button handler — dispatches to correct mode
    # ======================================================================

    def _on_run(self):
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network", "Load a network first.")
            return

        mode_idx = self.tabs.currentIndex()
        mode = self.MODES[mode_idx]

        self.progress.setVisible(True)
        self.run_btn.setEnabled(False)
        self.show_canvas_btn.setEnabled(False)
        self.results_table.setRowCount(0)
        self.summary_label.setText("Running analysis…")
        QApplication.processEvents()

        try:
            if mode == 'age':
                self._run_age()
            elif mode == 'chlorine':
                self._run_chlorine()
            elif mode == 'trace':
                self._run_trace()
        except Exception as exc:
            QMessageBox.critical(self, "Analysis Error",
                                 f"Analysis failed.\n\n{type(exc).__name__}: {exc}")
            self.summary_label.setText("Analysis failed — see error dialog.")
        finally:
            self.progress.setVisible(False)
            self.run_btn.setEnabled(True)

    def _run_age(self):
        duration = self.age_duration_spin.value()
        results = self.api.run_water_quality(
            parameter='age', duration_hrs=duration, save_plot=False
        )
        if 'error' in results:
            QMessageBox.critical(self, "Water Age Error", results['error'])
            return

        self._results = results
        jq = results.get('junction_quality', {})
        n_stagnant = len(results.get('stagnation_risk', []))
        n_total = len(jq)

        # ---- Populate results table ----
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels([
            "Junction", "Max Age (hrs)", "Avg Age (hrs)", "Status"
        ])
        self.results_table.setRowCount(0)

        for junc, vals in sorted(jq.items()):
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)

            max_a = vals['max_age_hrs']
            avg_a = vals['avg_age_hrs']
            is_stagnant = max_a > 24.0

            _set_cell(self.results_table, row, 0, junc)
            _set_cell(self.results_table, row, 1, f"{max_a:.1f} hrs")
            _set_cell(self.results_table, row, 2, f"{avg_a:.1f} hrs")

            status = "STAGNATION RISK" if is_stagnant else "OK"
            status_item = QTableWidgetItem(status)
            colour = _COL_WARN if is_stagnant else _COL_PASS
            status_item.setBackground(colour)
            self.results_table.setItem(row, 3, status_item)

        self.results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.results_table.horizontalHeader().setStretchLastSection(True)

        # ---- Summary ----
        if n_stagnant == 0:
            msg = f"PASS — All {n_total} junctions have water age <= 24 hrs."
            self.summary_label.setStyleSheet("color: #a6e3a1;")
        else:
            msg = (f"WARNING — {n_stagnant} / {n_total} junction(s) have "
                   f"water age > 24 hrs (stagnation risk).")
            self.summary_label.setStyleSheet("color: #f9e2af;")
        self.summary_label.setText(msg)
        self.show_canvas_btn.setEnabled(self.canvas is not None)

    def _run_chlorine(self):
        results = self.api.run_water_quality_chlorine(
            initial_conc=self.cl_init_spin.value(),
            bulk_coeff=self.cl_bulk_spin.value(),
            wall_coeff=self.cl_wall_spin.value(),
            duration_hrs=self.cl_duration_spin.value(),
            save_plot=False,
        )
        if 'error' in results:
            QMessageBox.critical(self, "Chlorine Error", results['error'])
            return

        self._results = results
        jq = results.get('junction_quality', {})
        non_compliant = results.get('non_compliant', [])
        n_total = len(jq)
        n_fail = len(non_compliant)

        # ---- Populate results table ----
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels([
            "Junction", "Min (mg/L)", "Avg (mg/L)", "Status"
        ])
        self.results_table.setRowCount(0)

        for junc, vals in sorted(jq.items()):
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)

            min_c = vals['min_conc']
            avg_c = vals['avg_conc']
            fails = junc in non_compliant

            _set_cell(self.results_table, row, 0, junc)
            _set_cell(self.results_table, row, 1, f"{min_c:.3f}")
            _set_cell(self.results_table, row, 2, f"{avg_c:.3f}")

            # WSAA WSA 03-2011: minimum 0.2 mg/L
            status = "< 0.2 mg/L FAIL" if fails else "OK"
            status_item = QTableWidgetItem(status)
            colour = _COL_FAIL if fails else _COL_PASS
            status_item.setBackground(colour)
            self.results_table.setItem(row, 3, status_item)

        self.results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.results_table.horizontalHeader().setStretchLastSection(True)

        # ---- Summary ----
        if n_fail == 0:
            msg = (f"PASS — All {n_total} junctions meet 0.2 mg/L chlorine residual "
                   f"(WSAA WSA 03-2011).")
            self.summary_label.setStyleSheet("color: #a6e3a1;")
        else:
            msg = (f"FAIL — {n_fail} / {n_total} junction(s) below 0.2 mg/L "
                   f"chlorine residual (WSAA WSA 03-2011).")
            self.summary_label.setStyleSheet("color: #f38ba8;")
        self.summary_label.setText(msg)
        self.show_canvas_btn.setEnabled(self.canvas is not None)

    def _run_trace(self):
        combo_text = self.trace_source_combo.currentText()
        if not combo_text:
            QMessageBox.warning(self, "No Source",
                                "No source nodes available in this network.")
            return

        # Strip "(reservoir)" / "(tank)" suffix
        source = combo_text.split()[0]
        duration = self.trace_duration_spin.value()

        results = self.api.run_water_quality_trace(
            source_node=source, duration_hrs=duration, save_plot=False
        )
        if 'error' in results:
            QMessageBox.critical(self, "Trace Error", results['error'])
            return

        self._results = results
        jq = results.get('junction_quality', {})
        n_total = len(jq)

        # ---- Populate results table ----
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels([
            "Junction", "Min (%)", "Avg (%)", "Max (%)"
        ])
        self.results_table.setRowCount(0)

        for junc, vals in sorted(jq.items()):
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            _set_cell(self.results_table, row, 0, junc)
            _set_cell(self.results_table, row, 1, f"{vals['min_pct']:.1f}")
            _set_cell(self.results_table, row, 2, f"{vals['avg_pct']:.1f}")
            _set_cell(self.results_table, row, 3, f"{vals['max_pct']:.1f}")

        self.results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.results_table.horizontalHeader().setStretchLastSection(True)

        # ---- Summary ----
        msg = (f"Trace from '{source}' — {n_total} junctions analysed. "
               f"Values show % of water originating from source.")
        self.summary_label.setStyleSheet("color: #89b4fa;")
        self.summary_label.setText(msg)
        self.show_canvas_btn.setEnabled(self.canvas is not None)

    # ======================================================================
    # Show on canvas
    # ======================================================================

    def _on_show_canvas(self):
        """Project results onto the network canvas via canvas.set_variable()."""
        if self._results is None or self.canvas is None:
            return

        mode_idx = self.tabs.currentIndex()
        mode = self.MODES[mode_idx]
        jq = self._results.get('junction_quality', {})

        if mode == 'age':
            # Map max age (hours) per junction
            data = {jid: v['max_age_hrs'] for jid, v in jq.items()}
            self.canvas.set_variable("Water Age (hrs)", data)
        elif mode == 'chlorine':
            # Map minimum chlorine concentration (mg/L) per junction
            data = {jid: v['min_conc'] for jid, v in jq.items()}
            self.canvas.set_variable("Chlorine Min (mg/L)", data)
        elif mode == 'trace':
            # Map average trace percentage per junction
            data = {jid: v['avg_pct'] for jid, v in jq.items()}
            source = self._results.get('source_node', 'source')
            self.canvas.set_variable(f"Trace from {source} (%)", data)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_cell(table, row, col, text):
    """Insert a non-editable QTableWidgetItem."""
    item = QTableWidgetItem(str(text))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    table.setItem(row, col, item)

"""
Calibration Tools Dialog
=========================
Import measured pressure data (CSV) and compare against model results.
Provides scatter plot, statistics, and canvas highlight of poorly calibrated nodes.

CSV format: node_id, pressure_m
"""

import math
import csv

import logging

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QGroupBox, QFormLayout, QFileDialog, QMessageBox,
    QWidget, QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

try:
    import pyqtgraph as pg
    _HAS_PYQTGRAPH = True
except ImportError:
    _HAS_PYQTGRAPH = False


# ─────────────────────────────────────────────────────────────────────────────
# Pure statistical functions (no Qt — importable for tests)
# ─────────────────────────────────────────────────────────────────────────────

def compute_r2(measured: list[float], modelled: list[float]) -> float:
    """
    Coefficient of determination (R²).
    R² = 1 - SS_res / SS_tot
    where SS_res = sum((measured - modelled)²),
          SS_tot = sum((measured - mean_measured)²)
    """
    n = len(measured)
    if n == 0:
        return float('nan')
    mean_m = sum(measured) / n
    ss_res = sum((o - p) ** 2 for o, p in zip(measured, modelled))
    ss_tot = sum((o - mean_m) ** 2 for o in measured)
    if ss_tot == 0.0:
        return 1.0 if ss_res == 0.0 else 0.0
    return 1.0 - ss_res / ss_tot


def compute_rmse(measured: list[float], modelled: list[float]) -> float:
    """
    Root Mean Square Error (metres).
    RMSE = sqrt(mean((measured - modelled)²))
    """
    n = len(measured)
    if n == 0:
        return float('nan')
    mse = sum((o - p) ** 2 for o, p in zip(measured, modelled)) / n
    return math.sqrt(mse)


def compute_nse(measured: list[float], modelled: list[float]) -> float:
    """
    Nash-Sutcliffe Efficiency.
    NSE = 1 - SS_res / SS_tot (same formula as R² when comparing measured vs modelled).
    """
    return compute_r2(measured, modelled)


# ─────────────────────────────────────────────────────────────────────────────
# Dialog
# ─────────────────────────────────────────────────────────────────────────────

class CalibrationDialog(QDialog):
    """Pressure calibration tool — compare measured vs modelled node pressures."""

    # Status thresholds (metres)
    WARN_THRESH = 2.0   # diff >= 2 m → WARNING
    FAIL_THRESH = 5.0   # diff >= 5 m → FAIL

    def __init__(self, api, canvas=None, parent=None):
        super().__init__(parent)
        self.api = api
        self.canvas = canvas

        # {node_id: (measured_m, modelled_m)}
        self._data: dict[str, tuple[float, float]] = {}

        self.setWindowTitle("Calibration Tools")
        self.setMinimumSize(900, 650)

        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)

        # ── Top toolbar ──────────────────────────────────────────────────────
        toolbar = QHBoxLayout()

        self.import_btn = QPushButton("Import Measured Data (CSV)...")
        self.import_btn.setFont(QFont("Consolas", 10))
        self.import_btn.clicked.connect(self._on_import)
        toolbar.addWidget(self.import_btn)

        self.highlight_btn = QPushButton("Highlight on Canvas")
        self.highlight_btn.setFont(QFont("Consolas", 10))
        self.highlight_btn.setToolTip(
            "Mark nodes with > 2 m pressure discrepancy on the network canvas."
        )
        self.highlight_btn.setEnabled(False)
        self.highlight_btn.clicked.connect(self._on_highlight)
        toolbar.addWidget(self.highlight_btn)

        self.auto_cal_btn = QPushButton("Auto-Calibrate Roughness")
        self.auto_cal_btn.setFont(QFont("Consolas", 10))
        self.auto_cal_btn.setToolTip(
            "Optimise Hazen-Williams C-factors by material group to minimise\n"
            "pressure residuals. Requires measured data loaded first.\n"
            "Uses scipy.optimize.minimize (L-BFGS-B)."
        )
        self.auto_cal_btn.setEnabled(False)
        self.auto_cal_btn.clicked.connect(self._on_auto_calibrate)
        toolbar.addWidget(self.auto_cal_btn)

        toolbar.addStretch()
        root.addLayout(toolbar)

        # ── Main splitter: left = table + stats, right = scatter plot ────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)

        # Comparison table
        table_label = QLabel("Pressure Comparison")
        table_label.setFont(QFont("Consolas", 10))
        left_layout.addWidget(table_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Node ID", "Measured (m)", "Modelled (m)", "Difference (m)", "Status"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setFont(QFont("Consolas", 9))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        left_layout.addWidget(self.table)

        # Statistics panel
        stats_group = QGroupBox("Calibration Statistics")
        stats_form = QFormLayout()
        stats_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def _stat_label(text="—"):
            lbl = QLabel(text)
            lbl.setFont(QFont("Consolas", 10))
            return lbl

        self.lbl_r2 = _stat_label()
        self.lbl_rmse = _stat_label()
        self.lbl_nse = _stat_label()
        self.lbl_n_points = _stat_label()
        self.lbl_n_within = _stat_label()

        stats_form.addRow("R²:", self.lbl_r2)
        stats_form.addRow("RMSE (m):", self.lbl_rmse)
        stats_form.addRow("Nash-Sutcliffe Efficiency:", self.lbl_nse)
        stats_form.addRow("Number of points:", self.lbl_n_points)
        stats_form.addRow("Points within ±2 m:", self.lbl_n_within)

        stats_group.setLayout(stats_form)
        left_layout.addWidget(stats_group)

        splitter.addWidget(left)

        # Right panel — scatter plot
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)

        scatter_label = QLabel("Measured vs Modelled Pressure (m)")
        scatter_label.setFont(QFont("Consolas", 10))
        right_layout.addWidget(scatter_label)

        if _HAS_PYQTGRAPH:
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.setBackground("#1e1e2e")
            self.plot_widget.setLabel("bottom", "Measured (m)")
            self.plot_widget.setLabel("left", "Modelled (m)")
            self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
            right_layout.addWidget(self.plot_widget)
        else:
            no_pg = QLabel("pyqtgraph not available — scatter plot disabled.")
            no_pg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_pg.setFont(QFont("Consolas", 10))
            right_layout.addWidget(no_pg)
            self.plot_widget = None

        splitter.addWidget(right)
        splitter.setSizes([480, 400])
        root.addWidget(splitter)

    # ── Import ────────────────────────────────────────────────────────────────

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Measured Pressures", "",
            "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return

        try:
            measured_raw = self._parse_csv(path)
        except (OSError, ValueError, RuntimeError) as e:
            QMessageBox.critical(
                self, "Import Error",
                f"Could not read CSV file.\n\n{type(e).__name__}: {e}"
            )
            return

        if not measured_raw:
            QMessageBox.warning(self, "Empty File", "No data rows found in CSV.")
            return

        # Cross-reference with model results
        self._data = {}
        missing = []
        no_result = []

        results = None
        # Try to get modelled pressures from the API
        try:
            raw = self.api.get_steady_results()
            if raw is not None and 'pressure' in raw.node.columns.tolist() or (
                raw is not None and hasattr(raw, 'node')
            ):
                # Multi-timestep: use mean pressure
                import numpy as np
                pressure_df = raw.node['pressure']
                results = {nid: float(pressure_df[nid].mean())
                           for nid in pressure_df.columns}
        except (KeyError, AttributeError, ValueError):
            pass

        for node_id, meas_val in measured_raw.items():
            # Check node exists in model
            try:
                self.api.get_node(node_id)
            except (KeyError, AttributeError, ValueError):
                missing.append(node_id)
                continue

            # Get modelled pressure
            if results and node_id in results:
                modelled_val = results[node_id]
            else:
                no_result.append(node_id)
                modelled_val = float('nan')

            self._data[node_id] = (meas_val, modelled_val)

        # Warn about issues
        warnings = []
        if missing:
            warnings.append(f"Nodes not found in model: {', '.join(missing[:5])}"
                            + (" ..." if len(missing) > 5 else ""))
        if no_result:
            warnings.append(f"No analysis results for: {', '.join(no_result[:5])}"
                            + (" ..." if len(no_result) > 5 else "")
                            + "\nRun a steady-state analysis first.")
        if warnings:
            QMessageBox.warning(self, "Import Warnings", "\n\n".join(warnings))

        self._refresh()

    def _parse_csv(self, path: str) -> dict[str, float]:
        """Parse CSV with columns: node_id, pressure_m.  Returns {node_id: float}."""
        result = {}
        with open(path, newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if not row:
                    continue
                # Skip header row if first column is non-numeric text
                if i == 0:
                    try:
                        float(row[1])
                    except (ValueError, IndexError):
                        continue  # skip header
                if len(row) < 2:
                    continue
                node_id = row[0].strip()
                try:
                    pressure = float(row[1].strip())
                except ValueError:
                    continue
                result[node_id] = pressure
        return result

    # ── Refresh display ───────────────────────────────────────────────────────

    def _refresh(self):
        """Rebuild table, stats, and scatter plot from self._data."""
        self._populate_table()
        self._update_stats()
        self._update_plot()
        self.highlight_btn.setEnabled(bool(self._data))
        self.auto_cal_btn.setEnabled(bool(self._data))

    def _populate_table(self):
        self.table.setRowCount(0)

        for node_id, (meas, mod) in sorted(self._data.items()):
            row = self.table.rowCount()
            self.table.insertRow(row)

            if math.isnan(mod):
                diff = float('nan')
                status = "NO DATA"
                status_color = QColor(137, 137, 180)  # muted purple
            else:
                diff = mod - meas
                abs_diff = abs(diff)
                if abs_diff < self.WARN_THRESH:
                    status = "OK"
                    status_color = QColor(166, 227, 161)   # green
                elif abs_diff < self.FAIL_THRESH:
                    status = "WARNING"
                    status_color = QColor(249, 226, 175)   # yellow
                else:
                    status = "FAIL"
                    status_color = QColor(243, 139, 168)   # red

            cells = [
                node_id,
                f"{meas:.1f}" if not math.isnan(meas) else "—",
                f"{mod:.1f}" if not math.isnan(mod) else "—",
                f"{diff:+.1f}" if not math.isnan(diff) else "—",
                status,
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 4:  # Status column gets colour
                    item.setForeground(status_color)
                self.table.setItem(row, col, item)

    def _update_stats(self):
        # Filter to entries with valid modelled data
        valid = [(m, p) for m, p in self._data.values()
                 if not math.isnan(m) and not math.isnan(p)]

        if not valid:
            for lbl in (self.lbl_r2, self.lbl_rmse, self.lbl_nse,
                        self.lbl_n_points, self.lbl_n_within):
                lbl.setText("—")
            return

        measured = [v[0] for v in valid]
        modelled = [v[1] for v in valid]

        r2 = compute_r2(measured, modelled)
        rmse = compute_rmse(measured, modelled)
        nse = compute_nse(measured, modelled)
        n_within = sum(1 for m, p in valid if abs(p - m) < self.WARN_THRESH)

        self.lbl_r2.setText(f"{r2:.4f}")
        self.lbl_rmse.setText(f"{rmse:.2f} m")
        self.lbl_nse.setText(f"{nse:.4f}")
        self.lbl_n_points.setText(str(len(valid)))
        self.lbl_n_within.setText(f"{n_within} / {len(valid)}")

    def _update_plot(self):
        if self.plot_widget is None:
            return

        self.plot_widget.clear()

        valid = [(m, p) for m, p in self._data.values()
                 if not math.isnan(m) and not math.isnan(p)]
        if not valid:
            return

        measured = [v[0] for v in valid]
        modelled = [v[1] for v in valid]

        all_vals = measured + modelled
        lo = min(all_vals) - 2.0
        hi = max(all_vals) + 2.0

        # 1:1 reference line (perfect calibration)
        ref_line = pg.PlotDataItem(
            [lo, hi], [lo, hi],
            pen=pg.mkPen(color='#cdd6f4', width=1.5, style=Qt.PenStyle.DashLine),
            name="1:1 line",
        )
        self.plot_widget.addItem(ref_line)

        # ±2 m tolerance band
        upper = pg.PlotDataItem(
            [lo, hi], [lo + self.WARN_THRESH, hi + self.WARN_THRESH],
            pen=pg.mkPen(color='#a6e3a1', width=1, style=Qt.PenStyle.DotLine),
            name="+2 m",
        )
        lower = pg.PlotDataItem(
            [lo, hi], [lo - self.WARN_THRESH, hi - self.WARN_THRESH],
            pen=pg.mkPen(color='#a6e3a1', width=1, style=Qt.PenStyle.DotLine),
            name="-2 m",
        )
        self.plot_widget.addItem(upper)
        self.plot_widget.addItem(lower)

        # Data scatter points — colour by status
        ok_x, ok_y = [], []
        warn_x, warn_y = [], []
        fail_x, fail_y = [], []

        for m, p in valid:
            diff = abs(p - m)
            if diff < self.WARN_THRESH:
                ok_x.append(m); ok_y.append(p)
            elif diff < self.FAIL_THRESH:
                warn_x.append(m); warn_y.append(p)
            else:
                fail_x.append(m); fail_y.append(p)

        scatter_cfg = [
            (ok_x, ok_y, '#a6e3a1', 'OK'),
            (warn_x, warn_y, '#f9e2af', 'Warning'),
            (fail_x, fail_y, '#f38ba8', 'Fail'),
        ]
        for xs, ys, colour, label in scatter_cfg:
            if xs:
                scatter = pg.ScatterPlotItem(
                    x=xs, y=ys,
                    pen=pg.mkPen(None),
                    brush=pg.mkBrush(colour),
                    size=9,
                    name=label,
                )
                self.plot_widget.addItem(scatter)

        self.plot_widget.setXRange(lo, hi, padding=0)
        self.plot_widget.setYRange(lo, hi, padding=0)

    # ── Highlight on Canvas ───────────────────────────────────────────────────

    def _on_highlight(self):
        """Push discrepancy values to the canvas via set_variable()."""
        if self.canvas is None:
            QMessageBox.information(
                self, "No Canvas",
                "Canvas is not available in this context."
            )
            return

        # Build {node_id: abs_diff} for nodes with diff > 2 m
        variable_data = {}
        for node_id, (meas, mod) in self._data.items():
            if not math.isnan(meas) and not math.isnan(mod):
                variable_data[node_id] = abs(mod - meas)

        if not variable_data:
            QMessageBox.information(self, "No Data", "No valid data to highlight.")
            return

        self.canvas.set_variable("Calibration Error (m)", variable_data)
        self.status_bar_message = (
            f"Highlighted {len(variable_data)} nodes by calibration error."
        )

    # ── Auto-Calibration ─────────────────────────────────────────────────────

    def _on_auto_calibrate(self):
        """
        Run automatic roughness calibration using scipy.optimize.

        Groups pipes by material, adjusts C-factors to minimise the sum of
        squared pressure residuals between modelled and measured values.
        Ref: WSAA Calibration Guidelines
        """
        if not self._data:
            QMessageBox.warning(self, "No Data",
                "Import measured pressure data first.")
            return

        if self.api.wn is None:
            QMessageBox.warning(self, "No Network", "No network loaded.")
            return

        # Build measured pressures dict
        measured = {}
        for nid, (meas, _mod) in self._data.items():
            if not math.isnan(meas):
                measured[nid] = meas

        if len(measured) < 2:
            QMessageBox.warning(self, "Insufficient Data",
                "Need at least 2 measured pressure points for calibration.")
            return

        # Show progress
        from PyQt6.QtWidgets import QProgressDialog
        progress = QProgressDialog(
            "Optimising roughness...", "Cancel", 0, 0, self)
        progress.setWindowTitle("Auto-Calibration")
        progress.setMinimumDuration(0)
        progress.setValue(0)

        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            result = self.api.auto_calibrate_roughness(measured)
        except (OSError, ValueError, RuntimeError) as e:
            progress.close()
            QMessageBox.critical(self, "Calibration Error",
                f"Optimisation failed: {e}")
            return

        progress.close()

        if 'error' in result:
            QMessageBox.warning(self, "Error", result['error'])
            return

        # Show results
        before = result['before']
        after = result['after']
        groups = result['groups']

        msg_parts = [
            "Auto-Calibration Complete",
            f"Iterations: {result['iterations']}",
            "",
            f"Before: R² = {before['r2']:.4f}, RMSE = {before['rmse']:.2f} m",
            f"After:  R² = {after['r2']:.4f}, RMSE = {after['rmse']:.2f} m",
            "",
            "Roughness adjustments by material group:",
        ]

        for gname, g in groups.items():
            msg_parts.append(
                f"  {gname}: C = {g['C_before']:.0f} → {g['C_after']:.0f} "
                f"({g['n_pipes']} pipes)"
            )

        QMessageBox.information(self, "Auto-Calibration Results",
                                "\n".join(msg_parts))

        # Re-run analysis to get updated modelled values
        try:
            new_results = self.api.run_steady_state(save_plot=False)
            pressures = new_results.get('pressures', {})
            # Update data with new modelled values
            for nid in list(self._data.keys()):
                meas, _ = self._data[nid]
                p = pressures.get(nid, {})
                mod = p.get('avg_m', float('nan'))
                self._data[nid] = (meas, mod)
            self._refresh()
        except (KeyError, AttributeError, ValueError):
            pass  # Non-critical — dialog will refresh on next import

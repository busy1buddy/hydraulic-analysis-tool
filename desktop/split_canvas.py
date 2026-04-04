"""
Split-Screen Scenario Comparison
==================================
Side-by-side dual canvas with linked viewports for comparing
two scenarios or a difference map (A-B).
"""

import numpy as np
import pyqtgraph as pg

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from desktop.network_canvas import NetworkCanvas


class SplitCanvas(QWidget):
    """
    Dual-canvas widget for side-by-side scenario comparison.

    Features:
    - Left canvas: Scenario A results
    - Right canvas: Scenario B results
    - Linked viewports: zoom/pan syncs both canvases
    - Difference mode: RdBu diverging colourmap showing (A-B) values
    """

    closed = pyqtSignal()

    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self._linking = True
        self._syncing = False  # Guard against recursive sync

        self.setWindowTitle("Scenario Comparison")
        self.setMinimumSize(1200, 600)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # --- Toolbar ---
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Left:"))
        self.left_combo = QComboBox()
        self.left_combo.setFont(QFont("Consolas", 9))
        self.left_combo.setMinimumWidth(180)
        toolbar.addWidget(self.left_combo)

        toolbar.addWidget(QLabel("Right:"))
        self.right_combo = QComboBox()
        self.right_combo.setFont(QFont("Consolas", 9))
        self.right_combo.setMinimumWidth(180)
        toolbar.addWidget(self.right_combo)

        self.diff_btn = QPushButton("Difference (A-B)")
        self.diff_btn.setCheckable(True)
        self.diff_btn.setFont(QFont("Consolas", 9))
        self.diff_btn.toggled.connect(self._on_diff_toggled)
        toolbar.addWidget(self.diff_btn)

        self.link_btn = QPushButton("Linked")
        self.link_btn.setCheckable(True)
        self.link_btn.setChecked(True)
        self.link_btn.setFont(QFont("Consolas", 9))
        self.link_btn.toggled.connect(self._on_link_toggled)
        toolbar.addWidget(self.link_btn)

        toolbar.addStretch()

        close_btn = QPushButton("Single View")
        close_btn.setFont(QFont("Consolas", 9))
        close_btn.clicked.connect(self._on_close)
        toolbar.addWidget(close_btn)

        layout.addLayout(toolbar)

        # --- Dual canvases ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left canvas
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_label = QLabel("Scenario A")
        self.left_label.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.left_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_label.setStyleSheet("color: #89b4fa;")
        left_layout.addWidget(self.left_label)
        self.left_canvas = NetworkCanvas()
        left_layout.addWidget(self.left_canvas)
        splitter.addWidget(left_container)

        # Right canvas
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_label = QLabel("Scenario B")
        self.right_label.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.right_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_label.setStyleSheet("color: #a6e3a1;")
        right_layout.addWidget(self.right_label)
        self.right_canvas = NetworkCanvas()
        right_layout.addWidget(self.right_canvas)
        splitter.addWidget(right_container)

        splitter.setSizes([600, 600])
        layout.addWidget(splitter)

        # --- Summary bar ---
        self.summary_label = QLabel("")
        self.summary_label.setFont(QFont("Consolas", 9))
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        # Wire viewport linking
        self._connect_viewports()

    def _connect_viewports(self):
        """Link left and right canvas viewports for sync zoom/pan."""
        self.left_canvas.plot_widget.sigRangeChanged.connect(
            lambda: self._sync_viewport('left'))
        self.right_canvas.plot_widget.sigRangeChanged.connect(
            lambda: self._sync_viewport('right'))

    def _sync_viewport(self, source):
        """Sync the other canvas viewport to match the source."""
        if not self._linking or self._syncing:
            return
        self._syncing = True
        try:
            if source == 'left':
                vr = self.left_canvas.plot_widget.plotItem.vb.viewRange()
                self.right_canvas.plot_widget.plotItem.vb.setRange(
                    xRange=vr[0], yRange=vr[1], padding=0)
            else:
                vr = self.right_canvas.plot_widget.plotItem.vb.viewRange()
                self.left_canvas.plot_widget.plotItem.vb.setRange(
                    xRange=vr[0], yRange=vr[1], padding=0)
        finally:
            self._syncing = False

    def _on_link_toggled(self, checked):
        self._linking = checked
        self.link_btn.setText("Linked" if checked else "Unlinked")

    def _on_diff_toggled(self, checked):
        if checked:
            self._show_difference()
        else:
            # Restore original results on right canvas
            self._restore_right()

    def _on_close(self):
        self.closed.emit()
        self.hide()

    def set_scenarios(self, scenarios):
        """
        Load scenario list into combo boxes.

        Parameters
        ----------
        scenarios : list of ScenarioData
            Each must have .name and .results attributes
        """
        self.left_combo.clear()
        self.right_combo.clear()
        self._scenarios = scenarios

        for sc in scenarios:
            label = f"{sc.name} ({sc.demand_multiplier:.1f}x)"
            self.left_combo.addItem(label)
            self.right_combo.addItem(label)

        if len(scenarios) >= 2:
            self.left_combo.setCurrentIndex(0)
            self.right_combo.setCurrentIndex(1)

        self.left_combo.currentIndexChanged.connect(self._update_canvases)
        self.right_combo.currentIndexChanged.connect(self._update_canvases)

        # Initialize both canvases with the network
        self.left_canvas.set_api(self.api)
        self.right_canvas.set_api(self.api)

        self._update_canvases()

    def _update_canvases(self):
        """Update both canvases with selected scenario results."""
        li = self.left_combo.currentIndex()
        ri = self.right_combo.currentIndex()

        if li < 0 or ri < 0 or not self._scenarios:
            return

        left_sc = self._scenarios[li]
        right_sc = self._scenarios[ri]

        self.left_label.setText(f"A: {left_sc.name}")
        self.right_label.setText(f"B: {right_sc.name}")

        if left_sc.results and 'error' not in left_sc.results:
            self.left_canvas.set_results(left_sc.results)
        if right_sc.results and 'error' not in right_sc.results:
            self.right_canvas.set_results(right_sc.results)
            self._right_original = right_sc.results

        # Update summary
        self._update_summary(left_sc, right_sc)

        # If difference mode is on, recompute
        if self.diff_btn.isChecked():
            self._show_difference()

    def _update_summary(self, left_sc, right_sc):
        """Show key differences between scenarios."""
        if not left_sc.results or not right_sc.results:
            self.summary_label.setText("Run all scenarios before comparing.")
            return

        lp = left_sc.results.get('pressures', {})
        rp = right_sc.results.get('pressures', {})

        if not lp or not rp:
            return

        # Compare min pressures
        common_nodes = set(lp.keys()) & set(rp.keys())
        diffs = []
        for nid in common_nodes:
            la = lp[nid].get('avg_m', 0)
            ra = rp[nid].get('avg_m', 0)
            diffs.append(ra - la)

        if diffs:
            avg_diff = sum(diffs) / len(diffs)
            max_diff = max(diffs, key=abs)
            self.summary_label.setText(
                f"Pressure difference (B-A): avg {avg_diff:+.1f} m, "
                f"max {max_diff:+.1f} m across {len(common_nodes)} nodes"
            )

    def _show_difference(self):
        """Show (A-B) difference on right canvas using RdBu diverging map."""
        li = self.left_combo.currentIndex()
        ri = self.right_combo.currentIndex()

        if li < 0 or ri < 0 or not self._scenarios:
            return

        left_sc = self._scenarios[li]
        right_sc = self._scenarios[ri]

        if not left_sc.results or not right_sc.results:
            return

        lp = left_sc.results.get('pressures', {})
        rp = right_sc.results.get('pressures', {})

        # Compute difference results
        diff_pressures = {}
        for nid in set(lp.keys()) & set(rp.keys()):
            la = lp[nid].get('avg_m', 0)
            ra = rp[nid].get('avg_m', 0)
            d = la - ra  # A - B
            diff_pressures[nid] = {
                'avg_m': d,
                'min_m': d,
                'max_m': d,
            }

        diff_results = {
            'pressures': diff_pressures,
            'flows': {},
            'compliance': [],
        }

        self.right_canvas.set_results(diff_results)
        self.right_label.setText(f"Difference: {left_sc.name} - {right_sc.name}")

    def _restore_right(self):
        """Restore original results on the right canvas."""
        if hasattr(self, '_right_original') and self._right_original:
            self.right_canvas.set_results(self._right_original)
            ri = self.right_combo.currentIndex()
            if ri >= 0 and self._scenarios:
                self.right_label.setText(f"B: {self._scenarios[ri].name}")

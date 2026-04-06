"""
Surge Protection Design Wizard
================================
Recommends surge protection after transient analysis identifies
significant water hammer. Shows vessel sizing, air valve placement,
and slow-closing valve specifications.

Ref: AS/NZS 2566, Wylie & Streeter (1993), Thorley (2004)
"""

import logging

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QTableWidget, QTableWidgetItem, QPushButton, QTextBrowser,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


class SurgeWizard(QDialog):
    """Surge protection design wizard — shown after transient analysis."""

    def __init__(self, api, transient_results, parent=None):
        super().__init__(parent)
        self.api = api
        self.transient_results = transient_results
        self.setWindowTitle("Surge Protection Design Assistant")
        self.setMinimumSize(800, 550)
        self._setup_ui()
        self._run_design()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Surge Protection Recommended")
        header.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #f38ba8;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        surge_m = self.transient_results.get('max_surge_m', 0)
        surge_kPa = self.transient_results.get('max_surge_kPa', 0)
        info = QLabel(
            f"Maximum surge: {surge_m:.1f} m ({surge_kPa:.0f} kPa) — "
            f"exceeds 30 m threshold for protection design."
        )
        info.setFont(QFont("Consolas", 10))
        info.setWordWrap(True)
        layout.addWidget(info)

        # Recommendations as rich text
        self.text_browser = QTextBrowser()
        self.text_browser.setFont(QFont("Consolas", 10))
        self.text_browser.setOpenExternalLinks(False)
        layout.addWidget(self.text_browser)

        # Air valve table
        self.air_table = QTableWidget(0, 4)
        self.air_table.setHorizontalHeaderLabels([
            "Node", "Elevation (m AHD)", "Valve Type", "Reason"
        ])
        self.air_table.horizontalHeader().setStretchLastSection(True)
        self.air_table.setFont(QFont("Consolas", 9))
        self.air_table.verticalHeader().setVisible(False)
        layout.addWidget(self.air_table)

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFont(QFont("Consolas", 10))
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _run_design(self):
        """Run the surge protection design and populate the dialog."""
        try:
            recs = self.api.design_surge_protection(self.transient_results)
        except (OSError, ValueError, RuntimeError) as e:
            self.text_browser.setHtml(
                f'<p style="color: #f38ba8;">Design calculation failed: {e}</p>')
            return

        if 'error' in recs:
            self.text_browser.setHtml(
                f'<p style="color: #f38ba8;">{recs["error"]}</p>')
            return

        # Build HTML report
        html = []

        # Surge vessel
        sv = recs.get('surge_vessel')
        if sv:
            html.append('<h3 style="color: #89b4fa;">1. Surge Vessel</h3>')
            html.append(f'<p><b>Volume:</b> {sv["volume_m3"]:.1f} m\u00b3</p>')
            html.append(f'<p><b>Pressure rating:</b> {sv["pressure_rating_kPa"]} kPa</p>')
            html.append(f'<p><b>Location:</b> {sv["location"]}</p>')
            html.append(f'<p><b>Design basis:</b> {sv["basis"]}</p>')

        # Slow-closing valve
        scv = recs.get('slow_valve')
        if scv:
            html.append('<h3 style="color: #a6e3a1;">2. Slow-Closing Valve</h3>')
            html.append(f'<p><b>Critical period:</b> {scv["critical_period_s"]:.1f} s</p>')
            html.append(f'<p><b>Recommended closure:</b> '
                       f'\u2265{scv["recommended_closure_s"]:.0f} s</p>')
            html.append(f'<p><b>Type:</b> {scv["type"]}</p>')
            html.append(f'<p><b>Design basis:</b> {scv["basis"]}</p>')

        # Air valves header
        avs = recs.get('air_valves', [])
        if avs:
            html.append(f'<h3 style="color: #f9e2af;">3. Air Valves '
                       f'({len(avs)} locations)</h3>')
            html.append('<p>See table below for placement details.</p>')

        # Summary
        summary = recs.get('summary', [])
        if summary:
            html.append('<h3 style="color: #cdd6f4;">Summary</h3>')
            for s in summary:
                html.append(f'<p>{s}</p>')

        self.text_browser.setHtml(''.join(html))

        # Populate air valve table
        for av in avs:
            row = self.air_table.rowCount()
            self.air_table.insertRow(row)
            self.air_table.setItem(row, 0, QTableWidgetItem(av['node']))
            self.air_table.setItem(row, 1,
                                    QTableWidgetItem(f"{av['elevation_m']:.1f} m"))
            self.air_table.setItem(row, 2, QTableWidgetItem(av['type']))
            self.air_table.setItem(row, 3, QTableWidgetItem(av['reason']))

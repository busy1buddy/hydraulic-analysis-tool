"""
Report Builder Dialog
======================
Checklist of sections to include, one-click generate to DOCX or PDF.
"""

import os
import logging

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton,
    QLabel, QLineEdit, QFormLayout, QDialogButtonBox, QFileDialog,
    QMessageBox, QGroupBox,
)
from PyQt6.QtGui import QFont


class ReportDialog(QDialog):
    """Report builder with section checklist."""

    # Base sections always available
    BASE_SECTIONS = [
        ("executive_summary", "Executive Summary"),
        ("network_summary", "Network Summary"),
        ("node_results", "Node Results"),
        ("pipe_results", "Pipe Results"),
        ("compliance", "Compliance Table"),
        ("scenario_comparison", "Scenario Comparison"),
        ("appendix", "Appendix: Input Parameters"),
    ]

    # Conditional sections (N4) — only shown when relevant analysis was run
    CONDITIONAL_SECTIONS = [
        ("slurry_design", "Slurry Pipeline Design"),
        ("water_quality", "Water Quality Analysis"),
        ("transient", "Transient / Water Hammer"),
        ("resilience", "Network Resilience"),
        ("rehabilitation", "Rehabilitation Priority"),
        ("uncertainty", "Monte Carlo Uncertainty"),
    ]

    def __init__(self, api, results, parent=None):
        super().__init__(parent)
        self.api = api
        self.results = results
        self.setWindowTitle("Generate Report")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Project info
        info_group = QGroupBox("Project Information")
        info_layout = QFormLayout()
        self.project_input = QLineEdit("Hydraulic Analysis")
        self.engineer_input = QLineEdit("")
        info_layout.addRow("Project Name:", self.project_input)
        info_layout.addRow("Engineer:", self.engineer_input)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Build section list based on what was actually run (N4)
        active_sections = list(self.BASE_SECTIONS)
        self._detect_conditional_sections(active_sections)

        # Section checklist
        sections_group = QGroupBox("Report Sections (auto-detected from analysis)")
        sections_layout = QVBoxLayout()
        self.checkboxes = {}
        for key, label in active_sections:
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.setFont(QFont("Consolas", 10))
            self.checkboxes[key] = cb
            sections_layout.addWidget(cb)
        sections_group.setLayout(sections_layout)
        layout.addWidget(sections_group)

    def _detect_conditional_sections(self, sections):
        """Add conditional sections based on what analysis was run (N4)."""
        if not self.results:
            return

        # Slurry mode was active?
        if self.results.get('slurry_mode') or self.results.get('slurry_headloss'):
            sections.append(("slurry_design", "Slurry Pipeline Design"))

        # Transient results present?
        if self.results.get('max_surge_m') or self.results.get('junctions'):
            if isinstance(self.results.get('junctions'), dict):
                sections.append(("transient", "Transient / Water Hammer"))

        # Water quality was run?
        if self.results.get('junction_quality'):
            sections.append(("water_quality", "Water Quality Analysis"))

        # Resilience index available?
        if self.api and self.api.wn:
            ri = self.api.compute_resilience_index(self.results)
            if 'error' not in ri:
                sections.append(("resilience", "Network Resilience"))

        # Scenarios with no data → uncheck scenario comparison
        if 'scenario_comparison' in self.checkboxes:
            pass  # Already in base sections

        # Buttons
        btn_layout = QHBoxLayout()

        docx_btn = QPushButton("Generate DOCX")
        docx_btn.setFont(QFont("Consolas", 10))
        docx_btn.clicked.connect(self._on_docx)
        btn_layout.addWidget(docx_btn)

        pdf_btn = QPushButton("Generate PDF")
        pdf_btn.setFont(QFont("Consolas", 10))
        pdf_btn.clicked.connect(self._on_pdf)
        btn_layout.addWidget(pdf_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _get_sections(self):
        return [k for k, cb in self.checkboxes.items() if cb.isChecked()]

    def _on_docx(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save DOCX Report", "report.docx",
            "Word Document (*.docx)"
        )
        if not path:
            return
        try:
            from reports.docx_report import generate_docx_report
            summary = self.api.get_network_summary()
            generate_docx_report(
                self.results, summary, path,
                title=self.project_input.text(),
                engineer_name=self.engineer_input.text(),
                project_name=self.project_input.text(),
            )
            QMessageBox.information(self, "Report Generated",
                                    f"DOCX report saved to:\n{path}")
            self.accept()
        except (OSError, ValueError, RuntimeError) as e:
            QMessageBox.critical(self, "Report Error", str(e))

    def _on_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF Report", "report.pdf",
            "PDF Document (*.pdf)"
        )
        if not path:
            return
        try:
            from reports.pdf_report import generate_pdf_report
            summary = self.api.get_network_summary()
            generate_pdf_report(
                self.results, summary, path,
                title=self.project_input.text(),
                engineer_name=self.engineer_input.text(),
                project_name=self.project_input.text(),
            )
            QMessageBox.information(self, "Report Generated",
                                    f"PDF report saved to:\n{path}")
            self.accept()
        except (OSError, ValueError, RuntimeError) as e:
            QMessageBox.critical(self, "Report Error", str(e))

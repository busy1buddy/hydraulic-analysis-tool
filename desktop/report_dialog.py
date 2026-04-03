"""
Report Builder Dialog
======================
Checklist of sections to include, one-click generate to DOCX or PDF.
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton,
    QLabel, QLineEdit, QFormLayout, QDialogButtonBox, QFileDialog,
    QMessageBox, QGroupBox,
)
from PyQt6.QtGui import QFont


class ReportDialog(QDialog):
    """Report builder with section checklist."""

    SECTIONS = [
        ("executive_summary", "Executive Summary"),
        ("network_summary", "Network Summary"),
        ("node_results", "Node Results"),
        ("pipe_results", "Pipe Results"),
        ("compliance", "Compliance Table"),
        ("scenario_comparison", "Scenario Comparison"),
        ("appendix", "Appendix: Input Parameters"),
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

        # Section checklist
        sections_group = QGroupBox("Report Sections")
        sections_layout = QVBoxLayout()
        self.checkboxes = {}
        for key, label in self.SECTIONS:
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.setFont(QFont("Consolas", 10))
            self.checkboxes[key] = cb
            sections_layout.addWidget(cb)
        sections_group.setLayout(sections_layout)
        layout.addWidget(sections_group)

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
        except Exception as e:
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
        except Exception as e:
            QMessageBox.critical(self, "Report Error", str(e))

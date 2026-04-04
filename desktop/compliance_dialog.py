"""
Design Compliance Certificate Dialog (L1)
==========================================
Runs all WSAA compliance checks and displays a formal certificate.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QProgressBar,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


class ComplianceDialog(QDialog):
    """Run all compliance checks and display certificate results."""

    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.certificate = None
        self.setWindowTitle("Design Compliance Certificate")
        self.setMinimumSize(700, 500)
        self._build_ui()
        self._run_checks()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("WSAA Design Compliance Certificate")
        header.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Info labels
        self.info_label = QLabel("")
        self.info_label.setFont(QFont("Consolas", 10))
        layout.addWidget(self.info_label)

        # Progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        layout.addWidget(self.progress)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Check", "Status", "Standard", "Details"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        # Overall status
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()
        self.export_btn = QPushButton("Export PDF Certificate")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._on_export_pdf)
        btn_layout.addWidget(self.export_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _run_checks(self):
        """Execute compliance check and populate table."""
        self.certificate = self.api.run_design_compliance_check()

        self.progress.hide()

        if 'error' in self.certificate:
            self.status_label.setText(self.certificate['error'])
            self.status_label.setStyleSheet("color: red;")
            return

        # Info
        self.info_label.setText(
            f"Network: {self.certificate['network_name']}  |  "
            f"Date: {self.certificate['date']}  |  "
            f"Software: v{self.certificate['software_version']}"
        )

        # Populate table
        checks = self.certificate['checks']
        self.table.setRowCount(len(checks))
        for row, check in enumerate(checks):
            self.table.setItem(row, 0, QTableWidgetItem(check.get('check', '')))

            status_item = QTableWidgetItem(check.get('status', ''))
            status = check.get('status', '')
            if status == 'PASS':
                status_item.setForeground(QColor('#a6e3a1'))  # green
            elif status == 'FAIL':
                status_item.setForeground(QColor('#f38ba8'))  # red
            elif status == 'ERROR':
                status_item.setForeground(QColor('#fab387'))  # orange
            else:
                status_item.setForeground(QColor('#a6adc8'))  # grey
            status_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            self.table.setItem(row, 1, status_item)

            self.table.setItem(row, 2, QTableWidgetItem(check.get('standard', '')))
            self.table.setItem(row, 3, QTableWidgetItem(check.get('details', '')))

        # Overall status
        overall = self.certificate['overall_status']
        self.status_label.setText(f"Overall: {overall}")
        if overall == 'COMPLIANT':
            self.status_label.setStyleSheet("color: #a6e3a1;")
        else:
            self.status_label.setStyleSheet("color: #f38ba8;")

        self.export_btn.setEnabled(True)

    def _on_export_pdf(self):
        """Export certificate as PDF."""
        if not self.certificate:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Compliance Certificate", "compliance_certificate.pdf",
            "PDF Files (*.pdf)")
        if not path:
            return

        try:
            from fpdf import FPDF

            pdf = FPDF()
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 18)
            pdf.cell(0, 15, 'Design Compliance Certificate', ln=True, align='C')
            pdf.ln(5)

            pdf.set_font('Helvetica', '', 10)
            pdf.cell(0, 8, f"Network: {self.certificate['network_name']}", ln=True)
            pdf.cell(0, 8, f"Date: {self.certificate['date']}", ln=True)
            pdf.cell(0, 8, f"Software: v{self.certificate['software_version']}", ln=True)
            pdf.ln(5)

            # Checks table
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(60, 8, 'Check', border=1)
            pdf.cell(20, 8, 'Status', border=1)
            pdf.cell(50, 8, 'Standard', border=1)
            pdf.cell(60, 8, 'Details', border=1, ln=True)

            pdf.set_font('Helvetica', '', 9)
            for check in self.certificate['checks']:
                status = check.get('status', '')
                if status == 'PASS':
                    pdf.set_text_color(0, 150, 0)
                elif status == 'FAIL':
                    pdf.set_text_color(200, 0, 0)
                else:
                    pdf.set_text_color(0, 0, 0)

                pdf.cell(60, 8, check.get('check', ''), border=1)
                pdf.cell(20, 8, status, border=1)
                pdf.cell(50, 8, check.get('standard', ''), border=1)
                pdf.cell(60, 8, check.get('details', '')[:40], border=1, ln=True)

            pdf.set_text_color(0, 0, 0)
            pdf.ln(10)

            # Overall
            overall = self.certificate['overall_status']
            pdf.set_font('Helvetica', 'B', 14)
            pdf.cell(0, 15, f"Overall Status: {overall}", ln=True, align='C')

            summary = self.certificate.get('summary', {})
            pdf.set_font('Helvetica', '', 10)
            pdf.cell(0, 8,
                     f"Checks: {summary.get('total_checks', 0)} total, "
                     f"{summary.get('passed', 0)} passed, "
                     f"{summary.get('failed', 0)} failed",
                     ln=True, align='C')

            pdf.output(path)
            QMessageBox.information(self, "Exported",
                                    f"Certificate exported to:\n{path}")

        except Exception as e:
            QMessageBox.warning(self, "Export Error", f"Failed to export PDF: {e}")

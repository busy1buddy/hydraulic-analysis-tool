"""
Safety Case Report Dialog (R2)
================================
Wires HydraulicAPI.safety_case_report() to a dialog with input fields,
verdict preview, and PDF export.
"""

import os
import json

import logging

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QDoubleSpinBox, QCheckBox, QTextEdit, QFileDialog,
    QMessageBox, QFormLayout, QGroupBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


class SafetyCaseDialog(QDialog):
    """Generate a formal pipeline safety case report."""

    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.report = None
        self.setWindowTitle("Safety Case Report")
        self.setMinimumSize(720, 640)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Disclaimer banner — audit + legality
        banner = QLabel(
            "⚠ Signature block is visual only — not cryptographically "
            "signed. Obtain engineer wet signature or digital certificate "
            "for legally binding compliance case.")
        banner.setWordWrap(True)
        banner.setStyleSheet(
            "background-color: #fff3cd; color: #856404; "
            "border: 1px solid #ffeaa7; padding: 6px; border-radius: 3px;")
        layout.addWidget(banner)

        # Project metadata
        meta_box = QGroupBox("Project Metadata")
        meta_form = QFormLayout(meta_box)
        self.engineer_edit = QLineEdit()
        self.engineer_edit.setPlaceholderText("e.g. Jane Smith, RPEQ #12345")
        self.engineer_edit.setToolTip(
            "Name of the Chartered/RPEQ engineer certifying the report.")
        meta_form.addRow("Certifying Engineer:", self.engineer_edit)

        self.project_ref_edit = QLineEdit()
        self.project_ref_edit.setPlaceholderText(
            "e.g. PIP-2026-0034 Mount Isa Copper Slurry")
        self.project_ref_edit.setToolTip(
            "Project reference for regulatory submission (optional).")
        meta_form.addRow("Project Ref:", self.project_ref_edit)
        layout.addWidget(meta_box)

        # Analysis parameters
        param_box = QGroupBox("Analysis Parameters")
        param_form = QFormLayout(param_box)

        self.wave_speed_spin = QDoubleSpinBox()
        self.wave_speed_spin.setRange(200.0, 1500.0)
        self.wave_speed_spin.setValue(1100.0)
        self.wave_speed_spin.setSuffix(" m/s")
        self.wave_speed_spin.setToolTip(
            "Wave speed for surge calculation.\n"
            "AS 2280 default: 1100 m/s ductile iron. "
            "PVC ~450 m/s. PE ~250-400 m/s.")
        param_form.addRow("Wave speed:", self.wave_speed_spin)

        self.closure_spin = QDoubleSpinBox()
        self.closure_spin.setRange(0.01, 300.0)
        self.closure_spin.setValue(0.5)
        self.closure_spin.setSuffix(" s")
        self.closure_spin.setDecimals(2)
        self.closure_spin.setToolTip(
            "Worst-case valve closure time.\n"
            "Rapid closure triggers water hammer REVIEW.")
        param_form.addRow("Valve closure:", self.closure_spin)

        self.pn_spin = QDoubleSpinBox()
        self.pn_spin.setRange(20.0, 400.0)
        self.pn_spin.setValue(150.0)
        self.pn_spin.setSuffix(" m")
        self.pn_spin.setToolTip(
            "Maximum allowable transient pressure (PN rating in m head).\n"
            "PN15 = 150m, PN25 = 250m, PN35 = 350m.")
        param_form.addRow("PN rating:", self.pn_spin)

        # Optional slurry check
        self.include_slurry_check = QCheckBox("Include slurry settling check")
        self.include_slurry_check.setToolTip(
            "Enable for slurry pipelines. Checks each pipe velocity "
            "against the Durand critical deposition velocity.")
        self.include_slurry_check.toggled.connect(self._on_slurry_toggled)
        param_form.addRow(self.include_slurry_check)

        self.slurry_vc_spin = QDoubleSpinBox()
        self.slurry_vc_spin.setRange(0.1, 10.0)
        self.slurry_vc_spin.setValue(1.8)
        self.slurry_vc_spin.setSuffix(" m/s")
        self.slurry_vc_spin.setDecimals(2)
        self.slurry_vc_spin.setToolTip(
            "Durand critical deposition velocity. Below this, solids "
            "settle and accumulate in the pipe invert.")
        self.slurry_vc_spin.setEnabled(False)
        param_form.addRow("Critical velocity:", self.slurry_vc_spin)

        layout.addWidget(param_box)

        # Generate button
        gen_row = QHBoxLayout()
        self.generate_btn = QPushButton("Preview Verdict")
        self.generate_btn.setToolTip(
            "Run safety case analysis and show verdict in the preview pane.")
        self.generate_btn.clicked.connect(self._on_generate)
        gen_row.addWidget(self.generate_btn)
        gen_row.addStretch()

        self.export_btn = QPushButton("Export to JSON...")
        self.export_btn.setToolTip(
            "Save the safety case as JSON (use for programmatic handoff "
            "or conversion to PDF via reports/pdf_report.py).")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._on_export)
        gen_row.addWidget(self.export_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        gen_row.addWidget(self.close_btn)
        layout.addLayout(gen_row)

        # Verdict display
        verdict_box = QGroupBox("Verdict Preview")
        v_layout = QVBoxLayout(verdict_box)
        self.verdict_label = QLabel("(click Preview Verdict to run analysis)")
        self.verdict_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.verdict_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.verdict_label.setMinimumHeight(40)
        v_layout.addWidget(self.verdict_label)
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setFont(QFont("Consolas", 9))
        v_layout.addWidget(self.summary_text)
        layout.addWidget(verdict_box, stretch=1)

    def _on_slurry_toggled(self, checked):
        self.slurry_vc_spin.setEnabled(checked)

    def _on_generate(self):
        if self.api is None or self.api.wn is None:
            QMessageBox.warning(
                self, "No Network",
                "Load a network first before running the safety case.\n"
                "Fix: File > Open.")
            return

        kwargs = {
            'wave_speed_ms': self.wave_speed_spin.value(),
            'valve_closure_s': self.closure_spin.value(),
            'max_transient_pressure_m': self.pn_spin.value(),
        }
        if self.include_slurry_check.isChecked():
            kwargs['slurry_critical_velocity_ms'] = self.slurry_vc_spin.value()

        self.report = self.api.safety_case_report(**kwargs)
        if 'error' in self.report:
            QMessageBox.warning(
                self, "Report Failed", self.report['error'])
            return

        # Colour by verdict
        verdict = self.report['overall_verdict']
        colour = {
            'APPROVED': '#4caf50',
            'CONDITIONAL APPROVAL': '#ff9800',
            'NOT APPROVED': '#f44336',
        }.get(verdict, '#757575')
        self.verdict_label.setStyleSheet(
            f"color: white; background-color: {colour}; padding: 8px;")
        self.verdict_label.setText(verdict)

        # Summary text
        lines = [
            f"Report:     {self.report['title']}",
            f"Network:    {self.report['network']}",
            f"Issued:     {self.report['issued']}",
            f"Engineer:   {self.engineer_edit.text() or '(not specified)'}",
            f"Project:    {self.project_ref_edit.text() or '(not specified)'}",
            '',
            '=' * 60,
        ]
        for section in self.report['sections']:
            lines.append('')
            lines.append(f"{section['section']}  [{section['overall']}]")
            lines.append(f"  Standard: {section.get('standard', '-')}")
            for check in section.get('checks', []):
                status = check.get('status', '-')
                item = check.get('item', '-')
                measured = check.get('measured', '-')
                margin = check.get('margin', '')
                lines.append(
                    f"    {status:6s} {item:38s} {measured:14s} {margin}")
        if self.report.get('verdict_reasons'):
            lines.append('')
            lines.append('Verdict reasons:')
            for r in self.report['verdict_reasons']:
                lines.append(f'  - {r}')
        lines.append('')
        lines.append('=' * 60)
        lines.append('Assumptions:')
        for a in self.report.get('assumptions', []):
            lines.append(f"  - {a.get('item')}: {a.get('note', '')}")

        self.summary_text.setPlainText('\n'.join(lines))
        self.export_btn.setEnabled(True)

    def _on_export(self):
        if self.report is None:
            return
        default_name = 'safety_case.json'
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Safety Case", default_name,
            "JSON Files (*.json);;All Files (*.*)")
        if not path:
            return
        # Include engineer/project fields in export
        export_payload = dict(self.report)
        export_payload['signature_block'] = dict(
            self.report.get('signature_block', {}))
        export_payload['signature_block']['certifying_engineer'] = \
            self.engineer_edit.text() or '(not specified)'
        export_payload['signature_block']['project_reference'] = \
            self.project_ref_edit.text() or '(not specified)'
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(export_payload, f, indent=2)
            QMessageBox.information(
                self, "Exported",
                f"Safety case saved to:\n{path}\n\n"
                f"Next step: attach to your regulatory submission package.")
        except (OSError, ValueError, RuntimeError) as e:
            QMessageBox.warning(
                self, "Export Failed",
                f"Could not write file: {e}\n"
                f"Fix: choose a different location or check permissions.")

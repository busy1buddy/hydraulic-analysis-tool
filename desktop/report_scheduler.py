"""
Report Scheduler — Automated Analysis & Report Generation
===========================================================
Creates Windows Task Scheduler entries to automatically run analysis
and generate reports at specified intervals.

Also provides a command-line mode for scheduled execution.
"""

import os
import sys
import json
import subprocess
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QComboBox, QSpinBox,
    QFileDialog, QMessageBox, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class ReportSchedulerDialog(QDialog):
    """Configure automated report generation using Windows Task Scheduler."""

    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Schedule Automated Reports")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Schedule settings
        sched_group = QGroupBox("Schedule")
        sched_form = QFormLayout(sched_group)

        self.freq_combo = QComboBox()
        self.freq_combo.addItems(["Daily", "Weekly", "Monthly"])
        self.freq_combo.setFont(QFont("Consolas", 10))
        sched_form.addRow("Frequency:", self.freq_combo)

        self.time_edit = QLineEdit("06:00")
        self.time_edit.setFont(QFont("Consolas", 10))
        self.time_edit.setToolTip("Time in 24-hour format (HH:MM)")
        sched_form.addRow("Time:", self.time_edit)

        layout.addWidget(sched_group)

        # Output settings
        out_group = QGroupBox("Output")
        out_form = QFormLayout(out_group)

        self.output_dir = QLineEdit()
        self.output_dir.setFont(QFont("Consolas", 10))
        self.output_dir.setPlaceholderText("C:\\Reports\\Hydraulic")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output)
        out_row = QHBoxLayout()
        out_row.addWidget(self.output_dir)
        out_row.addWidget(browse_btn)
        out_form.addRow("Output folder:", out_row)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["DOCX", "PDF", "Both"])
        self.format_combo.setFont(QFont("Consolas", 10))
        out_form.addRow("Report format:", self.format_combo)

        self.engineer_edit = QLineEdit()
        self.engineer_edit.setFont(QFont("Consolas", 10))
        out_form.addRow("Engineer name:", self.engineer_edit)

        layout.addWidget(out_group)

        # Network file
        net_group = QGroupBox("Network")
        net_form = QFormLayout(net_group)
        self.inp_path = QLineEdit()
        self.inp_path.setFont(QFont("Consolas", 10))
        if self.api._inp_file:
            self.inp_path.setText(self.api._inp_file)
        net_form.addRow("Network file:", self.inp_path)
        layout.addWidget(net_group)

        # Buttons
        btn_row = QHBoxLayout()
        self.create_btn = QPushButton("Create Scheduled Task")
        self.create_btn.setFont(QFont("Consolas", 10))
        self.create_btn.clicked.connect(self._on_create)
        btn_row.addWidget(self.create_btn)

        self.preview_btn = QPushButton("Preview Command")
        self.preview_btn.setFont(QFont("Consolas", 10))
        self.preview_btn.clicked.connect(self._on_preview)
        btn_row.addWidget(self.preview_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Preview label
        self.preview_label = QLabel("")
        self.preview_label.setFont(QFont("Consolas", 9))
        self.preview_label.setWordWrap(True)
        self.preview_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.preview_label)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self.output_dir.setText(path)

    def _build_command(self):
        """Build the scheduled task command string."""
        python = sys.executable
        script = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'scripts', 'scheduled_report.py')

        inp = self.inp_path.text().strip()
        output = self.output_dir.text().strip()
        fmt = self.format_combo.currentText().lower()
        engineer = self.engineer_edit.text().strip()

        cmd = f'"{python}" "{script}" --inp "{inp}" --output "{output}" --format {fmt}'
        if engineer:
            cmd += f' --engineer "{engineer}"'

        return cmd

    def _build_schtasks_command(self):
        """Build Windows schtasks command."""
        freq = self.freq_combo.currentText().upper()
        time = self.time_edit.text().strip()
        task_name = "HydraulicAnalysis_AutoReport"
        cmd = self._build_command()

        schtasks = (
            f'schtasks /Create /TN "{task_name}" '
            f'/TR "{cmd}" /SC {freq} /ST {time} /F'
        )
        return schtasks

    def _on_preview(self):
        cmd = self._build_schtasks_command()
        self.preview_label.setText(f"Command:\n{cmd}")

    def _on_create(self):
        if not self.inp_path.text().strip():
            QMessageBox.warning(self, "Missing Input",
                "Specify a network (.inp) file path.")
            return
        if not self.output_dir.text().strip():
            QMessageBox.warning(self, "Missing Output",
                "Specify an output folder for reports.")
            return

        cmd = self._build_schtasks_command()
        self.preview_label.setText(f"Creating task...\n{cmd}")

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                QMessageBox.information(self, "Task Created",
                    f"Scheduled task created successfully.\n\n"
                    f"Reports will be generated {self.freq_combo.currentText().lower()} "
                    f"at {self.time_edit.text()}.\n\n"
                    f"Output: {self.output_dir.text()}")
            else:
                QMessageBox.warning(self, "Task Creation Failed",
                    f"Could not create scheduled task.\n\n"
                    f"Try running as Administrator.\n\n"
                    f"Error: {result.stderr}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

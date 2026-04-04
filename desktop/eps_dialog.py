"""
Extended Period Simulation (EPS) Configuration Dialog
======================================================
Configures and runs EPS with duration, timestep, and results display.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QPushButton,
    QDialogButtonBox, QLabel, QGroupBox,
)
from PyQt6.QtGui import QFont


class EPSConfigDialog(QDialog):
    """Dialog to configure EPS parameters before running."""

    DURATION_OPTIONS = {
        '24 hours (1 day)': 24,
        '48 hours (2 days)': 48,
        '168 hours (1 week)': 168,
    }

    TIMESTEP_OPTIONS = {
        '15 minutes': 900,
        '30 minutes': 1800,
        '1 hour': 3600,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Extended Period Simulation")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.duration_combo = QComboBox()
        self.duration_combo.addItems(self.DURATION_OPTIONS.keys())
        self.duration_combo.setCurrentIndex(0)  # default 24h
        self.duration_combo.setFont(QFont("Consolas", 10))
        form.addRow("Duration:", self.duration_combo)

        self.timestep_combo = QComboBox()
        self.timestep_combo.addItems(self.TIMESTEP_OPTIONS.keys())
        self.timestep_combo.setCurrentIndex(2)  # default 1h
        self.timestep_combo.setFont(QFont("Consolas", 10))
        form.addRow("Time Step:", self.timestep_combo)

        layout.addLayout(form)

        # Info
        info = QLabel(
            "EPS runs the hydraulic simulation over the full duration,\n"
            "applying diurnal demand patterns at each timestep.\n\n"
            "WSAA compliance is checked against the MINIMUM pressure\n"
            "across all timesteps (not the average)."
        )
        info.setFont(QFont("Consolas", 9))
        info.setStyleSheet("color: #a6adc8;")
        layout.addWidget(info)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_duration_hours(self):
        text = self.duration_combo.currentText()
        return self.DURATION_OPTIONS.get(text, 24)

    def get_timestep_seconds(self):
        text = self.timestep_combo.currentText()
        return self.TIMESTEP_OPTIONS.get(text, 3600)

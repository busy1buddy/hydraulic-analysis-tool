"""
Welcome Dialog
===============
Shown on first launch when no network is loaded.
Provides quick access to demo, file open, and tutorials.
"""

import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class WelcomeDialog(QDialog):
    """Welcome dialog shown on first launch."""

    DEMO = 'demo'
    OPEN = 'open'
    TUTORIALS = 'tutorials'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.choice = None
        self.setWindowTitle("Welcome")
        self.setFixedSize(420, 250)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Welcome to Hydraulic Analysis Toolkit")
        title.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(
            "Professional hydraulic analysis for Australian\n"
            "water supply and mining engineers."
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Buttons
        demo_btn = QPushButton("Open Demo Network")
        demo_btn.setMinimumHeight(32)
        demo_btn.clicked.connect(lambda: self._choose(self.DEMO))
        layout.addWidget(demo_btn)

        open_btn = QPushButton("Open Network File...")
        open_btn.setMinimumHeight(32)
        open_btn.clicked.connect(lambda: self._choose(self.OPEN))
        layout.addWidget(open_btn)

        tut_btn = QPushButton("View Tutorials")
        tut_btn.setMinimumHeight(32)
        tut_btn.clicked.connect(lambda: self._choose(self.TUTORIALS))
        layout.addWidget(tut_btn)

        layout.addSpacing(4)

        # Skip checkbox
        self.skip_cb = QCheckBox("Don't show this again")
        layout.addWidget(self.skip_cb, alignment=Qt.AlignmentFlag.AlignCenter)

    def _choose(self, choice):
        self.choice = choice
        self.accept()

    def skip_next_time(self):
        return self.skip_cb.isChecked()

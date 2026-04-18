"""
Tutorial Manager — Guided User Onboarding
========================================
Sequences a series of tooltips and highlights to teach new users the basics.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt

class TutorialManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.steps = [
            {
                'title': 'Welcome!',
                'text': "Welcome to the Hydraulic Analysis Tool. Let's take a quick tour.",
                'target': None
            },
            {
                'title': '1. Load a Network',
                'text': "Go to <b>File > Open (.inp)</b> to load your EPANET model.",
                'target': 'file_menu'
            },
            {
                'title': '2. Run Analysis',
                'text': "Click the <b>Run</b> button on the toolbar or go to <b>Analysis > Steady State</b>.",
                'target': 'analysis_menu'
            },
            {
                'title': '3. Explore Results',
                'text': "View pressure and flow results in the <b>Project Explorer</b> or directly on the <b>Map</b>.",
                'target': 'explorer_dock'
            }
        ]
        self.current_step = 0

    def start(self):
        self.current_step = 0
        self.show_step()

    def show_step(self):
        if self.current_step >= len(self.steps):
            QMessageBox.information(self.main_window, "Tutorial Complete", "You are ready to go!")
            return
            
        step = self.steps[self.current_step]
        dlg = QDialog(self.main_window)
        dlg.setWindowTitle(step['title'])
        layout = QVBoxLayout(dlg)
        
        text_label = QLabel(step['text'])
        text_label.setWordWrap(True)
        text_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(text_label)
        
        btn_layout = QHBoxLayout()
        next_btn = QPushButton("Next" if self.current_step < len(self.steps)-1 else "Finish")
        next_btn.clicked.connect(lambda: self.next_step(dlg))
        btn_layout.addStretch()
        btn_layout.addWidget(next_btn)
        layout.addLayout(btn_layout)
        
        dlg.exec()

    def next_step(self, dlg):
        dlg.accept()
        self.current_step += 1
        self.show_step()

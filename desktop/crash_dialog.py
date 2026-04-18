"""
Crash Dialog — Global Error Reporting
====================================
Displays a user-friendly error message when an unhandled exception occurs.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout
)
from PyQt6.QtCore import Qt
import traceback

class CrashDialog(QDialog):
    def __init__(self, exception, tb, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Application Error")
        self.setMinimumSize(500, 400)
        
        self.layout = QVBoxLayout(self)
        
        # 1. Headline
        self.headline = QLabel("Opps! Something went wrong.")
        self.headline.setStyleSheet("font-size: 18px; font-weight: bold; color: #f38ba8;")
        self.layout.addWidget(self.headline)
        
        self.layout.addWidget(QLabel("The application encountered an unexpected error. Please find the details below:"))
        
        # 2. Traceback
        self.traceback_edit = QTextEdit()
        self.traceback_edit.setReadOnly(True)
        self.traceback_edit.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4; font-family: 'Consolas', monospace;")
        
        err_msg = f"{type(exception).__name__}: {str(exception)}\n\n"
        err_msg += "".join(traceback.format_tb(tb))
        self.traceback_edit.setPlainText(err_msg)
        self.layout.addWidget(self.traceback_edit)
        
        # 3. Actions
        btn_layout = QHBoxLayout()
        self.copy_btn = QPushButton("Copy to Clipboard")
        self.copy_btn.clicked.connect(self._on_copy)
        self.close_btn = QPushButton("Close Application")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setStyleSheet("background-color: #f38ba8; color: #11111b; font-weight: bold;")
        
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        self.layout.addLayout(btn_layout)

    def _on_copy(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.traceback_edit.toPlainText())

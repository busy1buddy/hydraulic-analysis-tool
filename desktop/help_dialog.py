"""
Help Dialog — Documentation and Support
======================================
Provides guidance and version information to the user.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTabWidget, QWidget, QTextBrowser, QPushButton
)
from PyQt6.QtCore import Qt

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help & Documentation")
        self.setMinimumSize(600, 450)
        
        self.layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # 1. Quick Start
        self.quick_start = QWidget()
        qs_layout = QVBoxLayout(self.quick_start)
        qs_browser = QTextBrowser()
        qs_browser.setHtml("""
            <h2>Quick Start Guide</h2>
            <ol>
                <li><b>File > Open:</b> Load an EPANET .inp file.</li>
                <li><b>Analysis > Steady State:</b> Run the baseline hydraulic model.</li>
                <li><b>What-If Panel:</b> Adjust sliders to see real-time impact on pressures.</li>
                <li><b>Pump Panel:</b> Analyze pump duty points and system curves.</li>
            </ol>
            <p>For more advanced analysis, check the <b>Analysis</b> menu for Slurry, Water Quality, and Calibration tools.</p>
        """)
        qs_layout.addWidget(qs_browser)
        self.tabs.addTab(self.quick_start, "Quick Start")
        
        # 2. Design Standards
        self.standards = QWidget()
        st_layout = QVBoxLayout(self.standards)
        st_browser = QTextBrowser()
        st_browser.setHtml("""
            <h2>Australian Design Standards (WSAA)</h2>
            <p>This tool follows the Water Services Association of Australia (WSAA) design codes:</p>
            <ul>
                <li><b>WSA 03:</b> Water Supply Code of Australia.</li>
                <li><b>Min Pressure:</b> 20m (target 25-30m for peak demand).</li>
                <li><b>Max Static Pressure:</b> 80m (PRV required if > 80m).</li>
                <li><b>Velocity:</b> Target 0.6m/s to 2.4m/s.</li>
            </ul>
        """)
        st_layout.addWidget(st_browser)
        self.tabs.addTab(self.standards, "WSAA Standards")
        
        # 3. About
        self.about = QWidget()
        ab_layout = QVBoxLayout(self.about)
        ab_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ab_layout.addWidget(QLabel("<h1>Hydraulic Analysis Tool</h1>"))
        ab_layout.addWidget(QLabel("Version 1.0.0 (Agentic Release)"))
        ab_layout.addWidget(QLabel("Built with WNTR, PyQt6, and Antigravity AI."))
        ab_layout.addWidget(QLabel("<br>Designed for Australian Mining & Water Utilities."))
        self.tabs.addTab(self.about, "About")
        
        # 4. Close
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        self.layout.addWidget(self.close_btn)

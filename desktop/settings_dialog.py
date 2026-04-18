"""
Settings Dialog — User Preferences
=================================
Allows users to configure application settings.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QGroupBox, QFormLayout, QSpinBox
)

class SettingsDialog(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Application Settings")
        self.setMinimumWidth(400)
        
        self.layout = QVBoxLayout(self)
        
        # 1. Units & Standards
        self.units_group = QGroupBox("Units & Standards")
        self.units_layout = QFormLayout(self.units_group)
        self.units_combo = QComboBox()
        self.units_combo.addItems(["LPS", "m3/h", "GPM"])
        self.units_combo.setCurrentText(self.api.settings.get('units', 'LPS'))
        self.units_layout.addRow("Flow Units:", self.units_combo)
        
        self.rough_spin = QSpinBox()
        self.rough_spin.setRange(50, 160)
        self.rough_spin.setValue(self.api.settings.get('default_roughness', 140))
        self.units_layout.addRow("Default Roughness (HW C):", self.rough_spin)
        self.layout.addWidget(self.units_group)
        
        # 2. Appearance
        self.ui_group = QGroupBox("Appearance")
        self.ui_layout = QFormLayout(self.ui_group)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "High Contrast"])
        self.theme_combo.setCurrentText(self.api.settings.get('theme', 'Dark'))
        self.ui_layout.addRow("Theme:", self.theme_combo)
        self.layout.addWidget(self.ui_group)
        
        # 3. Actions
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self._on_save)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        self.layout.addLayout(btn_layout)

    def _on_save(self):
        self.api.settings['units'] = self.units_combo.currentText()
        self.api.settings['default_roughness'] = self.rough_spin.value()
        self.api.settings['theme'] = self.theme_combo.currentText()
        self.api.save_settings()
        self.accept()

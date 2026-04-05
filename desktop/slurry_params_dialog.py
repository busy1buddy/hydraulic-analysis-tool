"""Slurry parameter dialog -- Bingham plastic tau_y / mu_p / density."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDoubleSpinBox, QDialogButtonBox,
    QLabel, QComboBox, QHBoxLayout,
)


# Named presets -- (tau_y Pa, mu_p Pa.s, density kg/m3, description)
PRESETS = {
    "Custom": (None, None, None, ""),
    "Iron ore tailings (Cv=15%)":
        (15.0, 0.05, 1800.0, "Typical SEQ iron ore tailings slurry"),
    "Copper concentrate (Cv=30%)":
        (35.0, 0.12, 2200.0, "High-solids copper concentrate"),
    "Coal slurry (Cv=50%)":
        (8.0, 0.03, 1350.0, "Coarse coal slurry, low yield stress"),
    "Bauxite residue (red mud, Cv=40%)":
        (60.0, 0.15, 1450.0, "Alumina refinery residue, high yield stress"),
    "Drilling mud (water-based)":
        (12.0, 0.04, 1250.0, "Standard oilfield bentonite mud"),
    "Cement paste":
        (100.0, 0.30, 2100.0, "Thick cement paste, very high yield"),
}


class SlurryParamsDialog(QDialog):
    """Edit Bingham-plastic slurry parameters used by the hydraulic solver."""

    def __init__(self, initial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Slurry Parameters (Bingham Plastic)")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        # Preset selector
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(PRESETS.keys()))
        self.preset_combo.currentTextChanged.connect(self._apply_preset)
        preset_row.addWidget(self.preset_combo, 1)
        layout.addLayout(preset_row)

        self.preset_desc = QLabel("")
        self.preset_desc.setStyleSheet("color: #888; font-style: italic;")
        self.preset_desc.setWordWrap(True)
        layout.addWidget(self.preset_desc)

        # Parameter form
        form = QFormLayout()
        self.tau_y = QDoubleSpinBox()
        self.tau_y.setRange(0.0, 500.0)
        self.tau_y.setDecimals(2)
        self.tau_y.setSuffix(" Pa")
        self.tau_y.setToolTip(
            "Yield stress: the minimum shear stress that must be exceeded\n"
            "before the slurry starts to flow. Typical range 5-100 Pa.")
        form.addRow("Yield stress (tau_y):", self.tau_y)

        self.mu_p = QDoubleSpinBox()
        self.mu_p.setRange(0.0, 10.0)
        self.mu_p.setDecimals(4)
        self.mu_p.setSingleStep(0.01)
        self.mu_p.setSuffix(" Pa.s")
        self.mu_p.setToolTip(
            "Plastic viscosity: the slope of the stress-strain curve above\n"
            "the yield stress. Typical range 0.01-0.30 Pa.s.")
        form.addRow("Plastic viscosity (mu_p):", self.mu_p)

        self.density = QDoubleSpinBox()
        self.density.setRange(800.0, 3000.0)
        self.density.setDecimals(0)
        self.density.setSuffix(" kg/m3")
        self.density.setToolTip(
            "Bulk slurry density. For water-based slurries, 1000-2500 kg/m3.")
        form.addRow("Density (rho):", self.density)
        layout.addLayout(form)

        # Any manual edit should flip preset back to Custom
        for spin in (self.tau_y, self.mu_p, self.density):
            spin.valueChanged.connect(self._on_value_edited)
        self._suppress_custom = False

        # OK / Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Seed values
        initial = initial or {}
        self._suppress_custom = True
        self.tau_y.setValue(initial.get('yield_stress', 15.0))
        self.mu_p.setValue(initial.get('plastic_viscosity', 0.05))
        self.density.setValue(initial.get('density', 1800.0))
        self._suppress_custom = False
        self.preset_combo.setCurrentText("Custom")

    def _apply_preset(self, name):
        tau_y, mu_p, rho, desc = PRESETS.get(name, (None, None, None, ""))
        self.preset_desc.setText(desc)
        if tau_y is None:
            return
        self._suppress_custom = True
        self.tau_y.setValue(tau_y)
        self.mu_p.setValue(mu_p)
        self.density.setValue(rho)
        self._suppress_custom = False

    def _on_value_edited(self, _):
        if self._suppress_custom:
            return
        if self.preset_combo.currentText() != "Custom":
            self._suppress_custom = True
            self.preset_combo.setCurrentText("Custom")
            self._suppress_custom = False

    def params(self) -> dict:
        return {
            'yield_stress': self.tau_y.value(),
            'plastic_viscosity': self.mu_p.value(),
            'density': self.density.value(),
        }

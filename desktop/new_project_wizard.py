"""
New Project Wizard
==================
First-launch / `File > New` entry point for engineers starting a from-scratch
design. Collects project metadata, source details, and pipe-design defaults
in a single dialog, then calls ``api.bootstrap_project(...)`` to seed a
WaterNetworkModel with one source node (reservoir / tank / junction-with-head).

Closes cold-start friction #1 from
``docs/walkthroughs/2026-04-25-cold-start/REPORT.md`` and is PR #2 of the
roadmap at ``docs/decisions/2026-04-25-cold-start-roadmap.md``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGroupBox, QLabel, QLineEdit, QVBoxLayout,
)


SOURCE_TYPES = [
    ('reservoir', 'Reservoir (unlimited fixed head)'),
    ('tank', 'Tank (finite storage with level dynamics)'),
    ('junction', 'Connection to existing main (junction with fixed head)'),
]

STANDARDS = [
    'WSAA WSA 03-2011 (Australian water supply)',
    'Mining / industrial (high-pressure override)',
    'Custom (no preset)',
]

# Mirror canvas_editor.MATERIAL_DEFAULTS keys but kept local so this file
# does not depend on the canvas editor's import surface.
MATERIAL_PRESETS = {
    'PVC PN12 (AS/NZS 1477)': {'roughness': 145, 'dn_mm': 100},
    'PVC PN18 (AS/NZS 1477)': {'roughness': 145, 'dn_mm': 100},
    'Ductile Iron (AS 2280)': {'roughness': 130, 'dn_mm': 150},
    'PE100 PN16 SDR11 (AS/NZS 4130)': {'roughness': 145, 'dn_mm': 110},
    'Concrete (AS 4058)': {'roughness': 110, 'dn_mm': 300},
}


class NewProjectWizard(QDialog):
    """Single-screen new-project setup dialog.

    A single screen rather than a multi-step QWizard because the total
    field count (~10) fits on one panel and engineers prefer to see all
    inputs at once. Three QGroupBox sections give the visual structure.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumWidth(500)
        self._build_ui()

    # ---- UI construction ---------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Set up a new hydraulic design from scratch. Click OK to create "
            "the network with a single source node — then use Edit Mode on "
            "the canvas to add junctions and pipes."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(self._build_metadata_group())
        layout.addWidget(self._build_source_group())
        layout.addWidget(self._build_defaults_group())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_metadata_group(self):
        group = QGroupBox("Project Metadata")
        form = QFormLayout()

        self.name_input = QLineEdit("New Project")
        self.name_input.setToolTip(
            "Used for the .inp filename in output/ and the window title.")
        form.addRow("Project name:", self.name_input)

        self.engineer_input = QLineEdit("")
        self.engineer_input.setPlaceholderText("(optional)")
        self.engineer_input.setToolTip(
            "Engineer of record. Pre-fills the report title page.")
        form.addRow("Engineer:", self.engineer_input)

        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        form.addRow("Date:", self.date_input)

        self.standard_combo = QComboBox()
        self.standard_combo.addItems(STANDARDS)
        self.standard_combo.setToolTip(
            "Drives the default WSAA threshold set used by the compliance "
            "check. Custom leaves the defaults untouched.")
        form.addRow("Target standard:", self.standard_combo)

        group.setLayout(form)
        return group

    def _build_source_group(self):
        group = QGroupBox("Source Node (the network's water supply)")
        form = QFormLayout()

        self.source_type_combo = QComboBox()
        for _, label in SOURCE_TYPES:
            self.source_type_combo.addItem(label)
        self.source_type_combo.currentIndexChanged.connect(self._on_source_type_changed)
        self.source_type_combo.setToolTip(
            "Reservoir = boundary with infinite supply at fixed head. "
            "Tank = finite storage. Junction = upstream connection where "
            "head is known but the upstream system is out of scope.")
        form.addRow("Source type:", self.source_type_combo)

        self.source_id_input = QLineEdit("R1")
        form.addRow("Source ID:", self.source_id_input)

        self.head_spin = QDoubleSpinBox()
        self.head_spin.setRange(-100.0, 1000.0)
        self.head_spin.setDecimals(1)
        self.head_spin.setValue(50.0)
        self.head_spin.setSuffix(" m")
        self.head_spin.setToolTip(
            "Fixed head at the source (m AHD for reservoirs, "
            "elevation for tanks/junctions).")
        form.addRow("Source head:", self.head_spin)

        group.setLayout(form)
        return group

    def _build_defaults_group(self):
        group = QGroupBox("Pipe Design Defaults (used by Add Pipe dialog)")
        form = QFormLayout()

        self.material_combo = QComboBox()
        self.material_combo.addItems(list(MATERIAL_PRESETS.keys()))
        self.material_combo.currentTextChanged.connect(self._on_material_changed)
        form.addRow("Default material:", self.material_combo)

        self.roughness_spin = QDoubleSpinBox()
        self.roughness_spin.setRange(60.0, 160.0)
        self.roughness_spin.setDecimals(0)
        self.roughness_spin.setValue(145)
        self.roughness_spin.setToolTip(
            "Hazen-Williams C-factor. Higher = smoother pipe.\n"
            "DI: 130-140  PVC/PE: 140-150  Concrete: 90-120")
        form.addRow("Default roughness (C):", self.roughness_spin)

        self.dn_spin = QDoubleSpinBox()
        self.dn_spin.setRange(50.0, 1200.0)
        self.dn_spin.setDecimals(0)
        self.dn_spin.setValue(100)
        self.dn_spin.setSuffix(" mm")
        form.addRow("Default DN:", self.dn_spin)

        group.setLayout(form)
        return group

    # ---- Reactive callbacks ------------------------------------------------

    def _on_source_type_changed(self, idx):
        """Update the default source ID and head label when source type changes."""
        type_id = SOURCE_TYPES[idx][0]
        defaults = {'reservoir': 'R1', 'tank': 'T1', 'junction': 'CONN1'}
        self.source_id_input.setText(defaults.get(type_id, 'R1'))

    def _on_material_changed(self, name):
        preset = MATERIAL_PRESETS.get(name)
        if preset:
            self.roughness_spin.setValue(preset['roughness'])
            self.dn_spin.setValue(preset['dn_mm'])

    # ---- Public accessor ---------------------------------------------------

    def get_config(self) -> dict:
        """Return the user's choices as a config dict.

        Suitable for passing the ``source_type``, ``source_id``,
        ``source_head_m``, ``name``, and ``project_defaults`` keys
        directly to ``api.bootstrap_project()``.
        """
        return {
            'name': self.name_input.text().strip() or 'New Project',
            'engineer': self.engineer_input.text().strip(),
            'date': self.date_input.date().toString('yyyy-MM-dd'),
            'standard': self.standard_combo.currentText(),
            'source_type': SOURCE_TYPES[self.source_type_combo.currentIndex()][0],
            'source_id': self.source_id_input.text().strip() or None,
            'source_head_m': float(self.head_spin.value()),
            'project_defaults': {
                'material': self.material_combo.currentText(),
                'roughness': float(self.roughness_spin.value()),
                'dn_mm': int(self.dn_spin.value()),
            },
        }

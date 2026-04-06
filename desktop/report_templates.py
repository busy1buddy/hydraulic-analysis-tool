"""
Report Template System
========================
Save and load custom report configurations as named templates.
Ships with 3 default templates: Standard, Executive, Technical.
"""

import os
import json

import logging

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QLabel, QListWidget, QListWidgetItem, QLineEdit, QCheckBox,
    QMessageBox, QFormLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'report_templates')

# Default templates
DEFAULT_TEMPLATES = {
    'Standard — All Sections': {
        'sections': {
            'executive_summary': True,
            'network_description': True,
            'steady_state': True,
            'compliance': True,
            'transient': True,
            'fire_flow': True,
            'water_quality': True,
            'conclusions': True,
        },
        'description': 'Complete report with all analysis sections.',
    },
    'Executive — Summary Only': {
        'sections': {
            'executive_summary': True,
            'network_description': False,
            'steady_state': False,
            'compliance': True,
            'transient': False,
            'fire_flow': False,
            'water_quality': False,
            'conclusions': True,
        },
        'description': 'Executive overview: summary, compliance, and conclusions.',
    },
    'Technical — Full Tables': {
        'sections': {
            'executive_summary': False,
            'network_description': True,
            'steady_state': True,
            'compliance': True,
            'transient': True,
            'fire_flow': True,
            'water_quality': True,
            'conclusions': False,
        },
        'description': 'Detailed technical report with all data tables.',
    },
}


def list_templates():
    """Return dict of available templates (defaults + saved)."""
    templates = dict(DEFAULT_TEMPLATES)
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    for f in os.listdir(TEMPLATES_DIR):
        if f.endswith('.json'):
            try:
                with open(os.path.join(TEMPLATES_DIR, f)) as fh:
                    data = json.load(fh)
                name = data.get('name', f.replace('.json', ''))
                templates[name] = data
            except (KeyError, AttributeError, ValueError):
                pass
    return templates


def save_template(name, sections, description=''):
    """Save a report template to disk."""
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    safe_name = "".join(c for c in name if c.isalnum() or c in ' _-').strip()
    path = os.path.join(TEMPLATES_DIR, f'{safe_name}.json')
    data = {
        'name': name,
        'sections': sections,
        'description': description,
    }
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    return path


def load_template(name):
    """Load a template by name."""
    templates = list_templates()
    return templates.get(name)


class ReportTemplateDialog(QDialog):
    """Dialog for managing report templates."""

    SECTION_LABELS = {
        'executive_summary': 'Executive Summary',
        'network_description': 'Network Description',
        'steady_state': 'Steady-State Results',
        'compliance': 'Compliance Summary',
        'transient': 'Transient Analysis',
        'fire_flow': 'Fire Flow Analysis',
        'water_quality': 'Water Quality',
        'conclusions': 'Conclusions',
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Report Templates")
        self.setMinimumSize(600, 450)
        self._selected_template = None
        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self):
        layout = QHBoxLayout(self)

        # Left: template list
        left = QVBoxLayout()
        left.addWidget(QLabel("Templates:"))
        self.template_list = QListWidget()
        self.template_list.setFont(QFont("Consolas", 10))
        self.template_list.currentRowChanged.connect(self._on_select)
        left.addWidget(self.template_list)

        btn_row = QHBoxLayout()
        self.use_btn = QPushButton("Use Template")
        self.use_btn.setFont(QFont("Consolas", 10))
        self.use_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.use_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setFont(QFont("Consolas", 9))
        self.delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self.delete_btn)
        left.addLayout(btn_row)

        layout.addLayout(left)

        # Right: template details + save new
        right = QVBoxLayout()

        self.desc_label = QLabel("Select a template.")
        self.desc_label.setFont(QFont("Consolas", 9))
        self.desc_label.setWordWrap(True)
        right.addWidget(self.desc_label)

        # Section checkboxes
        sections_group = QGroupBox("Sections")
        sections_layout = QVBoxLayout(sections_group)
        self.section_checks = {}
        for key, label in self.SECTION_LABELS.items():
            cb = QCheckBox(label)
            cb.setFont(QFont("Consolas", 9))
            cb.setChecked(True)
            sections_layout.addWidget(cb)
            self.section_checks[key] = cb
        right.addWidget(sections_group)

        # Save new template
        save_group = QGroupBox("Save as New Template")
        save_layout = QFormLayout(save_group)
        self.name_edit = QLineEdit()
        self.name_edit.setFont(QFont("Consolas", 10))
        self.name_edit.setPlaceholderText("My Custom Template")
        save_layout.addRow("Name:", self.name_edit)

        self.save_btn = QPushButton("Save Template")
        self.save_btn.setFont(QFont("Consolas", 10))
        self.save_btn.clicked.connect(self._on_save)
        save_layout.addRow(self.save_btn)
        right.addWidget(save_group)

        layout.addLayout(right)

    def _refresh_list(self):
        self.template_list.clear()
        templates = list_templates()
        for name in templates:
            self.template_list.addItem(name)

    def _on_select(self, row):
        if row < 0:
            return
        name = self.template_list.item(row).text()
        template = load_template(name)
        if template:
            self._selected_template = template
            desc = template.get('description', '')
            self.desc_label.setText(desc or name)
            sections = template.get('sections', {})
            for key, cb in self.section_checks.items():
                cb.setChecked(sections.get(key, True))

    def _on_save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Enter a template name.")
            return
        sections = {key: cb.isChecked() for key, cb in self.section_checks.items()}
        save_template(name, sections)
        self._refresh_list()
        QMessageBox.information(self, "Saved", f"Template '{name}' saved.")

    def _on_delete(self):
        item = self.template_list.currentItem()
        if item is None:
            return
        name = item.text()
        if name in DEFAULT_TEMPLATES:
            QMessageBox.warning(self, "Cannot Delete",
                "Default templates cannot be deleted.")
            return
        safe_name = "".join(c for c in name if c.isalnum() or c in ' _-').strip()
        path = os.path.join(TEMPLATES_DIR, f'{safe_name}.json')
        if os.path.exists(path):
            os.remove(path)
        self._refresh_list()

    def get_selected_sections(self):
        """Return dict of section selections."""
        return {key: cb.isChecked() for key, cb in self.section_checks.items()}

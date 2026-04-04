"""
Rehabilitation Prioritisation Dialog
======================================
Pipe asset management: import condition data, score pipes by age/condition/
breaks/hydraulics, rank for capital works replacement.
Ref: WSAA Asset Management Guidelines, IPWEA Practice Note 7
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox,
    QHeaderView, QComboBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


# Risk category colours (Catppuccin Mocha tones)
RISK_COLORS = {
    'CRITICAL': QColor(243, 139, 168),  # red
    'HIGH':     QColor(250, 179, 135),  # peach
    'MEDIUM':   QColor(249, 226, 175),  # yellow
    'LOW':      QColor(166, 227, 161),  # green
}


class RehabDialog(QDialog):
    """Dialog for pipe rehabilitation prioritisation."""

    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Rehabilitation Prioritisation")
        self.setMinimumSize(1000, 600)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Import section ---
        import_group = QGroupBox("Pipe Condition Data")
        import_layout = QHBoxLayout(import_group)

        self.import_btn = QPushButton("Import CSV...")
        self.import_btn.setFont(QFont("Consolas", 10))
        self.import_btn.setToolTip(
            "CSV columns: pipe_id, install_year, condition_score (1-5), "
            "break_history, material"
        )
        self.import_btn.clicked.connect(self._on_import)
        import_layout.addWidget(self.import_btn)

        self.status_label = QLabel("No condition data loaded")
        self.status_label.setFont(QFont("Consolas", 9))
        import_layout.addWidget(self.status_label)

        import_layout.addStretch()

        self.analyze_btn = QPushButton("Run Prioritisation")
        self.analyze_btn.setFont(QFont("Consolas", 10))
        self.analyze_btn.clicked.connect(self._on_analyze)
        import_layout.addWidget(self.analyze_btn)

        layout.addWidget(import_group)

        # --- Filter ---
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "CRITICAL", "HIGH", "MEDIUM", "LOW"])
        self.filter_combo.setFont(QFont("Consolas", 9))
        self.filter_combo.currentTextChanged.connect(self._on_filter)
        filter_row.addWidget(self.filter_combo)
        filter_row.addStretch()

        self.summary_label = QLabel("")
        self.summary_label.setFont(QFont("Consolas", 9))
        filter_row.addWidget(self.summary_label)

        layout.addLayout(filter_row)

        # --- Results table ---
        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels([
            "Pipe", "DN (mm)", "Length (m)", "Material", "Year",
            "Age", "Condition", "Breaks", "Vel (m/s)",
            "Score", "Risk"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setFont(QFont("Consolas", 9))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        # Store full results for filtering
        self._all_results = []

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Pipe Condition CSV", "",
            "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return

        try:
            count = self.api.import_pipe_conditions_csv(path)
            self.status_label.setText(f"Loaded condition data for {count} pipes")
        except Exception as e:
            QMessageBox.critical(self, "Import Error",
                                 f"Could not import CSV.\n\n{type(e).__name__}: {e}")

    def _on_analyze(self):
        if self.api.wn is None:
            QMessageBox.warning(self, "No Network", "Load a network first.")
            return

        try:
            results = self.api.prioritize_rehabilitation()
        except Exception as e:
            QMessageBox.critical(self, "Analysis Error", str(e))
            return

        if isinstance(results, dict) and 'error' in results:
            QMessageBox.warning(self, "Error", results['error'])
            return

        self._all_results = results
        self._populate_table(results)

        # Summary
        counts = {}
        for r in results:
            cat = r['risk_category']
            counts[cat] = counts.get(cat, 0) + 1
        parts = [f"{cat}: {n}" for cat, n in sorted(counts.items())]
        self.summary_label.setText("  |  ".join(parts))

    def _on_filter(self, text):
        if text == "All":
            self._populate_table(self._all_results)
        else:
            filtered = [r for r in self._all_results if r['risk_category'] == text]
            self._populate_table(filtered)

    def _populate_table(self, results):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for r in results:
            row = self.table.rowCount()
            self.table.insertRow(row)

            age_str = str(r['age_years']) if r['age_years'] is not None else "--"
            cond_str = f"{r['condition_score']:.0f}" if r['condition_score'] is not None else "--"
            year_str = str(r['install_year']) if r['install_year'] is not None else "--"

            values = [
                r['pipe_id'],
                str(r['diameter_mm']),
                f"{r['length_m']:.0f}",
                r['material'],
                year_str,
                age_str,
                cond_str,
                str(r['break_history']),
                f"{r['velocity_ms']:.2f}",
                f"{r['priority_score']:.1f}",
                r['risk_category'],
            ]

            risk_color = RISK_COLORS.get(r['risk_category'], QColor(200, 200, 200))

            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                # Colour the risk column and score
                if col >= 9:
                    item.setForeground(risk_color)
                self.table.setItem(row, col, item)

        self.table.setSortingEnabled(True)

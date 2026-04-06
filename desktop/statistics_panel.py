"""
Network Statistics Panel
=========================
QWidget tab that displays summary statistics for the loaded network and
the most recent analysis results.

Shown as a tab in the Results dock after analysis completes.
"""

import logging

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


class StatisticsPanel(QWidget):
    """
    Network-wide statistics panel.

    Call update_statistics(api, results) after each analysis run.
    Can also be called with api only (no results) to show structural stats.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(4, 4, 4, 4)

        # Scroll area so the panel is usable at any dock height
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(6)

        # ── Network structure ─────────────────────────────────────────────────
        struct_group = QGroupBox("Network Structure")
        struct_form = QFormLayout()
        struct_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def _lbl(text="—"):
            l = QLabel(text)
            l.setFont(QFont("Consolas", 10))
            return l

        self.lbl_pipe_length = _lbl()
        self.lbl_total_demand = _lbl()
        self.lbl_n_junctions = _lbl()
        self.lbl_n_pipes = _lbl()
        self.lbl_n_pumps = _lbl()
        self.lbl_n_valves = _lbl()
        self.lbl_n_tanks = _lbl()
        self.lbl_n_reservoirs = _lbl()

        struct_form.addRow("Total pipe length:", self.lbl_pipe_length)
        struct_form.addRow("Total base demand:", self.lbl_total_demand)
        struct_form.addRow("Junctions:", self.lbl_n_junctions)
        struct_form.addRow("Pipes:", self.lbl_n_pipes)
        struct_form.addRow("Pumps:", self.lbl_n_pumps)
        struct_form.addRow("Valves:", self.lbl_n_valves)
        struct_form.addRow("Tanks:", self.lbl_n_tanks)
        struct_form.addRow("Reservoirs:", self.lbl_n_reservoirs)

        struct_group.setLayout(struct_form)
        layout.addWidget(struct_group)

        # ── Pipe material summary ─────────────────────────────────────────────
        material_group = QGroupBox("Pipe Material Summary (by Hazen-Williams C-factor)")
        material_layout = QVBoxLayout()

        self.material_table = QTableWidget(0, 3)
        self.material_table.setHorizontalHeaderLabels(
            ["Material Group", "Length (km)", "% of Total"]
        )
        self.material_table.horizontalHeader().setStretchLastSection(True)
        self.material_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.material_table.verticalHeader().setVisible(False)
        self.material_table.setFont(QFont("Consolas", 9))
        self.material_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.material_table.setMaximumHeight(150)
        material_layout.addWidget(self.material_table)
        material_group.setLayout(material_layout)
        layout.addWidget(material_group)

        # ── Hydraulic ranges ─────────────────────────────────────────────────
        hydraulic_group = QGroupBox("Hydraulic Results")
        hydraulic_form = QFormLayout()
        hydraulic_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.lbl_pressure_range = _lbl()
        self.lbl_velocity_range = _lbl()

        hydraulic_form.addRow("Pressure range (m):", self.lbl_pressure_range)
        hydraulic_form.addRow("Velocity range (m/s):", self.lbl_velocity_range)

        hydraulic_group.setLayout(hydraulic_form)
        layout.addWidget(hydraulic_group)

        # ── Compliance summary ────────────────────────────────────────────────
        compliance_group = QGroupBox("WSAA Compliance Summary")
        compliance_form = QFormLayout()
        compliance_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.lbl_pass = _lbl()
        self.lbl_warning = _lbl()
        self.lbl_info = _lbl()

        compliance_form.addRow("Pass:", self.lbl_pass)
        compliance_form.addRow("Warning / Critical:", self.lbl_warning)
        compliance_form.addRow("Info:", self.lbl_info)

        compliance_group.setLayout(compliance_form)
        layout.addWidget(compliance_group)

        layout.addStretch()
        scroll.setWidget(container)
        root_layout.addWidget(scroll)

    # ── Public API ────────────────────────────────────────────────────────────

    def update_statistics(self, api, results: dict | None = None):
        """
        Refresh all statistics from api (structural) and results (hydraulic).

        Parameters
        ----------
        api     : HydraulicAPI instance
        results : dict returned by run_steady_state() / run_transient_analysis()
                  May be None if only structural stats are needed.
        """
        self._update_structure(api)
        self._update_materials(api)
        if results:
            self._update_hydraulics(results)
            self._update_compliance(api, results)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _update_structure(self, api):
        """Populate network element counts and totals."""
        if api.wn is None:
            return

        summary = api.get_network_summary()
        if 'error' in summary:
            return

        # Total pipe length (sum all pipe lengths)
        total_length_m = 0.0
        for pid in api.get_link_list('pipe'):
            try:
                pipe = api.get_link(pid)
                total_length_m += pipe.length
            except (KeyError, AttributeError, ValueError):
                pass
        total_length_km = total_length_m / 1000.0

        # Total base demand (sum all junction demands, convert m³/s → LPS)
        total_demand_lps = 0.0
        for jid in api.get_node_list('junction'):
            try:
                node = api.get_node(jid)
                if node.demand_timeseries_list:
                    total_demand_lps += node.demand_timeseries_list[0].base_value * 1000
            except (KeyError, AttributeError, ValueError):
                pass

        self.lbl_pipe_length.setText(f"{total_length_km:.1f} km")
        self.lbl_total_demand.setText(f"{total_demand_lps:.1f} LPS")
        self.lbl_n_junctions.setText(str(summary.get('junctions', 0)))
        self.lbl_n_pipes.setText(str(summary.get('pipes', 0)))
        self.lbl_n_pumps.setText(str(summary.get('pumps', 0)))
        self.lbl_n_valves.setText(str(summary.get('valves', 0)))
        self.lbl_n_tanks.setText(str(summary.get('tanks', 0)))
        self.lbl_n_reservoirs.setText(str(summary.get('reservoirs', 0)))

    def _update_materials(self, api):
        """Populate pipe material summary table grouped by C-factor range."""
        if api.wn is None:
            return

        # Group lengths by material based on Hazen-Williams C-factor (AS/NZS standards)
        # AS 2280 Ductile Iron: C = 120-140
        # AS/NZS 1477 PVC:      C = 145-150
        # AS/NZS 4130 PE/HDPE:  C = 140-150
        # AS 4058 Concrete:     C = 90-120
        # Other:                remaining

        MATERIAL_GROUPS = [
            ("Concrete (C 90-119)",  90,  119),
            ("Ductile Iron (C 120-139)", 120, 139),
            ("PE/HDPE (C 140-144)",  140, 144),
            ("PVC (C 145-150)",      145, 150),
            ("Smooth (C >150)",      151, 9999),
            ("Other",                  0,  89),
        ]

        group_lengths = {name: 0.0 for name, *_ in MATERIAL_GROUPS}

        for pid in api.get_link_list('pipe'):
            try:
                pipe = api.get_link(pid)
                c = pipe.roughness
                length = pipe.length
                matched = False
                for name, lo, hi in MATERIAL_GROUPS:
                    if lo <= c <= hi:
                        group_lengths[name] += length
                        matched = True
                        break
                if not matched:
                    group_lengths["Other"] += length
            except (KeyError, AttributeError, ValueError):
                pass

        total_m = sum(group_lengths.values())

        self.material_table.setRowCount(0)
        for name, *_ in MATERIAL_GROUPS:
            length_m = group_lengths[name]
            if length_m == 0.0:
                continue
            length_km = length_m / 1000.0
            pct = (length_m / total_m * 100) if total_m > 0 else 0.0

            row = self.material_table.rowCount()
            self.material_table.insertRow(row)
            self.material_table.setItem(row, 0, QTableWidgetItem(name))
            self.material_table.setItem(row, 1, QTableWidgetItem(f"{length_km:.1f}"))
            self.material_table.setItem(row, 2, QTableWidgetItem(f"{pct:.1f}%"))

    def _update_hydraulics(self, results: dict):
        """Populate pressure and velocity ranges from analysis results."""
        pressures_dict = results.get('pressures', {})
        flows_dict = results.get('flows', {})

        if pressures_dict:
            all_pressures = []
            for pdata in pressures_dict.values():
                all_pressures.append(pdata.get('min_m', 0))
                all_pressures.append(pdata.get('max_m', 0))
            if all_pressures:
                p_min = min(all_pressures)
                p_max = max(all_pressures)
                self.lbl_pressure_range.setText(f"{p_min:.1f} – {p_max:.1f} m")
        else:
            self.lbl_pressure_range.setText("—")

        if flows_dict:
            all_velocities = [
                v.get('max_velocity_ms', 0) for v in flows_dict.values()
            ]
            if all_velocities:
                v_min = min(
                    v.get('min_velocity_ms', v.get('max_velocity_ms', 0))
                    for v in flows_dict.values()
                )
                v_max = max(all_velocities)
                self.lbl_velocity_range.setText(f"{v_min:.2f} – {v_max:.2f} m/s")
        else:
            self.lbl_velocity_range.setText("—")

    def _update_compliance(self, api, results: dict):
        """Populate WSAA compliance counts."""
        compliance = results.get('compliance', [])

        n_warning = sum(
            1 for c in compliance if c.get('type') in ('WARNING', 'CRITICAL')
        )
        n_info = sum(1 for c in compliance if c.get('type') == 'INFO')

        # Count junctions with PASS status (pressure within 20–50 m)
        pressures = results.get('pressures', {})
        n_pass = sum(
            1 for pdata in pressures.values()
            if 20.0 <= pdata.get('min_m', 0) and pdata.get('max_m', 0) <= 50.0
        )

        self.lbl_pass.setText(str(n_pass))

        warn_lbl = QLabel(str(n_warning))
        warn_lbl.setFont(QFont("Consolas", 10))
        if n_warning > 0:
            self.lbl_warning.setText(str(n_warning))
            self.lbl_warning.setStyleSheet("color: #f38ba8;")
        else:
            self.lbl_warning.setText("0")
            self.lbl_warning.setStyleSheet("")

        self.lbl_info.setText(str(n_info))

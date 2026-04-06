"""
Network Health Dashboard
=========================
At-a-glance overview of network status showing key performance
indicators (KPIs) with traffic-light indicators.

Designed to be the first thing an engineer sees when opening a project.
Answers: "Is my network healthy right now?"
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QGridLayout, QPushButton,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


def _kpi_widget(title, value, unit, status='ok', tooltip=''):
    """Create a single KPI display widget."""
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(2)

    # Status colour
    colours = {
        'ok': '#a6e3a1',      # green
        'warning': '#f9e2af',  # yellow
        'fail': '#f38ba8',     # red
        'info': '#89b4fa',     # blue
        'na': '#6c7086',       # grey
    }
    border_colour = colours.get(status, colours['na'])

    container.setStyleSheet(
        f"background-color: #313244; border-radius: 8px; "
        f"border: 2px solid {border_colour};")

    title_lbl = QLabel(title)
    title_lbl.setFont(QFont("Consolas", 9))
    title_lbl.setStyleSheet(f"color: {border_colour}; border: none;")
    title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title_lbl)

    value_lbl = QLabel(f"{value}")
    value_lbl.setFont(QFont("Consolas", 18, QFont.Weight.Bold))
    value_lbl.setStyleSheet(f"color: #cdd6f4; border: none;")
    value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(value_lbl)

    unit_lbl = QLabel(unit)
    unit_lbl.setFont(QFont("Consolas", 9))
    unit_lbl.setStyleSheet("color: #a6adc8; border: none;")
    unit_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(unit_lbl)

    if tooltip:
        container.setToolTip(tooltip)

    return container


class DashboardWidget(QWidget):
    """Network health dashboard — KPI cards in a grid layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("Network Health Dashboard")
        header.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #cdd6f4;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(header)

        self.grid = QGridLayout()
        self.grid.setSpacing(8)
        self._layout.addLayout(self.grid)
        self._layout.addStretch()

    def update_dashboard(self, api, results=None):
        """Populate dashboard KPIs from API and results."""
        # Clear existing
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if api.wn is None:
            self.grid.addWidget(
                _kpi_widget("Status", "No Network", "Load a .inp file", 'na'), 0, 0)
            return

        summary = api.get_network_summary()

        # Row 0: Network size
        self.grid.addWidget(_kpi_widget(
            "Junctions", str(summary.get('junctions', 0)), "nodes", 'info',
            "Total junction nodes in the network"), 0, 0)
        self.grid.addWidget(_kpi_widget(
            "Pipes", str(summary.get('pipes', 0)), "links", 'info',
            "Total pipe links in the network"), 0, 1)

        total_length_km = sum(
            api.wn.get_link(pid).length for pid in api.wn.pipe_name_list) / 1000
        self.grid.addWidget(_kpi_widget(
            "Network Length", f"{total_length_km:.1f}", "km", 'info',
            "Total pipe length"), 0, 2)

        total_demand = sum(
            api.wn.get_node(jid).demand_timeseries_list[0].base_value * 1000
            for jid in api.wn.junction_name_list
            if api.wn.get_node(jid).demand_timeseries_list) if api.wn else 0
        self.grid.addWidget(_kpi_widget(
            "Total Demand", f"{total_demand:.1f}", "LPS", 'info',
            "Sum of all junction base demands"), 0, 3)

        if results is None:
            # No analysis results — show placeholders
            for col in range(4):
                self.grid.addWidget(
                    _kpi_widget("--", "--", "Run analysis (F5)", 'na'), 1, col)
            return

        pressures = results.get('pressures', {})
        flows = results.get('flows', {})
        compliance = results.get('compliance', [])

        # Row 1: Pressure KPIs
        if pressures:
            all_min = [p.get('min_m', 0) for p in pressures.values()]
            all_max = [p.get('max_m', 0) for p in pressures.values()]
            min_p = min(all_min) if all_min else 0
            max_p = max(all_max) if all_max else 0

            min_status = 'ok' if min_p >= 20 else ('warning' if min_p >= 15 else 'fail')
            self.grid.addWidget(_kpi_widget(
                "Min Pressure", f"{min_p:.1f}", "m head", min_status,
                f"WSAA WSA 03-2011: minimum 20 m\nCurrent: {min_p:.1f} m"), 1, 0)

            max_status = 'ok' if max_p <= 50 else ('warning' if max_p <= 60 else 'fail')
            self.grid.addWidget(_kpi_widget(
                "Max Pressure", f"{max_p:.1f}", "m head", max_status,
                f"WSAA WSA 03-2011: maximum 50 m\nCurrent: {max_p:.1f} m"), 1, 1)

        # Row 1: Velocity KPIs (use slurry velocity if available)
        slurry_data = results.get('slurry', {})
        if flows:
            all_vel = []
            for pid, f in flows.items():
                sd = slurry_data.get(pid)
                v = sd.get('velocity_ms', f.get('max_velocity_ms', 0)) if sd else f.get('max_velocity_ms', 0)
                all_vel.append(v)
            max_v = max(all_vel) if all_vel else 0
            vel_status = 'ok' if max_v <= 2.0 else ('warning' if max_v <= 2.5 else 'fail')
            self.grid.addWidget(_kpi_widget(
                "Max Velocity", f"{max_v:.2f}", "m/s", vel_status,
                f"WSAA limit: 2.0 m/s\nCurrent: {max_v:.2f} m/s"), 1, 2)

        # Compliance
        fails = sum(1 for c in compliance if c.get('type') in ('WARNING', 'CRITICAL'))
        infos = sum(1 for c in compliance if c.get('type') == 'INFO')
        if fails == 0:
            wsaa_status = 'ok'
            wsaa_text = 'PASS'
        else:
            wsaa_status = 'fail'
            wsaa_text = f'{fails} issues'
        self.grid.addWidget(_kpi_widget(
            "WSAA Compliance", wsaa_text,
            f"{infos} info" if infos else "All clear", wsaa_status,
            "WSAA WSA 03-2011 compliance check"), 1, 3)

        # Row 2: Resilience index (Todini)
        ri = api.compute_resilience_index(results)
        if 'error' not in ri:
            ri_val = ri['resilience_index']
            if ri_val >= 0.3:
                ri_status = 'ok'
            elif ri_val >= 0.15:
                ri_status = 'warning'
            else:
                ri_status = 'fail'
            self.grid.addWidget(_kpi_widget(
                "Resilience", f"{ri_val:.3f}", f"Grade {ri['grade']}", ri_status,
                "Todini Index: 0.0 = no redundancy, 1.0 = full redundancy.\n"
                "Target > 0.3 for reliable distribution networks.\n"
                f"{ri['interpretation']}"), 2, 0)

        # Network topology summary
        topo = api.analyse_topology()
        if 'error' not in topo:
            de_status = 'ok' if topo['dead_end_count'] <= 3 else (
                'warning' if topo['dead_end_count'] <= 10 else 'fail')
            self.grid.addWidget(_kpi_widget(
                "Dead Ends", str(topo['dead_end_count']), "nodes", de_status,
                "Dead-end nodes can cause water quality issues"), 2, 1)
            self.grid.addWidget(_kpi_widget(
                "Loops", str(topo['loops']), "independent", 'info',
                "Higher loop count = better redundancy"), 2, 2)
            br_status = 'ok' if topo['bridge_count'] == 0 else 'warning'
            self.grid.addWidget(_kpi_widget(
                "Bridges", str(topo['bridge_count']), "critical pipes", br_status,
                "Bridge pipes disconnect the network if removed"), 2, 3)

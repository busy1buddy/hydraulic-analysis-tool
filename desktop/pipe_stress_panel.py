"""
Pipe Stress Analysis Panel
============================
Shows hoop stress, von Mises stress, and safety factor per pipe.
Highlights pipes where safety factor < 1.5 in red.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel,
)
from PyQt6.QtGui import QFont, QColor

from pipe_stress import analyze_pipe_stress, MATERIAL_STRENGTH


# Material detection by roughness (Hazen-Williams C-factor)
def _detect_material_key(roughness):
    """Map HW roughness to a pipe_stress.py material key."""
    if roughness >= 145:
        return 'pvc_pn12'
    elif roughness >= 135:
        return 'pe100'
    elif roughness >= 120:
        return 'ductile_iron'
    elif roughness >= 80:
        return 'concrete_class3'
    else:
        return 'ductile_iron'


# PN ratings in kPa for pressure class safety factor
# These are the maximum allowable operating pressures per standard
_PN_RATING_KPA = {
    'ductile_iron': 3500,    # PN35 — AS 2280
    'pvc_pn12': 1200,        # PN12 — AS/NZS 1477
    'pvc_pn18': 1800,        # PN18 — AS/NZS 1477
    'pe100': 1600,           # PN16 SDR11 — AS/NZS 4130
    'concrete_class3': 2500, # Class 3 — AS 4058
}


class PipeStressPanel(QWidget):
    """Table showing pipe stress analysis results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        header = QLabel("Pipe Stress Analysis")
        header.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        header.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(header)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Pipe ID", "DN (mm)", "Material", "Pressure (kPa)",
            "Hoop (MPa)", "PN Rating (kPa)", "SF (PN/P)"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setFont(QFont("Consolas", 9))
        layout.addWidget(self.table)

        self.summary_label = QLabel("")
        self.summary_label.setFont(QFont("Consolas", 9))
        self.summary_label.setStyleSheet("color: #a6adc8;")
        layout.addWidget(self.summary_label)

    def update_results(self, api, results):
        """Calculate and display pipe stress for all pipes.

        Parameters
        ----------
        api : HydraulicAPI
            API with loaded network.
        results : dict
            Steady-state results with pressures.
        """
        self.table.setRowCount(0)

        if api is None or api.wn is None or results is None:
            return

        pressures = results.get('pressures', {})
        fail_count = 0

        for pid in api.get_link_list('pipe'):
            pipe = api.get_link(pid)
            dn_mm = int(pipe.diameter * 1000)

            # Get max pressure at pipe endpoints
            p_start = pressures.get(pipe.start_node_name, {}).get('max_m', 0)
            p_end = pressures.get(pipe.end_node_name, {}).get('max_m', 0)
            max_p_m = max(p_start, p_end)
            # Convert m head to kPa: 1 m = 9.81 kPa
            pressure_kPa = max_p_m * 9.81

            # Detect material from roughness
            material_key = _detect_material_key(pipe.roughness)

            # Estimate wall thickness — use au_pipes.py if available
            wall_mm = _estimate_wall_thickness(dn_mm, material_key)

            try:
                stress = analyze_pipe_stress(
                    pressure_kPa=pressure_kPa,
                    diameter_mm=dn_mm,
                    wall_thickness_mm=wall_mm,
                    material=material_key,
                )
            except Exception:
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)

            hoop = stress.get('hoop_stress_MPa', 0)
            mat_display = material_key.replace('_', ' ').title()

            # PN safety factor = rated pressure / operating pressure
            # This is the meaningful engineering metric for pipe selection
            pn_rating = _PN_RATING_KPA.get(material_key, 3500)
            sf = round(pn_rating / pressure_kPa, 2) if pressure_kPa > 0 else float('inf')

            items = [
                pid, str(dn_mm), mat_display, f"{pressure_kPa:.0f}",
                f"{hoop:.1f}", str(pn_rating), f"{sf:.2f}"
            ]

            for col, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                # Highlight safety factor < 1.5 in red
                if col == 6 and sf < 1.5:
                    item.setForeground(QColor(243, 139, 168))
                    fail_count += 1
                elif col == 6 and sf < 2.0:
                    item.setForeground(QColor(249, 226, 175))  # yellow warning
                elif col == 6:
                    item.setForeground(QColor(166, 227, 161))
                self.table.setItem(row, col, item)

        total = self.table.rowCount()
        if fail_count > 0:
            self.summary_label.setText(
                f"{fail_count}/{total} pipes below SF 1.5 — review required"
            )
            self.summary_label.setStyleSheet("color: #f38ba8;")
        else:
            self.summary_label.setText(f"All {total} pipes above SF 1.5")
            self.summary_label.setStyleSheet("color: #a6e3a1;")


def _estimate_wall_thickness(dn_mm, material_key):
    """Estimate wall thickness from pipe database or standard formulas."""
    try:
        from data.au_pipes import get_pipe_properties

        if 'pvc' in material_key:
            props = get_pipe_properties('PVC', dn_mm)
        elif 'pe' in material_key:
            props = get_pipe_properties('PE', dn_mm)
        elif 'concrete' in material_key:
            props = get_pipe_properties('Concrete', dn_mm)
        else:
            props = get_pipe_properties('Ductile Iron', dn_mm)

        if props:
            return props['wall_thickness_mm']
    except Exception:
        pass

    # Fallback: approximate wall thickness
    if 'pvc' in material_key:
        return max(dn_mm * 0.04, 3.0)
    elif 'pe' in material_key:
        return max(dn_mm * 0.09, 5.0)  # SDR11
    elif 'concrete' in material_key:
        return max(dn_mm * 0.10, 40.0)
    else:  # DI
        return max(dn_mm * 0.03, 6.0)

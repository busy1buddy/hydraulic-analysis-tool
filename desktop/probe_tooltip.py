"""
Probe Tooltip — Element Inspector Overlay
==========================================
Dark semi-transparent tooltip that displays all hydraulic result variables
for a clicked node or pipe element.

Usage
-----
    tooltip = ProbeTooltip(parent_widget)
    tooltip.show_junction(element_id, node, pdata)   # pdata from results
    tooltip.show_pipe(element_id, pipe, fdata)        # fdata from results
    tooltip.move_near(global_x, global_y)
    # Disappears on Escape or next show_ call
"""

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen, QKeyEvent

# WSAA thresholds (WSAA WSA 03-2011 Table 3.1)
_WSAA_MIN = 20.0
_WSAA_MAX = 50.0

_BG_COLOR = QColor(30, 30, 46, 230)   # #1e1e2e at ~0.9 opacity
_BORDER_COLOR = QColor(69, 71, 90)     # subtle border
_TEXT_COLOR = "#cdd6f4"
_KEY_COLOR = "#a6adc8"
_PASS_COLOR = "#a6e3a1"
_FAIL_COLOR = "#f38ba8"
_WARN_COLOR = "#f9e2af"


class ProbeTooltip(QWidget):
    """Semi-transparent floating tooltip for element inspection."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._lines: list[tuple[str, str, str]] = []  # (key, value, value_color)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        self._container = QWidget(self)
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(2)
        layout.addWidget(self._container)

        self._font_key = QFont("Consolas", 9)
        self._font_val = QFont("Consolas", 9)
        self._font_val.setBold(True)

        self._label_widgets: list[QLabel] = []

    # ------------------------------------------------------------------
    # Public show methods
    # ------------------------------------------------------------------

    def show_junction(self, eid: str, node, pdata: dict | None, wsaa_status: str = ""):
        """Populate and show tooltip for a junction."""
        lines = [
            ("Type", "Junction", _TEXT_COLOR),
            ("ID", eid, _TEXT_COLOR),
            ("Elevation", f"{node.elevation:.1f} m", _TEXT_COLOR),
        ]

        # Demand
        demand_lps = 0.0
        try:
            if node.demand_timeseries_list:
                demand_lps = node.demand_timeseries_list[0].base_value * 1000
        except Exception:
            pass
        lines.append(("Demand", f"{demand_lps:.2f} LPS", _TEXT_COLOR))

        # Pressure & head from results
        if pdata:
            min_p = pdata.get("min_m")
            avg_p = pdata.get("avg_m")
            max_p = pdata.get("max_m")
            if min_p is not None:
                lines.append(("Pressure (min)", f"{min_p:.1f} m", _TEXT_COLOR))
            if avg_p is not None:
                lines.append(("Pressure (avg)", f"{avg_p:.1f} m", _TEXT_COLOR))
            if max_p is not None:
                lines.append(("Pressure (max)", f"{max_p:.1f} m", _TEXT_COLOR))
            if avg_p is not None:
                head = node.elevation + avg_p
                lines.append(("Head (avg)", f"{head:.1f} m", _TEXT_COLOR))

            # WSAA status
            p_check = min_p if min_p is not None else avg_p
            if p_check is not None:
                if p_check < _WSAA_MIN or (max_p is not None and max_p > _WSAA_MAX):
                    status_color = _FAIL_COLOR
                    status_text = "FAIL"
                    if p_check < _WSAA_MIN:
                        status_text += f" (<{_WSAA_MIN} m — WSAA)"
                    elif max_p is not None and max_p > _WSAA_MAX:
                        status_text += f" (>{_WSAA_MAX} m — WSAA)"
                else:
                    status_color = _PASS_COLOR
                    status_text = "PASS (WSAA)"
                lines.append(("WSAA Status", status_text, status_color))
        else:
            lines.append(("Pressure", "No results", _KEY_COLOR))
            lines.append(("WSAA Status", "—", _KEY_COLOR))

        self._render(lines)

    def show_pipe(self, eid: str, pipe, fdata: dict | None):
        """Populate and show tooltip for a pipe."""
        dn_mm = int(pipe.diameter * 1000)
        lines = [
            ("Type", "Pipe", _TEXT_COLOR),
            ("ID", eid, _TEXT_COLOR),
            ("DN", f"{dn_mm} mm", _TEXT_COLOR),
            ("Length", f"{pipe.length:.1f} m", _TEXT_COLOR),
            ("Roughness (C)", f"{pipe.roughness:.0f}", _TEXT_COLOR),
        ]

        if fdata:
            v = fdata.get("max_velocity_ms")
            q = fdata.get("avg_lps")
            hl = fdata.get("headloss_m_per_km")

            if v is not None:
                v_color = _FAIL_COLOR if v > 2.0 else (_WARN_COLOR if v > 1.5 else _TEXT_COLOR)
                lines.append(("Velocity (max)", f"{v:.2f} m/s", v_color))
            if q is not None:
                lines.append(("Flow (avg)", f"{q:.2f} LPS", _TEXT_COLOR))
            if hl is None and fdata and v is not None and q is not None:
                # Estimate headloss per km via Hazen-Williams if not provided
                try:
                    if pipe.length > 0 and pipe.diameter > 0:
                        Q_m3s = abs(q) / 1000
                        hl_per_m = (10.67 * Q_m3s ** 1.852) / (
                            pipe.roughness ** 1.852 * pipe.diameter ** 4.87)
                        hl = hl_per_m * 1000
                except Exception:
                    hl = None
            if hl is not None:
                lines.append(("Headloss", f"{hl:.1f} m/km", _TEXT_COLOR))
        else:
            lines.append(("Velocity", "No results", _KEY_COLOR))
            lines.append(("Flow", "No results", _KEY_COLOR))
            lines.append(("Headloss", "No results", _KEY_COLOR))

        self._render(lines)

    def show_reservoir(self, eid: str, node):
        """Populate and show tooltip for a reservoir."""
        lines = [
            ("Type", "Reservoir", _TEXT_COLOR),
            ("ID", eid, _TEXT_COLOR),
            ("Head", f"{node.base_head:.1f} m", _TEXT_COLOR),
        ]
        self._render(lines)

    def show_tank(self, eid: str, node):
        """Populate and show tooltip for a tank."""
        lines = [
            ("Type", "Tank", _TEXT_COLOR),
            ("ID", eid, _TEXT_COLOR),
            ("Elevation", f"{node.elevation:.1f} m", _TEXT_COLOR),
        ]
        try:
            lines.append(("Init Level", f"{node.init_level:.1f} m", _TEXT_COLOR))
            lines.append(("Min Level", f"{node.min_level:.1f} m", _TEXT_COLOR))
            lines.append(("Max Level", f"{node.max_level:.1f} m", _TEXT_COLOR))
            lines.append(("Diameter", f"{node.diameter:.1f} m", _TEXT_COLOR))
        except Exception:
            pass
        self._render(lines)

    def move_near(self, gx: int, gy: int, offset_x: int = 16, offset_y: int = 8):
        """Position tooltip near (gx, gy) in global screen coordinates, avoiding edges."""
        screen = self.screen()
        if screen is None:
            self.move(gx + offset_x, gy + offset_y)
            return

        geo = screen.availableGeometry()
        w, h = self.width(), self.height()
        x = gx + offset_x
        y = gy + offset_y

        # Flip if too close to right/bottom edge
        if x + w > geo.right() - 4:
            x = gx - w - offset_x
        if y + h > geo.bottom() - 4:
            y = gy - h - offset_y

        self.move(max(geo.left(), x), max(geo.top(), y))

    # ------------------------------------------------------------------
    # Internal rendering
    # ------------------------------------------------------------------

    def _render(self, lines: list[tuple[str, str, str]]):
        """Clear old labels, create new ones, resize, and show."""
        # Remove old labels
        for lbl in self._label_widgets:
            self._container_layout.removeWidget(lbl)
            lbl.deleteLater()
        self._label_widgets.clear()

        max_key = max((len(k) for k, _, _ in lines), default=12)

        for key, val, val_color in lines:
            # Separator line
            if key == "---":
                sep = QLabel()
                sep.setFixedHeight(1)
                sep.setStyleSheet("background: #45475a; margin: 2px 0;")
                self._container_layout.addWidget(sep)
                self._label_widgets.append(sep)
                continue

            # Pad key for fixed-width alignment
            padded_key = key.ljust(max_key)
            lbl = QLabel(
                f'<span style="color:{_KEY_COLOR};">{padded_key}</span>'
                f'  <span style="color:{val_color};"><b>{val}</b></span>'
            )
            lbl.setFont(self._font_key)
            lbl.setTextFormat(Qt.TextFormat.RichText)
            self._container_layout.addWidget(lbl)
            self._label_widgets.append(lbl)

        self.adjustSize()
        self.show()
        self.raise_()

    # ------------------------------------------------------------------
    # Painting — dark rounded background
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(_BG_COLOR))
        painter.setPen(QPen(_BORDER_COLOR, 1))
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(rect, 8, 8)

    # ------------------------------------------------------------------
    # Keyboard handling
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)

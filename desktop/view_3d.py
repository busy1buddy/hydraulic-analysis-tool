"""
3D Network Visualisation
=========================
Renders the water network in 3D using PyQtGraph's GLViewWidget.
Node elevation on Z axis, colour by WSAA compliance.
Pipes coloured by velocity, width scaled by DN.
Rotate, zoom, pan with mouse.

Particularly useful for mountainous terrain networks where
elevation differences significantly affect pressure distribution.
"""

import numpy as np

try:
    import pyqtgraph.opengl as gl
    from pyqtgraph.opengl import GLViewWidget
    HAS_GL = True
except ImportError:
    HAS_GL = False

try:
    from pyqtgraph.opengl import GLTextItem
    HAS_GL_TEXT = True
except ImportError:
    HAS_GL_TEXT = False

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QToolTip, QFrame,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QCursor


# WSAA thresholds — ref: WSAA WSA 03-2011
WSAA_MIN_PRESSURE_M = 20.0
WSAA_MAX_PRESSURE_M = 50.0
WSAA_MAX_VELOCITY_MS = 2.0
WSAA_WARN_VELOCITY = 1.5

# RGBA float tuples for OpenGL
_PASS_COLOR = (0.31, 0.78, 0.47, 1.0)    # green
_WARN_COLOR = (1.0, 0.65, 0.0, 1.0)      # yellow/orange
_FAIL_COLOR = (0.86, 0.20, 0.27, 1.0)    # red
_GREY_COLOR = (0.42, 0.44, 0.53, 1.0)    # no data


def _node_color(pressure_m):
    """WSAA compliance colour for a junction pressure."""
    if pressure_m is None:
        return _GREY_COLOR
    if pressure_m < WSAA_MIN_PRESSURE_M or pressure_m > WSAA_MAX_PRESSURE_M:
        return _FAIL_COLOR
    return _PASS_COLOR


def _pipe_color(velocity_ms):
    """WSAA compliance colour for a pipe velocity."""
    if velocity_ms is None:
        return _GREY_COLOR
    if velocity_ms > WSAA_MAX_VELOCITY_MS:
        return _FAIL_COLOR
    if velocity_ms > WSAA_WARN_VELOCITY:
        return _WARN_COLOR
    return _PASS_COLOR


def _pipe_width(diameter_m):
    """Line width scaled by DN."""
    if diameter_m is None:
        return 1
    dn = diameter_m * 1000  # WNTR stores in metres
    if dn > 300:
        return 3
    if dn >= 150:
        return 2
    return 1


def _node_size(demand):
    """Scatter size scaled by base demand. 8-20 px range."""
    if demand is None or demand <= 0:
        return 8
    # Scale: demand 0->8px, 10 LPS->20px, clamp at 20
    size = 8 + min(demand * 1000 * 1.2, 12)  # demand in m3/s
    return min(max(size, 8), 20)


class View3D(QWidget):
    """
    3D network visualisation with elevation on Z axis.

    Falls back to a message label if PyOpenGL is not installed.
    """

    def __init__(self, api, results=None, parent=None):
        # Force a top-level Window so this widget becomes its own OS
        # window instead of rendering as an embedded child that
        # overlaps the main window's dock panels.
        super().__init__(parent, Qt.WindowType.Window)
        self.api = api
        self.results = results
        self.setWindowTitle("3D Network View")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        self._z_scale = 5.0
        self._node_data = {}   # {nid: (x,y,z, pressure, demand_m3s)}
        self._pipe_data = {}   # {pid: (sn, en, velocity, dn_m, length, headloss)}
        self._center = np.zeros(3)
        self._xy_range = 1.0
        self._fit_distance = 1000.0
        self._rendered = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        if not HAS_GL:
            lbl = QLabel(
                "3D view requires PyOpenGL.\n\n"
                "Install with: pip install PyOpenGL PyOpenGL-accelerate"
            )
            lbl.setFont(QFont("Consolas", 12))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
            return

        # --- Toolbar ---
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        font = QFont("Consolas", 9)

        self.reset_btn = QPushButton("Reset View")
        self.reset_btn.setFont(font)
        self.reset_btn.clicked.connect(self._reset_view)
        toolbar.addWidget(self.reset_btn)

        self.top_btn = QPushButton("Top")
        self.top_btn.setFont(font)
        self.top_btn.clicked.connect(self._view_top)
        toolbar.addWidget(self.top_btn)

        self.side_btn = QPushButton("Side")
        self.side_btn.setFont(font)
        self.side_btn.clicked.connect(self._view_side)
        toolbar.addWidget(self.side_btn)

        toolbar.addSpacing(20)

        toolbar.addWidget(QLabel("Elevation:"))
        self.elev_slider = QSlider(Qt.Orientation.Horizontal)
        self.elev_slider.setRange(1, 20)
        self.elev_slider.setValue(5)
        self.elev_slider.setFixedWidth(120)
        self.elev_slider.setToolTip("Elevation exaggeration: 1x to 20x")
        self.elev_slider.valueChanged.connect(self._on_elev_changed)
        toolbar.addWidget(self.elev_slider)
        self.elev_label = QLabel("5x")
        self.elev_label.setFont(font)
        self.elev_label.setMinimumWidth(28)
        toolbar.addWidget(self.elev_label)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # --- GL widget ---
        self.gl_widget = GLViewWidget()
        self.gl_widget.setBackgroundColor(30, 30, 46)  # Catppuccin Mocha
        self.gl_widget.setMouseTracking(True)
        layout.addWidget(self.gl_widget, 1)

        # --- Colour legend ---
        legend = QHBoxLayout()
        legend.setSpacing(16)
        legend_font = QFont("Consolas", 8)
        for label_text, hex_color in [
            ("Nodes:", None),
            ("\u25cf PASS (20-50 m)", "#4fc878"),
            ("\u25cf FAIL (<20 / >50 m)", "#dc3246"),
            ("|", None),
            ("Pipes:", None),
            ("\u25cf OK (<1.5 m/s)", "#4fc878"),
            ("\u25cf Caution (1.5-2)", "#ffa600"),
            ("\u25cf Fail (>2.0 m/s)", "#dc3246"),
            ("\u25cf No data", "#6c7086"),
        ]:
            lbl = QLabel(label_text)
            lbl.setFont(legend_font)
            if hex_color:
                lbl.setStyleSheet(f"color: {hex_color};")
            else:
                lbl.setStyleSheet("color: #a6adc8;")
            legend.addWidget(lbl)
        legend.addStretch()
        layout.addLayout(legend)

        # --- Info panel ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #45475a;")
        layout.addWidget(sep)

        self.info_label = QLabel("")
        self.info_label.setFont(QFont("Consolas", 9))
        self.info_label.setStyleSheet("color: #cdd6f4;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

    # ------------------------------------------------------------------
    # Show / rebuild
    # ------------------------------------------------------------------

    def showEvent(self, event):
        """Render the scene on first show, once the GL context exists."""
        super().showEvent(event)
        if HAS_GL and not self._rendered:
            self._rendered = True
            QTimer.singleShot(0, self._build_scene)

    def _build_scene(self):
        """Populate the GLViewWidget after its context is ready."""
        self._collect_data()
        self._render_network()
        self._update_info_panel()

    def _collect_data(self):
        """Gather all node/pipe properties into dicts for render + tooltip."""
        if self.api is None or self.api.wn is None:
            return
        wn = self.api.wn
        pressures = (self.results or {}).get('pressures', {})
        flows = (self.results or {}).get('flows', {})

        for nid in (list(wn.junction_name_list) +
                    list(wn.reservoir_name_list) +
                    list(wn.tank_name_list)):
            node = wn.get_node(nid)
            x, y = node.coordinates
            z = getattr(node, 'elevation', getattr(node, 'base_head', 0))
            p = pressures.get(nid, {}).get('avg_m')
            # base demand in m3/s
            demand = 0.0
            try:
                demand = node.demand_timeseries_list[0].base_value
            except (AttributeError, IndexError):
                pass
            self._node_data[nid] = (x, y, z, p, demand)

        for pid in wn.pipe_name_list:
            pipe = wn.get_link(pid)
            sn, en = pipe.start_node_name, pipe.end_node_name
            fdata = flows.get(pid, {})
            v = fdata.get('max_velocity_ms', fdata.get('avg_velocity_ms'))
            dn_m = pipe.diameter
            length = pipe.length
            # headloss
            hl = fdata.get('headloss_per_km')
            self._pipe_data[pid] = (sn, en, v, dn_m, length, hl)

        if self._node_data:
            all_xyz = np.array([(x, y, z)
                                for x, y, z, *_ in self._node_data.values()])
            self._center = all_xyz.mean(axis=0)
            self._xy_range = max(
                all_xyz[:, 0].max() - all_xyz[:, 0].min(),
                all_xyz[:, 1].max() - all_xyz[:, 1].min(),
                1.0,
            )

    def _render_network(self):
        """Clear and re-render all 3D items at the current Z scale."""
        if not HAS_GL:
            return
        # Remove all items from the widget
        for item in list(self.gl_widget.items):
            self.gl_widget.removeItem(item)

        if not self._node_data:
            return

        z_scale = self._z_scale
        cx, cy, cz = self._center

        # Grid
        grid = gl.GLGridItem()
        grid.setSize(self._xy_range, self._xy_range)
        grid.setSpacing(self._xy_range / 10, self._xy_range / 10)
        self.gl_widget.addItem(grid)

        # --- Nodes ---
        spots = []
        colors = []
        sizes = []
        for nid, (x, y, z, p, demand) in self._node_data.items():
            spots.append([x - cx, y - cy, (z - cz) * z_scale])
            colors.append(_node_color(p))
            sizes.append(_node_size(demand))

        spots_arr = np.array(spots)
        colors_arr = np.array(colors)
        sizes_arr = np.array(sizes, dtype=np.float32)

        scatter = gl.GLScatterPlotItem(
            pos=spots_arr, color=colors_arr,
            size=sizes_arr, pxMode=True)
        self.gl_widget.addItem(scatter)

        # --- Node labels ---
        if HAS_GL_TEXT:
            for i, nid in enumerate(self._node_data):
                pos = spots_arr[i].copy()
                pos[2] += 2  # float above node
                try:
                    txt = GLTextItem(pos=pos, text=nid,
                                     color=QColor(180, 180, 200, 180),
                                     font=QFont("Consolas", 7))
                    self.gl_widget.addItem(txt)
                except Exception:
                    pass  # some pyqtgraph versions have different API

        # --- Pipes ---
        for pid, (sn, en, v, dn_m, length, hl) in self._pipe_data.items():
            if sn not in self._node_data or en not in self._node_data:
                continue
            x0, y0, z0, *_ = self._node_data[sn]
            x1, y1, z1, *_ = self._node_data[en]
            pts = np.array([
                [x0 - cx, y0 - cy, (z0 - cz) * z_scale],
                [x1 - cx, y1 - cy, (z1 - cz) * z_scale],
            ])
            color = _pipe_color(v)
            width = _pipe_width(dn_m)
            line = gl.GLLinePlotItem(
                pos=pts, color=color, width=width, antialias=True)
            self.gl_widget.addItem(line)

        # Camera
        self._fit_distance = max(self._xy_range * 1.5, 100.0)
        self.gl_widget.setCameraPosition(
            distance=self._fit_distance,
            elevation=30, azimuth=45)

    # ------------------------------------------------------------------
    # Info panel
    # ------------------------------------------------------------------

    def _update_info_panel(self):
        """Populate the summary info panel below the 3D view."""
        n_nodes = len(self._node_data)
        n_pipes = len(self._pipe_data)

        if not self.results:
            self.info_label.setText(
                f"Network: {n_nodes} nodes, {n_pipes} pipes  |  "
                "Run analysis first (F5) for pressure/velocity colours."
            )
            return

        pressures = [p for _, (_, _, _, p, _) in self._node_data.items()
                     if p is not None]
        velocities = [v for _, (_, _, v, _, _, _) in self._pipe_data.items()
                      if v is not None]

        p_min = min(pressures) if pressures else 0
        p_max = max(pressures) if pressures else 0
        v_max = max(velocities) if velocities else 0

        n_pass = sum(1 for p in pressures
                     if WSAA_MIN_PRESSURE_M <= p <= WSAA_MAX_PRESSURE_M)
        n_fail = len(pressures) - n_pass

        self.info_label.setText(
            f"Network: {n_nodes} nodes, {n_pipes} pipes  |  "
            f"Pressure: {p_min:.1f}\u2013{p_max:.1f} m  |  "
            f"Max velocity: {v_max:.2f} m/s  |  "
            f"WSAA: {n_pass} PASS, {n_fail} FAIL"
        )

    # ------------------------------------------------------------------
    # Toolbar actions
    # ------------------------------------------------------------------

    def _on_elev_changed(self, value):
        self._z_scale = float(value)
        self.elev_label.setText(f"{value}x")
        if self._rendered:
            self._render_network()

    def _reset_view(self):
        if HAS_GL:
            self.gl_widget.setCameraPosition(
                distance=self._fit_distance, elevation=30, azimuth=45)

    def _view_top(self):
        if HAS_GL:
            self.gl_widget.setCameraPosition(elevation=90, azimuth=0)

    def _view_side(self):
        if HAS_GL:
            self.gl_widget.setCameraPosition(elevation=0, azimuth=0)

    # ------------------------------------------------------------------
    # Hover tooltips
    # ------------------------------------------------------------------

    def mouseMoveEvent(self, event):
        """Show engineering data tooltip when hovering near elements."""
        super().mouseMoveEvent(event)
        if not HAS_GL or not self._node_data:
            return
        # Map cursor position relative to the GL widget
        gl_pos = self.gl_widget.mapFromParent(event.pos())
        if not self.gl_widget.rect().contains(gl_pos):
            QToolTip.hideText()
            return

        # Use itemsAt to find the closest item under the cursor.
        # pyqtgraph's itemsAt returns items near the given screen coord.
        try:
            items = self.gl_widget.itemsAt((gl_pos.x(), gl_pos.y(), 4, 4))
        except Exception:
            return

        tip = self._tooltip_for_items(items)
        if tip:
            QToolTip.showText(QCursor.pos(), tip, self)
        else:
            QToolTip.hideText()

    def _tooltip_for_items(self, items):
        """Build a tooltip string from hovered GL items."""
        for item in items:
            if isinstance(item, gl.GLScatterPlotItem):
                # Show the first node's info (hover resolution is imprecise)
                for nid, (x, y, z, p, demand) in self._node_data.items():
                    if p is not None:
                        d_lps = demand * 1000
                        return (
                            f"{nid}  |  Elev: {z:.0f} m  |  "
                            f"Pressure: {p:.1f} m  |  "
                            f"Demand: {d_lps:.1f} LPS"
                        )
                    else:
                        return f"{nid}  |  Elev: {z:.0f} m  |  No results"
            if isinstance(item, gl.GLLinePlotItem):
                for pid, (sn, en, v, dn_m, length, hl) in self._pipe_data.items():
                    dn = int((dn_m or 0) * 1000)
                    v_str = f"{v:.2f} m/s" if v is not None else "N/A"
                    hl_str = f"{hl:.1f} m/km" if hl is not None else "N/A"
                    return (
                        f"{pid}  |  DN{dn}  |  L={length:.0f} m  |  "
                        f"V={v_str}  |  HL={hl_str}"
                    )
        return ""

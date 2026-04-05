"""
3D Network Visualisation
=========================
Renders the water network in 3D using PyQtGraph's GLViewWidget.
Node elevation on Z axis, pipe colour = WSAA compliance.
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

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


# WSAA compliance colours (RGBA float tuples for OpenGL)
_PASS_COLOR = (0.31, 0.78, 0.47, 1.0)    # green
_WARN_COLOR = (1.0, 0.65, 0.0, 1.0)      # orange
_FAIL_COLOR = (0.86, 0.20, 0.27, 1.0)    # red
_GREY_COLOR = (0.42, 0.44, 0.53, 1.0)    # no results


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
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        if not HAS_GL:
            lbl = QLabel(
                "3D view requires PyOpenGL.\n\n"
                "Install with: pip install PyOpenGL PyOpenGL-accelerate"
            )
            lbl.setFont(QFont("Consolas", 12))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
            return

        # Toolbar
        toolbar = QHBoxLayout()
        self.reset_btn = QPushButton("Reset View")
        self.reset_btn.setFont(QFont("Consolas", 9))
        self.reset_btn.clicked.connect(self._reset_view)
        toolbar.addWidget(self.reset_btn)

        self.top_btn = QPushButton("Top")
        self.top_btn.setFont(QFont("Consolas", 9))
        self.top_btn.clicked.connect(self._view_top)
        toolbar.addWidget(self.top_btn)

        self.side_btn = QPushButton("Side")
        self.side_btn.setFont(QFont("Consolas", 9))
        self.side_btn.clicked.connect(self._view_side)
        toolbar.addWidget(self.side_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # GL widget
        self.gl_widget = GLViewWidget()
        self.gl_widget.setBackgroundColor(30, 30, 46)  # Catppuccin Mocha
        layout.addWidget(self.gl_widget)

        # Add grid
        grid = gl.GLGridItem()
        grid.setSize(1000, 1000)
        grid.setSpacing(100, 100)
        self.gl_widget.addItem(grid)

        self._render_network()

    def _render_network(self):
        """Render all nodes and pipes in 3D."""
        if self.api is None or self.api.wn is None:
            return

        wn = self.api.wn
        pressures = (self.results or {}).get('pressures', {})
        flows = (self.results or {}).get('flows', {})

        # Collect node positions with elevation as Z
        node_pos = {}
        for nid in list(wn.junction_name_list) + list(wn.reservoir_name_list) + list(wn.tank_name_list):
            node = wn.get_node(nid)
            x, y = node.coordinates
            z = getattr(node, 'elevation', getattr(node, 'base_head', 0))
            node_pos[nid] = (x, y, z)

        if not node_pos:
            return

        # Center the view
        all_xyz = np.array(list(node_pos.values()))
        center = all_xyz.mean(axis=0)

        # Elevation exaggeration: 5x makes terrain readable without
        # distorting the network into an abstract sculpture.
        xy_range = max(all_xyz[:, 0].max() - all_xyz[:, 0].min(),
                       all_xyz[:, 1].max() - all_xyz[:, 1].min())
        z_scale = 5.0

        # Render nodes as scatter
        spots = []
        colors = []
        for nid, (x, y, z) in node_pos.items():
            spots.append([x - center[0], y - center[1], (z - center[2]) * z_scale])
            # Colour by WSAA compliance
            p = pressures.get(nid, {}).get('avg_m')
            if p is None:
                colors.append(_GREY_COLOR)
            elif p < 20:
                colors.append(_FAIL_COLOR)
            elif p > 50:
                colors.append(_WARN_COLOR)
            else:
                colors.append(_PASS_COLOR)

        spots_arr = np.array(spots)
        colors_arr = np.array(colors)

        scatter = gl.GLScatterPlotItem(
            pos=spots_arr, color=colors_arr,
            size=8, pxMode=True)
        self.gl_widget.addItem(scatter)

        # Render pipes as lines
        for pid in wn.pipe_name_list:
            pipe = wn.get_link(pid)
            sn, en = pipe.start_node_name, pipe.end_node_name
            if sn not in node_pos or en not in node_pos:
                continue

            x0, y0, z0 = node_pos[sn]
            x1, y1, z1 = node_pos[en]
            pts = np.array([
                [x0 - center[0], y0 - center[1], (z0 - center[2]) * z_scale],
                [x1 - center[0], y1 - center[1], (z1 - center[2]) * z_scale],
            ])

            # Colour by velocity compliance
            fdata = flows.get(pid, {})
            v = fdata.get('max_velocity_ms')
            if v is None:
                color = _GREY_COLOR
            elif v > 2.0:
                color = _FAIL_COLOR
            elif v > 1.5:
                color = _WARN_COLOR
            else:
                color = _PASS_COLOR

            line = gl.GLLinePlotItem(
                pos=pts, color=color, width=2, antialias=True)
            self.gl_widget.addItem(line)

        # Default camera: 30 deg elevation, 45 deg azimuth, framed to
        # the network's XY extent so the user sees the whole layout.
        self._fit_distance = max(xy_range * 1.5, 100.0)
        self.gl_widget.setCameraPosition(
            distance=self._fit_distance,
            elevation=30,
            azimuth=45,
        )

    def _reset_view(self):
        if HAS_GL:
            dist = getattr(self, '_fit_distance', 1000.0)
            self.gl_widget.setCameraPosition(
                distance=dist, elevation=30, azimuth=45)

    def _view_top(self):
        if HAS_GL:
            self.gl_widget.setCameraPosition(elevation=90, azimuth=0)

    def _view_side(self):
        if HAS_GL:
            self.gl_widget.setCameraPosition(elevation=0, azimuth=0)

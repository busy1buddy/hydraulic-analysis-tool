"""
Pipe Profile Longitudinal Section
===================================
Select a path through the network and view the hydraulic profile:
distance on X-axis, elevation + HGL on Y-axis.
Shows pipe invert, hydraulic grade line, and pressure head.
"""

import pyqtgraph as pg

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QAbstractItemView, QGroupBox,
    QMessageBox, QTableWidget, QTableWidgetItem, QSplitter,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


class PipeProfileDialog(QDialog):
    """Longitudinal section dialog — select path, view HGL profile."""

    def __init__(self, api, results=None, parent=None):
        super().__init__(parent)
        self.api = api
        self.results = results
        self._path = []
        self.setWindowTitle("Pipe Profile — Longitudinal Section")
        self.setMinimumSize(1000, 600)
        self._setup_ui()
        self._populate_nodes()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left: Path selection ---
        left = QGroupBox("Path Selection")
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Click nodes in order to build a path:"))

        self.node_list = QListWidget()
        self.node_list.setFont(QFont("Consolas", 9))
        self.node_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.node_list.itemDoubleClicked.connect(self._add_to_path)
        left_layout.addWidget(self.node_list)

        left_layout.addWidget(QLabel("Current path:"))
        self.path_list = QListWidget()
        self.path_list.setFont(QFont("Consolas", 9))
        left_layout.addWidget(self.path_list)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Add to Path")
        self.add_btn.setFont(QFont("Consolas", 9))
        self.add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(self.add_btn)

        self.clear_btn = QPushButton("Clear Path")
        self.clear_btn.setFont(QFont("Consolas", 9))
        self.clear_btn.clicked.connect(self._on_clear)
        btn_row.addWidget(self.clear_btn)

        self.draw_btn = QPushButton("Draw Profile")
        self.draw_btn.setFont(QFont("Consolas", 10))
        self.draw_btn.clicked.connect(self._on_draw)
        btn_row.addWidget(self.draw_btn)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left)

        # --- Right: Profile chart + warnings ---
        right = QGroupBox("Longitudinal Section")
        right_layout = QVBoxLayout(right)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#1e1e2e')
        self.plot_widget.setLabel('bottom', 'Chainage (m)')
        self.plot_widget.setLabel('left', 'Elevation (m AHD)')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.addLegend(offset=(10, 10))
        right_layout.addWidget(self.plot_widget)

        self.warnings_label = QLabel("")
        self.warnings_label.setFont(QFont("Consolas", 9))
        self.warnings_label.setWordWrap(True)
        self.warnings_label.setStyleSheet("color: #f9e2af;")
        right_layout.addWidget(self.warnings_label)

        splitter.addWidget(right)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter)

    def _populate_nodes(self):
        if self.api.wn is None:
            return
        for nid in (list(self.api.wn.reservoir_name_list) +
                    list(self.api.wn.tank_name_list) +
                    list(self.api.wn.junction_name_list)):
            self.node_list.addItem(nid)

    def _add_to_path(self, item):
        nid = item.text()
        if nid not in self._path:
            self._path.append(nid)
            self.path_list.addItem(nid)

    def _on_add(self):
        item = self.node_list.currentItem()
        if item:
            self._add_to_path(item)

    def _on_clear(self):
        self._path.clear()
        self.path_list.clear()
        self.plot_widget.clear()
        self.warnings_label.clear()

    def _on_draw(self):
        if len(self._path) < 2:
            QMessageBox.warning(self, "Insufficient Path",
                "Select at least 2 nodes to draw a profile.")
            return

        profile = self.api.compute_pipe_profile(self._path, self.results)

        if 'error' in profile:
            QMessageBox.warning(self, "Profile Error", profile['error'])
            return

        self.plot_widget.clear()

        stations = profile['stations']
        ground = profile['ground']
        hgl = profile['hgl']

        # Ground / invert line (brown fill)
        self.plot_widget.plot(stations, ground,
                              pen=pg.mkPen('#a18072', width=2),
                              fillLevel=min(ground) - 5,
                              fillBrush=pg.mkBrush(100, 80, 60, 40),
                              name='Ground / Invert')

        # HGL line (blue)
        self.plot_widget.plot(stations, hgl,
                              pen=pg.mkPen('#89b4fa', width=3),
                              name='HGL (Hydraulic Grade Line)')

        # Pressure head shading between HGL and ground
        import numpy as np
        s_arr = np.array(stations)
        g_arr = np.array(ground)
        h_arr = np.array(hgl)

        # Mark nodes
        scatter = pg.ScatterPlotItem(
            pos=list(zip(stations, ground)),
            size=10, brush=pg.mkBrush('#f38ba8'),
            pen=pg.mkPen('#313244', width=1),
            name='Nodes',
        )
        self.plot_widget.addItem(scatter)

        # Label nodes
        font = QFont("Consolas", 7)
        for i, nid in enumerate(profile['node_ids']):
            text = pg.TextItem(nid, color='#cdd6f4', anchor=(0.5, 1.2))
            text.setPos(stations[i], ground[i])
            text.setFont(font)
            self.plot_widget.addItem(text)

        # Label pipe diameters at midpoints
        for pipe in profile['pipes']:
            mid_s = (pipe['start_station'] + pipe['end_station']) / 2
            # Find interpolated ground at midpoint
            mid_g = ground[0]  # fallback
            for j in range(len(stations) - 1):
                if stations[j] <= mid_s <= stations[j + 1]:
                    t = (mid_s - stations[j]) / (stations[j + 1] - stations[j])
                    mid_g = ground[j] + t * (ground[j + 1] - ground[j])
                    break
            text = pg.TextItem(f"DN{pipe['diameter_mm']}", color='#a6adc8',
                               anchor=(0.5, -0.5))
            text.setPos(mid_s, mid_g)
            text.setFont(font)
            self.plot_widget.addItem(text)

        # Warnings
        if profile['warnings']:
            self.warnings_label.setText(
                "Warnings:\n" + "\n".join(f"  - {w}" for w in profile['warnings']))
        else:
            self.warnings_label.setText("No warnings — profile is hydraulically sound.")

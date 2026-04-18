"""
Profile Panel — Longitudinal Elevation & HGL Plotting
====================================================
Displays a 2D profile of elevation and Hydraulic Grade Line (HGL) 
along a selected pipeline path (Chainage vs Elevation).
"""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

class ProfilePanel(QWidget):
    """Widget for displaying pipeline elevation and HGL profiles."""
    
    path_selection_toggled = pyqtSignal(bool)
    clear_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(2)

        # Toolbar
        self.toolbar = QHBoxLayout()
        
        self.select_path_btn = QPushButton("Select Path")
        self.select_path_btn.setCheckable(True)
        self.select_path_btn.setFont(QFont("Consolas", 9))
        self.select_path_btn.toggled.connect(self.path_selection_toggled.emit)
        self.toolbar.addWidget(self.select_path_btn)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFont(QFont("Consolas", 9))
        self.clear_btn.clicked.connect(self.clear_requested.emit)
        self.toolbar.addWidget(self.clear_btn)
        
        self.hgl_btn = QPushButton("HGL")
        self.hgl_btn.setCheckable(True)
        self.hgl_btn.setChecked(True)
        self.hgl_btn.setFont(QFont("Consolas", 9))
        self.hgl_btn.toggled.connect(self._on_hgl_toggled)
        self.toolbar.addWidget(self.hgl_btn)
        
        self.toolbar.addStretch()
        
        self.layout.addLayout(self.toolbar)

        # Plot Widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#1e1e2e')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', 'Elevation / Head', units='m')
        self.plot_widget.setLabel('bottom', 'Chainage', units='m')
        self.layout.addWidget(self.plot_widget)

        # Legend
        self.plot_widget.addLegend(offset=(30, 30))

        # Data Items
        self.ground_line = pg.PlotDataItem(
            pen=pg.mkPen('#a6e3a1', width=1.5),
            name="Ground Level (AHD)"
        )
        self.fill_item = pg.FillBetweenItem(
            curve1=self.ground_line,
            curve2=pg.PlotDataItem(pen=None),
            brush=pg.mkBrush(166, 227, 161, 40)
        )
        self.plot_widget.addItem(self.ground_line)
        self.plot_widget.addItem(self.fill_item)

        self.pipe_line = self.plot_widget.plot(
            pen=pg.mkPen('#fab387', width=2),
            name="Pipe Elevation"
        )

        self.hgl_line = self.plot_widget.plot(
            pen=pg.mkPen('#89b4fa', width=2, style=Qt.PenStyle.DashLine),
            name="Hydraulic Grade (HGL)"
        )
        
        self.node_markers = pg.ScatterPlotItem(
            size=10, brush=pg.mkBrush('#fab387'),
            pen=pg.mkPen('#1e1e2e', width=1),
            name="Key Nodes"
        )
        self.plot_widget.addItem(self.node_markers)
        
        self.appurtenance_markers = pg.ScatterPlotItem(
            size=12, symbol='t', brush=pg.mkBrush('#f38ba8'),
            name="Appurtenances (Pumps/Valves)"
        )
        self.plot_widget.addItem(self.appurtenance_markers)

        self.vacuum_overlay = pg.PlotDataItem(
            pen=pg.mkPen('#f38ba8', width=4, style=Qt.PenStyle.SolidLine),
            name="Vacuum / Sub-Atmospheric Zone"
        )
        self.plot_widget.addItem(self.vacuum_overlay)
        self.vacuum_overlay.hide()

        self.cavitation_overlay = pg.PlotDataItem(
            pen=pg.mkPen('#e64553', width=6, style=Qt.PenStyle.SolidLine),
            name="Cavitation / Column Separation Risk"
        )
        self.plot_widget.addItem(self.cavitation_overlay)
        self.cavitation_overlay.hide()
        
        self.suggested_av_markers = pg.ScatterPlotItem(
            size=12, symbol='t', brush=pg.mkBrush('#fab387'),
            pen=pg.mkPen('#1e1e2e', width=1),
            name="Suggested Air Valve"
        )
        self.plot_widget.addItem(self.suggested_av_markers)
        
        self.suggested_scour_markers = pg.ScatterPlotItem(
            size=12, symbol='s', brush=pg.mkBrush('#94e2d5'),
            pen=pg.mkPen('#1e1e2e', width=1),
            name="Suggested Scour Valve"
        )
        self.plot_widget.addItem(self.suggested_scour_markers)

        # Visibility states
        self._show_hgl = True

        # Info Label
        self.info_label = QLabel("Select a pipeline path to view profile.")
        self.info_label.setFont(QFont("Consolas", 9))
        self.info_label.setStyleSheet("color: #bac2de;")
        self.layout.addWidget(self.info_label)

    def _on_hgl_toggled(self, checked):
        self._show_hgl = checked
        if checked:
            self.hgl_line.show()
        else:
            self.hgl_line.hide()

    def update_profile(self, chainage, pipe_elev, ground_elev=None, hgl=None, 
                       labels=None, appurtenances=None, vacuum_zones=None, **kwargs):
        """
        Update the plot with new profile data.
        """
        if not chainage or not pipe_elev:
            self.clear()
            return

        self.pipe_line.setData(chainage, pipe_elev)
        
        # Vacuum Overlay
        if vacuum_zones and len(vacuum_zones) > 0:
            vx, vy = [], []
            for start_c, end_c in vacuum_zones:
                # Find indices in chainage
                idx1 = np.searchsorted(chainage, start_c)
                idx2 = np.searchsorted(chainage, end_c)
                vx.extend(chainage[idx1:idx2+1])
                vy.extend(pipe_elev[idx1:idx2+1])
                vx.append(float('nan')) # Break segments
                vy.append(float('nan'))
            self.vacuum_overlay.setData(vx, vy)
            self.vacuum_overlay.show()
        else:
            self.vacuum_overlay.hide()
            
        # Cavitation Overlay
        if 'cavitation_risk' in kwargs and kwargs['cavitation_risk']:
            cx, cy = [], []
            for start_c, end_c in kwargs['cavitation_risk']:
                idx1 = np.searchsorted(chainage, start_c)
                idx2 = np.searchsorted(chainage, end_c)
                cx.extend(chainage[idx1:idx2+1])
                cy.extend(pipe_elev[idx1:idx2+1])
                cx.append(float('nan'))
                cy.append(float('nan'))
            self.cavitation_overlay.setData(cx, cy)
            self.cavitation_overlay.show()
        else:
            self.cavitation_overlay.hide()

        # Suggested Air Valves
        if 'suggested_avs' in kwargs and kwargs['suggested_avs']:
            sav = kwargs['suggested_avs']
            sx = [s['chainage'] for s in sav]
            sy = [s['elevation'] for s in sav]
            stips = [s['label'] for s in sav]
            self.suggested_av_markers.setData(sx, sy, tip=stips)
            self.suggested_av_markers.show()
        else:
            self.suggested_av_markers.hide()
            
        # Suggested Scour Valves
        if 'suggested_scours' in kwargs and kwargs['suggested_scours']:
            ssc = kwargs['suggested_scours']
            sx = [s['chainage'] for s in ssc]
            sy = [s['elevation'] for s in ssc]
            stips = [s['label'] for s in ssc]
            self.suggested_scour_markers.setData(sx, sy, tip=stips)
            self.suggested_scour_markers.show()
        else:
            self.suggested_scour_markers.hide()
        
        if ground_elev is not None and len(ground_elev) == len(chainage):
            self.ground_line.setData(chainage, ground_elev)
            self.ground_line.show()
            self.fill_item.show()
        else:
            # If no ground data provided, assume pipe is at ground for now
            self.ground_line.setData(chainage, pipe_elev)
            self.ground_line.show()
            self.fill_item.show()
        
        # Update markers for key nodes
        self.node_markers.setData(chainage, pipe_elev, tip=labels)
        
        # Appurtenances (Pumps, Valves)
        if appurtenances:
            # appurtenances: list of {'chainage', 'elevation', 'label'}
            ax = [a['chainage'] for a in appurtenances]
            ay = [a['elevation'] for a in appurtenances]
            atips = [a['label'] for a in appurtenances]
            self.appurtenance_markers.setData(ax, ay, tip=atips)
            self.appurtenance_markers.show()
        else:
            self.appurtenance_markers.hide()

        if hgl is not None and len(hgl) == len(chainage):
            self.hgl_line.setData(chainage, hgl)
            if self._show_hgl:
                self.hgl_line.show()
            else:
                self.hgl_line.hide()
        else:
            self.hgl_line.hide()

        self.info_label.setText(f"Profile: {chainage[-1]:.0f}m total length | {len(chainage)} nodes.")
        self.plot_widget.autoRange()

    def clear(self):
        """Clear the profile plot."""
        self.ground_line.setData([], [])
        self.pipe_line.setData([], [])
        self.hgl_line.setData([], [])
        self.node_markers.setData([], [])
        self.appurtenance_markers.setData([], [])
        self.vacuum_overlay.hide()
        self.cavitation_overlay.hide()
        self.suggested_av_markers.hide()
        self.suggested_scour_markers.hide()
        self.info_label.setText("Select a pipeline path to view profile.")

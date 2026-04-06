"""
Animation Panel — Transient playback controls
===============================================
Transport controls for stepping through TSNet/WNTR-MSX transient simulation
results frame by frame, with play/pause, speed multiplier, and loop mode.

Transient data format (matches TSNet output wrangled by HydraulicAPI):
  timestamps : np.ndarray   shape (T,)  seconds
  node_data  : dict  {node_id: {'head': np.ndarray shape (T,), ...}}
  pipe_data  : dict  {pipe_id: {'start_node_velocity': np.ndarray (T,),
                                 'end_node_velocity':   np.ndarray (T,),
                                 'start_node_flowrate': np.ndarray (T,),
                                 ...}}
"""

import numpy as np

import logging

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QCheckBox, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont


_SPEEDS = [0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
_SPEED_LABELS = ["0.25x", "0.5x", "1x", "2x", "5x", "10x"]
_BASE_INTERVAL_MS = 33   # ~30 fps at 1x speed


class AnimationPanel(QWidget):
    """
    Transient-result playback panel.

    Signals
    -------
    frame_changed(int) : emitted whenever the displayed timestep changes.
                         The integer is the 0-based frame index.
    """

    frame_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timestamps: np.ndarray | None = None
        self._node_data: dict = {}
        self._pipe_data: dict = {}
        self._current_frame: int = 0
        self._playing: bool = False

        self._timer = QTimer(self)
        self._timer.setInterval(_BASE_INTERVAL_MS)
        self._timer.timeout.connect(self._on_timer_tick)

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        font = QFont("Consolas", 9)

        # --- Transport buttons ---
        btn_row = QHBoxLayout()

        self.first_btn = QPushButton("|<")
        self.prev_btn = QPushButton("<")
        self.play_btn = QPushButton("Play")
        self.next_btn = QPushButton(">")
        self.last_btn = QPushButton(">|")

        for btn in (self.first_btn, self.prev_btn, self.play_btn,
                    self.next_btn, self.last_btn):
            btn.setFont(font)
            btn.setFixedHeight(26)
            btn_row.addWidget(btn)

        self.first_btn.clicked.connect(self._on_first)
        self.prev_btn.clicked.connect(self._on_prev)
        self.play_btn.clicked.connect(self._on_play_pause)
        self.next_btn.clicked.connect(self._on_next)
        self.last_btn.clicked.connect(self._on_last)

        layout.addLayout(btn_row)

        # --- Slider ---
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)

        # --- Time label ---
        self.time_label = QLabel("t = 0.00 s / 0.00 s")
        self.time_label.setFont(font)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.time_label)

        # --- Speed + Loop row ---
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("Speed:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(_SPEED_LABELS)
        self.speed_combo.setCurrentIndex(2)   # default 1x
        self.speed_combo.setFont(font)
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        self.speed_combo.setToolTip(
            "Animation playback speed.\n"
            "1x = real time, 4x = 4× faster.")
        ctrl_row.addWidget(self.speed_combo)

        self.loop_check = QCheckBox("Loop")
        self.loop_check.setFont(font)
        self.loop_check.setToolTip(
            "Continuously replay the animation when it reaches the end.")
        ctrl_row.addWidget(self.loop_check)

        ctrl_row.addStretch()

        self.export_btn = QPushButton("Export GIF...")
        self.export_btn.setFont(font)
        self.export_btn.setToolTip(
            "Export animation as GIF or MP4 (requires Pillow; imageio for MP4)")
        self.export_btn.clicked.connect(self._on_export)
        ctrl_row.addWidget(self.export_btn)

        layout.addLayout(ctrl_row)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._update_time_label()
        self._update_buttons_enabled()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_transient_data(self, timestamps: np.ndarray, node_data: dict, pipe_data: dict):
        """
        Load transient simulation data.

        Parameters
        ----------
        timestamps : np.ndarray, shape (T,), seconds
        node_data  : {node_id: {'head': np.ndarray(T), ...}}
        pipe_data  : {pipe_id: {'start_node_velocity': np.ndarray(T), ...}}
        """
        # Stop any ongoing playback
        self._stop_playback()

        self._timestamps = np.asarray(timestamps, dtype=float)
        self._node_data = node_data
        self._pipe_data = pipe_data
        self._current_frame = 0

        n = max(len(self._timestamps) - 1, 0)
        self.slider.setMaximum(n)
        self.slider.setValue(0)

        self._update_time_label()
        self._update_buttons_enabled()

    @property
    def n_frames(self) -> int:
        """Number of timesteps in the loaded data."""
        if self._timestamps is None:
            return 0
        return len(self._timestamps)

    @property
    def current_frame(self) -> int:
        return self._current_frame

    @property
    def timestamps(self) -> np.ndarray | None:
        return self._timestamps

    @property
    def node_data(self) -> dict:
        return self._node_data

    @property
    def pipe_data(self) -> dict:
        return self._pipe_data

    # ------------------------------------------------------------------
    # Transport actions
    # ------------------------------------------------------------------

    def _on_first(self):
        self._set_frame(0)

    def _on_last(self):
        self._set_frame(self.n_frames - 1)

    def _on_prev(self):
        self._set_frame(max(0, self._current_frame - 1))

    def _on_next(self):
        n = self.n_frames
        if n == 0:
            return
        next_f = self._current_frame + 1
        if next_f >= n:
            if self.loop_check.isChecked():
                next_f = 0
            else:
                next_f = n - 1
        self._set_frame(next_f)

    def _on_play_pause(self):
        if self._playing:
            self._stop_playback()
        else:
            self._start_playback()

    def _start_playback(self):
        if self.n_frames == 0:
            return
        self._playing = True
        self.play_btn.setText("Pause")
        self._update_timer_interval()
        self._timer.start()

    def _stop_playback(self):
        self._playing = False
        self.play_btn.setText("Play")
        self._timer.stop()

    def _on_timer_tick(self):
        """Advance one frame; handle end-of-sequence."""
        if self.n_frames == 0:
            self._stop_playback()
            return

        next_f = self._current_frame + 1
        if next_f >= self.n_frames:
            if self.loop_check.isChecked():
                next_f = 0
            else:
                self._stop_playback()
                return

        self._set_frame(next_f)

    def _on_slider_changed(self, value: int):
        if value != self._current_frame:
            self._set_frame(value)

    def _on_speed_changed(self):
        self._update_timer_interval()

    def _update_timer_interval(self):
        idx = self.speed_combo.currentIndex()
        speed = _SPEEDS[idx]
        interval = max(1, int(_BASE_INTERVAL_MS / speed))
        self._timer.setInterval(interval)

    def _set_frame(self, frame: int):
        n = self.n_frames
        if n == 0:
            return
        frame = max(0, min(frame, n - 1))
        self._current_frame = frame

        # Update slider without triggering _on_slider_changed recursively
        self.slider.blockSignals(True)
        self.slider.setValue(frame)
        self.slider.blockSignals(False)

        self._update_time_label()
        self.frame_changed.emit(frame)

    def _update_time_label(self):
        if self._timestamps is None or len(self._timestamps) == 0:
            self.time_label.setText("t = 0.00 s / 0.00 s")
            return
        t_cur = self._timestamps[self._current_frame]
        t_total = self._timestamps[-1]
        self.time_label.setText(f"t = {t_cur:.2f} s / {t_total:.2f} s")

    def _update_buttons_enabled(self):
        has_data = self.n_frames > 0
        for btn in (self.first_btn, self.prev_btn, self.play_btn,
                    self.next_btn, self.last_btn):
            btn.setEnabled(has_data)
        self.slider.setEnabled(has_data)
        self.export_btn.setEnabled(has_data)

    # ------------------------------------------------------------------
    # GIF / MP4 export
    # ------------------------------------------------------------------

    def _on_export(self):
        """Export animation frames as GIF or MP4."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog

        if self.n_frames == 0:
            QMessageBox.warning(self, "No Data",
                "No animation data loaded. Run an analysis first.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Animation", "",
            "GIF Image (*.gif);;MP4 Video (*.mp4);;All Files (*)"
        )
        if not path:
            return

        is_mp4 = path.lower().endswith('.mp4')

        if is_mp4:
            try:
                import imageio
            except ImportError:
                QMessageBox.warning(self, "Missing Dependency",
                    "MP4 export requires the imageio package.\n\n"
                    "Install with: pip install imageio[ffmpeg]")
                return
        else:
            try:
                from PIL import Image
            except ImportError:
                QMessageBox.warning(self, "Missing Dependency",
                    "GIF export requires the Pillow package.\n\n"
                    "Install with: pip install Pillow")
                return

        # Capture frames
        progress = QProgressDialog(
            "Exporting animation...", "Cancel", 0, self.n_frames, self)
        progress.setWindowTitle("Export")
        progress.setMinimumDuration(0)

        frames = []
        original_frame = self._current_frame

        for i in range(self.n_frames):
            if progress.wasCanceled():
                self._set_frame(original_frame)
                return

            progress.setValue(i)
            self._set_frame(i)

            # Let Qt process the frame update
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()

            # Grab the parent canvas widget if available
            canvas = self._find_canvas()
            if canvas is None:
                QMessageBox.warning(self, "Export Error",
                    "Cannot find canvas widget for frame capture.")
                self._set_frame(original_frame)
                return

            pixmap = canvas.plot_widget.grab()
            img = pixmap.toImage()
            # Convert QImage to bytes
            from PyQt6.QtCore import QBuffer, QIODevice
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            img.save(buf, 'PNG')
            frames.append(buf.data().data())

        progress.setValue(self.n_frames)
        self._set_frame(original_frame)

        # Write output
        try:
            if is_mp4:
                import imageio
                import io
                from PIL import Image as PILImage
                writer = imageio.get_writer(path, fps=15)
                for frame_bytes in frames:
                    pil_img = PILImage.open(io.BytesIO(frame_bytes))
                    writer.append_data(np.array(pil_img))
                writer.close()
            else:
                from PIL import Image
                import io
                pil_frames = []
                for frame_bytes in frames:
                    pil_frames.append(Image.open(io.BytesIO(frame_bytes)))
                if pil_frames:
                    pil_frames[0].save(
                        path, save_all=True,
                        append_images=pil_frames[1:],
                        duration=66,  # ~15 fps
                        loop=0,
                    )

            QMessageBox.information(self, "Export Complete",
                f"Animation saved to:\n{path}\n\n"
                f"{self.n_frames} frames exported.")

        except (OSError, ValueError, RuntimeError) as e:
            QMessageBox.critical(self, "Export Error",
                f"Could not save animation.\n\n{e}")

    def _find_canvas(self):
        """Find the parent NetworkCanvas widget."""
        # Walk up the widget tree to find the MainWindow, then get its canvas
        widget = self.parent()
        while widget is not None:
            if hasattr(widget, 'canvas'):
                return widget.canvas
            widget = widget.parent() if hasattr(widget, 'parent') else None
        return None

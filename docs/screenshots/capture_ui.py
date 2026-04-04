"""
Automated UI Screenshot Capture (Qt-native rendering)
======================================================
Uses QWidget.grab() to render the app to images — works headlessly
without a desktop compositor. Exercises the full UI workflow.

Run: python docs/screenshots/capture_ui.py
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

SCREENSHOT_DIR = os.path.join(ROOT, 'docs', 'screenshots')
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from desktop.main_window import MainWindow


def screenshot(widget, name):
    """Grab the widget's rendered pixmap and save to file."""
    path = os.path.join(SCREENSHOT_DIR, name)
    pixmap = widget.grab()
    pixmap.save(path)
    size = os.path.getsize(path)
    print(f"  Saved: {name} ({pixmap.width()}x{pixmap.height()}, {size:,} bytes)")


def main():
    print("=" * 60)
    print("UI Screenshot Capture (Qt-native rendering)")
    print("=" * 60)

    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1400, 900)
    w.show()
    app.processEvents()

    # --- 01: Startup ---
    print("\n1. Empty startup state...")
    screenshot(w, '01_startup.png')

    # --- 02: Load network ---
    print("\n2. Loading australian_network.inp...")
    import wntr
    w.api.wn = wntr.network.WaterNetworkModel('models/australian_network.inp')
    w.api._inp_file = os.path.abspath('models/australian_network.inp')
    w._current_file = w.api._inp_file
    w._populate_explorer()
    w._update_status_bar()
    w.canvas.set_api(w.api)
    w.setWindowTitle(f"Hydraulic Analysis Tool — australian_network.inp")
    app.processEvents()
    screenshot(w, '02_network_loaded.png')

    # --- 03: Run steady state ---
    print("\n3. Running steady-state analysis...")
    results = w.api.run_steady_state(save_plot=False)
    w._on_analysis_finished(results)
    app.processEvents()
    screenshot(w, '03_after_analysis.png')

    # --- 04: Select pipe P4 ---
    print("\n4. Selecting pipe P4...")
    w._on_canvas_element_selected('P4', 'pipe')
    app.processEvents()
    screenshot(w, '04_pipe_selected.png')

    # --- 05: Switch to Velocity color mode ---
    print("\n5. Switching to Velocity color mode...")
    w.canvas.color_mode_combo.setCurrentText("Velocity")
    app.processEvents()
    screenshot(w, '05_velocity_mode.png')

    # --- 06: Toggle Slurry Mode ---
    print("\n6. Enabling Slurry Mode...")
    w.slurry_act.setChecked(True)
    app.processEvents()
    screenshot(w, '06_slurry_mode.png')

    # --- 07: Switch to Pressure color mode ---
    print("\n7. Switching to Pressure color mode...")
    w.canvas.color_mode_combo.setCurrentText("Pressure")
    app.processEvents()
    screenshot(w, '07_pressure_mode.png')

    # --- 08: Toggle labels on ---
    print("\n8. Turning on node/pipe labels...")
    w.canvas.labels_btn.setChecked(True)
    app.processEvents()
    screenshot(w, '08_with_labels.png')

    # --- 09: Select junction J4 (low pressure) ---
    print("\n9. Selecting junction J4 (low pressure)...")
    w._on_canvas_element_selected('J4', 'junction')
    app.processEvents()
    screenshot(w, '09_j4_selected.png')

    # --- 10: Final WSAA Compliance view ---
    print("\n10. WSAA Compliance overview...")
    w.canvas.color_mode_combo.setCurrentText("WSAA Compliance")
    w.canvas.labels_btn.setChecked(False)
    app.processEvents()
    screenshot(w, '10_final_wsaa.png')

    w.close()
    print("\n" + "=" * 60)
    print("All screenshots captured!")
    print("=" * 60)


if __name__ == '__main__':
    main()

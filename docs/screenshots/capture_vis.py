"""
FEA Visualisation Screenshot Capture
======================================
Captures screenshots of all new FEA visualisation features using QWidget.grab().
"""

import os
import sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

SCREENSHOT_DIR = os.path.join(ROOT, 'docs', 'screenshots')
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

from PyQt6.QtWidgets import QApplication
from desktop.main_window import MainWindow


def shot(widget, name):
    path = os.path.join(SCREENSHOT_DIR, name)
    pixmap = widget.grab()
    pixmap.save(path)
    size = os.path.getsize(path)
    print("  Saved: %s (%dx%d, %d bytes)" % (name, pixmap.width(), pixmap.height(), size))


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1400, 900)
    w.show()
    app.processEvents()

    # --- Load transient_network.inp ---
    from epanet_api import HydraulicAPI
    w.api.load_network_from_path(os.path.abspath('models/transient_network.inp'))
    w._current_file = os.path.abspath('models/transient_network.inp')
    w._populate_explorer()
    w._update_status_bar()
    w.canvas.set_api(w.api)
    w.setWindowTitle("Hydraulic Analysis Tool — transient_network.inp")
    app.processEvents()

    # --- 01: Steady state analysis ---
    print("\n1. Running steady state...")
    results = w.api.run_steady_state(save_plot=False)
    w._on_analysis_finished(results)
    app.processEvents()
    shot(w, 'vis_01_startup.png')

    # --- 02: Switch to Viridis + Pressure variable ---
    print("\n2. Viridis colourmap, Pressure variable...")
    w._colourmap_widget.cmap_combo.setCurrentText("Viridis")
    app.processEvents()
    # Set pressure variable data
    pressures = results.get('pressures', {})
    p_data = {nid: pdata.get('avg_m', 0) for nid, pdata in pressures.items()}
    w._colourmap_widget.set_unit("Pressure (m)")
    if p_data:
        vals = list(p_data.values())
        w._colourmap_widget.set_range(min(vals), max(vals))
    w.canvas.set_colourmap(w._colourmap_widget)
    w.canvas.set_variable("Pressure (m)", p_data)
    app.processEvents()
    shot(w, 'vis_02_viridis_pressure.png')

    # --- 03: RdBu + Velocity ---
    print("\n3. RdBu colourmap, Velocity variable...")
    w._colourmap_widget.cmap_combo.setCurrentText("RdBu")
    app.processEvents()
    flows = results.get('flows', {})
    v_data = {pid: fdata.get('max_velocity_ms', 0) for pid, fdata in flows.items()}
    w._colourmap_widget.set_unit("Velocity (m/s)")
    if v_data:
        vals = list(v_data.values())
        w._colourmap_widget.set_range(min(vals), max(vals))
    w.canvas.set_variable("Velocity (m/s)", v_data)
    app.processEvents()
    shot(w, 'vis_03_rdbu_velocity.png')

    # --- 04: Values overlay + pipe DN scaling ---
    print("\n4. Values overlay + Scale pipes by DN...")
    w.values_btn.setChecked(True)
    w.scale_pipes_act.setChecked(True)
    app.processEvents()
    shot(w, 'vis_04_values_and_scaling.png')

    # --- 05: Run transient analysis ---
    print("\n5. Running transient analysis...")
    w.values_btn.setChecked(False)
    app.processEvents()

    trans_results = w.api.run_transient(
        valve_name='V1', closure_time=2.0, start_time=2.0,
        wave_speed=1000, sim_duration=20, save_plot=False)
    w._on_analysis_finished(trans_results)
    app.processEvents()

    # Now populate the animation panel from the TSNet model
    tm = w.api.tm
    if tm is not None:
        timestamps = np.array(tm.simulation_timestamps)
        node_data = {}
        for nid in tm.junction_name_list:
            node = tm.get_node(nid)
            node_data[nid] = {'head': np.array(node.head)}

        pipe_data = {}
        for pid in tm.pipe_name_list:
            pipe = tm.get_link(pid)
            pipe_data[pid] = {
                'start_node_velocity': np.array(pipe.start_node_velocity),
                'start_node_flowrate': np.array(pipe.start_node_flowrate),
                'start_node_head': np.array(pipe.start_node_head),
            }

        w.animation_panel.set_transient_data(timestamps, node_data, pipe_data)
        w.animation_dock.raise_()
        app.processEvents()

    shot(w, 'vis_05_transient_loaded.png')

    # --- 06: Advance to frame 100 ---
    print("\n6. Animation frame 100...")
    if w.animation_panel.n_frames > 100:
        w.animation_panel.slider.setValue(100)
        app.processEvents()
        # Trigger the frame manually
        w._on_animation_frame(100)
        app.processEvents()
    shot(w, 'vis_06_animation_frame100.png')

    # --- 07: Advance to frame 198 (peak surge) ---
    print("\n7. Animation frame 198 (peak surge)...")
    last = w.animation_panel.n_frames - 1
    if last > 0:
        w.animation_panel.slider.setValue(last)
        app.processEvents()
        w._on_animation_frame(last)
        app.processEvents()
    shot(w, 'vis_07_animation_peak_surge.png')

    # --- 08: RdBu diverging map during animation ---
    print("\n8. RdBu pressure wave at frame 50...")
    w._colourmap_widget.cmap_combo.setCurrentText("RdBu")
    app.processEvents()
    if w.animation_panel.n_frames > 50:
        w.animation_panel.slider.setValue(50)
        app.processEvents()
        w._on_animation_frame(50)
        app.processEvents()
    # Set pressure variable from the transient snapshot
    if node_data:
        p_snapshot = {}
        for nid, nd in node_data.items():
            if len(nd['head']) > 50:
                try:
                    elev = w.api.get_node(nid).elevation
                except:
                    elev = 0
                p_snapshot[nid] = float(nd['head'][50]) - elev
        w.canvas.set_variable("Pressure (m)", p_snapshot)
        app.processEvents()
    shot(w, 'vis_08_pressure_wave.png')

    w.close()
    print("\nAll screenshots captured!")


if __name__ == '__main__':
    main()

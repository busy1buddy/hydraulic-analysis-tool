"""Verify 5 specific UX fixes by driving the live app and screenshotting."""
from __future__ import annotations
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QCursor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from desktop.main_window import MainWindow  # noqa: E402

OUT = ROOT / "docs" / "ux_walkthrough"
OUT.mkdir(parents=True, exist_ok=True)


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1600, 1000)
    w.show()
    QCursor.setPos(0, 0)

    seq = []

    def load():
        print("\n[1] Loading demo_network...")
        w.api.load_network_from_path(str(ROOT / "tutorials" / "demo_network" / "network.inp"))
        w._current_file = str(ROOT / "tutorials" / "demo_network" / "network.inp")
        w._populate_explorer()
        w._update_status_bar()
        w.canvas.set_api(w.api)
        w.what_if_panel.set_api(w.api)
        w.dashboard_widget.update_dashboard(w.api)

    def shot_1():
        w.grab().save(str(OUT / "verify_1_loaded.png"))
        print("    -> verify_1_loaded.png")
        # Check button widths
        combo = w.canvas.color_mode_combo
        fit = w.canvas.fit_btn
        labels = w.canvas.labels_btn
        edit = w.canvas.edit_btn
        values = w.values_btn
        probe = w.probe_btn
        print(f"    combo: {combo.width()}px, fit: {fit.width()}px, labels: {labels.width()}px, "
              f"edit: {edit.width()}px, values: {values.width()}px, probe: {probe.width()}px")
        # Overlap check:
        def r(wdg): return wdg.mapTo(w, wdg.rect().topLeft()), wdg.rect().size()
        for n, wdg in [("combo", combo), ("fit", fit), ("labels", labels),
                       ("edit", edit), ("values", values), ("probe", probe)]:
            p, s = r(wdg)
            print(f"    {n}: x={p.x()}..{p.x()+s.width()}")

    def run_f5():
        print("\n[2] Running F5 steady state...")
        w._on_run_steady()

    def wait_for_analysis():
        if w._worker and w._worker.isRunning():
            QTimer.singleShot(100, wait_for_analysis)
            return
        print("    Analysis complete")
        print(f"    results_dock visible: {w.results_dock.isVisible()}")
        print(f"    animation_dock visible: {w.animation_dock.isVisible()}")
        print(f"    dashboard_dock visible: {w.dashboard_dock.isVisible()}")
        print(f"    results geom: {w.results_dock.geometry()}")
        w.grab().save(str(OUT / "verify_2_after_f5.png"))
        print("    -> verify_2_after_f5.png")
        # Check column headers
        hdr = w.node_results_table.horizontalHeader()
        for i in range(5):
            text = w.node_results_table.horizontalHeaderItem(i).text()
            width = hdr.sectionSize(i)
            print(f"    node col {i}: '{text}' = {width}px")
        hdr = w.pipe_results_table.horizontalHeader()
        for i in range(5):
            text = w.pipe_results_table.horizontalHeaderItem(i).text()
            width = hdr.sectionSize(i)
            print(f"    pipe col {i}: '{text}' = {width}px")

    def show_what_if():
        print("\n[3] Opening What-If tab and moving demand to 150%...")
        w.what_if_dock.raise_()
        w.what_if_panel.demand_slider.setValue(150)
        w.what_if_panel._run_analysis()
        print(f"    slider: {w.what_if_panel.demand_slider.value()}%")
        print(f"    status: {w.what_if_panel.status_label.text()}")

    def shot_3():
        w.grab().save(str(OUT / "verify_3_whatif.png"))
        print("    -> verify_3_whatif.png")

    def shot_4():
        # Full colourbar view — crop to canvas+sidebar
        pix = w.grab()
        pix.save(str(OUT / "verify_4_colourbar.png"))
        print("    -> verify_4_colourbar.png")
        print("\n[DONE]")
        app.quit()

    QTimer.singleShot(800, load)
    QTimer.singleShot(1600, shot_1)
    QTimer.singleShot(2000, run_f5)
    QTimer.singleShot(2400, wait_for_analysis)
    QTimer.singleShot(5000, show_what_if)
    QTimer.singleShot(5600, shot_3)
    QTimer.singleShot(6400, shot_4)
    app.exec()


if __name__ == "__main__":
    main()

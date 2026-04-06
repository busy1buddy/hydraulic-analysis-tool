"""UX walkthrough driver — scripts human-style interactions on the live app.

Runs the real PyQt6 MainWindow and triggers a sequence of actions with
visible pauses so a human can watch each step and report UX problems.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from desktop.main_window import MainWindow  # noqa: E402


STEP_DELAY_MS = 2500  # pause between actions so the human can observe
SCREENSHOT_DIR = PROJECT_ROOT / "docs" / "ux_walkthrough"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class Walkthrough:
    def __init__(self, window: MainWindow):
        self.w = window
        self.steps = [
            ("Open demo network via File > Open path", self.load_network),
            ("Click a pipe in the Project Explorer tree", self.click_explorer_pipe),
            ("Press F5 — run steady-state analysis", self.run_steady),
            ("Wait for analysis to finish, then verify Results label", self.verify_results_label),
            ("Switch to the Dashboard dock", self.show_dashboard),
            ("Open What-If panel, slide demand to 120%", self.what_if_demand),
            ("Reset demand to 100%", self.what_if_reset),
            ("Open Analysis > Pressure Zones", self.pressure_zones),
            ("Toggle Labels on the canvas", self.toggle_labels),
            ("Toggle Values overlay", self.toggle_values),
            ("Click a node in the canvas to select", self.click_node),
            ("Walkthrough complete — app remains open for manual testing", self.done),
        ]
        self.i = 0

    def start(self):
        QTimer.singleShot(1500, self.run_next)

    def run_next(self):
        if self.i >= len(self.steps):
            return
        name, fn = self.steps[self.i]
        self.i += 1
        print(f"\n[Step {self.i:02d}] {name}", flush=True)
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            print(f"   ERROR: {type(e).__name__}: {e}", flush=True)
        # Take screenshot AFTER action + short settle delay
        QTimer.singleShot(800, self._screenshot)
        QTimer.singleShot(STEP_DELAY_MS, self.run_next)

    def _screenshot(self):
        path = SCREENSHOT_DIR / f"step_{self.i:02d}.png"
        self.w.grab().save(str(path))
        print(f"   -> screenshot saved: {path.relative_to(PROJECT_ROOT)}", flush=True)

    # ---- step implementations ---------------------------------------
    def load_network(self):
        path = str(PROJECT_ROOT / "tutorials" / "demo_network" / "network.inp")
        self.w.api.load_network_from_path(path)
        self.w._current_file = path
        self.w._populate_explorer()
        self.w._update_status_bar()
        self.w.setWindowTitle(f"Hydraulic Analysis Tool v2.9.0 — {os.path.basename(path)}")
        self.w.canvas.set_api(self.w.api)
        self.w.dashboard_widget.update_dashboard(self.w.api)
        print(f"   Loaded: {self.w.api.wn.num_junctions} junctions, "
              f"{self.w.api.wn.num_pipes} pipes")

    def click_explorer_pipe(self):
        tree = self.w.explorer_tree
        # walk tree to find a pipe child
        root = tree.invisibleRootItem()
        for i in range(root.childCount()):
            project = root.child(i)
            for j in range(project.childCount()):
                cat = project.child(j)
                if cat.text(0).startswith("Pipes") and cat.childCount() > 0:
                    pipe = cat.child(0)
                    tree.setCurrentItem(pipe)
                    self.w._on_tree_item_clicked(pipe, 0)
                    print(f"   Selected pipe: {pipe.text(0)}")
                    return
        print("   (no pipes item found in tree)")

    def run_steady(self):
        self.w._on_run_steady()
        print("   Analysis worker started")

    def verify_results_label(self):
        # worker runs in a thread; wait a short while for completion
        from PyQt6.QtCore import QEventLoop
        loop = QEventLoop()
        QTimer.singleShot(1500, loop.quit)
        loop.exec()
        item = getattr(self.w, "_results_tree_item", None)
        if item:
            print(f"   Explorer results label: {item.text(0)!r}")
        print(f"   Status WSAA: {self.w.wsaa_label.text()!r}")
        print(f"   Tooltip: {self.w.wsaa_label.toolTip()!r}")

    def show_dashboard(self):
        self.w.dashboard_dock.raise_()
        print("   Dashboard dock raised")

    def what_if_demand(self):
        self.w.what_if_dock.raise_()
        self.w.what_if_panel.demand_slider.setValue(120)
        self.w.what_if_panel._run_analysis()
        print(f"   Set demand slider to 120%: {self.w.what_if_panel.status_label.text()}")

    def what_if_reset(self):
        self.w.what_if_panel.demand_slider.setValue(100)
        self.w.what_if_panel._run_analysis()
        print(f"   Demand reset to 100%: {self.w.what_if_panel.status_label.text()}")

    def pressure_zones(self):
        try:
            self.w._on_pressure_zones()
            print("   Pressure Zones dialog launched (close it manually)")
        except Exception as e:  # noqa: BLE001
            print(f"   ERROR opening Pressure Zones: {e}")

    def toggle_labels(self):
        if hasattr(self.w.canvas, "labels_btn"):
            self.w.canvas.labels_btn.toggle()
            print(f"   Labels button now: {self.w.canvas.labels_btn.isChecked()}")

    def toggle_values(self):
        if hasattr(self.w, "values_btn"):
            self.w.values_btn.toggle()
            print(f"   Values button now: {self.w.values_btn.isChecked()}")

    def click_node(self):
        try:
            nid = self.w.api.wn.junction_name_list[0]
            self.w._on_canvas_element_selected('node', nid)
            print(f"   Selected node {nid} — properties should be populated")
        except Exception as e:  # noqa: BLE001
            print(f"   ERROR: {e}")

    def done(self):
        print("\n=== Walkthrough complete ===")
        print("App is still open. Close the window to exit.")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    wk = Walkthrough(window)
    wk.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

"""
Analysis Worker — QThread for Background Analysis
===================================================
Runs steady-state and transient analysis in a background thread
so the UI never freezes during a solve.
"""

import traceback
from PyQt6.QtCore import QThread, pyqtSignal


class AnalysisWorker(QThread):
    """Background worker for hydraulic analysis."""

    started_signal = pyqtSignal()
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, api, analysis_type='steady', params=None, parent=None):
        super().__init__(parent)
        self.api = api
        self.analysis_type = analysis_type
        self.params = params or {}

    def run(self):
        self.started_signal.emit()
        self.progress.emit(10)

        try:
            if self.analysis_type == 'steady':
                self.progress.emit(30)
                results = self.api.run_steady_state(save_plot=False)
                self.progress.emit(90)

            elif self.analysis_type == 'transient':
                self.progress.emit(20)
                valve = self.params.get('valve_name')
                if not valve:
                    # Find first valve
                    valves = self.api.get_link_list('valve')
                    if not valves:
                        self.error.emit("No valves in network for transient analysis.")
                        return
                    valve = valves[0]

                results = self.api.run_transient(
                    valve_name=valve,
                    closure_time=self.params.get('closure_time', 2.0),
                    start_time=self.params.get('start_time', 2.0),
                    wave_speed=self.params.get('wave_speed', 1000),
                    sim_duration=self.params.get('sim_duration', 20),
                    save_plot=False,
                )
                self.progress.emit(90)

            elif self.analysis_type == 'slurry':
                self.progress.emit(30)
                # Run steady state then apply slurry corrections
                results = self.api.run_steady_state(save_plot=False)
                self.progress.emit(60)

                # Add slurry analysis for each pipe
                from slurry_solver import bingham_headloss
                slurry_results = {}
                slurry_params = self.params.get('slurry', {})
                tau_y = slurry_params.get('yield_stress', 10.0)
                mu_p = slurry_params.get('plastic_viscosity', 0.01)
                density = slurry_params.get('density', 1500)

                for pid in self.api.get_link_list('pipe'):
                    pipe = self.api.get_link(pid)
                    flow_data = results.get('flows', {}).get(pid, {})
                    avg_lps = flow_data.get('avg_lps', 0)
                    # convert LPS to m³/s
                    Q_m3s = abs(avg_lps) / 1000

                    if Q_m3s > 0 and pipe.diameter > 0:
                        slurry = bingham_headloss(
                            Q_m3s=Q_m3s,
                            diameter_m=pipe.diameter,
                            length_m=pipe.length,
                            tau_y=tau_y,
                            mu_p=mu_p,
                            density=density,
                            roughness_mm=0.1,
                        )
                        slurry_results[pid] = slurry

                results['slurry'] = slurry_results
                self.progress.emit(90)

            else:
                self.error.emit(f"Unknown analysis type: {self.analysis_type}")
                return

            self.progress.emit(100)
            self.finished.emit(results)

        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")

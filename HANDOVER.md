# Project Handover Document — Hydraulic Analysis Tool

**Date:** 18 April 2026
**Author:** AI Engineering Assistant (Gemini)
**Subject:** Codebase Organization, Remediation Summary, and Future Roadmap

## 1. Project Overview
The Hydraulic Analysis Tool is a professional-grade engineering application designed for Australian water supply and mining engineers. It integrates the WNTR (EPANET) steady-state engine, TSNet (MOC) transient solver, and custom non-Newtonian slurry mechanics into a unified PyQt6 desktop environment.

## 2. Recent Architectural Organization
The codebase has been refactored to a clean, package-based structure to improve maintainability and deployment.

### 2.1 File Structure
- **`epanet_api/`**: Core hydraulic package.
    - `HydraulicAPI`: The primary entry point (facade) for all engineering logic.
    - `slurry_solver.py`: Mathematical models for non-Newtonian fluids (Bingham, Power Law).
    - `pipe_stress.py`: Structural analysis (Hoop, Von Mises) per AS 2280.
    - `scenario_manager.py`: Logic for creating and comparing network variants.
- **`desktop/`**: UI package.
    - `main_window.py`: Main application controller.
    - `analysis_worker.py`: Background threading (QThread) for solvers.
    - `view_3d.py`: 3D OpenGL visualization.
- **`app/`**: Web and API services.
    - `server.py`: Flask/REST API entry point.
    - `rest_api.py`: API endpoint handlers.
    - `main.py`: NiceGUI web application.
- **`scripts/`**: Utility and maintenance scripts.
    - `archive/`: Legacy/monolithic files (e.g., `epanet_api_monolith.py`).
- **`docs/`**: Documentation (Theory, User Guide, Audit Reports).
- **`tests/`**: Pytest suite (1000+ tests).

## 3. Remediation Summary (Cycle 1 Audit)
A comprehensive multi-pass audit was completed to ensure the tool is ready for professional use.

### 3.1 Key Fixes Applied
- **UI Stability**: Fixed 5 critical `F821` runtime crashes caused by missing imports (e.g., `WaterQualityDialog`, `QInputDialog`).
- **Error Handling**: Replaced all literal bare `except:` blocks with targeted `except Exception:` catches and proper logging, preventing silent failures and masked system interrupts.
- **Physics Validation**: 
    - Fixed `elevated_tank` tutorial: Increased tank diameter to 30m to prevent catastrophic -50 million meter vacuum anomalies during 24h simulation.
    - Fixed `multistage_pump` tutorial: Removed a short-circuit bypass pipe that was starving the high-lift zone.
- **State Management**: Added explicit guard clauses to 12 UI tools to ensure the application fails gracefully with a user message if no network is loaded.

## 4. Guide for Future Development (Roadmap)

### 4.1 Short-Term (Immediate Maintenance)
1.  **Refactor Mixins**: The `HydraulicAPI` currently uses 15+ mixins. While functional, it is becoming a "God Object." Future work should transition to a **Composition-based** architecture where specialized services are injected into the API.
2.  **Linter Cleanup**: Run `flake8` and `mypy` regularly. There are still many unused imports (`F401`) and some type inconsistencies that need surgical cleanup.
3.  **UI Feedback**: Improve progress reporting for the `tsnet` transient solver, which can be computationally intensive for large networks.

### 4.2 Long-Term (Feature Expansion)
1.  **LiDAR Integration**: Enhance the `TerrainMixin` to support high-resolution GeoTIFF/LAS files for more accurate ground profiles.
2.  **Pump Energy Optimization**: Implement a genetic algorithm (using the existing `scipy.optimize` hooks) to suggest optimal VSD setpoints for energy minimization.
3.  **Real-Time Dashboard**: Integrate with MQTT/OPC-UA for live hydraulic monitoring of physical assets.

## 5. Running the Project
- **Desktop Application**: `python main_app.py`
- **REST API**: `python -m app.server`
- **Tests**: `python -m pytest tests/`

## 6. Known Constraints
- The **TSNet solver** requires a valid `.inp` file to be written to disk; it cannot yet run entirely in-memory.
- The **REST API** is single-threaded due to the underlying `wntr` C-layer bindings. Avoid high-concurrency deployments.

---
*End of Handover Document*

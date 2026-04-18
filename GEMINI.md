# GEMINI.md — Hydraulic Analysis Tool Instructions

This document provides foundational context and instructions for AI agents (like Gemini) working on this project.

## Project Overview
The **Hydraulic Analysis Tool** is a professional-grade engineering application designed for Australian water supply and mining engineers. It provides a free alternative to commercial hydraulic modeling software by integrating several high-performance solvers:
- **WNTR / EPANET**: For steady-state and extended period hydraulic simulation.
- **TSNet**: For transient (water hammer) analysis using the Method of Characteristics (MOC).
- **Custom Solvers**: For non-Newtonian slurry fluid mechanics (Bingham Plastic, Power Law).
- **Compliance Engine**: Evaluates designs against Australian Standards (WSAA 03, AS 2280, AS/NZS 1477).

## Architecture & Structure
The project follows a modular, package-based architecture:

- **`epanet_api/`**: The core logic layer.
    - `HydraulicAPI`: A facade class using mixins for various features (Core, Slurry, Surge, etc.).
    - `slurry_solver.py` & `pipe_stress.py`: Pure mathematical modules for specialized engineering.
- **`desktop/`**: The PyQt6-based desktop application.
    - Uses `analysis_worker.py` (QThread) to ensure heavy solvers don't freeze the UI.
    - Features 2D (PyQtGraph) and 3D (OpenGL) network visualization.
- **`app/`**: Web and API integration.
    - `server.py`: REST API entry point (Flask).
    - `main.py`: Interactive web dashboard (NiceGUI).
- **`scripts/`**: Utility scripts for maintenance, diagnostics, and CLI-based analysis.
- **`models/` & `tutorials/`**: EPANET `.inp` files used for benchmarking and user training.

## Building and Running
### 1. Installation
Install dependencies via pip:
```bash
pip install -r requirements_desktop.txt
```
*Note: Ensure you have `fpdf2`, `python-docx`, and `pyqt6` installed for full feature support.*

### 2. Launching the App
```bash
python main_app.py
```

### 3. Running the REST API
```bash
python -m app.server
```

### 4. Testing
Run the comprehensive test suite (1000+ tests) using pytest:
```bash
python -m pytest tests/
```

## Development Conventions
- **Domain Accuracy**: Changes to physics modules (`slurry_solver.py`, `pipe_stress.py`) MUST be verified against hand calculations or the `THEORY_MANUAL.md`.
- **UI Responsiveness**: Never run heavy analysis directly in the UI thread. Always use `AnalysisWorker` or similar `QThread` patterns.
- **Error Handling**: Use explicit `except Exception:` blocks with logging. Avoid bare `except:` statements.
- **Imports**: Use package-absolute imports for core logic (e.g., `from epanet_api.slurry_solver import ...`).
- **Standard Units**: Internally, the tool operates in SI units (m, m³/s, Pa, kg/m³). Display conversions (LPS, kPa) happen at the UI boundary.
- **Australian Standards**: Always prioritize WSAA and AS/NZS compliance logic in reporting modules.

## Maintenance Roadmap
- **Mixins to Composition**: Transition the `HydraulicAPI` from a large mixin stack to a composition-based service architecture.
- **Async API**: The REST API is currently synchronous; future iterations should explore async handlers for multi-network batch processing.
- **LiDAR Processing**: Enhance the `TerrainMixin` to support LAS/GeoTIFF ingestion for high-fidelity elevation profiling.

---
*For more detailed developer instructions, see **HANDOVER.md**.*

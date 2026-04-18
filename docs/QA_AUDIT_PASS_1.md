# General QA & Static Analysis (Pass 1) - Audit Report
**Date**: 2026-04-18
**Role**: Codebase QA Engineer

## Executive Summary
This report summarizes the findings from Phase 2, Pass 1 of the Codebase Audit Plan. Using `flake8`, static analysis revealed several critical runtime UI crashing bugs (`F821 undefined names`), several literal bare `except:` blocks, and multiple broad `except Exception:` catch-alls. 

The previous architecture review (2026-04-06) was found to be partially outdated: the missing dependency `fpdf2` *is* present in the current `requirements_desktop.txt`, and the placeholder `assert True` tests have been removed from the test suite.

## 1. Dependency Audit
- **Result**: PASS
- **Details**: Checked `requirements.txt` and `requirements_desktop.txt`. Both contain `fpdf2>=2.7.0` and all other necessary core packages (`tsnet`, `wntr`, `python-docx`, `PyQt6`). The previously reported missing dependency has already been resolved.

## 2. Static Analysis: Critical Runtime Bugs (F821)
These are instances where variables or classes are referenced without being defined or imported, which will cause immediate crashes at runtime.

| File | Line | Finding | Impact |
|------|------|---------|--------|
| `desktop/calibration_dashboard.py` | 92 | `Qt` is undefined | UI crash on opening calibration dashboard |
| `desktop/main_window.py` | 2094 | `WaterQualityDialog` is undefined | UI crash on opening Water Quality dialog |
| `desktop/main_window.py` | 2695 | `QInputDialog` is undefined | UI crash on specific input prompt |
| `desktop/report_dialog.py` | 125 | `layout` is undefined | UI crash on report dialog layout configuration |
| `epanet_api/calibration.py` | 121 | `logger` is undefined | Crash when calibration fails and attempts to log |

**Action Required**: The PyQt Architect must import `Qt` from `PyQt6.QtCore`, `QInputDialog` from `PyQt6.QtWidgets`, `WaterQualityDialog`, define `layout`, and add a `logger` import.

## 3. Static Analysis: Exception Handling (E722 & Broad Excepts)
There are multiple instances of literal bare `except:` blocks (which catch `KeyboardInterrupt` and `SystemExit`) and broad `except Exception as e:` blocks.

**Literal Bare `except:` Blocks (E722)**
| File | Lines |
|------|-------|
| `desktop/main_window.py` | 2949 |
| `desktop/network_canvas.py` | 620, 1259 |
| `desktop/quality_dialog.py` | 158 |
| `epanet_api/__init__.py` | 91, 100 |
| `epanet_api/assets.py` | 783 |
| `epanet_api/terrain.py` | 63, 195 |

**Broad `except Exception as e:` Blocks**
- Found 23 additional instances across `desktop/` (mostly in `main_window.py` and `scenario_panel.py`). These often swallow errors silently, making debugging difficult.

**Action Required**: The PyQt Architect needs to systematically replace these with specific catches (e.g., `except FileNotFoundError`, `except KeyError`, `except APIError`) or at least ensure proper exception tracebacks are logged or displayed in a UI message box.

## 4. Unused Imports (F401)
- **Result**: HIGH VOLUME
- **Details**: Dozens of unused imports across the `desktop/` and `epanet_api/` modules. For example, `traceback`, `os`, and many `PyQt6` widgets are imported but not used. 
- **Action Required**: Low priority. Can be cleaned up during general refactoring.

## 5. Test Suite Sanity
- **Result**: PASS
- **Details**: The previously reported `assert True` placeholders in `test_eps.py:202` and `test_ui_smoke.py:114` are no longer present.

## Next Steps
The General QA Pass is complete.
1. The **PyQt Architect** should address the critical `F821` runtime crashes and begin refactoring the `E722` bare excepts (Phase 4 of the audit plan).
2. The **Hydraulic SME** should begin Phase 3 to audit the physics formulas and fix the `demo_network.inp` unit scaling bug.
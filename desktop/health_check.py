"""
System Health Check — Dependency Verification
============================================
Checks if all required libraries and drivers are functional.

Solver checks (WNTR/TSNet) are reached through the HydraulicAPI to keep
the desktop layer free of direct wntr/tsnet imports (Layer-4 purity rule).
"""

import sys


def run_health_check(api=None):
    """Run a quick dependency check.

    Parameters
    ----------
    api : HydraulicAPI, optional
        When provided, ``api.health_check()`` is used to validate the WNTR /
        EPANET solver. When omitted, a fresh HydraulicAPI is constructed for
        the check (which still runs through the API layer).

    Returns
    -------
    (bool, str) : (overall ok, multi-line report)
    """
    report = []
    status = True

    # 1. Python Version
    report.append(f"Python: {sys.version}")

    # 2. WNTR / EPANET — via API (no direct wntr import in desktop)
    try:
        if api is None:
            from epanet_api import HydraulicAPI
            api = HydraulicAPI()
        hc = api.health_check()
        report.append(hc.get('report', ''))
        if not hc.get('ok', False):
            status = False
    except Exception as e:
        report.append(f"WNTR/EPANET Error: {e}")
        status = False

    # 3. PyQt6
    try:
        from PyQt6 import QtCore
        report.append(f"PyQt6: {QtCore.PYQT_VERSION_STR} - OK")
    except Exception as e:
        report.append(f"PyQt6 Error: {e}")
        status = False

    # 4. Scipy / Pandas
    try:
        import scipy  # noqa: F401
        import pandas  # noqa: F401
        report.append("SciPy/Pandas: OK")
    except Exception as e:
        report.append(f"Data Libraries Error: {e}")
        status = False

    return status, "\n".join(report)


if __name__ == "__main__":
    ok, r = run_health_check()
    print(r)
    sys.exit(0 if ok else 1)

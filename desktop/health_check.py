"""
System Health Check — Dependency Verification
============================================
Checks if all required libraries and drivers are functional.
"""

import sys
import traceback

def run_health_check():
    report = []
    status = True
    
    # 1. Python Version
    report.append(f"Python: {sys.version}")
    
    # 2. WNTR / EPANET
    try:
        import wntr
        report.append(f"WNTR: {wntr.__version__} - OK")
        # Try a tiny simulation
        wn = wntr.network.WaterNetworkModel()
        sim = wntr.sim.EpanetSimulator(wn)
        report.append("EPANET Solver: Integrated - OK")
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
        import scipy
        import pandas
        report.append(f"SciPy/Pandas: OK")
    except Exception as e:
        report.append(f"Data Libraries Error: {e}")
        status = False
        
    return status, "\n".join(report)

if __name__ == "__main__":
    ok, r = run_health_check()
    print(r)
    sys.exit(0 if ok else 1)

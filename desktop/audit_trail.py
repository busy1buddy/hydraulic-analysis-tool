"""
Audit Trail — Analysis Run Logging
====================================
Every analysis run is auto-logged with input snapshot, parameters,
full results, solver version, and WSAA compliance summary.
"""

import os
import json
import shutil
from datetime import datetime


class AuditTrail:
    """Manages the analysis audit trail."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'docs', 'audit'
        )

    def log_run(self, inp_file, parameters, results, analysis_type='steady'):
        """Log an analysis run to the audit trail.

        Parameters
        ----------
        inp_file : str
            Path to the .inp file used.
        parameters : dict
            Analysis parameters (wave speed, closure time, etc.).
        results : dict
            Full results dictionary from HydraulicAPI.
        analysis_type : str
            'steady', 'transient', or 'slurry'.

        Returns
        -------
        str : Path to the audit directory for this run.
        """
        now = datetime.now()
        date_dir = os.path.join(self.base_dir, now.strftime('%Y-%m-%d'))
        run_dir = os.path.join(date_dir, now.strftime('%H%M%S'))
        os.makedirs(run_dir, exist_ok=True)

        # Snapshot the .inp file
        if inp_file and os.path.exists(inp_file):
            shutil.copy2(inp_file, os.path.join(run_dir, 'network.inp'))

        # Save parameters
        meta = {
            'timestamp': now.isoformat(),
            'analysis_type': analysis_type,
            'parameters': parameters,
            'inp_file': inp_file or '',
            'solver_versions': _get_solver_versions(),
        }
        with open(os.path.join(run_dir, 'metadata.json'), 'w') as f:
            json.dump(meta, f, indent=2, default=str)

        # Save results (convert numpy types)
        results_clean = _make_json_safe(results)
        with open(os.path.join(run_dir, 'results.json'), 'w') as f:
            json.dump(results_clean, f, indent=2, default=str)

        # Save compliance summary
        compliance = results.get('compliance', [])
        summary = {
            'total_items': len(compliance),
            'critical': sum(1 for c in compliance if c.get('type') == 'CRITICAL'),
            'warnings': sum(1 for c in compliance if c.get('type') == 'WARNING'),
            'ok': sum(1 for c in compliance if c.get('type') == 'OK'),
            'items': compliance,
        }
        with open(os.path.join(run_dir, 'compliance_summary.json'), 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        return run_dir

    def list_runs(self):
        """Return a list of all audit runs, newest first.

        Returns
        -------
        list of dict : Each with 'path', 'timestamp', 'analysis_type'.
        """
        runs = []
        if not os.path.exists(self.base_dir):
            return runs

        for date_dir in sorted(os.listdir(self.base_dir), reverse=True):
            date_path = os.path.join(self.base_dir, date_dir)
            if not os.path.isdir(date_path):
                continue
            for time_dir in sorted(os.listdir(date_path), reverse=True):
                run_path = os.path.join(date_path, time_dir)
                meta_path = os.path.join(run_path, 'metadata.json')
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path) as f:
                            meta = json.load(f)
                        runs.append({
                            'path': run_path,
                            'timestamp': meta.get('timestamp', ''),
                            'analysis_type': meta.get('analysis_type', ''),
                        })
                    except Exception:
                        pass
        return runs

    def load_run(self, run_path):
        """Load results from a previous audit run.

        Returns
        -------
        dict : The results dict, or None if not found.
        """
        results_path = os.path.join(run_path, 'results.json')
        if os.path.exists(results_path):
            with open(results_path) as f:
                return json.load(f)
        return None


def _get_solver_versions():
    """Get installed solver versions."""
    versions = {}
    try:
        import wntr
        versions['wntr'] = getattr(wntr, '__version__', 'unknown')
    except ImportError:
        pass
    try:
        import tsnet
        versions['tsnet'] = getattr(tsnet, '__version__', 'unknown')
    except ImportError:
        pass
    return versions


def _make_json_safe(obj):
    """Convert numpy types to Python native for JSON serialization."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_json_safe(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

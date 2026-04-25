"""
Layer-4 purity tests — desktop/ must reach the solvers only through HydraulicAPI.

CLAUDE.md §2 forbids the desktop layer from:
- importing wntr or tsnet directly
- importing the domain modules (epanet_api.slurry_solver, epanet_api.pipe_stress)
- mutating ``api.wn.options.*`` (read access is fine)

This test scans every Python file under ``desktop/`` with the standard library
``ast`` module and fails if any of those rules is violated. It is intentionally
fast (no solver is run) so it can run on every commit / pre-merge.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import List, Tuple

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
DESKTOP_DIR = REPO_ROOT / 'desktop'

FORBIDDEN_TOP_LEVEL_IMPORTS = {
    'wntr',
    'tsnet',
}
FORBIDDEN_FROM_PREFIXES = (
    'wntr',
    'tsnet',
    'epanet_api.slurry_solver',
    'epanet_api.pipe_stress',
)
FORBIDDEN_OPTIONS_ATTRS = (
    'time',
    'quality',
    'reaction',
    'hydraulic',
    'energy',
    'report',
)


def _python_files(root: Path) -> List[Path]:
    return sorted(p for p in root.rglob('*.py') if '__pycache__' not in p.parts)


def _violations_for_file(path: Path) -> List[Tuple[int, str]]:
    """Return list of (lineno, message) for purity violations in this file."""
    source = path.read_text(encoding='utf-8')
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [(exc.lineno or 0, f'syntax error: {exc.msg}')]

    violations: List[Tuple[int, str]] = []

    for node in ast.walk(tree):
        # `import wntr` / `import tsnet`
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split('.', 1)[0]
                if top in FORBIDDEN_TOP_LEVEL_IMPORTS:
                    violations.append((node.lineno,
                        f"forbidden import: 'import {alias.name}' "
                        f"— use the HydraulicAPI wrapper instead"))

        # `from wntr import ...`, `from epanet_api.slurry_solver import ...`
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for prefix in FORBIDDEN_FROM_PREFIXES:
                if module == prefix or module.startswith(prefix + '.'):
                    violations.append((node.lineno,
                        f"forbidden import: 'from {module} import ...' "
                        f"— use the HydraulicAPI wrapper instead"))
                    break

        # `api.wn.options.<group>.<attr> = ...` (mutation)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Attribute):
                    continue
                # Walk up the attribute chain: looking for ...wn.options.<group>.<attr>
                chain = []
                cur = target
                while isinstance(cur, ast.Attribute):
                    chain.append(cur.attr)
                    cur = cur.value
                # chain is in reverse: e.g. ['duration', 'time', 'options', 'wn']
                if (len(chain) >= 3
                        and chain[-2] == 'options'
                        and chain[-3] in FORBIDDEN_OPTIONS_ATTRS):
                    # Confirm the chain root is something like ``wn`` (i.e. attribute access)
                    # We accept api.wn.options.* and self.api.wn.options.*
                    violations.append((node.lineno,
                        f"forbidden mutation: 'api.wn.options.{chain[-3]}.* = ...' "
                        f"— use api.set_simulation_options(...) / "
                        f"api.set_water_quality_mode(...) instead"))

    return violations


def test_no_forbidden_imports_in_desktop():
    """desktop/*.py must not import wntr/tsnet or the domain solver modules."""
    bad: List[str] = []
    for path in _python_files(DESKTOP_DIR):
        for lineno, message in _violations_for_file(path):
            if 'forbidden import' in message:
                bad.append(f"{path.relative_to(REPO_ROOT)}:{lineno} — {message}")

    assert not bad, (
        "Layer-4 purity violations (forbidden imports in desktop/):\n  "
        + "\n  ".join(bad)
        + "\nUse HydraulicAPI methods (api.compute_slurry_headloss, "
          "api.compute_pipe_stress, api.solver_versions, api.health_check) "
          "instead of importing solver/domain modules directly."
    )


def test_no_options_mutation_in_desktop():
    """desktop/*.py must not mutate api.wn.options.* — use api setters."""
    bad: List[str] = []
    for path in _python_files(DESKTOP_DIR):
        for lineno, message in _violations_for_file(path):
            if 'forbidden mutation' in message:
                bad.append(f"{path.relative_to(REPO_ROOT)}:{lineno} — {message}")

    assert not bad, (
        "Layer-4 purity violations (api.wn.options mutation in desktop/):\n  "
        + "\n  ".join(bad)
        + "\nUse api.set_simulation_options(...) or api.set_water_quality_mode(...) "
          "instead of mutating api.wn.options.* directly."
    )


def test_desktop_dir_exists_and_has_files():
    """Sanity check — the scanner must actually have something to scan."""
    files = _python_files(DESKTOP_DIR)
    assert len(files) >= 30, (
        f"Expected ≥30 Python files in desktop/; found {len(files)}. "
        f"Did the scan path break?"
    )


@pytest.mark.parametrize("path", [
    "desktop/analysis_worker.py",
    "desktop/pipe_stress_panel.py",
    "desktop/audit_trail.py",
    "desktop/health_check.py",
    "desktop/main_window.py",
])
def test_known_violation_sites_are_clean(path):
    """The five recommendation-#1/#3 sites must remain compliant going forward."""
    full_path = REPO_ROOT / path
    assert full_path.exists(), f"missing file: {path}"
    violations = _violations_for_file(full_path)
    assert not violations, (
        f"{path} has Layer-4 purity violations:\n  "
        + "\n  ".join(f"line {ln}: {msg}" for ln, msg in violations)
    )

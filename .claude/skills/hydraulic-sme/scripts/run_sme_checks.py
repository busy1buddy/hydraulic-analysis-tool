"""
SME quick-check ledger — chains the four ground-truth tiers and prints PASS/FAIL.

Run from the project root:
    python .claude/skills/hydraulic-sme/scripts/run_sme_checks.py

Exits 0 if every benchmark passes, non-zero on first failure.

Tiers run (in order, each gated):
  1. Hand calculations    — tests/test_hand_calculations.py
  2. Hydraulic benchmarks — tests/test_hydraulic_benchmarks.py
  3. KB fidelity          — tests/test_kb_fidelity.py
  4. EPANET verification  — tests/test_epanet_verification.py
  5. Pipe DB validation   — scripts/validate_pipe_db.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def run(label: str, cmd: list[str]) -> bool:
    print(f"\n=== {label} ===")
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)
    ok = result.returncode == 0
    print(f"--- {label}: {'PASS' if ok else 'FAIL'} ---")
    return ok


def main() -> int:
    tiers = [
        ("Hand calculations",    [sys.executable, "-m", "pytest", "tests/test_hand_calculations.py", "-q"]),
        ("Hydraulic benchmarks", [sys.executable, "-m", "pytest", "tests/test_hydraulic_benchmarks.py", "-q"]),
        ("KB fidelity",          [sys.executable, "-m", "pytest", "tests/test_kb_fidelity.py", "-q"]),
        ("EPANET verification",  [sys.executable, "-m", "pytest", "tests/test_epanet_verification.py", "-q"]),
        ("Pipe DB",              [sys.executable, "scripts/validate_pipe_db.py"]),
    ]
    failed: list[str] = []
    for label, cmd in tiers:
        if not run(label, cmd):
            failed.append(label)

    print("\n=== SME LEDGER SUMMARY ===")
    for label, _ in tiers:
        status = "FAIL" if label in failed else "PASS"
        print(f"  [{status}] {label}")

    if failed:
        print(f"\n{len(failed)} tier(s) failed. Investigate before changing any formula.")
        return 1
    print("\nAll tiers PASS. Safe to proceed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Quality gate aggregator — Phase-5 deliverable from the multi-agent review plan.

Chains the project's authoritative gates into one command. Exits non-zero on
the first failure so CI can fail fast.

Tiers (in order, each must PASS):
  1. Pipe-DB validator      — scripts/validate_pipe_db.py (58 checks)
  2. SME ground-truth ledger — chains hand calcs + benchmarks + KB fidelity +
                                EPANET verification + pipe DB
  3. Layer-purity AST scan   — tests/test_layer_purity.py
  4. UI-freeze regression    — tests/test_ui_freeze.py
  5. Forecasting unit tests  — tests/test_forecasting.py
  6. Terrain unit tests      — tests/test_terrain.py
  7. Canvas state regression — tests/test_canvas_state.py
  8. Regression baselines    — tests/test_regression.py
  9. Performance gates       — tests/test_performance.py (slow marker)
 10. Centurion stress harness — scripts/tester_agent.py (100 cases)

Run from the project root:

    python scripts/quality_gate.py            # all tiers
    python scripts/quality_gate.py --no-slow  # skip Centurion + perf
    python scripts/quality_gate.py --fast     # smoke set only (1, 2, 3, 4)

Exit code 0 = pass, non-zero = first failed tier (1-based).

Replaces the 24-line stub at ``scripts/run_agent_loop.py``.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Tier:
    def __init__(self, name: str, cmd: list[str], slow: bool = False):
        self.name = name
        self.cmd = cmd
        self.slow = slow

    def run(self) -> tuple[bool, float]:
        t0 = time.perf_counter()
        result = subprocess.run(self.cmd, cwd=ROOT)
        return result.returncode == 0, time.perf_counter() - t0


def build_tiers(skip_slow: bool, fast_only: bool) -> list[Tier]:
    py = sys.executable
    tiers = [
        Tier("Pipe DB",            [py, "scripts/validate_pipe_db.py"]),
        Tier("SME ledger",         [py, ".claude/skills/hydraulic-sme/scripts/run_sme_checks.py"]),
        Tier("Layer purity",       [py, "-m", "pytest", "tests/test_layer_purity.py", "-q"]),
        Tier("UI freeze",          [py, "-m", "pytest", "tests/test_ui_freeze.py", "-q"]),
    ]
    if fast_only:
        return tiers

    tiers.extend([
        Tier("Forecasting",        [py, "-m", "pytest", "tests/test_forecasting.py", "-q"]),
        Tier("Terrain",            [py, "-m", "pytest", "tests/test_terrain.py", "-q"]),
        Tier("Canvas state",       [py, "-m", "pytest", "tests/test_canvas_state.py", "-q"]),
        Tier("Regression",         [py, "-m", "pytest", "tests/test_regression.py", "-q"]),
    ])

    if not skip_slow:
        tiers.extend([
            Tier("Performance",    [py, "-m", "pytest", "tests/test_performance.py", "-m", "slow", "-q"], slow=True),
            Tier("Centurion",      [py, "-m", "pytest", "scripts/tester_agent.py", "-q"], slow=True),
        ])

    return tiers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--no-slow', action='store_true',
                        help='Skip slow gates (Centurion + perf)')
    parser.add_argument('--fast', action='store_true',
                        help='Run only the smoke set (pipe DB + SME + layer purity + UI freeze)')
    args = parser.parse_args()

    tiers = build_tiers(skip_slow=args.no_slow, fast_only=args.fast)
    print(f"Quality gate — running {len(tiers)} tier(s)\n")

    width = max(len(t.name) for t in tiers)
    results: list[tuple[Tier, bool, float]] = []
    first_failure: int | None = None

    for idx, tier in enumerate(tiers, start=1):
        print(f"=== [{idx}/{len(tiers)}] {tier.name} ===")
        print(f"$ {' '.join(tier.cmd)}")
        ok, elapsed = tier.run()
        results.append((tier, ok, elapsed))
        status = "PASS" if ok else "FAIL"
        print(f"--- {tier.name}: {status} ({elapsed:.1f}s) ---\n")
        if not ok and first_failure is None:
            first_failure = idx
            # Fail fast — don't burn CI minutes after the first regression
            break

    # Summary
    print("=" * 60)
    print("QUALITY GATE SUMMARY")
    print("=" * 60)
    for tier, ok, elapsed in results:
        marker = "OK  " if ok else "FAIL"
        print(f"  [{marker}] {tier.name.ljust(width)}  {elapsed:6.1f}s")

    if first_failure is not None:
        print(f"\nFAILED at tier {first_failure} ({results[first_failure - 1][0].name}).")
        return first_failure
    print("\nAll tiers PASS — safe to proceed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

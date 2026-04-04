"""
Submit for Automated Review
=============================
Usage:
  python scripts/submit_for_review.py --context "task name" --question "what to assess"
  python scripts/submit_for_review.py --context "..." --question "..." --thorough
  python scripts/submit_for_review.py --context "..." --question "..." --output "override"

Default mode is --fast (uses Haiku for quick JSON reviews).
Use --thorough for full Sonnet/Opus review on critical changes.

Auto-collects context: recent progress, test count, modified files.
"""

import os
import sys
import json
import argparse
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEXT_INSTRUCTIONS_FILE = os.path.join(ROOT, 'docs', 'review_loop', 'next_instructions.md')


def _auto_collect_context():
    """Gather recent project state for the reviewer."""
    parts = []

    # Last 20 lines of progress.md
    progress_file = os.path.join(ROOT, 'docs', 'progress.md')
    if os.path.exists(progress_file):
        with open(progress_file) as f:
            lines = f.readlines()
        tail = lines[-20:] if len(lines) > 20 else lines
        parts.append("RECENT PROGRESS:\n" + "".join(tail))

    # Test count
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/', '-q', '--co', '-q'],
            capture_output=True, text=True, timeout=30, cwd=ROOT,
            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
        )
        count_line = [l for l in result.stdout.strip().split('\n') if 'test' in l.lower()]
        if count_line:
            parts.append(f"TEST COUNT: {count_line[-1].strip()}")
    except Exception:
        pass

    # Recently modified files
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', 'HEAD~1'],
            capture_output=True, text=True, timeout=10, cwd=ROOT,
        )
        if result.stdout.strip():
            parts.append("RECENTLY MODIFIED FILES:\n" + result.stdout.strip())
    except Exception:
        pass

    return "\n\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description='Submit work for automated review')
    parser.add_argument('--output', default=None, help='What was built (auto-collected if omitted)')
    parser.add_argument('--context', required=True, help='Task name')
    parser.add_argument('--question', required=True, help='What to assess')
    parser.add_argument('--fast', action='store_true', default=True,
                        help='Use Haiku for fast review (default)')
    parser.add_argument('--thorough', action='store_true', default=False,
                        help='Use full model for thorough review')
    args = parser.parse_args()

    bridge_url = 'http://localhost:7771'
    mode = 'thorough' if args.thorough else 'fast'

    # Auto-collect context
    auto_context = _auto_collect_context()
    if args.output:
        output = args.output + "\n\n" + auto_context
    else:
        output = auto_context

    # Check health
    try:
        import urllib.request
        req = urllib.request.Request(f'{bridge_url}/health', method='GET')
        with urllib.request.urlopen(req, timeout=5) as resp:
            health = json.loads(resp.read())
            if health.get('status') != 'ok':
                print("Bridge health check failed — skipping review")
                sys.exit(0)
    except Exception:
        print("Bridge not running on localhost:7771 — skipping review")
        sys.exit(0)

    print(f"Submitting review ({mode} mode)...")

    # Submit review
    payload = json.dumps({
        'output': output,
        'context': args.context,
        'question': args.question,
        'mode': mode,
    }).encode('utf-8')

    timeout = 200 if mode == 'fast' else 360

    try:
        req = urllib.request.Request(
            f'{bridge_url}/review',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
    except Exception as e:
        print(f"Review submission failed: {e}")
        sys.exit(0)

    # Format output
    sep = '=' * 50
    print(sep)
    print(f"AUTOMATED REVIEW — {args.context}")
    quality = result.get('quality', 'UNKNOWN')
    print(f"Quality: {quality}")
    print(sep)
    print(result.get('assessment', ''))
    print()

    issues = result.get('issues', [])
    if issues:
        print("Issues:")
        for issue in issues:
            print(f"  - {issue}")
        print()

    next_inst = result.get('next_instructions', '')
    if next_inst:
        print("Next instructions:")
        print(f"  {next_inst}")
    print(sep)

    # Write next_instructions
    os.makedirs(os.path.dirname(NEXT_INSTRUCTIONS_FILE), exist_ok=True)
    with open(NEXT_INSTRUCTIONS_FILE, 'w') as f:
        f.write(f"# Next Instructions — {args.context}\n\n")
        f.write(f"Quality: {quality}\n\n")
        if next_inst:
            f.write(f"{next_inst}\n")
        else:
            f.write("No further instructions — work can continue.\n")

    # Exit code
    can_continue = result.get('can_continue', True)
    sys.exit(0 if can_continue else 1)


if __name__ == '__main__':
    main()

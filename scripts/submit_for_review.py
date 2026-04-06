"""
Submit work for automated review.

Usage:
  python scripts/submit_for_review.py --context "task name" --question "what to check"
  python scripts/submit_for_review.py --context "task" --question "check" --thorough
  python scripts/submit_for_review.py --context "task" --question "check" --output-file result.json

Exit codes:
  0 = GOOD or ACCEPTABLE (continue working)
  1 = NEEDS_WORK (fix issues, then continue)
  2 = BLOCKER (stop, fix immediately)
  3 = bridge not running or error (continue, don't block)
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error


def _collect_auto_context():
    """Gather recent project state for richer reviews."""
    context_parts = []

    # Recent git changes
    try:
        diff = subprocess.run(
            ['git', 'diff', '--name-only', 'HEAD~1'],
            capture_output=True, text=True, timeout=10
        )
        if diff.returncode == 0 and diff.stdout.strip():
            context_parts.append(f"Changed files:\n{diff.stdout.strip()}")
    except Exception:
        pass

    # Current test count
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/', '-k', 'not transient',
             '-q', '--tb=no', '--co', '-q'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            # Last line usually shows "X tests collected"
            for line in reversed(lines):
                if 'test' in line.lower():
                    context_parts.append(f"Tests: {line.strip()}")
                    break
    except Exception:
        pass

    # Last 10 lines of progress
    progress_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'docs', 'progress.md'
    )
    if os.path.exists(progress_file):
        try:
            with open(progress_file, encoding='utf-8') as f:
                lines = f.readlines()
            recent = ''.join(lines[-10:]).strip()
            if recent:
                context_parts.append(f"Recent progress:\n{recent}")
        except Exception:
            pass

    return '\n\n'.join(context_parts)


def _check_bridge():
    """Check if review bridge is running."""
    try:
        req = urllib.request.Request('http://localhost:7771/health')
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        return data.get('status') == 'ok'
    except Exception:
        return False


def _submit(context, output, question, thorough=False):
    """Submit review to bridge and return parsed response."""
    payload = json.dumps({
        'context': context,
        'output': output,
        'question': question,
        'thorough': thorough,
    }).encode('utf-8')

    req = urllib.request.Request(
        'http://localhost:7771/review',
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    resp = urllib.request.urlopen(req, timeout=300)
    return json.loads(resp.read())


def main():
    parser = argparse.ArgumentParser(description='Submit work for automated review')
    parser.add_argument('--context', required=True, help='What task was completed')
    parser.add_argument('--question', required=True, help='Specific question to assess')
    parser.add_argument('--output', default='', help='Detailed output text')
    parser.add_argument('--thorough', action='store_true',
                        help='Use Opus instead of Sonnet (slower, deeper)')
    parser.add_argument('--output-file', default=None,
                        help='Save full JSON response to this file')
    args = parser.parse_args()

    # Check bridge
    if not _check_bridge():
        print("WARNING: Review bridge not running on localhost:7771")
        print("Start it: scripts\\start_review_loop.bat")
        print("Continuing without review.")
        sys.exit(3)

    # Collect auto-context if no explicit output provided
    output = args.output
    if not output:
        output = _collect_auto_context()

    model_label = "Opus (thorough)" if args.thorough else "Sonnet (fast)"
    print(f"Submitting review [{model_label}]...")

    try:
        response = _submit(args.context, output, args.question, args.thorough)
    except Exception as e:
        print(f"Review failed: {e}")
        sys.exit(3)

    # Display formatted response
    quality = response.get('quality', 'UNKNOWN')
    assessment = response.get('assessment', '')
    issues = response.get('issues', [])
    instructions = response.get('next_instructions', '')
    needs_live = response.get('needs_live_testing', False)
    elapsed = response.get('elapsed_s', 0)
    model = response.get('model_used', 'unknown')

    # Colour-code quality for terminal
    quality_markers = {
        'GOOD': '✓',
        'ACCEPTABLE': '~',
        'NEEDS_WORK': '!',
        'BLOCKER': 'X',
    }
    marker = quality_markers.get(quality, '?')

    print()
    print("=" * 56)
    print(f"  REVIEW [{marker}] {quality}  ({model}, {elapsed}s)")
    print("=" * 56)
    print()
    print(assessment)

    if needs_live:
        print()
        print("  >> NEEDS LIVE TESTING — human must run the app <<")

    if issues:
        print()
        print("Issues:")
        for issue in issues:
            print(f"  - {issue}")

    if instructions:
        print()
        print("Next instructions:")
        print(f"  {instructions}")

    print()
    print("=" * 56)

    # Save to file if requested
    if args.output_file:
        next_instructions_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'docs', 'review_loop'
        )
        os.makedirs(next_instructions_dir, exist_ok=True)

        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(response, f, indent=2, ensure_ascii=False)
        print(f"Saved to {args.output_file}")

    # Also always write next_instructions for Claude Code to read
    ni_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'docs', 'review_loop', 'next_instructions.md'
    )
    with open(ni_path, 'w', encoding='utf-8') as f:
        f.write(f"# Review Result — {args.context}\n")
        f.write(f"Quality: {quality}\n")
        f.write(f"{instructions}\n")

    # Exit code based on quality
    if quality == 'BLOCKER':
        sys.exit(2)
    elif quality == 'NEEDS_WORK':
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()

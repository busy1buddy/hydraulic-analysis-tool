"""
Submit for Automated Review
=============================
Usage:
  python scripts/submit_for_review.py --output "..." --context "..." --question "..."

Submits to the review bridge at localhost:7771.
If bridge is not running, prints a warning and exits 0 (never blocks work).
"""

import os
import sys
import json
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEXT_INSTRUCTIONS_FILE = os.path.join(ROOT, 'docs', 'review_loop', 'next_instructions.md')


def main():
    parser = argparse.ArgumentParser(description='Submit work for automated review')
    parser.add_argument('--output', required=True, help='What was built')
    parser.add_argument('--context', required=True, help='Task name')
    parser.add_argument('--question', required=True, help='What to assess')
    args = parser.parse_args()

    bridge_url = 'http://localhost:7771'

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

    # Submit review
    payload = json.dumps({
        'output': args.output,
        'context': args.context,
        'question': args.question,
    }).encode('utf-8')

    try:
        req = urllib.request.Request(
            f'{bridge_url}/review',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
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

"""
Automated Review Bridge
========================
Flask server on localhost:7771 that spawns Claude Code CLI as a
reviewer subprocess. No external API key needed.

Start: python scripts/review_bridge.py
Health: curl localhost:7771/health
Submit: POST localhost:7771/review with JSON body

Configure: set REVIEW_TIMEOUT=240 before starting to increase timeout.
"""

import os
import sys
import json
import subprocess
import time
import tempfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(ROOT, 'docs', 'review_loop', 'history.jsonl')
os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)

try:
    from flask import Flask, request, jsonify
except ImportError:
    print("Flask not installed. Run: pip install flask")
    sys.exit(1)

app = Flask(__name__)

# Configurable via environment variable
TIMEOUT_FAST = int(os.environ.get('REVIEW_TIMEOUT', '180'))
TIMEOUT_THOROUGH = int(os.environ.get('REVIEW_TIMEOUT_THOROUGH', '300'))

REVIEWER_PROMPT_TEMPLATE = """You are a senior hydraulic engineer and software architect \
reviewing output from an autonomous Claude Code session building a professional \
hydraulic analysis desktop tool.

The tool uses PyQt6, WNTR, TSNet, and custom slurry solvers targeting \
Australian water and mining engineers.
Standards: WSAA, AS/NZS 1477, AS 2280, AS/NZS 4130, AS 4058.
Current test suite: 467+ passing (growing), 12 xfailed.

TASK COMPLETED: {context}

OUTPUT TO REVIEW:
{output}

SPECIFIC QUESTION: {question}

Review for:
- Hydraulic calculation correctness
- Australian standards compliance
- UI decisions appropriate for professional engineers
- Regressions vs previous state
- Test coverage adequacy
- Anything a professional engineer would notice is missing

Respond in valid JSON only. No text outside the JSON:
{{
  "assessment": "one paragraph honest assessment",
  "quality": "GOOD | ACCEPTABLE | NEEDS_WORK | BLOCKER",
  "issues": ["specific issue 1", "specific issue 2"],
  "next_instructions": "exact text for Claude Code to act on, or empty string if nothing needed",
  "can_continue": true
}}"""


def _check_claude_cli():
    """Check if claude CLI is available and measure startup time."""
    try:
        t0 = time.perf_counter()
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True, text=True, timeout=15,
        )
        elapsed = time.perf_counter() - t0
        version = result.stdout.strip().split('\n')[0] if result.stdout else 'unknown'
        if elapsed > 5:
            print(f"WARNING: claude CLI startup took {elapsed:.1f}s — reviews will be slow")
        else:
            print(f"claude CLI ready: {version} (startup: {elapsed:.1f}s)")
        return True, elapsed
    except FileNotFoundError:
        print("WARNING: claude CLI not found on PATH")
        return False, 0
    except subprocess.TimeoutExpired:
        print("WARNING: claude --version timed out after 15s")
        return False, 0


def _run_claude_reviewer(prompt, model=None, timeout=TIMEOUT_FAST):
    """Run claude CLI via stdin (temp file) to avoid arg length limits. Retries once."""
    # Write prompt to temp file and pipe via stdin
    prompt_file = None
    try:
        prompt_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.txt', delete=False, encoding='utf-8',
        )
        prompt_file.write(prompt)
        prompt_file.close()

        cmd = ["claude", "--print", "--dangerously-skip-permissions"]
        if model:
            cmd.extend(["--model", model])

        for attempt in range(2):
            t0 = time.perf_counter()
            try:
                with open(prompt_file.name, 'r', encoding='utf-8') as stdin_f:
                    result = subprocess.run(
                        cmd, stdin=stdin_f,
                        capture_output=True, text=True,
                        timeout=timeout, cwd=ROOT,
                    )
                elapsed = time.perf_counter() - t0
                return result.stdout.strip(), result.returncode, elapsed, False
            except FileNotFoundError:
                return ('{"assessment": "Claude CLI not found on PATH", '
                        '"quality": "NEEDS_WORK", "issues": ["claude CLI not installed"], '
                        '"next_instructions": "", "can_continue": true}'), 1, 0, False
            except subprocess.TimeoutExpired:
                elapsed = time.perf_counter() - t0
                if attempt == 0:
                    continue
                return ('{"assessment": "Review timed out after retry", '
                        '"quality": "ACCEPTABLE", "issues": ["timeout after 2 attempts"], '
                        '"next_instructions": "", "can_continue": true}'), 1, elapsed, True
    finally:
        if prompt_file and os.path.exists(prompt_file.name):
            try:
                os.unlink(prompt_file.name)
            except OSError:
                pass

    return '{}', 1, 0, True


def _parse_json_from_output(text):
    """Extract the first JSON object from text."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find('{')
    if start == -1:
        return None

    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    return None
    return None


def _log_exchange(context, question, response, elapsed_s=0, timed_out=False):
    """Append to history.jsonl with timing metadata."""
    entry = {
        'timestamp': datetime.now().isoformat(),
        'context': context,
        'question': question,
        'response': response,
        'elapsed_s': round(elapsed_s, 1),
        'timed_out': timed_out,
    }
    with open(HISTORY_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def _compute_stats():
    """Compute timeout statistics from history."""
    entries = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    recent = entries[-10:] if len(entries) > 10 else entries
    total = len(recent)
    timeouts = sum(1 for e in recent if e.get('timed_out', False))
    elapsed_vals = [e.get('elapsed_s', 0) for e in recent if e.get('elapsed_s', 0) > 0]
    avg_time = sum(elapsed_vals) / len(elapsed_vals) if elapsed_vals else 0
    timeout_rate = (timeouts / total * 100) if total > 0 else 0

    return {
        'total': total,
        'timeouts': timeouts,
        'timeout_rate': f"{timeout_rate:.0f}%",
        'avg_response_time_s': round(avg_time, 1),
    }


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'reviewer': 'claude-code-cli',
                    'timeout_fast': TIMEOUT_FAST, 'timeout_thorough': TIMEOUT_THOROUGH})


@app.route('/review', methods=['POST'])
def review():
    data = request.get_json(force=True)
    output = data.get('output', '')
    context = data.get('context', '')
    question = data.get('question', '')
    mode = data.get('mode', 'fast')

    prompt = REVIEWER_PROMPT_TEMPLATE.format(
        output=output, context=context, question=question
    )

    if mode == 'fast':
        model = 'claude-haiku-4-5-20251001'
        timeout = TIMEOUT_FAST
    else:
        model = None
        timeout = TIMEOUT_THOROUGH

    stdout, rc, elapsed, timed_out = _run_claude_reviewer(prompt, model=model, timeout=timeout)

    parsed = _parse_json_from_output(stdout)
    if parsed is None:
        parsed = {
            'assessment': f'Could not parse reviewer response. Raw: {stdout[:500]}',
            'quality': 'NEEDS_WORK',
            'issues': ['Response was not valid JSON'],
            'next_instructions': '',
            'can_continue': True,
        }

    _log_exchange(context, question, parsed, elapsed_s=elapsed, timed_out=timed_out)

    return jsonify(parsed)


@app.route('/history', methods=['GET'])
def history():
    entries = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    stats = _compute_stats()
    return jsonify({'entries': entries[-20:], 'stats': stats})


if __name__ == '__main__':
    print(f"Review bridge starting on http://localhost:7771")
    print(f"Timeouts: fast={TIMEOUT_FAST}s, thorough={TIMEOUT_THOROUGH}s")
    print(f"History: {HISTORY_FILE}")
    print()

    # Startup check
    _check_claude_cli()
    print()

    app.run(host='127.0.0.1', port=7771, debug=False)

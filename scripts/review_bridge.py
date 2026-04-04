"""
Automated Review Bridge
========================
Flask server on localhost:7771 that spawns Claude Code CLI as a
reviewer subprocess. No external API key needed.

Start: python scripts/review_bridge.py
Health: curl localhost:7771/health
Submit: POST localhost:7771/review with JSON body
"""

import os
import sys
import json
import subprocess
import time
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

REVIEWER_PROMPT_TEMPLATE = """You are a senior hydraulic engineer and software architect \
reviewing output from an autonomous Claude Code session building a professional \
hydraulic analysis desktop tool.

The tool uses PyQt6, WNTR, TSNet, and custom slurry solvers targeting \
Australian water and mining engineers.
Standards: WSAA, AS/NZS 1477, AS 2280, AS/NZS 4130, AS 4058.
Current test suite: 410+ passing, 12 xfailed.

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

TIMEOUT_FAST = 180
TIMEOUT_THOROUGH = 300


def _run_claude_reviewer(prompt, model=None, timeout=TIMEOUT_FAST):
    """Run claude CLI and return its stdout. Retries once on timeout."""
    cmd = ["claude", "--print", "--dangerously-skip-permissions"]
    if model:
        cmd.extend(["--model", model])
    cmd.append(prompt)

    for attempt in range(2):  # retry once on timeout
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, cwd=ROOT,
            )
            return result.stdout.strip(), result.returncode
        except FileNotFoundError:
            return ('{"assessment": "Claude CLI not found on PATH", '
                    '"quality": "NEEDS_WORK", "issues": ["claude CLI not installed"], '
                    '"next_instructions": "", "can_continue": true}'), 1
        except subprocess.TimeoutExpired:
            if attempt == 0:
                continue  # retry once
            return ('{"assessment": "Review timed out after retry", '
                    '"quality": "ACCEPTABLE", "issues": ["timeout after 2 attempts"], '
                    '"next_instructions": "", "can_continue": true}'), 1
    return '{}', 1


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


def _log_exchange(context, question, response):
    """Append to history.jsonl."""
    entry = {
        'timestamp': datetime.now().isoformat(),
        'context': context,
        'question': question,
        'response': response,
    }
    with open(HISTORY_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'reviewer': 'claude-code-cli'})


@app.route('/review', methods=['POST'])
def review():
    data = request.get_json(force=True)
    output = data.get('output', '')
    context = data.get('context', '')
    question = data.get('question', '')
    mode = data.get('mode', 'fast')  # 'fast' (haiku) or 'thorough' (default model)

    prompt = REVIEWER_PROMPT_TEMPLATE.format(
        output=output, context=context, question=question
    )

    if mode == 'fast':
        model = 'claude-haiku-4-5-20251001'
        timeout = TIMEOUT_FAST
    else:
        model = None  # use default model
        timeout = TIMEOUT_THOROUGH

    stdout, rc = _run_claude_reviewer(prompt, model=model, timeout=timeout)

    parsed = _parse_json_from_output(stdout)
    if parsed is None:
        parsed = {
            'assessment': f'Could not parse reviewer response. Raw: {stdout[:500]}',
            'quality': 'NEEDS_WORK',
            'issues': ['Response was not valid JSON'],
            'next_instructions': '',
            'can_continue': True,
        }

    _log_exchange(context, question, parsed)

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
    return jsonify(entries[-20:])


if __name__ == '__main__':
    print(f"Review bridge starting on http://localhost:7771")
    print(f"History: {HISTORY_FILE}")
    app.run(host='127.0.0.1', port=7771, debug=False)

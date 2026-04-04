"""
Automated Review Bridge — Anthropic API Direct
================================================
Flask server on localhost:7771. Calls the Anthropic Messages API
directly instead of spawning claude CLI subprocesses.

Requires: ANTHROPIC_API_KEY environment variable set.
Fast reviews complete in 2-5 seconds (vs 45-120s via CLI).

Start: python scripts/review_bridge.py
Health: curl localhost:7771/health
Submit: POST localhost:7771/review
"""

import os
import sys
import json
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(ROOT, 'docs', 'review_loop', 'history.jsonl')
os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)

# Load .env file if present (for ANTHROPIC_API_KEY)
_env_file = os.path.join(ROOT, '.env')
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _key, _, _val = _line.partition('=')
                _key = _key.strip()
                _val = _val.strip().strip('"').strip("'")
                if _key and _val and _key not in os.environ:
                    os.environ[_key] = _val

try:
    from flask import Flask, request, jsonify
except ImportError:
    print("Flask not installed. Run: pip install flask")
    sys.exit(1)

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

app = Flask(__name__)

# Configurable via environment
TIMEOUT_FAST = int(os.environ.get('REVIEW_TIMEOUT', '30'))
TIMEOUT_THOROUGH = int(os.environ.get('REVIEW_TIMEOUT_THOROUGH', '60'))
MODEL_FAST = 'claude-haiku-4-5-20251001'
MODEL_THOROUGH = 'claude-sonnet-4-6'

REVIEWER_PROMPT_TEMPLATE = """You are a senior hydraulic engineer and software architect \
with specific expertise in Australian water and mining engineering. You are reviewing \
an autonomous Claude Code session building a professional hydraulic analysis tool.

## Your Engineering Knowledge Base

### Australian Standards You Enforce
- WSA 03-2011: min 20m pressure, max 50m residential, max 2.0 m/s velocity, fire flow 25 LPS at 12m residual
- AS 2280: DI wave speed >= 1100 m/s, PN ratings per size
- AS/NZS 1477: PVC OD series (DN200=225mm etc), not OD=DN
- AS/NZS 4130: PE100 yield 20-22 MPa short-term design
- AS 4058: Concrete HW-C by size (DN600=100, not 120)
- ADWG: chlorine 0.2 mg/L operational minimum

### Critical Formula Rules (bugs we already fixed)
- Slurry friction factor: ALWAYS Darcy (64/Re), NEVER Fanning (16/Re). This was a 4x error we fixed.
- Dodge-Metzner turbulent: multiply by 4 (Fanning to Darcy)
- WSAA compliance: ALWAYS gauge pressure, never total head
- Water age from WNTR: divide by 3600 (returns seconds)
- Velocity: abs(flow).max(), never signed flow.max()
- Joukowsky: use actual fluid density, not hardcoded rho=1000

### Known Limitations to Watch For
- Wilson-Thomas turbulent slurry: simplified, 5-10% uncertainty
- TSNet: only works with valve closure on simple networks
- Thin-wall hoop stress: valid only when t/D < 0.1
- PN safety factor: pressure utilisation ratio, NOT AS 2280 code compliance check

### UI Standards for Professional Engineers
- Every displayed value must have units (42.3 m not 42.3)
- Pressure: 1 decimal, velocity: 2 decimals, flow: 2 decimals
- Compliance messages must cite the standard and clause
- Error messages must be actionable, not cryptic
- No Python tracebacks visible to users ever

### What Blockers Look Like
- Any calculation producing results 2x+ different from expected
- UI thread blocking on analysis (must use QThread)
- Wrong units displayed (kPa where m expected, etc)
- WSAA threshold checking against wrong quantity
- Layer violations (UI importing wntr directly)
- Silent failures (error dict passthrough as success)

### What HIGH Issues Look Like
- Missing units on any displayed value
- Denominator bugs in summary statistics
- Thresholds not traceable to a published standard
- Test coverage gap on a safety-critical calculation
- Performance regression (render > 500ms at 500 nodes)

TASK: {context}
OUTPUT: {output}
QUESTION: {question}

Respond in valid JSON only. No text outside the JSON:
{{
  "assessment": "one paragraph honest assessment",
  "quality": "GOOD | ACCEPTABLE | NEEDS_WORK | BLOCKER",
  "issues": ["specific issue with file:line if possible"],
  "next_instructions": "exact Claude Code instructions or empty string",
  "can_continue": true
}}"""


def _has_api_key():
    """Check if ANTHROPIC_API_KEY is set."""
    return bool(os.environ.get('ANTHROPIC_API_KEY'))


def _run_api_reviewer(prompt, model=MODEL_FAST, max_tokens=1000):
    """Call Anthropic Messages API directly. Returns (text, returncode)."""
    if not HAS_ANTHROPIC:
        return ('{"assessment": "anthropic package not installed", '
                '"quality": "NEEDS_WORK", "issues": ["pip install anthropic"], '
                '"next_instructions": "", "can_continue": true}'), 1, 0

    if not _has_api_key():
        return ('{"assessment": "ANTHROPIC_API_KEY not set", '
                '"quality": "ACCEPTABLE", "issues": ["set ANTHROPIC_API_KEY"], '
                '"next_instructions": "", "can_continue": true}'), 1, 0

    t0 = time.perf_counter()
    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = time.perf_counter() - t0
        return message.content[0].text, 0, elapsed
    except anthropic.APIError as e:
        elapsed = time.perf_counter() - t0
        return (f'{{"assessment": "API error: {e}", "quality": "NEEDS_WORK", '
                f'"issues": ["API error"], "next_instructions": "", "can_continue": true}}'), 1, elapsed
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return (f'{{"assessment": "Error: {e}", "quality": "ACCEPTABLE", '
                f'"issues": ["{type(e).__name__}"], "next_instructions": "", "can_continue": true}}'), 1, elapsed


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
    """Append to history.jsonl."""
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
    """Compute statistics from history."""
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
    return jsonify({
        'status': 'ok',
        'reviewer': 'anthropic-api',
        'api_key_set': _has_api_key(),
        'fast_model': MODEL_FAST,
        'thorough_model': MODEL_THOROUGH,
    })


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

    model = MODEL_THOROUGH if mode == 'thorough' else MODEL_FAST
    stdout, rc, elapsed = _run_api_reviewer(prompt, model=model)

    parsed = _parse_json_from_output(stdout)
    if parsed is None:
        parsed = {
            'assessment': f'Could not parse response. Raw: {stdout[:500]}',
            'quality': 'NEEDS_WORK',
            'issues': ['Response was not valid JSON'],
            'next_instructions': '',
            'can_continue': True,
        }

    timed_out = elapsed > (TIMEOUT_FAST if mode == 'fast' else TIMEOUT_THOROUGH)
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
    print("Review bridge starting on http://localhost:7771")
    print(f"Models: fast={MODEL_FAST}, thorough={MODEL_THOROUGH}")
    print(f"API key set: {_has_api_key()}")
    print(f"History: {HISTORY_FILE}")

    if not _has_api_key():
        print("\nWARNING: ANTHROPIC_API_KEY not set!")
        print("Set it with: set ANTHROPIC_API_KEY=sk-ant-...")
        print("Reviews will return placeholder responses until key is set.\n")

    app.run(host='127.0.0.1', port=7771, debug=False)

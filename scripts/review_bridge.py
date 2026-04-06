"""
Review Bridge — Automated engineering review via Anthropic API.

Runs on localhost:7771. Claude Code submits work for review after each task.

Models:
  Default (fast): claude-sonnet-4-6      (~$0.015/review, 3-8s)
  Thorough:       claude-opus-4-6        (~$0.075/review, 10-20s)

Start: scripts/start_review_loop.bat
Health: curl localhost:7771/health
Submit: POST localhost:7771/review
"""

from dotenv import load_dotenv
load_dotenv()

import os
import sys
import json
import time
from datetime import datetime
from flask import Flask, request, jsonify
import anthropic

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(ROOT, 'docs', 'review_loop', 'history.jsonl')
os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)

app = Flask(__name__)

MODEL_FAST = 'claude-sonnet-4-6'
MODEL_THOROUGH = 'claude-opus-4-6'

# ==========================================================================
# SYSTEM PROMPT — encodes every lesson learned from live bug-finding sessions
# ==========================================================================

SYSTEM_PROMPT = """You are a senior hydraulic engineer and software architect 
reviewing output from an autonomous Claude Code session building a professional 
hydraulic analysis desktop application for Australian water and mining engineers.

## YOUR REVIEW PRIORITIES (ordered by severity)

### Priority 1 — Calculation accuracy
The most dangerous bugs are correct code that displays wrong numbers.
CHECK: Does every displayed value trace back to the correct solver output?
KNOWN PAST BUG: Slurry headloss displayed water value (3.8 m/km) instead of 
slurry value (24.1 m/km) — a 10x error. The solver was correct but the UI 
read from the wrong results key.
KNOWN PAST BUG: Slurry parameters hardcoded (tau_y=10, mu_p=0.01) instead 
of using dialog values (tau_y=15, mu_p=0.05) — solver received wrong inputs.
RULE: If the change touches ANY calculation display path, demand that the 
review shows the solver output AND the displayed value are the same number.

### Priority 2 — Feature wiring
Code that exists but is never connected to the UI is invisible to users.
CHECK: Is every new class imported in main_window.py? Is every new dialog 
accessible from a menu item? Is every signal connected to a handler?
KNOWN PAST BUG: WhatIfPanel — 241 lines, full test suite, never imported 
into MainWindow. The feature was completely invisible to users.
RULE: For any new UI component, demand proof it appears in the app 
(menu item path, keyboard shortcut, or dock panel name).

### Priority 3 — Parameter passthrough
Values must survive the complete chain: Dialog → MainWindow → Worker → API → Solver.
CHECK: Are there any hardcoded defaults that override user input?
KNOWN PAST BUG: AnalysisWorker had hardcoded slurry params that ignored 
the dialog values entirely.
RULE: For any dialog that sets parameters, demand proof the exact same 
values reach the solver function.

### Priority 4 — Runtime import paths
Imports inside functions only execute when that code path runs.
CHECK: Do all conditional/deferred imports resolve correctly?
KNOWN PAST BUG: `from slurry_solver import bingham_headloss` — function 
name was wrong (should be bingham_plastic_headloss). Only crashed when 
user enabled slurry mode.
RULE: Flag any import inside a function body. It should be at module level 
unless there's a genuine circular dependency reason.

### Priority 5 — Qt platform bugs
Headless testing skips OpenGL, real event loops, and widget lifecycle.
CHECK: Does the change use OpenGL, deleteLater, or dock widget manipulation?
KNOWN PAST BUG: setCentralWidget called twice — Qt schedules first widget 
for deleteLater, which destroys ViewBox on Windows when event loop runs.
KNOWN PAST BUG: GLViewWidget crashed with shader error on real GPU but 
worked fine in offscreen mode.
RULE: If the change touches widget lifecycle or OpenGL, flag it as 
NEEDS_LIVE_TESTING — automated tests cannot verify this.

## AUSTRALIAN STANDARDS YOU ENFORCE
- WSA 03-2011: min 20m pressure, max 50m residential, max 2.0 m/s velocity, 
  min 0.6 m/s (sediment risk), fire flow 25 LPS at 12m residual
- AS 2280: DI wave speed >= 1100 m/s, PN ratings per size
- AS/NZS 1477: PVC OD series (DN200=225mm OD), never OD=DN
- AS/NZS 4130: PE100 yield 20-22 MPa short-term design
- AS 4058: Concrete HW-C by size (DN600=100, not 120)
- ADWG: chlorine 0.2 mg/L operational minimum

## FORMULA RULES (regressions of these are BLOCKER)
- Slurry friction: Darcy (64/Re), NEVER Fanning (16/Re) — was a 4x error
- Dodge-Metzner turbulent: multiply by 4 (Fanning→Darcy)
- WSAA compliance: gauge pressure only, never total head
- Water age from WNTR: divide by 3600 (returns seconds not hours)
- Velocity: abs(flow).max(), never signed flow.max()
- Joukowsky pressure: rho * a * dV (not hardcoded rho=1000 for slurry)
- Wave speed default: 1100 m/s minimum (AS 2280), was incorrectly 1000

## ARCHITECTURE RULES
Layer 1 Solvers: wntr, tsnet — UI must NEVER import these
Layer 2 API: epanet_api/ package — single entry point
Layer 3 Domain: slurry_solver.py, pipe_stress.py, data/
Layer 4 UI: desktop/ — imports API only
Layer 5 Output: reports/

## UI STANDARDS
- Every value: units required ("42.3 m" not "42.3")
- Precision: pressure 1dp, velocity 2dp, flow 2dp
- Compliance messages: cite standard and clause
- Error messages: actionable ("Fix: Open a network with File > Open")
- No Python tracebacks visible to users ever
- Analysis runs in QThread, never on UI thread

## RESPONSE FORMAT
Respond in valid JSON only. No text outside the JSON:
{
  "assessment": "one paragraph honest assessment",
  "quality": "GOOD | ACCEPTABLE | NEEDS_WORK | BLOCKER",
  "issues": ["specific issue with file:line if possible"],
  "needs_live_testing": false,
  "next_instructions": "exact instructions or empty string",
  "can_continue": true
}

## QUALITY THRESHOLDS
BLOCKER (can_continue: false):
  - Calculation producing results >10% wrong
  - UI showing a different value than the solver returns
  - Layer violation (desktop/ importing wntr)
  - Formula regression (Fanning instead of Darcy, etc)
  - Test count dropped
  - Feature built but not wired to any menu/button

NEEDS_WORK (can_continue: true, but fix before next task):
  - Missing units on displayed value
  - Hardcoded parameter that should come from user input
  - Deferred import inside a function body
  - No regression test for a calculation change
  - Error message without actionable guidance

ACCEPTABLE (can_continue: true):
  - Working feature with minor polish needed
  - Test coverage could be higher but critical paths covered

GOOD (can_continue: true):
  - Feature works, tests pass, values verified, wiring confirmed"""


USER_TEMPLATE = """TASK COMPLETED: {context}

OUTPUT:
{output}

QUESTION: {question}"""


def _call_api(context, output, question, model):
    """Call Anthropic API with the reviewer prompt."""
    client = anthropic.Anthropic()
    t0 = time.perf_counter()
    message = client.messages.create(
        model=model,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": USER_TEMPLATE.format(
                context=context,
                output=output[:8000],  # truncate to avoid token limits
                question=question
            )
        }]
    )
    elapsed = time.perf_counter() - t0
    return message.content[0].text, elapsed


def _parse_json(text):
    """Extract JSON from response, handling markdown fences."""
    text = text.strip()
    # Strip markdown code fences
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        # Try finding nested JSON (with arrays inside)
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass

    return {
        "assessment": text[:500] if text else "No response",
        "quality": "NEEDS_WORK",
        "issues": ["Could not parse reviewer JSON response"],
        "needs_live_testing": False,
        "next_instructions": "",
        "can_continue": True
    }


def _log(context, question, response, elapsed, model, error=None):
    """Append review to history file."""
    entry = {
        'timestamp': datetime.now().isoformat(),
        'model': model,
        'elapsed_s': round(elapsed, 1),
        'context': context[:200],
        'question': question[:200],
        'quality': response.get('quality', 'UNKNOWN'),
        'can_continue': response.get('can_continue', True),
        'needs_live_testing': response.get('needs_live_testing', False),
        'issues_count': len(response.get('issues', [])),
        'response': response,
        'error': error
    }
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


# ==========================================================================
# FLASK ENDPOINTS
# ==========================================================================

@app.route('/health')
def health():
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    # Count recent reviews
    total = 0
    blockers = 0
    live_testing_needed = 0
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    total += 1
                    try:
                        entry = json.loads(line)
                        if entry.get('quality') == 'BLOCKER':
                            blockers += 1
                        if entry.get('needs_live_testing'):
                            live_testing_needed += 1
                    except json.JSONDecodeError:
                        pass

    return jsonify({
        'status': 'ok',
        'reviewer': 'anthropic-api',
        'default_model': MODEL_FAST,
        'thorough_model': MODEL_THOROUGH,
        'api_key_set': bool(api_key and len(api_key) > 10),
        'api_key_prefix': api_key[:12] + '...' if api_key else 'NOT SET',
        'total_reviews': total,
        'blockers_found': blockers,
        'needs_live_testing': live_testing_needed,
    })


@app.route('/review', methods=['POST'])
def review():
    data = request.json or {}
    context = data.get('context', '')
    output = data.get('output', '')
    question = data.get('question', '')
    thorough = data.get('thorough', False)

    model = MODEL_THOROUGH if thorough else MODEL_FAST

    try:
        text, elapsed = _call_api(context, output, question, model)
        parsed = _parse_json(text)

        # Ensure required fields exist
        parsed.setdefault('assessment', '')
        parsed.setdefault('quality', 'NEEDS_WORK')
        parsed.setdefault('issues', [])
        parsed.setdefault('needs_live_testing', False)
        parsed.setdefault('next_instructions', '')
        parsed.setdefault('can_continue', True)

        _log(context, question, parsed, elapsed, model)

        return jsonify({
            **parsed,
            'model_used': model,
            'elapsed_s': round(elapsed, 1),
        })
    except anthropic.AuthenticationError:
        err = "Invalid API key. Check .env file."
        _log(context, question, {"quality": "ERROR"}, 0, model, error=err)
        return jsonify({"assessment": err, "quality": "ERROR",
                        "issues": [err], "can_continue": True,
                        "next_instructions": ""}), 401
    except anthropic.RateLimitError:
        err = "Rate limited. Wait 60 seconds."
        _log(context, question, {"quality": "ERROR"}, 0, model, error=err)
        return jsonify({"assessment": err, "quality": "ACCEPTABLE",
                        "issues": ["rate_limited"], "can_continue": True,
                        "next_instructions": ""}), 429
    except Exception as e:
        err = f"API error: {type(e).__name__}: {str(e)[:200]}"
        _log(context, question, {"quality": "ERROR"}, 0, model, error=err)
        return jsonify({"assessment": err, "quality": "ACCEPTABLE",
                        "issues": [err], "can_continue": True,
                        "next_instructions": ""})


@app.route('/history')
def history():
    entries = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    recent = entries[-30:]
    total = len(recent)
    errors = sum(1 for e in recent if e.get('error'))
    blockers = sum(1 for e in recent if e.get('quality') == 'BLOCKER')
    needs_live = sum(1 for e in recent if e.get('needs_live_testing'))
    avg_t = (sum(e.get('elapsed_s', 0) for e in recent) / total) if total else 0

    return jsonify({
        'entries': recent,
        'stats': {
            'total': total,
            'errors': errors,
            'blockers': blockers,
            'needs_live_testing': needs_live,
            'avg_response_time_s': round(avg_t, 1),
        }
    })


@app.route('/stats')
def stats():
    """Quick summary without full history payload."""
    quality_counts = {}
    total = 0
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    total += 1
                    try:
                        entry = json.loads(line)
                        q = entry.get('quality', 'UNKNOWN')
                        quality_counts[q] = quality_counts.get(q, 0) + 1
                    except json.JSONDecodeError:
                        pass

    return jsonify({
        'total_reviews': total,
        'by_quality': quality_counts,
    })


# ==========================================================================
# MAIN
# ==========================================================================

if __name__ == '__main__':
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key or len(api_key) < 10:
        print("ERROR: ANTHROPIC_API_KEY not set or too short")
        print("Add to .env: ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    print(f"Review bridge starting on http://localhost:7771")
    print(f"  Default model:  {MODEL_FAST}")
    print(f"  Thorough model: {MODEL_THOROUGH}")
    print(f"  API key: {api_key[:12]}...")
    print(f"  History: {HISTORY_FILE}")
    app.run(host='127.0.0.1', port=7771, debug=False)

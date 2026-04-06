# Deep Diagnostic: Systematic Bug Detection

## Context

This project has 1071+ passing tests but live use found 7 critical bugs 
that tests missed entirely. The testing approach is fundamentally flawed —
it tests components in isolation but never verifies the boundaries between 
them. This diagnostic session fixes that.

Do NOT build new features. Do NOT add to the task queue.
Your only job is finding bugs and writing tests that catch them.

Work through each diagnostic category below. For each:
1. Run the diagnostic check
2. Document every finding in docs/DIAGNOSTIC_REPORT.md
3. Write a regression test for every real bug found
4. Fix every bug found
5. Move to the next category

---

## DIAGNOSTIC 1 — Wiring Verification

**Problem this catches:** Features that exist as classes but are never 
connected to the UI. Example: WhatIfPanel was built, tested, but never 
imported into MainWindow.

**Method:** For every desktop/*.py module, verify it is imported and 
instantiated in main_window.py.

```python
# Run this diagnostic:
import os, ast, importlib

# 1. Find all desktop modules
desktop_modules = []
for f in os.listdir('desktop'):
    if f.endswith('.py') and f != '__init__.py':
        desktop_modules.append(f[:-3])

# 2. Find all imports in main_window.py
with open('desktop/main_window.py') as fh:
    tree = ast.parse(fh.read())

imported_names = set()
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        if node.module and 'desktop' in (node.module or ''):
            for alias in node.names:
                imported_names.add(alias.name)
    elif isinstance(node, ast.Import):
        for alias in node.names:
            imported_names.add(alias.name)

# 3. For each module, check if its main class is imported
for mod in desktop_modules:
    spec = importlib.util.find_spec(f'desktop.{mod}')
    if spec:
        module = importlib.import_module(f'desktop.{mod}')
        classes = [name for name, obj in vars(module).items() 
                   if isinstance(obj, type) and not name.startswith('_')]
        for cls in classes:
            if cls not in imported_names:
                print(f'UNWIRED: desktop/{mod}.py class {cls} — '
                      f'not imported in main_window.py')
```

Run this. For every UNWIRED class, determine:
- Is it intentionally unused? (helper class, mixin) → document why
- Should it be wired to the UI? → wire it and add a test

Also check: every QAction in main_window.py has a .triggered.connect() call.
Find any QAction without a connection — those are dead menu items.

```python
# Find unconnected QActions
import re
with open('desktop/main_window.py') as f:
    content = f.read()

# Find all QAction creations
actions = re.findall(r'(\w+)\s*=\s*QAction\(', content)
# Find all .triggered.connect calls
connected = re.findall(r'(\w+)\.triggered\.connect', content)

for action in actions:
    if action not in connected:
        print(f'DEAD MENU ITEM: {action} — created but never connected')
```

---

## DIAGNOSTIC 2 — Display vs Calculation Consistency

**Problem this catches:** The solver returns correct values but the UI 
shows different values. Example: slurry headloss 24.1 m/km from solver,
but UI showed 3.8 m/km (the water value).

**Method:** Run analysis programmatically, then read the actual text 
from every QTableWidget cell and compare against the results dict.

```python
# This must run with a real QApplication (offscreen OK for cell text)
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)

from desktop.main_window import MainWindow
from epanet_api import HydraulicAPI

# Create and populate window
w = MainWindow()
api = HydraulicAPI()

# Test each tutorial network
tutorials = [
    'tutorials/simple_loop/network.inp',
    'tutorials/demo_network/network.inp',
    'tutorials/mining_slurry_line/network.inp',
    'tutorials/dead_end_network/network.inp',
]

for inp_path in tutorials:
    if not os.path.exists(inp_path):
        continue
    
    api.load_network_from_path(inp_path)
    results = api.run_steady_state(save_plot=False)
    
    # Simulate what the UI does
    w.api = api
    w._last_results = results
    w._populate_results_tables(results)
    
    # Now read back every cell in the node results table
    table = w.node_results_table
    mismatches = []
    
    for row in range(table.rowCount()):
        # Get node ID from first column
        node_id_item = table.item(row, 0)
        if not node_id_item:
            continue
        node_id = node_id_item.text()
        
        # Get displayed values from each column
        for col in range(1, table.columnCount()):
            header = table.horizontalHeaderItem(col)
            if not header:
                continue
            header_text = header.text()
            cell_item = table.item(row, col)
            if not cell_item:
                continue
            displayed_text = cell_item.text()
            
            # Compare against API results
            api_data = results.get('pressures', {}).get(node_id, {})
            
            # Map column headers to API keys
            if 'Min' in header_text and 'Pressure' in header_text:
                api_val = api_data.get('min_m')
            elif 'Avg' in header_text and 'Pressure' in header_text:
                api_val = api_data.get('avg_m')
            elif 'Max' in header_text and 'Pressure' in header_text:
                api_val = api_data.get('max_m')
            else:
                continue
            
            if api_val is not None:
                try:
                    displayed_val = float(displayed_text.replace(' m', '')
                                         .replace(' kPa', ''))
                except ValueError:
                    mismatches.append(
                        f'{inp_path} {node_id} col={header_text}: '
                        f'displayed="{displayed_text}" not parseable')
                    continue
                
                if abs(displayed_val - api_val) > 0.15:
                    mismatches.append(
                        f'{inp_path} {node_id} col={header_text}: '
                        f'API={api_val:.2f} displayed={displayed_val:.2f} '
                        f'diff={abs(displayed_val - api_val):.2f}')
    
    # Same check for pipe results table
    pipe_table = w.pipe_results_table
    for row in range(pipe_table.rowCount()):
        pipe_id_item = pipe_table.item(row, 0)
        if not pipe_id_item:
            continue
        pipe_id = pipe_id_item.text()
        
        for col in range(1, pipe_table.columnCount()):
            header = pipe_table.horizontalHeaderItem(col)
            if not header:
                continue
            header_text = header.text()
            cell_item = pipe_table.item(row, col)
            if not cell_item:
                continue
            displayed_text = cell_item.text()
            
            api_fdata = results.get('flows', {}).get(pipe_id, {})
            
            if 'Velocity' in header_text:
                api_val = api_fdata.get('max_velocity_ms')
            elif 'Headloss' in header_text:
                api_val = api_fdata.get('headloss_per_km')
            elif 'Flow' in header_text:
                api_val = api_fdata.get('avg_lps')
            else:
                continue
            
            if api_val is not None:
                try:
                    displayed_val = float(
                        displayed_text.split()[0]  # strip units
                    )
                except (ValueError, IndexError):
                    continue
                
                if abs(displayed_val - api_val) > 0.15:
                    mismatches.append(
                        f'{inp_path} {pipe_id} col={header_text}: '
                        f'API={api_val:.2f} displayed={displayed_val:.2f}')
    
    if mismatches:
        print(f'\n=== MISMATCHES in {inp_path} ===')
        for m in mismatches:
            print(f'  {m}')
    else:
        print(f'{inp_path}: all displayed values match API ✓')
```

Run this diagnostic. EVERY mismatch is a potential repeat of the 
slurry headloss bug.

**CRITICAL EXTENSION — Slurry mode consistency:**

After running the water mode check above, also run with slurry mode 
on the mining_slurry_line network. The check must verify:

1. The results dict contains slurry headloss values (not water)
2. The pipe results table column header says "Headloss Slurry (m/km)"
3. The displayed headloss value matches the slurry solver output
4. Re_B and Regime columns are present and populated

For each check, if the displayed value doesn't match the solver:
that is a BLOCKER finding.

---

## DIAGNOSTIC 3 — Parameter Passthrough Verification

**Problem this catches:** Dialog shows one value, solver receives 
a different value. Example: slurry dialog showed tau_y=15 but solver 
received tau_y=10 (hardcoded defaults).

**Method:** Intercept parameters at every boundary they cross.

The parameter flow in the app is:
```
Dialog (user enters values)
  → MainWindow stores them
    → AnalysisWorker receives them
      → HydraulicAPI method receives them
        → Solver function receives them
```

At each arrow, a bug can silently change the values.

```python
# Instrument the parameter chain
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)

# Monkey-patch to capture parameters at each boundary
captured = {}

# Patch 1: What does the slurry dialog produce?
from desktop.main_window import MainWindow
w = MainWindow()

# Check what default slurry params the app uses
# Find the slurry action and see what params it would set
if hasattr(w, 'slurry_params'):
    captured['mainwindow_slurry_params'] = dict(w.slurry_params)
    print(f'MainWindow slurry_params: {w.slurry_params}')

# Check what the slurry dialog defaults to
try:
    from desktop.slurry_dialog import SlurryDialog
    dlg = SlurryDialog(parent=None)
    captured['dialog_defaults'] = {
        'tau_y': dlg.tau_y_spin.value() if hasattr(dlg, 'tau_y_spin') else 'MISSING',
        'mu_p': dlg.mu_p_spin.value() if hasattr(dlg, 'mu_p_spin') else 'MISSING',
        'density': dlg.density_spin.value() if hasattr(dlg, 'density_spin') else 'MISSING',
    }
    print(f'SlurryDialog defaults: {captured["dialog_defaults"]}')
except Exception as e:
    print(f'SlurryDialog import failed: {e}')

# Patch the actual solver to capture what it receives
from slurry_solver import bingham_plastic_headloss as _original_bingham
call_log = []
def _capturing_bingham(**kwargs):
    call_log.append(dict(kwargs))
    return _original_bingham(**kwargs)

import slurry_solver
slurry_solver.bingham_plastic_headloss = _capturing_bingham

# Now trigger a slurry analysis through the API
from epanet_api import HydraulicAPI
api = HydraulicAPI()
api.load_network_from_path('tutorials/mining_slurry_line/network.inp')

# What does the API's run_slurry method actually pass?
# Try to find and call it the same way MainWindow does
if hasattr(api, 'run_slurry_analysis'):
    try:
        r = api.run_slurry_analysis(
            tau_y=15.0, mu_p=0.05, density=1800.0
        )
        if call_log:
            print(f'Solver received: {call_log[-1]}')
            # Check: do the solver params match what we sent?
            sent = {'tau_y': 15.0, 'mu_p': 0.05, 'density': 1800.0}
            for k, v in sent.items():
                received = call_log[-1].get(k)
                if received is not None and abs(received - v) > 0.001:
                    print(f'PARAM MISMATCH: sent {k}={v}, '
                          f'solver received {k}={received}')
    except Exception as e:
        print(f'run_slurry_analysis failed: {e}')

# Restore original
slurry_solver.bingham_plastic_headloss = _original_bingham
```

Run this. ANY parameter mismatch between what the dialog shows and 
what the solver receives is a critical bug — it means the engineer 
sees one thing but the calculation uses another.

**Extend this pattern to ALL dialogs that pass parameters:**
- Fire flow dialog → fire flow sweep parameters
- EPS dialog → duration, timestep
- Calibration dialog → measurement data, iteration count
- Demand pattern dialog → multiplier values
- Compliance threshold dialog → WSAA thresholds
- Safety case dialog → engineer name, analysis type selections

For each dialog: verify the parameter chain end-to-end.

---

## DIAGNOSTIC 4 — Runtime Import Verification

**Problem this catches:** Imports that only execute when a specific 
feature is triggered. Example: `from slurry_solver import 
bingham_headloss` crashed because the function name was wrong 
(should be bingham_plastic_headloss).

**Method:** Force-import every conditional import in the codebase.

```python
import os, re, importlib

# Find all conditional/deferred imports in the codebase
deferred_imports = []
for root, _, files in os.walk('.'):
    if any(skip in root for skip in ['__pycache__', '.git', 'test', 
                                      'node_modules', 'dist', 'build']):
        continue
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(root, f)
        try:
            with open(path) as fh:
                lines = fh.readlines()
        except:
            continue
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Find imports inside functions (indented imports)
            if (stripped.startswith('import ') or 
                stripped.startswith('from ')) and line[0] == ' ':
                deferred_imports.append((path, i+1, stripped))

print(f'Found {len(deferred_imports)} deferred/conditional imports\n')

# Try each import
failures = []
for path, lineno, import_stmt in deferred_imports:
    # Parse the import statement
    try:
        if import_stmt.startswith('from '):
            match = re.match(r'from\s+(\S+)\s+import\s+(.+)', import_stmt)
            if match:
                module_name = match.group(1)
                names = [n.strip().split(' as ')[0] 
                         for n in match.group(2).split(',')]
                mod = importlib.import_module(module_name)
                for name in names:
                    if not hasattr(mod, name.strip()):
                        failures.append(
                            f'{path}:{lineno} — {import_stmt}\n'
                            f'  Module {module_name} has no attribute "{name.strip()}"')
        elif import_stmt.startswith('import '):
            match = re.match(r'import\s+(\S+)', import_stmt)
            if match:
                importlib.import_module(match.group(1))
    except ImportError as e:
        failures.append(f'{path}:{lineno} — {import_stmt}\n  ImportError: {e}')
    except Exception as e:
        failures.append(f'{path}:{lineno} — {import_stmt}\n  Error: {e}')

if failures:
    print('=== IMPORT FAILURES ===')
    for f in failures:
        print(f)
else:
    print('All deferred imports resolve correctly ✓')
```

Run this. Every failure is a latent crash waiting for a user to 
trigger that code path.

---

## DIAGNOSTIC 5 — Signal Chain Verification

**Problem this catches:** Qt signals connected to methods that don't 
exist, or connected with wrong argument signatures. These only crash 
when the signal fires at runtime.

**Method:** Find every .connect() call and verify the target method 
exists and has a compatible signature.

```python
import os, re, ast, inspect

signal_connections = []
for root, _, files in os.walk('desktop'):
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(root, f)
        with open(path) as fh:
            content = fh.read()
        
        # Find .connect() calls
        pattern = r'(\w+(?:\.\w+)*)\.connect\((?:self\.)?(\w+)\)'
        matches = re.finditer(pattern, content)
        for m in matches:
            signal_path = m.group(1)
            handler = m.group(2)
            line = content[:m.start()].count('\n') + 1
            signal_connections.append((path, line, signal_path, handler))

print(f'Found {len(signal_connections)} signal connections\n')

# For connections using self.handler, verify the method exists
# on the class defined in that file
for path, line, signal, handler in signal_connections:
    with open(path) as fh:
        content = fh.read()
    
    # Check if handler method is defined in this file
    method_pattern = rf'def\s+{re.escape(handler)}\s*\('
    if not re.search(method_pattern, content):
        # Could be inherited — check if it's a known Qt method
        known_qt = {'close', 'show', 'hide', 'update', 'repaint',
                     'accept', 'reject', 'raise_', 'setVisible',
                     'setText', 'clear', 'deleteLater'}
        if handler not in known_qt:
            print(f'MISSING HANDLER: {path}:{line} '
                  f'{signal}.connect({handler}) — '
                  f'method {handler}() not found in file')
```

Run this. Every MISSING HANDLER is a potential crash when that 
signal fires.

---

## DIAGNOSTIC 6 — Widget Geometry and State Verification

**Problem this catches:** Widgets that are created but invisible, 
too small to read, or overlapping. Example: Properties panel was 
invisible because dock wasn't raised. Toolbar buttons truncated.

**Method:** After creating and populating the MainWindow, inspect 
every visible widget's geometry.

```python
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)

from desktop.main_window import MainWindow

w = MainWindow()
w.resize(1400, 900)
w.show()
app.processEvents()

issues = []

def check_widget_tree(widget, depth=0, path=''):
    """Recursively check all visible widgets for problems."""
    name = widget.objectName() or widget.__class__.__name__
    current_path = f'{path}/{name}'
    
    if not widget.isVisible():
        return  # Skip invisible widgets
    
    geom = widget.geometry()
    
    # Check 1: Widget too small to be usable
    if geom.width() < 20 and geom.height() < 20:
        issues.append(f'TOO SMALL: {current_path} '
                      f'size={geom.width()}x{geom.height()}')
    
    # Check 2: Widget has zero size (likely not laid out)
    if geom.width() == 0 or geom.height() == 0:
        issues.append(f'ZERO SIZE: {current_path} '
                      f'size={geom.width()}x{geom.height()}')
    
    # Check 3: QLabel or QPushButton text truncated
    from PyQt6.QtWidgets import QLabel, QPushButton, QToolButton
    if isinstance(widget, (QLabel, QPushButton, QToolButton)):
        text = widget.text()
        if text:
            fm = widget.fontMetrics()
            text_width = fm.horizontalAdvance(text)
            if text_width > geom.width() + 5:
                issues.append(
                    f'TRUNCATED TEXT: {current_path} '
                    f'text="{text}" needs {text_width}px '
                    f'but widget is {geom.width()}px wide')
    
    # Check 4: QTableWidget columns truncated
    from PyQt6.QtWidgets import QTableWidget
    if isinstance(widget, QTableWidget):
        for col in range(widget.columnCount()):
            header = widget.horizontalHeaderItem(col)
            if header:
                header_text = header.text()
                col_width = widget.columnWidth(col)
                fm = widget.fontMetrics()
                text_width = fm.horizontalAdvance(header_text)
                if text_width > col_width + 10:
                    issues.append(
                        f'TRUNCATED HEADER: {current_path} '
                        f'column {col} "{header_text}" '
                        f'needs {text_width}px, has {col_width}px')
    
    # Recurse into children
    for child in widget.children():
        from PyQt6.QtWidgets import QWidget
        if isinstance(child, QWidget):
            check_widget_tree(child, depth+1, current_path)

check_widget_tree(w)

if issues:
    print(f'\n=== {len(issues)} WIDGET ISSUES ===')
    for issue in issues:
        print(f'  {issue}')
else:
    print('All widgets properly sized ✓')
```

Run this. Every TRUNCATED TEXT finding is a label an engineer can't 
read. Every ZERO SIZE is an invisible widget.

---

## DIAGNOSTIC 7 — Cross-Verification: Hand Calculations

**Problem this catches:** The solver produces a number. Is that 
number actually correct physics?

**Method:** For 5 critical calculations, compute the expected 
answer from first principles in a separate script (not using the 
tool's own solver), then compare.

```python
import math

results = []

# =============================================
# CHECK 1: Hazen-Williams headloss
# DN200, C=130, Q=20 LPS, L=500m
# =============================================
D = 0.200  # m
C = 130
Q = 0.020  # m3/s
L = 500  # m

# Hazen-Williams in SI: hL = 10.67 * L * Q^1.852 / (C^1.852 * D^4.87)
hw_headloss = 10.67 * L * Q**1.852 / (C**1.852 * D**4.87)
hw_per_km = hw_headloss / L * 1000

# Get tool's answer
from epanet_api import HydraulicAPI
api = HydraulicAPI()
api.load_network_from_path('tutorials/mining_slurry_line/network.inp')
r = api.run_steady_state(save_plot=False)

tool_flow = r['flows']['P1']['avg_lps']
pipe = api.wn.get_link('P1')
tool_velocity = r['flows']['P1']['max_velocity_ms']

# Tool uses EPANET/WNTR internally — get its headloss
# from the simulation results directly
headloss_data = api.steady_results.link['headloss']
if 'P1' in headloss_data.columns:
    tool_hl = float(abs(headloss_data['P1']).max())
    tool_hl_per_km = tool_hl / pipe.length * 1000
    
    diff_pct = abs(tool_hl_per_km - hw_per_km) / hw_per_km * 100
    status = 'PASS' if diff_pct < 5 else 'FAIL'
    results.append(
        f'{status}: Hazen-Williams headloss '
        f'hand={hw_per_km:.2f} m/km, tool={tool_hl_per_km:.2f} m/km, '
        f'diff={diff_pct:.1f}%')

# =============================================
# CHECK 2: Bingham Plastic headloss
# Same pipe, tau_y=15, mu_p=0.05, rho=1800
# =============================================
from slurry_solver import bingham_plastic_headloss

rho = 1800
tau_y = 15.0
mu_p = 0.05
A = math.pi / 4 * D**2
V = Q / A

# Bingham Reynolds: Re_B = rho * V * D / mu_p
Re_B = rho * V * D / mu_p

# Hedstrom: He = rho * tau_y * D^2 / mu_p^2
He = rho * tau_y * D**2 / mu_p**2

# For laminar (Re_B < Re_critical):
# f_darcy = 64/Re_B * [1 + He/6/Re_B - 64/3 * He^4 / (Re_B * f^3)]
# Simplified Buckingham-Reiner:
# f ≈ 64/Re_B * (1 + He/(6*Re_B))  for He/Re_B < 1
f_approx = 64 / Re_B * (1 + He / (6 * Re_B))
hand_hl = f_approx * (L / D) * (V**2) / (2 * 9.81)
hand_hl_per_km = hand_hl / L * 1000

# Tool's Bingham answer
tool_r = bingham_plastic_headloss(
    flow_m3s=Q, diameter_m=D, length_m=L,
    density=rho, tau_y=tau_y, mu_p=mu_p, roughness_mm=0.1
)
tool_bingham_hl = tool_r['headloss_m'] / L * 1000

# Note: the simplified B-R may differ from full B-R by a few %
diff_pct = abs(tool_bingham_hl - hand_hl_per_km) / hand_hl_per_km * 100
status = 'PASS' if diff_pct < 15 else 'FAIL'  # wider tolerance for B-R approximation
results.append(
    f'{status}: Bingham headloss '
    f'hand(approx)={hand_hl_per_km:.2f} m/km, '
    f'tool={tool_bingham_hl:.2f} m/km, diff={diff_pct:.1f}% '
    f'(Re_B={Re_B:.0f}, He={He:.0f})')

# =============================================
# CHECK 3: Joukowsky pressure rise
# a=1100 m/s (AS 2280), V=2.0 m/s, rho=1000
# =============================================
a = 1100
V_jou = 2.0
rho_w = 1000

hand_dH = a * V_jou / 9.81  # head rise (m)
hand_dP = rho_w * a * V_jou / 1000  # pressure rise (kPa)

tool_j = api.joukowsky(wave_speed=a, velocity_change=V_jou, density=rho_w)

dH_diff = abs(tool_j['head_rise_m'] - hand_dH)
dP_diff = abs(tool_j['pressure_rise_kPa'] - hand_dP)

status = 'PASS' if dH_diff < 1 and dP_diff < 10 else 'FAIL'
results.append(
    f'{status}: Joukowsky — '
    f'hand: dH={hand_dH:.1f}m dP={hand_dP:.0f}kPa, '
    f'tool: dH={tool_j["head_rise_m"]}m dP={tool_j["pressure_rise_kPa"]}kPa')

# =============================================
# CHECK 4: Joukowsky with slurry density
# Same as above but rho=1800
# =============================================
rho_s = 1800
hand_dH_s = a * V_jou / 9.81  # head rise same (independent of density)
hand_dP_s = rho_s * a * V_jou / 1000  # pressure rise higher

tool_j_s = api.joukowsky(wave_speed=a, velocity_change=V_jou, density=rho_s)

dP_diff_s = abs(tool_j_s['pressure_rise_kPa'] - hand_dP_s)
dH_same = abs(tool_j_s['head_rise_m'] - hand_dH_s) < 0.5

status = 'PASS' if dP_diff_s < 10 and dH_same else 'FAIL'
results.append(
    f'{status}: Joukowsky (slurry rho=1800) — '
    f'hand: dP={hand_dP_s:.0f}kPa, tool: dP={tool_j_s["pressure_rise_kPa"]}kPa '
    f'(head same as water: {dH_same})')

# =============================================
# CHECK 5: Velocity from flow and diameter
# Q=20 LPS, DN200 → V = Q/A
# =============================================
Q_check = 0.020
D_check = 0.200
A_check = math.pi / 4 * D_check**2
V_hand = Q_check / A_check

V_tool = r['flows']['P1']['max_velocity_ms']
V_diff = abs(V_tool - V_hand)

status = 'PASS' if V_diff < 0.01 else 'FAIL'
results.append(
    f'{status}: Velocity — '
    f'hand={V_hand:.3f} m/s, tool={V_tool:.3f} m/s, diff={V_diff:.4f}')

# =============================================
# REPORT
# =============================================
print('\n=== HAND CALCULATION VERIFICATION ===')
for r in results:
    print(f'  {r}')
failures = [r for r in results if r.startswith('FAIL')]
print(f'\n{len(results)} checks: {len(results)-len(failures)} PASS, {len(failures)} FAIL')
```

Run this. ANY failure means the tool is producing incorrect 
physics — these are the most dangerous bugs.

---

## DIAGNOSTIC 8 — Menu and Keyboard Shortcut Completeness

**Problem this catches:** Menu items that crash, keyboard shortcuts 
that do nothing, or shortcuts that conflict.

```python
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)

from desktop.main_window import MainWindow
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

w = MainWindow()
w.show()
app.processEvents()

# Walk all menu items and try to trigger each one
def walk_menus(menubar):
    items = []
    for action in menubar.actions():
        menu = action.menu()
        if menu:
            for sub_action in menu.actions():
                if sub_action.isSeparator():
                    continue
                items.append((menu.title(), sub_action))
                # Check for submenus
                sub_menu = sub_action.menu()
                if sub_menu:
                    for sub_sub in sub_menu.actions():
                        if not sub_sub.isSeparator():
                            items.append(
                                (f'{menu.title()} > {sub_action.text()}',
                                 sub_sub))
    return items

menu_items = walk_menus(w.menuBar())
print(f'Found {len(menu_items)} menu items\n')

crashes = []
for menu_path, action in menu_items:
    label = action.text().replace('&', '')
    if not action.isEnabled():
        print(f'  DISABLED: {menu_path} > {label}')
        continue
    
    # Try triggering each menu item
    # (many will open dialogs — we just check they don't crash)
    try:
        action.trigger()
        app.processEvents()
        
        # Close any dialog that opened
        from PyQt6.QtWidgets import QDialog
        for widget in app.topLevelWidgets():
            if isinstance(widget, QDialog) and widget.isVisible():
                widget.reject()
                app.processEvents()
        
        print(f'  OK: {menu_path} > {label}')
    except Exception as e:
        crashes.append(f'{menu_path} > {label}: {e}')
        print(f'  CRASH: {menu_path} > {label}: {e}')

# Check keyboard shortcuts
shortcut_map = {}
for _, action in menu_items:
    shortcut = action.shortcut().toString()
    if shortcut:
        label = action.text().replace('&', '')
        if shortcut in shortcut_map:
            print(f'  CONFLICT: shortcut {shortcut} used by both '
                  f'"{shortcut_map[shortcut]}" and "{label}"')
        shortcut_map[shortcut] = label

print(f'\nRegistered shortcuts: {len(shortcut_map)}')
for key, label in sorted(shortcut_map.items()):
    print(f'  {key}: {label}')

if crashes:
    print(f'\n=== {len(crashes)} MENU CRASHES ===')
    for c in crashes:
        print(f'  {c}')
```

Run this. Every CRASH is a bug the user will hit.

---

## REPORTING AND FIXING

After running all 8 diagnostics, write:

### docs/DIAGNOSTIC_REPORT.md

Format:
```markdown
# Deep Diagnostic Report — {date}

## Summary
| Diagnostic | Findings | Critical | Fixed |
|---|---|---|---|
| 1. Wiring | N unwired classes | N | Y/N |
| 2. Display consistency | N mismatches | N | Y/N |
| ... | ... | ... | ... |

## Findings

### D1-001: [class name] not wired to UI
Severity: HIGH
File: desktop/xxx.py
Fix: [what was done]
Test: [test name that prevents regression]

### D2-001: [pipe headloss mismatch]
...
```

### For every finding rated HIGH or CRITICAL:
1. Fix the bug
2. Write a regression test that would have caught it
3. The test must fail WITHOUT the fix and pass WITH it
4. Add the test to tests/test_diagnostic_regression.py

### After all fixes:
Run full test suite:
```
python -m pytest tests/ -k "not transient" -q --tb=short
```
Test count must be HIGHER than before (new regression tests added).

Run the interactive driver:
```
python scripts/interactive_driver.py
```
All steps must still pass.

Commit: "Deep diagnostic: N bugs found, M fixed, K regression tests added"
Push to GitHub.

---

## EXIT CRITERIA

Stop when ALL of the following are true:
- All 8 diagnostics have been run
- Every CRITICAL finding is fixed
- Every HIGH finding is fixed or documented in blockers.md
- A regression test exists for every fix
- The interactive driver still passes 48+/48+ steps
- The full test suite passes
- docs/DIAGNOSTIC_REPORT.md is complete
- Everything is committed and pushed

Do NOT add features. Do NOT optimise. Do NOT refactor.
Only find bugs and fix them.

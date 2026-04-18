import os, ast, importlib, re, sys

print("=== DIAGNOSTIC 1: Wiring Verification ===")
desktop_modules = []
for f in os.listdir('desktop'):
    if f.endswith('.py') and f != '__init__.py':
        desktop_modules.append(f[:-3])

with open('desktop/main_window.py', encoding='utf-8') as fh:
    content = fh.read()
    tree = ast.parse(content)

imported_names = set()
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        if node.module and 'desktop' in (node.module or ''):
            for alias in node.names:
                imported_names.add(alias.name)
    elif isinstance(node, ast.Import):
        for alias in node.names:
            imported_names.add(alias.name)

for mod in desktop_modules:
    if mod == 'main_window':
        continue
    spec = importlib.util.find_spec(f'desktop.{mod}')
    if spec:
        try:
            module = importlib.import_module(f'desktop.{mod}')
        except Exception as e:
            print(f"Skipping desktop.{mod} due to import error: {e}")
            continue
        # Only flag classes DEFINED in this module (not re-imported Qt classes)
        classes = [
            name for name, obj in vars(module).items()
            if (isinstance(obj, type)
                and not name.startswith('_')
                and getattr(obj, '__module__', '').startswith('desktop.'))
        ]
        for cls in classes:
            if cls not in imported_names:
                print(f'UNWIRED: desktop/{mod}.py class {cls} — not imported in main_window.py')

actions = re.findall(r'self\.(\w+)\s*=\s*QAction\(', content)
connected = set(re.findall(r'self\.(\w+)\.triggered\.connect', content))
connected |= set(re.findall(r'self\.(\w+)\.toggled\.connect', content))
for action in actions:
    if action not in connected:
        print(f'DEAD MENU ITEM: {action} — created but never connected')

print("\n=== DIAGNOSTIC 4: Runtime Import Verification ===")
deferred_imports = []
for root, _, files in os.walk('.'):
    if any(skip in root for skip in ['__pycache__', '.git', 'test', 'tests', 'node_modules', 'dist', 'build']):
        continue
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(root, f)
        try:
            with open(path, encoding='utf-8') as fh:
                lines = fh.readlines()
        except:
            continue
        for i, line in enumerate(lines):
            stripped = line.strip()
            if (stripped.startswith('import ') or stripped.startswith('from ')) and line[0] == ' ':
                # Skip start of multi-line imports like `from mod import (`
                if stripped.endswith('('):
                    continue
                deferred_imports.append((path, i+1, stripped))

failures = []
for path, lineno, import_stmt in deferred_imports:
    try:
        if import_stmt.startswith('from '):
            match = re.match(r'from\s+(\S+)\s+import\s+(.+)', import_stmt)
            if match:
                module_name = match.group(1)
                # Strip inline comments (e.g. `_sanitize  # Latin-1 safe`)
                raw_names_str = match.group(2).split('#')[0].strip()
                # Skip if still a multi-line opener
                if raw_names_str == '(':
                    continue
                names = [n.strip().split(' as ')[0].strip('()') for n in raw_names_str.split(',')]
                try:
                    mod = importlib.import_module(module_name)
                except ImportError as e:
                    failures.append(f'{path}:{lineno} — {import_stmt}\n  ImportError: {e}')
                    continue
                for name in names:
                    name = name.strip()
                    if not name:
                        continue
                    if not hasattr(mod, name):
                        failures.append(f'{path}:{lineno} — {import_stmt}\n  Module {module_name} has no attribute "{name}"')
        elif import_stmt.startswith('import '):
            match = re.match(r'import\s+(\S+)', import_stmt)
            if match:
                importlib.import_module(match.group(1))
    except ImportError as e:
        failures.append(f'{path}:{lineno} — {import_stmt}\n  ImportError: {e}')
    except Exception as e:
        failures.append(f'{path}:{lineno} — {import_stmt}\n  Error: {e}')

if failures:
    for f in failures:
        print(f)
else:
    print('All deferred imports resolve correctly [OK]')

print("\n=== DIAGNOSTIC 5: Signal Chain Verification ===")
signal_connections = []
for root, _, files in os.walk('desktop'):
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(root, f)
        with open(path, encoding='utf-8') as fh:
            content = fh.read()
        pattern = r'(\w+(?:\.\w+)*)\.connect\((?:self\.)?(\w+)\)'
        matches = re.finditer(pattern, content)
        for m in matches:
            signal_path = m.group(1)
            handler = m.group(2)
            line = content[:m.start()].count('\n') + 1
            signal_connections.append((path, line, signal_path, handler))

for path, line, signal, handler in signal_connections:
    with open(path, encoding='utf-8') as fh:
        content = fh.read()
    method_pattern = rf'def\s+{re.escape(handler)}\s*\('
    if not re.search(method_pattern, content):
        known_qt = {'close', 'show', 'hide', 'update', 'repaint', 'accept', 'reject', 'raise_', 'setVisible', 'setText', 'clear', 'deleteLater'}
        if handler not in known_qt:
            print(f'MISSING HANDLER: {path}:{line} {signal}.connect({handler}) — method not found')

print("\n=== DIAGNOSTIC 7: Hand Calculations ===")
import math
from epanet_api import HydraulicAPI
results = []
D, C, Q, L = 0.200, 100, 0.020, 500
hw_headloss = 10.67 * L * Q**1.852 / (C**1.852 * D**4.87)
hw_per_km = hw_headloss / L * 1000

api = HydraulicAPI()
api.load_network_from_path('tutorials/mining_slurry_line/network.inp')
r = api.run_steady_state(save_plot=False)
pipe = api.wn.get_link('P1')
headloss_data = api.steady_results.link['headloss']
if 'P1' in headloss_data.columns:
    tool_hl = float(abs(headloss_data['P1']).max())  # WNTR returns gradient in m/m
    tool_hl_per_km = tool_hl * 1000  # m/m to m/km
    diff_pct = abs(tool_hl_per_km - hw_per_km) / hw_per_km * 100
    status = 'PASS' if diff_pct < 5 else 'FAIL'
    results.append(f'{status}: Hazen-Williams headloss hand={hw_per_km:.2f} m/km, tool={tool_hl_per_km:.2f} m/km, diff={diff_pct:.1f}%')

from slurry_solver import bingham_plastic_headloss
rho, tau_y, mu_p = 1800, 15.0, 0.05
A = math.pi / 4 * D**2
V = Q / A
Re_B = rho * V * D / mu_p
He = rho * tau_y * D**2 / mu_p**2
f_approx = 64 / Re_B * (1 + He / (6 * Re_B))
hand_hl = f_approx * (L / D) * (V**2) / (2 * 9.81)
hand_hl_per_km = hand_hl / L * 1000
tool_r = bingham_plastic_headloss(flow_m3s=Q, diameter_m=D, length_m=L, density=rho, tau_y=tau_y, mu_p=mu_p, roughness_mm=0.1)
tool_bingham_hl = tool_r['headloss_m'] / L * 1000
diff_pct = abs(tool_bingham_hl - hand_hl_per_km) / hand_hl_per_km * 100
status = 'PASS' if diff_pct < 15 else 'FAIL'
results.append(f'{status}: Bingham headloss hand(approx)={hand_hl_per_km:.2f} m/km, tool={tool_bingham_hl:.2f} m/km, diff={diff_pct:.1f}%')

a, V_jou, rho_w = 1100, 2.0, 1000
hand_dH = a * V_jou / 9.81
hand_dP = rho_w * a * V_jou / 1000
tool_j = api.joukowsky(wave_speed=a, velocity_change=V_jou, density=rho_w)
status = 'PASS' if abs(tool_j['head_rise_m'] - hand_dH) < 1 and abs(tool_j['pressure_rise_kPa'] - hand_dP) < 10 else 'FAIL'
results.append(f'{status}: Joukowsky water')

rho_s = 1800
hand_dH_s = a * V_jou / 9.81
hand_dP_s = rho_s * a * V_jou / 1000
tool_j_s = api.joukowsky(wave_speed=a, velocity_change=V_jou, density=rho_s)
status = 'PASS' if abs(tool_j_s['pressure_rise_kPa'] - hand_dP_s) < 10 and abs(tool_j_s['head_rise_m'] - hand_dH_s) < 0.5 else 'FAIL'
results.append(f'{status}: Joukowsky slurry')

V_tool = r['flows']['P1']['max_velocity_ms']
status = 'PASS' if abs(V_tool - V) < 0.01 else 'FAIL'
results.append(f'{status}: Velocity V={V:.3f}')

for r in results: print(r)

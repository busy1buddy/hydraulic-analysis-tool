import re

files_to_check = [
    "network_canvas.py", "canvas_editor.py", "calibration_dialog.py",
    "what_if_panel.py", "statistics_panel.py", "animation_panel.py",
    "report_dialog.py", "pipe_stress_panel.py", "compliance_dialog.py",
    "view_3d.py", "pipe_profile_dialog.py", "fire_flow_dialog.py",
    "pressure_zone_dialog.py", "rehab_dialog.py", "split_canvas.py",
    "surge_wizard.py", "water_quality_dialog.py", "colourmap_widget.py",
    "probe_tooltip.py", "dashboard_widget.py"
]

for fname in files_to_check:
    with open(fname, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        if 'except Exception' in line:
            # Get context: 5 lines before
            start = max(0, i - 5)
            context = ''.join(lines[start:i+1])
            line_num = i + 1
            print(f"\n{'='*60}")
            print(f"FILE: {fname} | LINE: {line_num}")
            print(f"{'='*60}")
            print(context)

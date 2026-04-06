# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Hydraulic Analysis Tool
=============================================
Bundles Python, PyQt6, WNTR, TSNet, and all domain modules into
a standalone Windows application.

Build:
    pyinstaller hydraulic_tool.spec --clean
"""

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# Collect all submodules for packages with dynamic imports
wntr_datas, wntr_binaries, wntr_hiddenimports = collect_all('wntr')
tsnet_datas, tsnet_binaries, tsnet_hiddenimports = collect_all('tsnet')

a = Analysis(
    ['main_app.py'],
    pathex=['.'],
    binaries=wntr_binaries + tsnet_binaries,
    datas=[
        ('data/au_pipes.py', 'data'),
        ('data/pump_curves.py', 'data'),
        ('data/__init__.py', 'data'),
        ('models/*.inp', 'models'),
        ('reports/*.py', 'reports'),
        ('slurry_solver.py', '.'),
        ('pipe_stress.py', '.'),
        ('epanet_api/*.py', 'epanet_api'),
        ('scenario_manager.py', '.'),
        ('desktop/*.py', 'desktop'),
        ('hydraulic_tool/*.py', 'hydraulic_tool'),
        ('tutorials/demo_network/network.inp', 'tutorials/demo_network'),
        ('tutorials/mining_slurry_line/network.inp', 'tutorials/mining_slurry_line'),
        ('tutorials/pump_station/network.inp', 'tutorials/pump_station'),
    ] + wntr_datas + tsnet_datas,
    hiddenimports=[
        'wntr', 'wntr.network', 'wntr.sim', 'wntr.epanet',
        'tsnet', 'tsnet.simulation', 'tsnet.network',
        'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui',
        'pyqtgraph', 'pyqtgraph.opengl',
        'numpy', 'scipy', 'pandas', 'matplotlib',
        'networkx', 'docx', 'fpdf',
        'epanet_api', 'epanet_api.core', 'epanet_api.analysis',
        'epanet_api.advanced', 'epanet_api.resilience',
        'epanet_api.comparison',
        'slurry_solver', 'pipe_stress',
        'data.au_pipes', 'data.pump_curves',
        'reports.docx_report', 'reports.pdf_report',
        'hydraulic_tool',
        'desktop.main_window', 'desktop.network_canvas',
        'desktop.analysis_worker', 'desktop.scenario_panel',
        'desktop.report_dialog', 'desktop.audit_trail',
        'desktop.pipe_stress_panel',
        'desktop.canvas_editor', 'desktop.colourmap_widget',
        'desktop.animation_panel', 'desktop.pattern_editor',
        'desktop.eps_dialog', 'desktop.fire_flow_dialog',
        'desktop.water_quality_dialog', 'desktop.probe_tooltip',
        'desktop.calibration_dialog', 'desktop.statistics_panel',
        'desktop.preferences', 'desktop.pressure_zone_dialog',
        'desktop.rehab_dialog', 'desktop.gis_basemap',
        'desktop.split_canvas', 'desktop.surge_wizard',
        'desktop.view_3d', 'desktop.report_scheduler',
        'desktop.pipe_profile_dialog', 'desktop.dashboard_widget',
        'desktop.report_templates', 'desktop.compliance_dialog',
        'desktop.welcome_dialog', 'desktop.pump_energy_dialog',
        'desktop.safety_case_dialog', 'desktop.slurry_params_dialog',
        'desktop.temp_audit', 'desktop.what_if_panel',
    ] + wntr_hiddenimports + tsnet_hiddenimports + collect_submodules('scipy'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'IPython', 'jupyter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HydraulicAnalysisTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window — GUI app
    icon=None,  # Add .ico file here if available
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HydraulicAnalysisTool',
)

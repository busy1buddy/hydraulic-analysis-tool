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
        ('epanet_api.py', '.'),
        ('scenario_manager.py', '.'),
        ('desktop/*.py', 'desktop'),
    ] + wntr_datas + tsnet_datas,
    hiddenimports=[
        'wntr', 'wntr.network', 'wntr.sim', 'wntr.epanet',
        'tsnet', 'tsnet.simulation', 'tsnet.network',
        'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui',
        'pyqtgraph', 'pyqtgraph.opengl',
        'numpy', 'scipy', 'pandas', 'matplotlib',
        'networkx', 'docx', 'fpdf',
        'epanet_api', 'slurry_solver', 'pipe_stress',
        'data.au_pipes', 'data.pump_curves',
        'reports.docx_report', 'reports.pdf_report',
        'desktop.main_window', 'desktop.network_canvas',
        'desktop.analysis_worker', 'desktop.scenario_panel',
        'desktop.report_dialog', 'desktop.audit_trail',
        'desktop.pipe_stress_panel',
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

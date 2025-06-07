# -*- mode: python ; coding: utf-8 -*-


import os
import sys


PYTHON_EXE = sys._base_executable
PYTHON_NAME = 'python.exe' if os.name == 'nt' else 'python'

a = Analysis(
    ['race_gui.py'],
    pathex=[],
    binaries=[(PYTHON_EXE, PYTHON_NAME)],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='race_gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

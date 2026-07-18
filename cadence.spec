# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files


qfluent_datas = collect_data_files("qfluentwidgets")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=qfluent_datas + [("resources", "resources")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Optional stacks discovered through pydicom/Fluent hooks are not used by
    # Cadence and would add tens of megabytes plus a long one-file startup.
    excludes=["cv2", "matplotlib", "pandas", "pyarrow", "pygame", "scipy", "tkinter"],
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
    name="Cadence",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["resources/cadence.ico"],
    version="resources/version_info.txt",
)

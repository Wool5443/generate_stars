# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_ROOT = Path(SPECPATH).resolve().parent
DEFAULT_CONFIG_DATA = [(str(PROJECT_ROOT / "generate_stars" / "default_config.toml"), "generate_stars")]


a = Analysis(
    [str(PROJECT_ROOT / "generate_stars_launcher.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=DEFAULT_CONFIG_DATA,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={
        "gi": {
            "module-versions": {
                "Gtk": "4.0",
                "Gdk": "4.0",
            },
            "icons": [
                "Adwaita",
            ],
            "themes": [
                "Adwaita",
            ],
        },
    },
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="generate-stars",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="generate-stars",
)

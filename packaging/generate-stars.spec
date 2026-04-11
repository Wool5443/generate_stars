# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_ROOT = Path(SPECPATH).resolve().parent
DEFAULT_CONFIG_DATA = [(str(PROJECT_ROOT / "generate_stars" / "default_config.toml"), "generate_stars")]
ICON_DATA = [
    (
        str(PROJECT_ROOT / "share" / "icons" / "hicolor" / "1024x1024" / "apps" / "com.twenty.generate-stars.png"),
        "share/icons/hicolor/1024x1024/apps",
    )
]
WINDOWS_ICON = str(PROJECT_ROOT / "packaging" / "generate-stars.ico")


a = Analysis(
    [str(PROJECT_ROOT / "generate_stars_launcher.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=DEFAULT_CONFIG_DATA + ICON_DATA,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={
        "gi": {
            "module-versions": {
                "Gtk": "4.0",
                "Gdk": "4.0",
            },
            "languages": [],
            "icons": [
                "Adwaita",
            ],
            "themes": [
                "Adwaita",
            ],
        },
    },
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pydoc",
        "distutils",
        "setuptools",
        "ensurepip",
        "idlelib",
        "turtle",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
    ],
    noarchive=False,
    optimize=2,
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
    strip=True,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=WINDOWS_ICON,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name="generate-stars",
)

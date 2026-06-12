# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Zoomies.

Produces a single one-dir bundle (dist/Zoomies/) with Zoomies.exe — the
instructor GUI only. The server is deployed separately on Ubuntu.

Build with:
    pyinstaller Zoomies.spec --noconfirm --clean
"""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = Path(SPECPATH)

# Read version so PyInstaller can stamp the Windows version resource.
_version_globals = {}
exec((PROJECT_ROOT / "version.py").read_text(encoding="utf-8"), _version_globals)
APP_VERSION = _version_globals["__version__"]

# Generate the VERSIONINFO resource file so Windows "Properties → Details"
# reports the right version on both exes.
sys.path.insert(0, str(PROJECT_ROOT / "installer"))
from version_info import write_version_file  # noqa: E402
VERSION_FILE = write_version_file(PROJECT_ROOT, PROJECT_ROOT / "build" / "file_version_info.txt")

# ---- Data files bundled inside the exe -----------------------------------
# The instructor app only needs version.py. Static files and media are
# served by the remote server; students connect directly to it.
datas = [
    (str(PROJECT_ROOT / "version.py"), "."),
]

# ---- Hidden imports ------------------------------------------------------
# The instructor app uses websockets (client) and httpx.
hiddenimports = []
hiddenimports += collect_submodules("websockets")


block_cipher = None

a = Analysis(
    ["entry.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "PyQt5",
        "PySide6",
        "PySide2",
        "pytest",
        "IPython",
        "jupyter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

_icon = PROJECT_ROOT / "installer" / "Zoomies_App_Icon.ico"
_icon_arg = str(_icon) if _icon.exists() else None

# Instructor GUI: windowless (no console window flashing on startup).
exe_gui = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Zoomies",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(VERSION_FILE),
    icon=_icon_arg,
)

coll = COLLECT(
    exe_gui,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Zoomies",
)

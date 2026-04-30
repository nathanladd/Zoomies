# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Rudi.

Produces a single one-dir bundle (dist/Rudi/) with Rudi.exe as the
entry point. The same executable dispatches to either the instructor GUI or
the FastAPI server based on argv (see entry.py).

Build with:
    pyinstaller Rudi.spec --noconfirm --clean
"""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

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
# Only ship what the server/instructor read at runtime. User-writable data
# (data/, media/, backups/) is created under %LOCALAPPDATA% on first run.
datas = [
    (str(PROJECT_ROOT / "static"), "static"),
    (str(PROJECT_ROOT / "version.py"), "."),
]

# ---- Hidden imports ------------------------------------------------------
# FastAPI / uvicorn / sqlalchemy pull in plenty of submodules dynamically.
hiddenimports = []
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("anyio")
hiddenimports += collect_submodules("sqlalchemy.dialects.sqlite")
hiddenimports += collect_submodules("aiosqlite")
hiddenimports += collect_submodules("websockets")
hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    "email.mime.text",
    "email.mime.multipart",
]


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

_icon = PROJECT_ROOT / "installer" / "rudi.ico"
_icon_arg = str(_icon) if _icon.exists() else None

# Instructor GUI: windowless (no console window flashing on startup).
exe_gui = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Rudi",
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

# Server role: must be a console subsystem exe so its stdout/stderr pipes are
# valid and the instructor's QProcess can stream them into the Server Console.
# Dispatch is by exe name (see entry.py _is_server_role).
exe_server = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Rudi-Server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
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
    exe_server,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Rudi",
)

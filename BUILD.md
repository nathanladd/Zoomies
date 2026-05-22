# Building the Rudi Instructor App

Rudi ships as a single `Rudi-Setup-<version>.exe` that installs the instructor
GUI on Windows. This document describes how to produce it from source.

The server runs separately on Ubuntu — see the server deployment docs for that.

## One-time prerequisites

1. **Python 3.13 virtual environment** with build deps:

   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements-build.txt
   ```

2. **Inno Setup 6** — download from <https://jrsoftware.org/isinfo.php> and
   install with the default options. The build script auto-locates
   `ISCC.exe` under `Program Files (x86)\Inno Setup 6\`.

3. *(Optional)* Place a `Rudi_App_Icon.ico` file under `installer\Rudi_App_Icon.ico`
   for a custom Start Menu / installer icon. The spec gracefully falls back to
   the default icon if the file is missing.

## Build

From the project root:

```powershell
.\build.ps1
```

The script:

1. Reads `__version__` from `version.py`.
2. Cleans `build\` and `dist\Rudi\`.
3. Runs `pyinstaller Rudi.spec --noconfirm --clean`, producing
   `dist\Rudi\Rudi.exe` plus its `_internal\` directory of Qt/Python DLLs.
4. Invokes `ISCC.exe /DAppVersion=<version> installer\Rudi.iss`,
   producing `dist\installer\Rudi-Setup-<version>.exe`.

Partial builds:

```powershell
.\build.ps1 -SkipInstaller     # only produce the PyInstaller bundle
.\build.ps1 -SkipPyInstaller   # only recompile the installer from existing bundle
```

## Runtime layout on the target machine

```
C:\Program Files\Rudi\              (installed by Setup, read-only)
├── Rudi.exe                        instructor GUI
└── _internal\                      PyInstaller-generated DLLs
```

All data (database, question images, backups) lives on the server. The
instructor app connects to it over HTTP/WebSocket and has no local data
directory of its own.

## Uninstall

The uninstaller removes the install directory, then asks whether to delete the
user-data tree at `%LOCALAPPDATA%\Rudi`. Choose **No** to preserve the
question database and images across reinstalls.

## Versioning workflow

1. Edit `version.py` — `__version__ = "0.3.0"`.
2. Commit.
3. Run `.\build.ps1`.
4. Upload `dist\installer\Rudi-Setup-0.3.0.exe` to a GitHub release.

All surfaces (instructor window title, `/api/version`, and the installer
filename + ARP entry) pick up the new version automatically.

`installer\version_info.py` generates the Windows `VERSIONINFO` resource at
build time so the **Properties → Details** tab on `Rudi.exe` reports the
correct version. It can also be run standalone for inspection:

```powershell
.venv\Scripts\python.exe installer\version_info.py
```

## Troubleshooting

- **"`ModuleNotFoundError: websockets…`"** — add the missing submodule to
  `hiddenimports` in `Rudi.spec`.
- **"Could not load the Qt platform plugin"** — clean `build\` and rebuild;
  the PyInstaller hooks for PyQt6 should handle this automatically.

# Building the Rudi Windows Installer

Rudi ships as a single `Rudi-Setup-<version>.exe`. This document
describes how to produce it from source.

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

3. *(Optional)* Place a `rudi.ico` file under `installer\rudi.ico`
   for a custom Start Menu / installer icon. The spec and `.iss` gracefully
   fall back to the default icon if the file is missing.

## Build

From the project root:

```powershell
.\build.ps1
```

The script:

1. Reads `__version__` from `version.py`.
2. Cleans `build\` and `dist\Rudi\`.
3. Runs `pyinstaller Rudi.spec --noconfirm --clean`, producing
   `dist\Rudi\Rudi.exe` plus its `_internal\` directory of Qt/
   Python DLLs and the bundled `static\` web UI.
4. Invokes `ISCC.exe /DAppVersion=<version> installer\Rudi.iss`,
   producing `dist\installer\Rudi-Setup-<version>.exe`.

Partial builds:

```powershell
.\build.ps1 -SkipInstaller     # only produce the PyInstaller bundle
.\build.ps1 -SkipPyInstaller   # only recompile the installer from existing bundle
```

## Runtime layout on the target machine

```
C:\Program Files\Rudi\                  (installed by Setup, read-only)
├── Rudi.exe                            GUI entry point (windowless)
├── Rudi-Server.exe                     server role (console subsystem)
├── _internal\                          PyInstaller-generated DLLs (shared)
└── _internal\static\                   bundled student web UI

%LOCALAPPDATA%\Rudi\                     (created on first launch)
├── data\rudi.db                        SQLite database
├── media\questions\                    uploaded question images
└── backups\                            backup zips
```

The split is enforced by `server/config.py`: when `sys.frozen` is true,
`USER_DATA_DIR` resolves to `%LOCALAPPDATA%\Rudi` and `BASE_DIR` resolves
to the PyInstaller `_MEIPASS` bundle where `static\` lives. On first launch
after the rename, an existing `%LOCALAPPDATA%\Zundpunkt` tree (and the legacy
`data\zundpunkt.db` file inside it) is renamed in place so upgrading users
keep their question bank, media, and backups.

## Dispatch

A single PyInstaller `Analysis` emits two executables that share the
`_internal\` dependency directory:

| Executable | Subsystem | Role |
|---|---|---|
| `Rudi.exe` | windowed (no console) | PyQt6 instructor app — spawns the server |
| `Rudi-Server.exe` | console | FastAPI / uvicorn server |

`entry.py` decides which role to run: if `--server` is passed **or** the exe
filename contains `server`, it runs the uvicorn server; otherwise it runs the
instructor GUI.

The console subsystem matters: `QProcess.MergedChannels` in the instructor can
only capture a child's stdout/stderr if the child exe is built with
`console=True`. That's why the server is a separate exe instead of a flag on
the GUI exe.

## Firewall

The installer offers (unchecked by default) a task to add a Windows Firewall
allow rule for inbound TCP 5000 so student laptops can reach the server:

```
netsh advfirewall firewall add rule name="Rudi" dir=in action=allow protocol=TCP localport=5000
```

The matching delete is run on uninstall.

## Uninstall

The uninstaller removes the install dir, then asks whether to delete the
user-data tree at `%LOCALAPPDATA%\Rudi`. Choose **No** to preserve the
question database and images across reinstalls.

## Versioning workflow

1. Edit `version.py` — `__version__ = "0.3.0"`.
2. Commit.
3. Run `.\build.ps1`.
4. Upload `dist\installer\Rudi-Setup-0.3.0.exe` to a GitHub release.

All surfaces (instructor window title, projection window title, student web
badges, FastAPI `/api/version`, and the installer filename + ARP entry) pick
up the new version automatically.

## Troubleshooting

- **"`ModuleNotFoundError: uvicorn.protocols.websockets.websockets_impl`"** —
  add the missing module to `hiddenimports` in `Rudi.spec`.
- **Server console blank in the frozen app** — `Rudi-Server.exe` must be
  built with `console=True` (see the `exe_server` block in `Rudi.spec`).
  A windowless child has no valid stdout file descriptor for `QProcess` to
  read.
- **"Could not load the Qt platform plugin"** — the PyInstaller hooks for
  PyQt6 should handle this; if it reappears, clean `build\` and rebuild.
- **Browser shows 404 for `/static/…`** — confirm `datas = [(…, "static")]`
  in the spec and re-run PyInstaller.

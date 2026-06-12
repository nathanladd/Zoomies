"""Entry point for the frozen Zoomies instructor executable.

In dev mode run_instructor.py is used directly; this file is only picked up
by the PyInstaller spec.
"""
from __future__ import annotations


def _migrate_user_data() -> None:
    """Rename %LOCALAPPDATA%\Rudi → %LOCALAPPDATA%\Zoomies on first run after rebrand."""
    import os
    import sys
    if not getattr(sys, "frozen", False):
        return
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return
    from pathlib import Path
    new_dir = Path(local) / "Zoomies"
    for old_dir in (Path(local) / "Rudi", Path(local) / "Zundpunkt"):
        if old_dir.exists() and not new_dir.exists():
            try:
                old_dir.rename(new_dir)
            except OSError:
                pass


def _run_instructor() -> None:
    _migrate_user_data()
    from instructor.main import main
    main()


if __name__ == "__main__":
    _run_instructor()

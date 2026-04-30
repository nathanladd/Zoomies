"""Unified entry point for the frozen Rudi executable.

The same Rudi.exe dispatches two roles based on argv:

    Rudi.exe            → launches the PyQt6 instructor app (which in
                           turn spawns the server as a child process)
    Rudi.exe --server   → runs the FastAPI/uvicorn server in-process

In dev mode run_instructor.py and run_server.py are used directly; this file
is only picked up by the PyInstaller spec.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _run_server() -> None:
    import uvicorn
    from server.config import SERVER_HOST, SERVER_PORT
    from server.main import app  # import directly so PyInstaller traces it

    uvicorn.run(
        app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,  # reload=True is unsupported inside a frozen exe
    )


def _run_instructor() -> None:
    from instructor.main import main
    main()


def _is_server_role() -> bool:
    # Explicit flag wins (useful for dev and manual runs).
    if "--server" in sys.argv[1:]:
        return True
    # Otherwise the exe name decides the role in a frozen build, so a single
    # spec can emit two EXEs (Rudi.exe + Rudi-Server.exe) that share
    # the same Analysis/PYZ.
    return "server" in Path(sys.executable).stem.lower()


if __name__ == "__main__":
    if _is_server_role():
        _run_server()
    else:
        _run_instructor()

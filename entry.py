"""Entry point for the frozen Rudi instructor executable.

In dev mode run_instructor.py is used directly; this file is only picked up
by the PyInstaller spec.
"""
from __future__ import annotations


def _run_instructor() -> None:
    from instructor.main import main
    main()


if __name__ == "__main__":
    _run_instructor()

"""Background QThread that checks the Rudi server for a newer instructor-app version.

Emits one of three signals:
  update_available(version, notes, download_url, sha256) — a newer version exists
  up_to_date()                                           — server version <= current
  check_failed(error_message)                            — network / parse error

Never raises to the caller; all errors go to check_failed.
"""
from __future__ import annotations

import httpx
from packaging.version import InvalidVersion, Version
from PyQt6.QtCore import QThread, pyqtSignal

from version import __version__


class UpdateChecker(QThread):
    update_available = pyqtSignal(str, str, str, str)  # version, notes, download_url, sha256
    up_to_date = pyqtSignal()
    check_failed = pyqtSignal(str)

    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url.rstrip("/")

    def run(self) -> None:
        try:
            resp = httpx.get(f"{self.base_url}/api/app/latest", timeout=8.0)
            if resp.status_code == 404:
                # No release published yet — not an error, just up to date.
                self.up_to_date.emit()
                return
            resp.raise_for_status()
            data = resp.json()
            latest_str: str = data.get("version", "")
            notes: str = data.get("notes", "")
            rel_url: str = data.get("download_url", "")
            sha256: str = data.get("sha256", "")
            # Resolve relative download paths against the server base URL.
            download_url = (
                rel_url if rel_url.startswith("http") else f"{self.base_url}{rel_url}"
            )
            try:
                if Version(latest_str) > Version(__version__):
                    self.update_available.emit(latest_str, notes, download_url, sha256)
                else:
                    self.up_to_date.emit()
            except InvalidVersion:
                self.check_failed.emit(f"Unexpected version string from server: {latest_str!r}")
        except Exception as exc:
            self.check_failed.emit(str(exc))

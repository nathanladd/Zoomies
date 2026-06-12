"""Background QThread that checks GitHub Releases for a newer instructor-app version.

Emits one of three signals:
  update_available(version, notes, download_url, sha256) — a newer version exists
  up_to_date()                                           — latest release <= current
  check_failed(error_message)                            — network / parse error

Never raises to the caller; all errors go to check_failed.
"""
from __future__ import annotations

import re

import httpx
from packaging.version import InvalidVersion, Version
from PyQt6.QtCore import QThread, pyqtSignal

from version import __version__

_RELEASES_URL = "https://api.github.com/repos/nathanladd/Zoomies/releases/latest"
_SHA256_RE = re.compile(r"sha256[:\s]+([0-9a-f]{64})", re.IGNORECASE)


class UpdateChecker(QThread):
    update_available = pyqtSignal(str, str, str, str)  # version, notes, download_url, sha256
    up_to_date = pyqtSignal()
    check_failed = pyqtSignal(str)

    def run(self) -> None:
        try:
            resp = httpx.get(
                _RELEASES_URL,
                headers={"Accept": "application/vnd.github+json"},
                timeout=8.0,
            )
            if resp.status_code == 404:
                self.up_to_date.emit()
                return
            resp.raise_for_status()
            data = resp.json()
            tag: str = data.get("tag_name", "").lstrip("v")
            notes: str = data.get("body", "") or ""
            sha256_match = _SHA256_RE.search(notes)
            sha256 = sha256_match.group(1) if sha256_match else ""
            assets = data.get("assets", [])
            exe_asset = next((a for a in assets if a.get("name", "").endswith(".exe")), None)
            download_url = exe_asset["browser_download_url"] if exe_asset else ""
            try:
                if Version(tag) > Version(__version__):
                    self.update_available.emit(tag, notes, download_url, sha256)
                else:
                    self.up_to_date.emit()
            except InvalidVersion:
                self.check_failed.emit(f"Unexpected version string from GitHub: {tag!r}")
        except Exception as exc:
            self.check_failed.emit(str(exc))

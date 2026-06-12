"""Persist and load server connection settings (host, port) as JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_DEFAULTS = {
    "server_host": "localhost",
    "server_port": 5000,
}


def _settings_path() -> Path:
    """Return the path to the connection settings JSON file."""
    if getattr(sys, "frozen", False):
        import os
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            return Path(local_app_data) / "Rudi" / "connection.json"
        return Path(sys.executable).parent / "connection.json"
    return Path(__file__).resolve().parent.parent / "connection.json"


def load() -> dict:
    """Load settings from disk, falling back to defaults."""
    path = _settings_path()
    settings = dict(_DEFAULTS)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data.get("server_host"), str):
                settings["server_host"] = data["server_host"]
            if isinstance(data.get("server_port"), int):
                settings["server_port"] = data["server_port"]
        except Exception:
            pass
    return settings


def save(server_host: str, server_port: int) -> None:
    """Write settings to disk."""
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"server_host": server_host, "server_port": server_port}, f, indent=2)

"""Persist and load server connection settings (host, port, credentials) as JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_DEFAULTS = {
    "server_host": "localhost",
    "server_port": 5000,
    "username": "instructor",
    "password": "rudi",
}


def _settings_path() -> Path:
    """Return the path to the connection settings JSON file."""
    if getattr(sys, "frozen", False):
        # Frozen build: store next to the executable
        return Path(sys.executable).parent / "connection.json"
    # Dev: store in the repo root (next to run_instructor.py)
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
            if isinstance(data.get("username"), str):
                settings["username"] = data["username"]
            if isinstance(data.get("password"), str):
                settings["password"] = data["password"]
        except Exception:
            pass
    return settings


def save(server_host: str, server_port: int, username: str | None = None, password: str | None = None) -> None:
    """Write settings to disk."""
    path = _settings_path()
    existing = load()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "server_host": server_host,
            "server_port": server_port,
            "username": username if username is not None else existing.get("username", _DEFAULTS["username"]),
            "password": password if password is not None else existing.get("password", _DEFAULTS["password"]),
        }, f, indent=2)

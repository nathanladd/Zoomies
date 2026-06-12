"""Persistent app-level settings for the instructor desktop app.

Stored separately from connection_settings.py (which holds server host/port).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DEFAULTS: dict = {
    "auto_check_updates": True,
    "skipped_version": None,
}


def _path() -> Path:
    if getattr(sys, "frozen", False):
        import os
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            return Path(local) / "Rudi" / "app_settings.json"
    return Path(__file__).resolve().parent.parent / "app_settings.json"


def load() -> dict:
    settings = dict(_DEFAULTS)
    path = _path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data.get("auto_check_updates"), bool):
                settings["auto_check_updates"] = data["auto_check_updates"]
            if "skipped_version" in data:
                settings["skipped_version"] = data["skipped_version"]
        except Exception:
            pass
    return settings


def save(**kwargs) -> None:
    current = load()
    current.update(kwargs)
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)

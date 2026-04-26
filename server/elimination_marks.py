"""Instructor-adjustable elimination marks.

Persists the two fractions of *elapsed* question time at which a wrong answer
is removed (multiple_choice / technician_ab). Marks are strictly ordered and
clamped into (0, 1) with a small minimum separation so they can't collide.
"""
from __future__ import annotations

import json
from threading import RLock

from server.config import DATA_DIR

_PATH = DATA_DIR / "elimination.json"
_lock = RLock()
_cache: tuple[float, ...] | None = None

DEFAULT_MARKS: tuple[float, ...] = (0.33, 0.66)
MIN_T = 0.02
MAX_T = 0.98
MIN_GAP = 0.02


def _normalize(marks: list[float] | tuple[float, ...]) -> tuple[float, ...]:
    pts = sorted(max(MIN_T, min(MAX_T, float(m))) for m in marks)
    if len(pts) != 2:
        return DEFAULT_MARKS
    if pts[1] - pts[0] < MIN_GAP:
        pts[1] = min(MAX_T, pts[0] + MIN_GAP)
        if pts[1] - pts[0] < MIN_GAP:
            pts[0] = max(MIN_T, pts[1] - MIN_GAP)
    return (pts[0], pts[1])


def load_marks() -> tuple[float, ...]:
    global _cache
    with _lock:
        if _cache is not None:
            return _cache
        try:
            raw = json.loads(_PATH.read_text())
            _cache = _normalize(raw["marks"])
        except Exception:
            _cache = DEFAULT_MARKS
        return _cache


def save_marks(marks: list[float] | tuple[float, ...]) -> tuple[float, ...]:
    global _cache
    with _lock:
        norm = _normalize(marks)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps({"marks": list(norm)}, indent=2))
        _cache = norm
        return norm

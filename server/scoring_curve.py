"""Instructor-adjustable scoring curve.

Persists a list of (t, points) control points to data/scoring.json where t is
the fraction of the question time *remaining* when the student answered
(1.0 = instant, 0.0 = buzzer). Points are linearly interpolated between
control points and clamped to [0, POINTS_MAX].

The file is cached in-process; save_curve() invalidates the cache so edits
from the Scoring Adjustment window apply to the next question without a
server restart.
"""
from __future__ import annotations

import json
import math
from threading import RLock

from server.config import DATA_DIR, POINTS_MAX, POINTS_MIN

_CURVE_PATH = DATA_DIR / "scoring.json"
_lock = RLock()
_cache: list[tuple[float, int]] | None = None


def _default_curve() -> list[tuple[float, int]]:
    """Match the original sqrt curve at 5 control points."""
    pts: list[tuple[float, int]] = []
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        pts.append((t, round(POINTS_MIN + (POINTS_MAX - POINTS_MIN) * math.sqrt(t))))
    return pts


def load_curve() -> list[tuple[float, int]]:
    global _cache
    with _lock:
        if _cache is not None:
            return _cache
        try:
            raw = json.loads(_CURVE_PATH.read_text())
            pts = [(float(p["t"]), int(p["points"])) for p in raw["points"]]
            pts = sorted(pts, key=lambda p: p[0])
            if len(pts) < 2 or pts[0][0] > 0 or pts[-1][0] < 1:
                raise ValueError("curve must span t=0..1 with >=2 points")
            _cache = pts
        except Exception:
            _cache = _default_curve()
        return _cache


def save_curve(points: list[tuple[float, int]]) -> list[tuple[float, int]]:
    global _cache
    with _lock:
        pts = sorted(
            [
                (
                    max(0.0, min(1.0, float(t))),
                    max(0, min(POINTS_MAX, int(p))),
                )
                for t, p in points
            ],
            key=lambda p: p[0],
        )
        if not pts:
            raise ValueError("curve requires at least one point")
        if pts[0][0] > 0:
            pts.insert(0, (0.0, pts[0][1]))
        if pts[-1][0] < 1:
            pts.append((1.0, pts[-1][1]))
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _CURVE_PATH.write_text(
            json.dumps(
                {"points": [{"t": t, "points": p} for t, p in pts]},
                indent=2,
            )
        )
        _cache = pts
        return pts


def interpolate(remaining_ratio: float) -> int:
    pts = load_curve()
    r = max(0.0, min(1.0, remaining_ratio))
    for i in range(1, len(pts)):
        t1, p1 = pts[i - 1]
        t2, p2 = pts[i]
        if r <= t2:
            if t2 == t1:
                return p2
            frac = (r - t1) / (t2 - t1)
            return round(p1 + (p2 - p1) * frac)
    return pts[-1][1]

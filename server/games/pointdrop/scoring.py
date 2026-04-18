import math

from server.config import POINTS_MAX, POINTS_MIN


def calculate_points(elapsed_ms: int, total_ms: int) -> int:
    """Calculate points using a square-root curve that keeps scores closer.

    points = min_points + (max_points - min_points) * sqrt(time_remaining / total)

    The curve stays high early (rewarding fast players modestly) and drops
    more steeply only near the end, so slower players don't fall too far behind.
    """
    if elapsed_ms <= 0:
        return POINTS_MAX
    if elapsed_ms >= total_ms:
        return POINTS_MIN

    remaining_ratio = 1 - (elapsed_ms / total_ms)
    return max(POINTS_MIN, round(POINTS_MIN + (POINTS_MAX - POINTS_MIN) * math.sqrt(remaining_ratio)))


def points_at_time(elapsed_ms: int, total_ms: int) -> int:
    """Return the current available points at a given elapsed time."""
    return calculate_points(elapsed_ms, total_ms)

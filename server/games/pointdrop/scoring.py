from server.config import POINTS_MAX, POINTS_MIN


def calculate_points(elapsed_ms: int, total_ms: int) -> int:
    """Calculate points using continuous decay formula.

    points = max_points - (elapsed_ms / total_ms) * (max_points - min_points)
    """
    if elapsed_ms <= 0:
        return POINTS_MAX
    if elapsed_ms >= total_ms:
        return POINTS_MIN

    decay = (elapsed_ms / total_ms) * (POINTS_MAX - POINTS_MIN)
    return max(POINTS_MIN, round(POINTS_MAX - decay))


def points_at_time(elapsed_ms: int, total_ms: int) -> int:
    """Return the current available points at a given elapsed time."""
    return calculate_points(elapsed_ms, total_ms)

from server.config import POINTS_MAX, POINTS_MIN
from server.scoring_curve import interpolate


def calculate_points(elapsed_ms: int, total_ms: int) -> int:
    """Calculate points by sampling the instructor-configured scoring curve.

    The curve maps *time remaining fraction* -> points. Defaults to the
    original sqrt curve when no custom curve is saved.
    """
    if total_ms <= 0 or elapsed_ms <= 0:
        return POINTS_MAX
    if elapsed_ms >= total_ms:
        return max(POINTS_MIN, interpolate(0.0))
    remaining_ratio = 1 - (elapsed_ms / total_ms)
    return max(POINTS_MIN, interpolate(remaining_ratio))


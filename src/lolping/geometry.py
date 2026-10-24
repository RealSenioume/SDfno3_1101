"""Pure geometry helpers for the ping wheel.

No Qt imports live here on purpose: this module is the unit-testable core of
the wheel's hit testing and easing maths.

Angle convention
----------------
Screen coordinates: x grows to the right, y grows **downwards**.
Angle 0 degrees points right (3 o'clock) and grows **clockwise**.
A wheel with ``count`` sectors puts sector ``i`` in the middle of
``[i*step - step/2, i*step + step/2)`` degrees, where ``step = 360 / count``.
With the default of 8 sectors: 0 = 3 o'clock, 2 = 6 o'clock, 4 = 9 o'clock,
6 = 12 o'clock.
"""

from __future__ import annotations

import math

__all__ = [
    "approach",
    "clamp",
    "distance",
    "ease_alpha",
    "sector_center_angle",
    "sector_index",
    "sector_label_point",
    "sector_span",
    "wrap_degrees",
]


def wrap_degrees(angle: float) -> float:
    """Wrap an angle in degrees into ``[0, 360)``."""
    return angle % 360.0


def distance(dx: float, dy: float) -> float:
    """Euclidean length of the vector ``(dx, dy)``."""
    return math.hypot(dx, dy)


def clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into ``[low, high]``."""
    if low > high:
        raise ValueError(f"low ({low}) must not exceed high ({high})")
    if value < low:
        return low
    if value > high:
        return high
    return value


def sector_index(dx: float, dy: float, dead_zone: float = 34.0, count: int = 8) -> int:
    """Return the hovered sector index, or ``-1`` inside the dead zone.

    ``(dx, dy)`` is the cursor offset from the wheel centre, in logical pixels.
    """
    if count < 1:
        raise ValueError(f"count must be >= 1, got {count}")
    if dead_zone < 0:
        raise ValueError(f"dead_zone must be >= 0, got {dead_zone}")

    if math.hypot(dx, dy) < dead_zone:
        return -1

    step = 360.0 / count
    angle = wrap_degrees(math.degrees(math.atan2(dy, dx)))
    # Rotate by half a sector so that sector boundaries sit on i*step +- step/2.
    return int(wrap_degrees(angle + step / 2.0) // step)


def sector_center_angle(index: int, count: int = 8) -> float:
    """Centre angle of ``index`` in degrees, clockwise from 3 o'clock."""
    if count < 1:
        raise ValueError(f"count must be >= 1, got {count}")
    if not 0 <= index < count:
        raise ValueError(f"index {index} out of range for {count} sectors")
    return wrap_degrees(index * (360.0 / count))


def sector_span(index: int, count: int = 8) -> tuple[float, float]:
    """``(start, end)`` of ``index`` in degrees, clockwise; ``end > start``."""
    centre = sector_center_angle(index, count)
    half = 180.0 / count
    return (centre - half, centre + half)


def sector_label_point(
    cx: float, cy: float, index: int, radius: float, count: int = 8
) -> tuple[float, float]:
    """Point on the circle of ``radius`` where sector ``index``'s label goes."""
    angle = math.radians(sector_center_angle(index, count))
    return (cx + radius * math.cos(angle), cy + radius * math.sin(angle))


def ease_alpha(dt: float, tau: float) -> float:
    """Frame-rate independent exponential smoothing factor for a step ``dt``."""
    if tau <= 0:
        return 1.0
    return 1.0 - math.exp(-max(dt, 0.0) / tau)


def approach(
    current: float, target: float, dt: float, tau: float, snap: float = 0.005
) -> float:
    """Exponentially move ``current`` towards ``target``; snap when close."""
    value = current + (target - current) * ease_alpha(dt, tau)
    if abs(value - target) < snap:
        return target
    return value

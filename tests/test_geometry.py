"""Tests for the pure wheel maths.

These lock down the angle convention: screen y grows downwards, angle 0 is
3 o'clock and grows clockwise, sector i is centred on i * 45 degrees.

Run with ``python -m unittest discover -s tests`` (stdlib only) or with pytest.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lolping.geometry import (  # noqa: E402 - after the path bootstrap
    approach,
    clamp,
    ease_alpha,
    sector_center_angle,
    sector_index,
    sector_label_point,
    sector_span,
    wrap_degrees,
)


class TestSectorIndex(unittest.TestCase):
    def test_dead_zone_returns_minus_one(self) -> None:
        self.assertEqual(sector_index(0.0, 0.0, dead_zone=34.0), -1)
        # 28.3 px away: still inside the dead zone.
        self.assertEqual(sector_index(20.0, 20.0, dead_zone=34.0), -1)

    def test_cardinal_directions(self) -> None:
        cases = {
            (100.0, 0.0): 0,  # 3 o'clock
            (100.0, 100.0): 1,  # 4:30
            (0.0, 100.0): 2,  # 6 o'clock
            (-100.0, 100.0): 3,
            (-100.0, 0.0): 4,  # 9 o'clock
            (-100.0, -100.0): 5,
            (0.0, -100.0): 6,  # 12 o'clock
            (100.0, -100.0): 7,
        }
        for (dx, dy), expected in cases.items():
            with self.subTest(dx=dx, dy=dy):
                self.assertEqual(sector_index(dx, dy), expected)

    def test_sector_boundaries_are_half_open(self) -> None:
        radius = 100.0
        just_below = math.radians(22.4)
        just_above = math.radians(22.6)
        self.assertEqual(
            sector_index(radius * math.cos(just_below), radius * math.sin(just_below)), 0
        )
        self.assertEqual(
            sector_index(radius * math.cos(just_above), radius * math.sin(just_above)), 1
        )

    def test_negative_angles_wrap(self) -> None:
        below = math.radians(-22.4)
        above = math.radians(-22.6)
        self.assertEqual(sector_index(100 * math.cos(below), 100 * math.sin(below)), 0)
        self.assertEqual(sector_index(100 * math.cos(above), 100 * math.sin(above)), 7)

    def test_custom_sector_count(self) -> None:
        self.assertEqual(sector_index(100.0, 0.0, count=4), 0)
        self.assertEqual(sector_index(0.0, 100.0, count=4), 1)
        self.assertEqual(sector_index(-100.0, 0.0, count=4), 2)
        self.assertEqual(sector_index(0.0, -100.0, count=4), 3)

    def test_invalid_arguments(self) -> None:
        with self.assertRaises(ValueError):
            sector_index(0.0, 0.0, count=0)
        with self.assertRaises(ValueError):
            sector_index(0.0, 0.0, dead_zone=-1)

    def test_index_matches_centre_angle(self) -> None:
        for angle in range(0, 360, 5):
            with self.subTest(angle=angle):
                radians = math.radians(angle)
                index = sector_index(
                    200.0 * math.cos(radians), 200.0 * math.sin(radians)
                )
                # Sector i owns [i*45 - 22.5, i*45 + 22.5), i.e. the cursor
                # angle is shifted by half a sector before flooring.
                self.assertEqual(index, int(((angle + 22.5) % 360) // 45))


class TestSectorGeometry(unittest.TestCase):
    def test_centres(self) -> None:
        self.assertEqual(sector_center_angle(0), 0.0)
        self.assertEqual(sector_center_angle(2), 90.0)
        self.assertEqual(sector_center_angle(4), 180.0)
        self.assertEqual(sector_center_angle(6), 270.0)

    def test_spans_are_contiguous(self) -> None:
        for index in range(8):
            with self.subTest(index=index):
                start, end = sector_span(index)
                self.assertAlmostEqual(end - start, 45.0)
                next_start, _ = sector_span((index + 1) % 8)
                self.assertAlmostEqual((next_start - end) % 360, 0.0)

    def test_span_of_sector_zero(self) -> None:
        self.assertEqual(sector_span(0), (-22.5, 22.5))

    def test_label_points_are_on_the_circle(self) -> None:
        for index in range(8):
            with self.subTest(index=index):
                x, y = sector_label_point(10.0, 20.0, index, radius=100.0)
                self.assertAlmostEqual(math.hypot(x - 10.0, y - 20.0), 100.0)

    def test_invalid_index(self) -> None:
        with self.assertRaises(ValueError):
            sector_center_angle(8)
        with self.assertRaises(ValueError):
            sector_center_angle(-1)


class TestEasing(unittest.TestCase):
    def test_wrap_degrees(self) -> None:
        self.assertAlmostEqual(wrap_degrees(-1.0), 359.0)
        self.assertAlmostEqual(wrap_degrees(360.0), 0.0)
        self.assertAlmostEqual(wrap_degrees(370.0), 10.0)

    def test_clamp(self) -> None:
        self.assertEqual(clamp(5, 0, 10), 5)
        self.assertEqual(clamp(-5, 0, 10), 0)
        self.assertEqual(clamp(15, 0, 10), 10)
        with self.assertRaises(ValueError):
            clamp(0, 10, 0)

    def test_ease_alpha_is_monotonic_and_bounded(self) -> None:
        self.assertEqual(ease_alpha(0.0, 0.035), 0.0)
        values = [ease_alpha(dt / 1000, 0.035) for dt in range(1, 200)]
        self.assertTrue(all(0.0 < value <= 1.0 for value in values))
        self.assertEqual(values, sorted(values))
        self.assertEqual(ease_alpha(1.0, 0.0), 1.0)  # tau <= 0 means instant

    def test_approach_converges_and_snaps(self) -> None:
        value = 0.0
        for _ in range(200):
            value = approach(value, 1.0, 0.016, 0.035)
        self.assertEqual(value, 1.0)
        # A value already within the snap distance jumps straight to the target.
        self.assertEqual(approach(0.996, 1.0, 0.001, 0.035, snap=0.005), 1.0)


if __name__ == "__main__":
    unittest.main()

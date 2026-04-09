from __future__ import annotations

import unittest

from generate_stars.models import Point
from generate_stars.ui.canvas import snap_coordinate_to_integer, snap_drag_center, snap_translation_delta, snap_world_point


class CanvasSnapTests(unittest.TestCase):
    def test_snap_coordinate_rounds_half_away_from_zero(self) -> None:
        self.assertEqual(snap_coordinate_to_integer(2.5, True), 3.0)
        self.assertEqual(snap_coordinate_to_integer(-2.5, True), -3.0)

    def test_snap_world_point_rounds_each_axis(self) -> None:
        snapped = snap_world_point(Point(2.49, -3.51), True)

        self.assertEqual(snapped.x, 2.0)
        self.assertEqual(snapped.y, -4.0)

    def test_snap_translation_delta_rounds_components(self) -> None:
        delta = snap_translation_delta(1.6, -0.2, True)

        self.assertEqual(delta.x, 2.0)
        self.assertEqual(delta.y, 0.0)

    def test_snap_drag_center_rounds_cluster_center(self) -> None:
        center = snap_drag_center(
            Point(8.4, 5.6),
            Point(2.2, -0.1),
            True,
        )

        self.assertEqual(center.x, 6.0)
        self.assertEqual(center.y, 6.0)


if __name__ == "__main__":
    unittest.main()

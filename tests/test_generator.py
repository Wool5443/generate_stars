from __future__ import annotations

import math
import random
import unittest

from generate_stars.generator import (
    allocate_cluster_counts,
    format_points_for_export,
    generate_ring_centers,
    generate_star_field,
    generate_trash_points,
)
from generate_stars.models import AppState, ClusterConfig, ClusterSize, DistributionMode, Point, ShapeKind
from generate_stars.shapes import get_shape


class GeneratorTests(unittest.TestCase):
    def test_equal_distribution_preserves_total(self) -> None:
        rng = random.Random(7)
        counts = allocate_cluster_counts(
            total=10,
            cluster_count=3,
            mode=DistributionMode.EQUAL,
            manual_counts=[],
            deviation_percent=0.0,
            rng=rng,
        )
        self.assertEqual(counts, [4, 3, 3])

    def test_deviation_distribution_preserves_total(self) -> None:
        rng = random.Random(11)
        counts = allocate_cluster_counts(
            total=25,
            cluster_count=4,
            mode=DistributionMode.DEVIATION,
            manual_counts=[],
            deviation_percent=35.0,
            rng=rng,
        )
        self.assertEqual(sum(counts), 25)
        self.assertEqual(len(counts), 4)

    def test_circle_sampling_stays_inside_radius(self) -> None:
        rng = random.Random(13)
        circle = get_shape(ShapeKind.CIRCLE)
        center = Point(10.0, -5.0)
        size = ClusterSize(radius=20.0)
        for _ in range(200):
            point = circle.sample_point(center, size, rng)
            self.assertLessEqual(math.hypot(point.x - center.x, point.y - center.y), size.radius + 1e-9)

    def test_rectangle_sampling_stays_inside_bounds(self) -> None:
        rng = random.Random(17)
        rectangle = get_shape(ShapeKind.RECTANGLE)
        center = Point(-15.0, 30.0)
        size = ClusterSize(width=60.0, height=40.0)
        for _ in range(200):
            point = rectangle.sample_point(center, size, rng)
            self.assertGreaterEqual(point.x, center.x - size.width / 2.0)
            self.assertLessEqual(point.x, center.x + size.width / 2.0)
            self.assertGreaterEqual(point.y, center.y - size.height / 2.0)
            self.assertLessEqual(point.y, center.y + size.height / 2.0)

    def test_trash_points_respect_edge_distance(self) -> None:
        rng = random.Random(19)
        cluster = ClusterConfig(center=Point(0.0, 0.0), size=ClusterSize(radius=50.0))
        points = generate_trash_points(
            cluster_configs=[cluster],
            shape_kind=ShapeKind.CIRCLE,
            count=50,
            min_edge_distance=15.0,
            rng=rng,
        )
        circle = get_shape(ShapeKind.CIRCLE)
        self.assertEqual(len(points), 50)
        for point in points:
            self.assertGreaterEqual(circle.edge_distance(point, cluster.center, cluster.size), 15.0)

    def test_export_format_uses_commas(self) -> None:
        payload = format_points_for_export([Point(1.25, -3.5), Point(0.0, 2.125)], precision=3)
        self.assertEqual(payload.splitlines()[0], "X Y")
        self.assertEqual(payload.splitlines()[1], "1,250 -3,500")
        self.assertEqual(payload.splitlines()[2], "0,000 2,125")

    def test_generate_ring_centers_moves_smaller_clusters_closer_to_origin(self) -> None:
        centers = generate_ring_centers(
            ShapeKind.CIRCLE,
            [
                ClusterSize(radius=20.0),
                ClusterSize(radius=60.0),
                ClusterSize(radius=40.0),
            ],
        )
        distances = [math.hypot(center.x, center.y) for center in centers]
        self.assertLess(distances[0], distances[2])
        self.assertLess(distances[2], distances[1])

    def test_generate_star_field_combines_cluster_and_trash_counts(self) -> None:
        rng = random.Random(23)
        state = AppState(
            shape_kind=ShapeKind.CIRCLE,
            cluster_count=2,
            total_cluster_stars=12,
            distribution_mode=DistributionMode.EQUAL,
            trash_star_count=3,
            trash_min_distance=10.0,
        )
        state.cluster_centers = [Point(-80.0, 0.0), Point(80.0, 0.0)]
        state.manual_counts = [6, 6]
        generated = generate_star_field(state, rng=rng)
        self.assertEqual(sum(generated.cluster_counts), 12)
        self.assertEqual(len(generated.points), 15)


if __name__ == "__main__":
    unittest.main()

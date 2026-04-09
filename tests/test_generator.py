from __future__ import annotations

import math
import random
import unittest

from generate_stars.generator import (
    allocate_cluster_counts,
    format_points_for_export,
    preview_cluster_counts,
    generate_ring_centers,
    generate_star_field,
    generate_trash_points,
    validate_state,
)
from generate_stars.models import (
    AppState,
    ClusterConfig,
    ClusterInstance,
    ClusterSize,
    DistributionMode,
    Point,
    ShapeKind,
    StarParameterConfig,
    StarRecord,
)
from generate_stars.shapes import get_shape


def make_cluster(
    cluster_id: int,
    shape_kind: ShapeKind,
    center: Point,
    *,
    radius: float = 10.0,
    width: float = 10.0,
    height: float = 10.0,
    manual_star_count: int = 0,
) -> ClusterInstance:
    return ClusterInstance(
        cluster_id=cluster_id,
        shape_kind=shape_kind,
        center=center,
        size=ClusterSize(radius=radius, width=width, height=height),
        manual_star_count=manual_star_count,
    )


class GeneratorTests(unittest.TestCase):
    def test_cluster_size_defaults_are_ten(self) -> None:
        size = ClusterSize()
        self.assertEqual(size.radius, 10.0)
        self.assertEqual(size.width, 10.0)
        self.assertEqual(size.height, 10.0)

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

    def test_preview_cluster_counts_for_manual_mode(self) -> None:
        state = AppState(
            distribution_mode=DistributionMode.MANUAL,
            total_cluster_stars=21,
            clusters=[
                make_cluster(1, ShapeKind.CIRCLE, Point(0.0, 0.0), manual_star_count=5),
                make_cluster(2, ShapeKind.RECTANGLE, Point(20.0, 0.0), manual_star_count=7),
                make_cluster(3, ShapeKind.CIRCLE, Point(40.0, 0.0), manual_star_count=9),
            ],
        )
        self.assertEqual(preview_cluster_counts(state), [5, 7, 9])

    def test_preview_cluster_counts_for_deviation_mode_is_none(self) -> None:
        state = AppState(
            distribution_mode=DistributionMode.DEVIATION,
            total_cluster_stars=21,
            clusters=[
                make_cluster(1, ShapeKind.CIRCLE, Point(0.0, 0.0)),
                make_cluster(2, ShapeKind.RECTANGLE, Point(20.0, 0.0)),
                make_cluster(3, ShapeKind.CIRCLE, Point(40.0, 0.0)),
            ],
        )
        self.assertIsNone(preview_cluster_counts(state))

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
        cluster = ClusterConfig(
            shape_kind=ShapeKind.CIRCLE,
            center=Point(0.0, 0.0),
            size=ClusterSize(radius=50.0),
        )
        points = generate_trash_points(
            cluster_configs=[cluster],
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

    def test_export_format_includes_third_parameter(self) -> None:
        payload = format_points_for_export(
            [
                StarRecord(1.25, -3.5, 0.5),
                StarRecord(0.0, 2.125, -1.75),
            ],
            parameter_name="Mass",
            precision=3,
        )
        self.assertEqual(payload.splitlines()[0], "X Y Mass")
        self.assertEqual(payload.splitlines()[1], "1,250 -3,500 0,500")
        self.assertEqual(payload.splitlines()[2], "0,000 2,125 -1,750")

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

    def test_generate_ring_centers_changes_radius_for_equal_shared_sizes(self) -> None:
        small_centers = generate_ring_centers(
            ShapeKind.CIRCLE,
            [ClusterSize(radius=20.0) for _ in range(3)],
        )
        large_centers = generate_ring_centers(
            ShapeKind.CIRCLE,
            [ClusterSize(radius=60.0) for _ in range(3)],
        )
        small_distance = math.hypot(small_centers[0].x, small_centers[0].y)
        large_distance = math.hypot(large_centers[0].x, large_centers[0].y)
        self.assertLess(small_distance, large_distance)

    def test_generate_ring_centers_keeps_minimum_origin_clearance_of_five(self) -> None:
        centers = generate_ring_centers(
            ShapeKind.CIRCLE,
            [ClusterSize(radius=10.0)],
        )
        distance = math.hypot(centers[0].x, centers[0].y)
        self.assertEqual(distance - 10.0, 5.0)

    def test_validate_state_rejects_blank_star_parameter_name(self) -> None:
        state = AppState(
            star_parameter=StarParameterConfig(
                enabled=True,
                name="   ",
                min_value=0.0,
                max_value=1.0,
            )
        )
        self.assertIn("Star parameter name cannot be empty.", validate_state(state))

    def test_validate_state_rejects_invalid_star_parameter_range(self) -> None:
        state = AppState(
            star_parameter=StarParameterConfig(
                enabled=True,
                name="Mass",
                min_value=2.0,
                max_value=1.0,
            )
        )
        self.assertIn("Star parameter max must be greater than or equal to min.", validate_state(state))

    def test_validate_state_requires_cluster_for_cluster_stars(self) -> None:
        state = AppState(total_cluster_stars=5)
        self.assertIn("Cluster stars require at least one cluster.", validate_state(state))

    def test_generate_star_field_combines_cluster_and_trash_counts_for_mixed_shapes(self) -> None:
        rng = random.Random(23)
        state = AppState(
            total_cluster_stars=12,
            distribution_mode=DistributionMode.EQUAL,
            trash_star_count=3,
            trash_min_distance=10.0,
            clusters=[
                make_cluster(1, ShapeKind.CIRCLE, Point(-80.0, 0.0), radius=20.0),
                make_cluster(2, ShapeKind.RECTANGLE, Point(80.0, 0.0), width=30.0, height=18.0),
            ],
        )
        generated = generate_star_field(state, rng=rng)
        self.assertEqual(sum(generated.cluster_counts), 12)
        self.assertEqual(len(generated.stars), 15)

    def test_generate_star_field_adds_parameter_to_every_star(self) -> None:
        rng = random.Random(29)
        state = AppState(
            total_cluster_stars=12,
            distribution_mode=DistributionMode.EQUAL,
            trash_star_count=3,
            trash_min_distance=10.0,
            star_parameter=StarParameterConfig(
                enabled=True,
                name="Mass",
                min_value=-1.5,
                max_value=2.5,
            ),
            clusters=[
                make_cluster(1, ShapeKind.CIRCLE, Point(-80.0, 0.0), radius=20.0),
                make_cluster(2, ShapeKind.RECTANGLE, Point(80.0, 0.0), width=30.0, height=18.0),
            ],
        )
        generated = generate_star_field(state, rng=rng)
        self.assertEqual(len(generated.stars), 15)
        for star in generated.stars:
            self.assertIsNotNone(star.parameter_value)
            assert star.parameter_value is not None
            self.assertGreaterEqual(star.parameter_value, -1.5)
            self.assertLessEqual(star.parameter_value, 2.5)


if __name__ == "__main__":
    unittest.main()

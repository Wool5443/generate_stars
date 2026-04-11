from __future__ import annotations

import math
import random
import unittest
from unittest.mock import patch

from generate_stars.generator import (
    allocate_cluster_counts,
    format_points_for_export,
    preview_cluster_counts,
    preview_parameter_function_result,
    generate_ring_centers,
    generate_star_field,
    generate_trash_points,
    validate_state,
)
from generate_stars.models import (
    AppState,
    CircleSize,
    ClusterConfig,
    ClusterInstance,
    DistributionMode,
    FunctionSize,
    FunctionStarParameterValue,
    FunctionOrientation,
    Point,
    PolygonSize,
    RandomStarParameterValue,
    RectangleSize,
    ShapeKind,
    StarParameterMode,
    StarParameterConfig,
    StarRecord,
)
from generate_stars.shapes import function_size_from_parameters, get_shape


def make_cluster(
    cluster_id: int,
    shape_kind: ShapeKind,
    center: Point,
    *,
    radius: float = 10.0,
    width: float = 10.0,
    height: float = 10.0,
    vertices_local: list[Point] | None = None,
    function_expression: str = "0",
    function_orientation: FunctionOrientation = FunctionOrientation.Y_OF_X,
    function_range_start: float = -10.0,
    function_range_end: float = 10.0,
    function_thickness: float = 4.0,
    manual_star_count: int = 0,
) -> ClusterInstance:
    if shape_kind is ShapeKind.FUNCTION:
        size = function_size_from_parameters(
            function_expression,
            function_orientation,
            function_range_start,
            function_range_end,
            function_thickness,
        )
    elif shape_kind is ShapeKind.CIRCLE:
        size = CircleSize(radius=radius)
    elif shape_kind is ShapeKind.RECTANGLE:
        size = RectangleSize(width=width, height=height)
    else:
        size = PolygonSize(
            vertices_local=[Point(vertex.x, vertex.y) for vertex in vertices_local or []],
        )
    return ClusterInstance(
        cluster_id=cluster_id,
        center=center,
        size=size,
        manual_star_count=manual_star_count,
    )


class GeneratorTests(unittest.TestCase):
    def test_cluster_size_defaults_are_ten(self) -> None:
        circle = CircleSize()
        rectangle = RectangleSize()
        self.assertEqual(circle.radius, 10.0)
        self.assertEqual(rectangle.width, 10.0)
        self.assertEqual(rectangle.height, 10.0)

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

    def test_preview_parameter_function_result_returns_value(self) -> None:
        preview, is_error = preview_parameter_function_result('return "alpha"')
        self.assertFalse(is_error)
        self.assertEqual(preview, "alpha")

    def test_preview_parameter_function_result_reports_invalid_body(self) -> None:
        preview, is_error = preview_parameter_function_result("return (")
        self.assertTrue(is_error)
        self.assertIn("invalid", preview.lower())

    def test_preview_parameter_function_result_reports_runtime_error(self) -> None:
        preview, is_error = preview_parameter_function_result('raise RuntimeError("boom")')
        self.assertTrue(is_error)
        self.assertIn("failed during generation", preview)

    def test_preview_parameter_function_result_reports_return_type_error(self) -> None:
        preview, is_error = preview_parameter_function_result("return 123")
        self.assertTrue(is_error)
        self.assertIn("must return string", preview)

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
        size = CircleSize(radius=20.0)
        for _ in range(200):
            point = circle.sample_point(center, size, rng)
            self.assertLessEqual(math.hypot(point.x - center.x, point.y - center.y), size.radius + 1e-9)

    def test_rectangle_sampling_stays_inside_bounds(self) -> None:
        rng = random.Random(17)
        rectangle = get_shape(ShapeKind.RECTANGLE)
        center = Point(-15.0, 30.0)
        size = RectangleSize(width=60.0, height=40.0)
        for _ in range(200):
            point = rectangle.sample_point(center, size, rng)
            self.assertGreaterEqual(point.x, center.x - size.width / 2.0)
            self.assertLessEqual(point.x, center.x + size.width / 2.0)
            self.assertGreaterEqual(point.y, center.y - size.height / 2.0)
            self.assertLessEqual(point.y, center.y + size.height / 2.0)

    def test_polygon_sampling_stays_inside_shape(self) -> None:
        rng = random.Random(18)
        polygon = get_shape(ShapeKind.POLYGON)
        center = Point(25.0, -30.0)
        size = PolygonSize(
            vertices_local=[
                Point(-20.0, -10.0),
                Point(10.0, -18.0),
                Point(25.0, -2.0),
                Point(15.0, 16.0),
                Point(-12.0, 20.0),
            ]
        )
        for _ in range(200):
            point = polygon.sample_point(center, size, rng)
            self.assertLessEqual(polygon.edge_distance(point, center, size), 1e-9)

    def test_function_sampling_stays_inside_shape(self) -> None:
        rng = random.Random(21)
        function_shape = get_shape(ShapeKind.FUNCTION)
        center = Point(-12.0, 8.0)
        size = function_size_from_parameters(
            "0.2 * x^2",
            FunctionOrientation.Y_OF_X,
            -6.0,
            6.0,
            2.5,
        )
        for _ in range(200):
            point = function_shape.sample_point(center, size, rng)
            self.assertLessEqual(function_shape.edge_distance(point, center, size), 1e-9)

    def test_function_sampling_uses_cached_vertices(self) -> None:
        rng = random.Random(22)
        function_shape = get_shape(ShapeKind.FUNCTION)
        center = Point(0.0, 0.0)
        size = function_size_from_parameters(
            "0.5 * x",
            FunctionOrientation.Y_OF_X,
            -10.0,
            10.0,
            3.0,
        )

        with patch("generate_stars.shapes.build_function_band_local_vertices", side_effect=AssertionError("rebuild")):
            point = function_shape.sample_point(center, size, rng)
            bounds = function_shape.bounding_box(center, size)

        self.assertLessEqual(function_shape.edge_distance(point, center, size), 1e-9)
        self.assertLess(bounds.min_x, bounds.max_x)
        self.assertLess(bounds.min_y, bounds.max_y)

    def test_trash_points_respect_edge_distance(self) -> None:
        rng = random.Random(19)
        cluster = ClusterConfig(
            center=Point(0.0, 0.0),
            size=CircleSize(radius=50.0),
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

    def test_trash_points_respect_polygon_edge_distance(self) -> None:
        rng = random.Random(20)
        cluster = ClusterConfig(
            center=Point(10.0, 5.0),
            size=PolygonSize(
                vertices_local=[
                    Point(-20.0, -10.0),
                    Point(5.0, -15.0),
                    Point(25.0, 10.0),
                    Point(-5.0, 18.0),
                ]
            ),
        )
        polygon = get_shape(ShapeKind.POLYGON)
        points = generate_trash_points(
            cluster_configs=[cluster],
            count=40,
            min_edge_distance=12.0,
            rng=rng,
        )
        self.assertEqual(len(points), 40)
        for point in points:
            self.assertGreaterEqual(polygon.edge_distance(point, cluster.center, cluster.size), 12.0)

    def test_trash_points_respect_function_edge_distance(self) -> None:
        rng = random.Random(22)
        cluster = ClusterConfig(
            center=Point(0.0, 0.0),
            size=function_size_from_parameters(
                "0.5 * x",
                FunctionOrientation.Y_OF_X,
                -10.0,
                10.0,
                3.0,
            ),
        )
        function_shape = get_shape(ShapeKind.FUNCTION)
        points = generate_trash_points(
            cluster_configs=[cluster],
            count=40,
            min_edge_distance=6.0,
            rng=rng,
        )
        self.assertEqual(len(points), 40)
        for point in points:
            self.assertGreaterEqual(function_shape.edge_distance(point, cluster.center, cluster.size), 6.0)

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
                CircleSize(radius=20.0),
                CircleSize(radius=60.0),
                CircleSize(radius=40.0),
            ],
        )
        distances = [math.hypot(center.x, center.y) for center in centers]
        self.assertLess(distances[0], distances[2])
        self.assertLess(distances[2], distances[1])

    def test_generate_ring_centers_changes_radius_for_equal_shared_sizes(self) -> None:
        small_centers = generate_ring_centers(
            ShapeKind.CIRCLE,
            [CircleSize(radius=20.0) for _ in range(3)],
        )
        large_centers = generate_ring_centers(
            ShapeKind.CIRCLE,
            [CircleSize(radius=60.0) for _ in range(3)],
        )
        small_distance = math.hypot(small_centers[0].x, small_centers[0].y)
        large_distance = math.hypot(large_centers[0].x, large_centers[0].y)
        self.assertLess(small_distance, large_distance)

    def test_generate_ring_centers_keeps_minimum_origin_clearance_of_five(self) -> None:
        centers = generate_ring_centers(
            ShapeKind.CIRCLE,
            [CircleSize(radius=10.0)],
        )
        distance = math.hypot(centers[0].x, centers[0].y)
        self.assertEqual(distance - 10.0, 5.0)

    def test_validate_state_rejects_blank_star_parameter_name(self) -> None:
        state = AppState(
            star_parameter=StarParameterConfig(
                enabled=True,
                name="   ",
                value=RandomStarParameterValue(min_value=0.0, max_value=1.0),
            )
        )
        self.assertIn("Star parameter name cannot be empty.", validate_state(state))

    def test_validate_state_rejects_invalid_star_parameter_range(self) -> None:
        state = AppState(
            star_parameter=StarParameterConfig(
                enabled=True,
                name="Mass",
                value=RandomStarParameterValue(min_value=2.0, max_value=1.0),
            )
        )
        self.assertIn("Star parameter max must be greater than or equal to min.", validate_state(state))

    def test_validate_state_rejects_invalid_parameter_function_body(self) -> None:
        state = AppState(
            star_parameter=StarParameterConfig(
                enabled=True,
                name="Tag",
                value=FunctionStarParameterValue(function_body="return ("),
            )
        )
        self.assertIn("Parameter function is invalid.", validate_state(state))

    def test_validate_state_rejects_self_intersecting_polygon(self) -> None:
        state = AppState(
            total_cluster_stars=10,
            clusters=[
                make_cluster(
                    1,
                    ShapeKind.POLYGON,
                    Point(0.0, 0.0),
                    vertices_local=[
                        Point(-10.0, -10.0),
                        Point(10.0, 10.0),
                        Point(-10.0, 10.0),
                        Point(10.0, -10.0),
                    ],
                )
            ],
        )
        self.assertTrue(
            any("Polygon must be simple and non-self-intersecting." in error for error in validate_state(state))
        )

    def test_validate_state_rejects_invalid_function_range(self) -> None:
        state = AppState(
            total_cluster_stars=5,
            clusters=[
                ClusterInstance(
                    cluster_id=1,
                    center=Point(0.0, 0.0),
                    size=FunctionSize(
                        function_expression="x",
                        function_orientation=FunctionOrientation.Y_OF_X,
                        function_range_start=5.0,
                        function_range_end=-5.0,
                        function_thickness=2.0,
                    ),
                )
            ],
        )
        self.assertTrue(
            any("Function range end must be greater than range start." in error for error in validate_state(state))
        )

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
                make_cluster(
                    3,
                    ShapeKind.POLYGON,
                    Point(0.0, 60.0),
                    vertices_local=[
                        Point(-18.0, -12.0),
                        Point(12.0, -16.0),
                        Point(20.0, 8.0),
                        Point(-10.0, 18.0),
                    ],
                ),
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
                value=RandomStarParameterValue(min_value=-1.5, max_value=2.5),
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

    def test_generate_star_field_function_mode_adds_string_parameter(self) -> None:
        rng = random.Random(31)
        state = AppState(
            total_cluster_stars=6,
            distribution_mode=DistributionMode.EQUAL,
            trash_star_count=1,
            trash_min_distance=5.0,
            star_parameter=StarParameterConfig(
                enabled=True,
                name="Tag",
                value=FunctionStarParameterValue(function_body='return "fixed_tag"'),
            ),
            clusters=[make_cluster(1, ShapeKind.CIRCLE, Point(0.0, 0.0), radius=20.0)],
        )
        generated = generate_star_field(state, rng=rng)
        self.assertEqual(len(generated.stars), 7)
        for star in generated.stars:
            self.assertEqual(star.parameter_value, "fixed_tag")

    def test_generate_star_field_function_mode_can_import_stdlib(self) -> None:
        rng = random.Random(37)
        state = AppState(
            total_cluster_stars=3,
            distribution_mode=DistributionMode.EQUAL,
            trash_star_count=0,
            star_parameter=StarParameterConfig(
                enabled=True,
                name="Tag",
                value=FunctionStarParameterValue(function_body='import random\nreturn str(random.randint(1, 9))'),
            ),
            clusters=[make_cluster(1, ShapeKind.CIRCLE, Point(0.0, 0.0), radius=10.0)],
        )
        generated = generate_star_field(state, rng=rng)
        for star in generated.stars:
            value = star.parameter_value
            self.assertIsInstance(value, str)
            self.assertTrue(value.isdigit())

    def test_generate_star_field_function_mode_requires_string_return(self) -> None:
        rng = random.Random(41)
        state = AppState(
            total_cluster_stars=2,
            distribution_mode=DistributionMode.EQUAL,
            trash_star_count=0,
            star_parameter=StarParameterConfig(
                enabled=True,
                name="Tag",
                value=FunctionStarParameterValue(function_body="return 123"),
            ),
            clusters=[make_cluster(1, ShapeKind.CIRCLE, Point(0.0, 0.0), radius=10.0)],
        )
        with self.assertRaisesRegex(RuntimeError, "must return string"):
            generate_star_field(state, rng=rng)

    def test_generate_star_field_function_mode_rejects_whitespace_tokens(self) -> None:
        rng = random.Random(43)
        state = AppState(
            total_cluster_stars=2,
            distribution_mode=DistributionMode.EQUAL,
            trash_star_count=0,
            star_parameter=StarParameterConfig(
                enabled=True,
                name="Tag",
                value=FunctionStarParameterValue(function_body='return "bad token"'),
            ),
            clusters=[make_cluster(1, ShapeKind.CIRCLE, Point(0.0, 0.0), radius=10.0)],
        )
        with self.assertRaisesRegex(RuntimeError, "without whitespace"):
            generate_star_field(state, rng=rng)

    def test_generate_star_field_function_mode_propagates_runtime_error(self) -> None:
        rng = random.Random(47)
        state = AppState(
            total_cluster_stars=2,
            distribution_mode=DistributionMode.EQUAL,
            trash_star_count=0,
            star_parameter=StarParameterConfig(
                enabled=True,
                name="Tag",
                value=FunctionStarParameterValue(function_body='raise RuntimeError("boom")'),
            ),
            clusters=[make_cluster(1, ShapeKind.CIRCLE, Point(0.0, 0.0), radius=10.0)],
        )
        with self.assertRaisesRegex(RuntimeError, "failed during generation"):
            generate_star_field(state, rng=rng)

    def test_export_format_includes_string_parameter(self) -> None:
        payload = format_points_for_export(
            [
                StarRecord(1.25, -3.5, "alpha"),
                StarRecord(0.0, 2.125, "beta"),
            ],
            parameter_name="Tag",
            precision=3,
        )
        self.assertEqual(payload.splitlines()[0], "X Y Tag")
        self.assertEqual(payload.splitlines()[1], "1,250 -3,500 alpha")
        self.assertEqual(payload.splitlines()[2], "0,000 2,125 beta")


if __name__ == "__main__":
    unittest.main()

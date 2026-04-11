from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from generate_stars.config import initialize_app_config
from generate_stars.controllers.editor_controller import EditorController
from generate_stars.models import AppState, ClusterInstance, ClusterSize, DistributionMode, FunctionOrientation, Point, ShapeKind, StarParameterMode
from generate_stars.shapes import function_size_from_parameters


def make_cluster(
    cluster_id: int,
    shape_kind: ShapeKind,
    center: Point,
    *,
    radius: float = 10.0,
    width: float = 10.0,
    height: float = 10.0,
    polygon_scale: float = 100.0,
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
    else:
        size = ClusterSize(
            radius=radius,
            width=width,
            height=height,
            polygon_scale=polygon_scale,
            vertices_local=[Point(vertex.x, vertex.y) for vertex in vertices_local or []],
        )
    return ClusterInstance(
        cluster_id=cluster_id,
        shape_kind=shape_kind,
        center=center,
        size=size,
        manual_star_count=manual_star_count,
    )


class EditorControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        config, _issues = initialize_app_config(create_missing=False)
        self.controller = EditorController(config)

    def test_window_view_model_hides_shape_selector_without_selection(self) -> None:
        view_model = self.controller.build_window_view_model()

        self.assertFalse(view_model.cluster_panel.selection.show_shape_selector)
        self.assertEqual(view_model.cluster_panel.selection.info_text, "No cluster selected.")
        self.assertEqual(view_model.status.text, "")
        self.assertEqual(view_model.status.kind, "neutral")
        self.assertFalse(view_model.toolbar.snap_to_integer_grid)
        self.assertEqual(
            view_model.toolbar.active_tool_description,
            self.controller.config.text.select_tool_description,
        )
        self.assertEqual(view_model.parameter_panel.mode, StarParameterMode.RANDOM)
        self.assertTrue(view_model.parameter_panel.show_random_range)
        self.assertFalse(view_model.parameter_panel.show_function_body)
        self.assertFalse(view_model.parameter_panel.show_function_preview)

    def test_parameter_mode_switches_view_model_fields(self) -> None:
        self.controller.set_parameter_enabled(True)
        self.controller.set_parameter_mode(StarParameterMode.FUNCTION)
        self.controller.set_parameter_function_body('return "token"', object())
        view_model = self.controller.build_window_view_model()

        self.assertEqual(view_model.parameter_panel.mode, StarParameterMode.FUNCTION)
        self.assertFalse(view_model.parameter_panel.show_random_range)
        self.assertTrue(view_model.parameter_panel.show_function_body)
        self.assertEqual(view_model.parameter_panel.function_body, 'return "token"')
        self.assertTrue(view_model.parameter_panel.show_function_preview)
        self.assertFalse(view_model.parameter_panel.function_preview_is_error)
        self.assertEqual(view_model.parameter_panel.function_preview_text, "token")

    def test_parameter_preview_shows_error_for_invalid_function(self) -> None:
        self.controller.set_parameter_enabled(True)
        self.controller.set_parameter_mode(StarParameterMode.FUNCTION)
        self.controller.set_parameter_function_body("return (", object())

        view_model = self.controller.build_window_view_model()

        self.assertTrue(view_model.parameter_panel.show_function_preview)
        self.assertTrue(view_model.parameter_panel.function_preview_is_error)
        self.assertIn("invalid", view_model.parameter_panel.function_preview_text.lower())

    def test_cluster_required_validation_stays_silent_when_no_clusters(self) -> None:
        self.controller.state.total_cluster_stars = 50

        view_model = self.controller.build_window_view_model()

        self.assertFalse(view_model.generate_enabled)
        self.assertEqual(view_model.status.text, "")
        self.assertEqual(view_model.status.kind, "neutral")

    def test_non_idle_validation_error_is_visible(self) -> None:
        self.controller.state.clusters = [
            make_cluster(1, ShapeKind.CIRCLE, Point(0.0, 0.0), radius=0.0),
        ]
        self.controller.state.total_cluster_stars = 25

        view_model = self.controller.build_window_view_model()

        self.assertFalse(view_model.generate_enabled)
        self.assertEqual(view_model.status.kind, "error")
        self.assertIn("radius", view_model.status.text.lower())

    def test_delete_selected_clusters_syncs_manual_total(self) -> None:
        self.controller.state = AppState(
            distribution_mode=DistributionMode.MANUAL,
            clusters=[
                make_cluster(1, ShapeKind.CIRCLE, Point(0.0, 0.0), manual_star_count=4),
                make_cluster(2, ShapeKind.RECTANGLE, Point(20.0, 0.0), manual_star_count=6),
            ],
            selected_cluster_ids=[2],
            total_cluster_stars=10,
        )

        self.controller.delete_selected_clusters()

        self.assertEqual(len(self.controller.state.clusters), 1)
        self.assertEqual(self.controller.state.total_cluster_stars, 4)

    def test_polygon_scale_updates_selected_polygon_geometry(self) -> None:
        self.controller.state.clusters = [
            make_cluster(
                1,
                ShapeKind.POLYGON,
                Point(0.0, 0.0),
                polygon_scale=100.0,
                vertices_local=[
                    Point(-5.0, -5.0),
                    Point(5.0, -5.0),
                    Point(5.0, 5.0),
                    Point(-5.0, 5.0),
                ],
            )
        ]
        self.controller.state.selected_cluster_ids = [1]

        source = object()
        self.controller.set_selection_polygon_scale(150.0, source)

        cluster = self.controller.state.clusters[0]
        self.assertEqual(cluster.size.polygon_scale, 150.0)
        self.assertEqual(cluster.size.vertices_local[0].x, -7.5)
        self.assertEqual(cluster.size.vertices_local[2].y, 7.5)

    def test_snap_toggle_updates_toolbar_without_creating_history(self) -> None:
        self.controller.set_snap_to_integer_grid(True)

        view_model = self.controller.build_window_view_model()
        self.assertTrue(view_model.toolbar.snap_to_integer_grid)
        self.assertFalse(self.controller.can_undo)

    def test_translate_selected_from_origins_preserves_relative_positions(self) -> None:
        self.controller.state.clusters = [
            make_cluster(1, ShapeKind.CIRCLE, Point(1.0, 2.0)),
            make_cluster(2, ShapeKind.RECTANGLE, Point(4.0, 6.0)),
        ]
        self.controller.state.selected_cluster_ids = [1, 2]

        self.controller.translate_selected_from_origins(
            {
                1: Point(1.0, 2.0),
                2: Point(4.0, 6.0),
            },
            3.0,
            -2.0,
        )

        self.assertEqual(self.controller.state.clusters[0].center.x, 4.0)
        self.assertEqual(self.controller.state.clusters[0].center.y, 0.0)
        self.assertEqual(self.controller.state.clusters[1].center.x, 7.0)
        self.assertEqual(self.controller.state.clusters[1].center.y, 4.0)

    def test_copy_then_paste_preserves_cluster_data_and_is_undoable(self) -> None:
        self.controller.state = AppState(
            distribution_mode=DistributionMode.MANUAL,
            clusters=[
                make_cluster(
                    1,
                    ShapeKind.POLYGON,
                    Point(10.5, 20.5),
                    polygon_scale=125.0,
                    vertices_local=[
                        Point(-3.0, -2.0),
                        Point(4.0, -1.0),
                        Point(1.0, 5.0),
                    ],
                    manual_star_count=7,
                )
            ],
            selected_cluster_ids=[1],
            next_cluster_id=2,
            total_cluster_stars=7,
        )

        copied_count = self.controller.copy_selected_clusters()

        self.assertEqual(copied_count, 1)
        self.assertFalse(self.controller.can_undo)

        pasted_count = self.controller.paste_copied_clusters()

        self.assertEqual(pasted_count, 1)
        self.assertEqual(len(self.controller.state.clusters), 2)
        pasted_cluster = self.controller.state.clusters[1]
        self.assertEqual(pasted_cluster.cluster_id, 2)
        self.assertEqual(pasted_cluster.shape_kind, ShapeKind.POLYGON)
        self.assertEqual(pasted_cluster.center.x, 11.5)
        self.assertEqual(pasted_cluster.center.y, 19.5)
        self.assertEqual(pasted_cluster.size.polygon_scale, 125.0)
        self.assertEqual(len(pasted_cluster.size.vertices_local), 3)
        self.assertEqual(pasted_cluster.manual_star_count, 7)
        self.assertEqual(self.controller.state.selected_cluster_ids, [2])
        self.assertEqual(self.controller.state.total_cluster_stars, 14)
        self.assertTrue(self.controller.can_undo)

        self.assertTrue(self.controller.undo())
        self.assertEqual(len(self.controller.state.clusters), 1)
        self.assertEqual(self.controller.state.selected_cluster_ids, [1])
        self.assertEqual(self.controller.state.total_cluster_stars, 7)

    def test_repeated_paste_chains_from_copied_payload(self) -> None:
        self.controller.state.clusters = [
            make_cluster(1, ShapeKind.CIRCLE, Point(0.0, 0.0), radius=10.0),
        ]
        self.controller.state.selected_cluster_ids = [1]
        self.controller.state.next_cluster_id = 2

        self.controller.copy_selected_clusters()
        self.controller.paste_copied_clusters()
        self.controller.paste_copied_clusters()

        self.assertEqual(len(self.controller.state.clusters), 3)
        self.assertEqual(self.controller.state.clusters[1].center.x, 2.0)
        self.assertEqual(self.controller.state.clusters[1].center.y, -2.0)
        self.assertEqual(self.controller.state.clusters[2].center.x, 4.0)
        self.assertEqual(self.controller.state.clusters[2].center.y, -4.0)
        self.assertEqual(self.controller.state.selected_cluster_ids, [3])

    def test_copy_without_selection_and_paste_without_clipboard_are_noops(self) -> None:
        copied_count = self.controller.copy_selected_clusters()
        pasted_count = self.controller.paste_copied_clusters()

        self.assertEqual(copied_count, 0)
        self.assertEqual(pasted_count, 0)
        self.assertEqual(self.controller.state.clusters, [])

    def test_function_selection_hides_shape_selector_and_exposes_function_editor(self) -> None:
        self.controller.state.clusters = [
            make_cluster(
                1,
                ShapeKind.FUNCTION,
                Point(5.0, -3.0),
                function_expression="0.25 * x",
                function_orientation=FunctionOrientation.Y_OF_X,
                function_range_start=-4.0,
                function_range_end=6.0,
                function_thickness=3.5,
            )
        ]
        self.controller.state.selected_cluster_ids = [1]

        view_model = self.controller.build_window_view_model()

        self.assertFalse(view_model.cluster_panel.selection.show_shape_selector)
        self.assertTrue(view_model.cluster_panel.selection.function_editor.visible)
        self.assertTrue(view_model.cluster_panel.selection.function_editor.show_expression)
        self.assertEqual(view_model.cluster_panel.selection.function_editor.expression, "0.25 * x")
        self.assertEqual(view_model.cluster_panel.selection.function_editor.orientation_id, "y_of_x")
        self.assertEqual(view_model.toolbar.active_tool_description, self.controller.config.text.select_tool_description)

    def test_export_cluster_configuration_to_path_writes_scene_payload(self) -> None:
        self.controller.state = AppState(
            distribution_mode=DistributionMode.MANUAL,
            clusters=[
                make_cluster(
                    1,
                    ShapeKind.POLYGON,
                    Point(10.5, 20.5),
                    polygon_scale=125.0,
                    vertices_local=[
                        Point(-3.0, -2.0),
                        Point(4.0, -1.0),
                        Point(1.0, 5.0),
                    ],
                    manual_star_count=7,
                ),
                make_cluster(
                    2,
                    ShapeKind.FUNCTION,
                    Point(-4.0, 3.0),
                    function_expression="0.5 * x",
                    function_orientation=FunctionOrientation.Y_OF_X,
                    function_range_start=-2.0,
                    function_range_end=6.0,
                    function_thickness=2.5,
                    manual_star_count=11,
                ),
            ],
            selected_cluster_ids=[2],
            next_cluster_id=3,
            total_cluster_stars=18,
            deviation_percent=12.5,
            trash_star_count=9,
            trash_min_distance=4.5,
        )
        self.controller.state.star_parameter.enabled = True
        self.controller.state.star_parameter.name = "Mass"
        self.controller.state.star_parameter.min_value = -1.5
        self.controller.state.star_parameter.max_value = 3.5

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "cluster_config.json"

            self.controller.export_cluster_configuration_to_path(output_path)

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["format"], "generate_stars_cluster_configuration")
            self.assertEqual(payload["version"], 2)
            self.assertEqual(sorted(payload.keys()), ["clusters", "format", "version"])
            self.assertEqual(payload["clusters"][0]["shape_kind"], "polygon")
            self.assertEqual(payload["clusters"][0]["manual_star_count"], 7)
            self.assertEqual(payload["clusters"][0]["size"]["polygon_scale"], 125.0)
            self.assertEqual(payload["clusters"][1]["shape_kind"], "function")
            self.assertEqual(payload["clusters"][1]["size"]["function_expression"], "0.5 * x")
            self.assertEqual(payload["clusters"][1]["size"]["function_orientation"], "y_of_x")
            self.assertEqual(self.controller.last_config_save_path, output_path)
            self.assertNotIn("distribution_mode", payload)
            self.assertNotIn("selected_cluster_ids", payload)
            self.assertNotIn("total_cluster_stars", payload)
            self.assertNotIn("star_parameter", payload)

    def test_import_cluster_configuration_replaces_clusters_and_preserves_global_settings(self) -> None:
        self.controller.state = AppState(
            distribution_mode=DistributionMode.DEVIATION,
            clusters=[
                make_cluster(10, ShapeKind.CIRCLE, Point(100.0, 200.0), radius=9.0),
            ],
            selected_cluster_ids=[10],
            next_cluster_id=11,
            total_cluster_stars=77,
            deviation_percent=33.0,
            trash_star_count=12,
            trash_min_distance=5.5,
        )
        self.controller.state.star_parameter.enabled = True
        self.controller.state.star_parameter.name = "Mass"
        self.controller.state.placement_circle_size.radius = 42.0

        payload = {
            "format": "generate_stars_cluster_configuration",
            "version": 2,
            "clusters": [
                {
                    "shape_kind": "circle",
                    "center": {"x": 1.5, "y": -2.5},
                    "size": {
                        "radius": 8.0,
                        "width": 16.0,
                        "height": 16.0,
                        "polygon_scale": 100.0,
                        "vertices_local": [],
                        "function_expression": "0",
                        "function_orientation": "y_of_x",
                        "function_range_start": -10.0,
                        "function_range_end": 10.0,
                        "function_thickness": 0.1,
                    },
                    "manual_star_count": 4,
                },
                {
                    "shape_kind": "rectangle",
                    "center": {"x": -3.0, "y": 4.0},
                    "size": {
                        "radius": 6.0,
                        "width": 12.0,
                        "height": 5.0,
                        "polygon_scale": 100.0,
                        "vertices_local": [],
                        "function_expression": "0",
                        "function_orientation": "y_of_x",
                        "function_range_start": -10.0,
                        "function_range_end": 10.0,
                        "function_thickness": 0.1,
                    },
                    "manual_star_count": 9,
                },
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "cluster_config.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")

            loaded_count = self.controller.import_cluster_configuration_from_path(input_path)

            self.assertEqual(loaded_count, 2)
            self.assertEqual(len(self.controller.state.clusters), 2)
            self.assertEqual(self.controller.state.clusters[0].cluster_id, 1)
            self.assertEqual(self.controller.state.clusters[1].cluster_id, 2)
            self.assertEqual(self.controller.state.clusters[0].center.x, 1.5)
            self.assertEqual(self.controller.state.clusters[1].size.width, 12.0)
            self.assertEqual(self.controller.state.selected_cluster_ids, [])
            self.assertEqual(self.controller.state.next_cluster_id, 3)
            self.assertEqual(self.controller.state.distribution_mode, DistributionMode.DEVIATION)
            self.assertEqual(self.controller.state.total_cluster_stars, 77)
            self.assertEqual(self.controller.state.deviation_percent, 33.0)
            self.assertTrue(self.controller.state.star_parameter.enabled)
            self.assertEqual(self.controller.state.star_parameter.name, "Mass")
            self.assertEqual(self.controller.state.trash_star_count, 12)
            self.assertEqual(self.controller.state.trash_min_distance, 5.5)
            self.assertEqual(self.controller.state.placement_circle_size.radius, 42.0)
            self.assertEqual(self.controller.last_config_save_path, input_path)
            self.assertTrue(self.controller.can_undo)

            self.assertTrue(self.controller.undo())
            self.assertEqual(len(self.controller.state.clusters), 1)
            self.assertEqual(self.controller.state.clusters[0].cluster_id, 10)

    def test_import_cluster_configuration_syncs_total_in_manual_mode(self) -> None:
        self.controller.state = AppState(
            distribution_mode=DistributionMode.MANUAL,
            clusters=[make_cluster(1, ShapeKind.CIRCLE, Point(0.0, 0.0), manual_star_count=99)],
            total_cluster_stars=99,
        )
        payload = {
            "format": "generate_stars_cluster_configuration",
            "version": 2,
            "clusters": [
                {
                    "shape_kind": "circle",
                    "center": {"x": 0.0, "y": 0.0},
                    "size": {
                        "radius": 3.0,
                        "width": 6.0,
                        "height": 6.0,
                        "polygon_scale": 100.0,
                        "vertices_local": [],
                        "function_expression": "0",
                        "function_orientation": "y_of_x",
                        "function_range_start": -10.0,
                        "function_range_end": 10.0,
                        "function_thickness": 0.1,
                    },
                    "manual_star_count": 4,
                },
                {
                    "shape_kind": "circle",
                    "center": {"x": 5.0, "y": 5.0},
                    "size": {
                        "radius": 2.0,
                        "width": 4.0,
                        "height": 4.0,
                        "polygon_scale": 100.0,
                        "vertices_local": [],
                        "function_expression": "0",
                        "function_orientation": "y_of_x",
                        "function_range_start": -10.0,
                        "function_range_end": 10.0,
                        "function_thickness": 0.1,
                    },
                    "manual_star_count": 6,
                },
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "cluster_config.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")

            self.controller.import_cluster_configuration_from_path(input_path)

            self.assertEqual(self.controller.state.total_cluster_stars, 10)

    def test_import_cluster_configuration_accepts_legacy_broad_payload(self) -> None:
        payload = {
            "format": "generate_stars_cluster_configuration",
            "version": 1,
            "placement_circle_size": {"radius": 999.0},
            "selected_cluster_ids": [99],
            "total_cluster_stars": 123,
            "clusters": [
                {
                    "cluster_id": 9,
                    "shape_kind": "polygon",
                    "center": {"x": 2.0, "y": 3.0},
                    "size": {
                        "radius": 5.0,
                        "width": 10.0,
                        "height": 12.0,
                        "polygon_scale": 150.0,
                        "vertices_local": [
                            {"x": -1.0, "y": -1.0},
                            {"x": 2.0, "y": -1.0},
                            {"x": 0.0, "y": 3.0},
                        ],
                        "function_expression": "0",
                        "function_orientation": "y_of_x",
                        "function_range_start": -10.0,
                        "function_range_end": 10.0,
                        "function_thickness": 0.1,
                    },
                    "manual_star_count": 8,
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "legacy_cluster_config.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")

            self.controller.import_cluster_configuration_from_path(input_path)

            self.assertEqual(len(self.controller.state.clusters), 1)
            self.assertEqual(self.controller.state.clusters[0].cluster_id, 1)
            self.assertEqual(self.controller.state.clusters[0].shape_kind, ShapeKind.POLYGON)
            self.assertEqual(self.controller.state.clusters[0].manual_star_count, 8)
            self.assertEqual(self.controller.state.selected_cluster_ids, [])
            self.assertEqual(self.controller.state.next_cluster_id, 2)

    def test_import_cluster_configuration_failure_does_not_mutate_state(self) -> None:
        self.controller.state = AppState(
            distribution_mode=DistributionMode.EQUAL,
            clusters=[make_cluster(1, ShapeKind.CIRCLE, Point(7.0, 8.0), radius=3.0)],
            selected_cluster_ids=[1],
            next_cluster_id=2,
            total_cluster_stars=25,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "invalid_cluster_config.json"
            input_path.write_text('{"format":"generate_stars_cluster_configuration","version":2,"clusters":"bad"}', encoding="utf-8")

            with self.assertRaises(RuntimeError):
                self.controller.import_cluster_configuration_from_path(input_path)

            self.assertEqual(len(self.controller.state.clusters), 1)
            self.assertEqual(self.controller.state.clusters[0].center.x, 7.0)
            self.assertEqual(self.controller.state.selected_cluster_ids, [1])
            self.assertEqual(self.controller.state.next_cluster_id, 2)
            self.assertEqual(self.controller.state.total_cluster_stars, 25)
            self.assertFalse(self.controller.can_undo)


if __name__ == "__main__":
    unittest.main()

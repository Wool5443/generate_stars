from __future__ import annotations

import unittest

from generate_stars.config import initialize_app_config
from generate_stars.controllers.editor_controller import EditorController
from generate_stars.models import AppState, ClusterInstance, ClusterSize, DistributionMode, Point, ShapeKind


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
    manual_star_count: int = 0,
) -> ClusterInstance:
    return ClusterInstance(
        cluster_id=cluster_id,
        shape_kind=shape_kind,
        center=center,
        size=ClusterSize(
            radius=radius,
            width=width,
            height=height,
            polygon_scale=polygon_scale,
            vertices_local=[Point(vertex.x, vertex.y) for vertex in vertices_local or []],
        ),
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
        self.assertEqual(
            view_model.toolbar.active_tool_description,
            self.controller.config.text.select_tool_description,
        )

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


if __name__ == "__main__":
    unittest.main()

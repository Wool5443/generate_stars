from __future__ import annotations

import unittest

from generate_stars.history import HistoryManager
from generate_stars.models import (
    AppState,
    ClusterInstance,
    ClusterSize,
    DistributionMode,
    Point,
    ShapeKind,
    StarParameterConfig,
)


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


class HistoryTests(unittest.TestCase):
    def test_editable_snapshot_round_trip_restores_editable_state(self) -> None:
        state = AppState(
            clusters=[
                make_cluster(1, ShapeKind.CIRCLE, Point(0.0, 0.0), radius=12.0, manual_star_count=5),
                make_cluster(
                    2,
                    ShapeKind.POLYGON,
                    Point(25.0, 10.0),
                    width=14.0,
                    height=20.0,
                    polygon_scale=135.0,
                    vertices_local=[
                        Point(-7.0, -10.0),
                        Point(9.0, -8.0),
                        Point(6.0, 10.0),
                        Point(-8.0, 7.0),
                    ],
                    manual_star_count=7,
                ),
            ],
            selected_cluster_ids=[2],
            next_cluster_id=3,
            total_cluster_stars=12,
            distribution_mode=DistributionMode.MANUAL,
            deviation_percent=35.0,
            star_parameter=StarParameterConfig(enabled=True, name="Mass", min_value=-2.0, max_value=4.0),
            trash_star_count=10,
            trash_min_distance=8.0,
        )
        state.placement_circle_size.radius = 18.0
        state.placement_rectangle_size.width = 30.0
        state.placement_rectangle_size.height = 22.0
        snapshot = state.to_editable_snapshot()

        state.clusters[0].center.x = 99.0
        state.clusters[1].size.width = 300.0
        state.clusters[1].size.polygon_scale = 250.0
        state.selected_cluster_ids = []
        state.total_cluster_stars = 999
        state.trash_star_count = 111
        state.star_parameter.name = "Changed"

        state.apply_editable_snapshot(snapshot)

        self.assertEqual(state.clusters[0].center.x, 0.0)
        self.assertEqual(state.clusters[1].size.width, 14.0)
        self.assertEqual(state.clusters[1].size.polygon_scale, 135.0)
        self.assertEqual(state.selected_cluster_ids, [2])
        self.assertEqual(state.total_cluster_stars, 12)
        self.assertEqual(state.trash_star_count, 10)
        self.assertEqual(state.star_parameter.name, "Mass")

    def test_history_manager_undo_redo_round_trip(self) -> None:
        state = AppState(
            clusters=[make_cluster(1, ShapeKind.CIRCLE, Point(0.0, 0.0), radius=10.0)],
            selected_cluster_ids=[1],
        )
        history = HistoryManager()

        history.begin(state)
        state.clusters[0].size.radius = 24.0
        state.trash_star_count = 50
        self.assertTrue(history.commit(state))
        self.assertTrue(history.can_undo)
        self.assertFalse(history.can_redo)

        self.assertTrue(history.undo(state))
        self.assertEqual(state.clusters[0].size.radius, 10.0)
        self.assertEqual(state.trash_star_count, 40)
        self.assertTrue(history.can_redo)

        self.assertTrue(history.redo(state))
        self.assertEqual(state.clusters[0].size.radius, 24.0)
        self.assertEqual(state.trash_star_count, 50)

    def test_new_edit_clears_redo_stack(self) -> None:
        state = AppState(
            clusters=[make_cluster(1, ShapeKind.CIRCLE, Point(0.0, 0.0), radius=10.0)],
        )
        history = HistoryManager()

        history.begin(state)
        state.total_cluster_stars = 10
        history.commit(state)
        history.undo(state)
        self.assertTrue(history.can_redo)

        history.begin(state)
        state.total_cluster_stars = 25
        history.commit(state)

        self.assertFalse(history.can_redo)
        self.assertFalse(history.redo(state))
        self.assertEqual(state.total_cluster_stars, 25)

    def test_history_limit_discards_oldest_snapshot(self) -> None:
        state = AppState(
            clusters=[make_cluster(1, ShapeKind.CIRCLE, Point(0.0, 0.0), radius=10.0)],
        )
        history = HistoryManager(limit=2)

        for radius in (12.0, 14.0, 16.0):
            history.begin(state)
            state.clusters[0].size.radius = radius
            history.commit(state)

        self.assertTrue(history.undo(state))
        self.assertEqual(state.clusters[0].size.radius, 14.0)
        self.assertTrue(history.undo(state))
        self.assertEqual(state.clusters[0].size.radius, 12.0)
        self.assertFalse(history.undo(state))


if __name__ == "__main__":
    unittest.main()

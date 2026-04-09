from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .config import get_app_config


class ShapeKind(StrEnum):
    CIRCLE = "circle"
    RECTANGLE = "rectangle"
    POLYGON = "polygon"


class DistributionMode(StrEnum):
    EQUAL = "equal"
    DEVIATION = "deviation"
    MANUAL = "manual"


class CanvasTool(StrEnum):
    SELECT = "select"
    CIRCLE = "circle"
    RECTANGLE = "rectangle"
    POLYGON = "polygon"

    def shape_kind(self) -> ShapeKind | None:
        if self is CanvasTool.CIRCLE:
            return ShapeKind.CIRCLE
        if self is CanvasTool.RECTANGLE:
            return ShapeKind.RECTANGLE
        if self is CanvasTool.POLYGON:
            return ShapeKind.POLYGON
        return None


@dataclass(slots=True)
class Point:
    x: float
    y: float

    def copy(self) -> "Point":
        return Point(self.x, self.y)


@dataclass(slots=True)
class StarParameterConfig:
    enabled: bool = field(default_factory=lambda: get_app_config().defaults.star_parameter_enabled)
    name: str = field(default_factory=lambda: get_app_config().defaults.star_parameter_name)
    min_value: float = field(default_factory=lambda: get_app_config().defaults.star_parameter_min_value)
    max_value: float = field(default_factory=lambda: get_app_config().defaults.star_parameter_max_value)

    def copy(self) -> "StarParameterConfig":
        return StarParameterConfig(
            enabled=self.enabled,
            name=self.name,
            min_value=self.min_value,
            max_value=self.max_value,
        )


@dataclass(slots=True)
class StarRecord:
    x: float
    y: float
    parameter_value: float | None = None

    @property
    def point(self) -> Point:
        return Point(self.x, self.y)


@dataclass(slots=True)
class ClusterSize:
    radius: float = field(default_factory=lambda: get_app_config().defaults.cluster_radius)
    width: float = field(default_factory=lambda: get_app_config().defaults.cluster_width)
    height: float = field(default_factory=lambda: get_app_config().defaults.cluster_height)
    polygon_scale: float = 100.0
    vertices_local: list[Point] = field(default_factory=list)

    def copy(self) -> "ClusterSize":
        return ClusterSize(
            radius=self.radius,
            width=self.width,
            height=self.height,
            polygon_scale=self.polygon_scale,
            vertices_local=[Point(vertex.x, vertex.y) for vertex in self.vertices_local],
        )

    def max_span(self, shape_kind: ShapeKind) -> float:
        if shape_kind is ShapeKind.CIRCLE:
            return self.radius * 2.0
        if shape_kind is ShapeKind.POLYGON and self.vertices_local:
            min_x = min(vertex.x for vertex in self.vertices_local)
            max_x = max(vertex.x for vertex in self.vertices_local)
            min_y = min(vertex.y for vertex in self.vertices_local)
            max_y = max(vertex.y for vertex in self.vertices_local)
            return max(max_x - min_x, max_y - min_y)
        return max(self.width, self.height)


@dataclass(slots=True)
class ClusterConfig:
    shape_kind: ShapeKind
    center: Point
    size: ClusterSize


@dataclass(slots=True)
class ClusterInstance:
    cluster_id: int
    shape_kind: ShapeKind
    center: Point
    size: ClusterSize
    manual_star_count: int = 0

    def to_config(self) -> ClusterConfig:
        return ClusterConfig(
            shape_kind=self.shape_kind,
            center=self.center,
            size=self.size.copy(),
        )

    def copy(self) -> "ClusterInstance":
        return ClusterInstance(
            cluster_id=self.cluster_id,
            shape_kind=self.shape_kind,
            center=self.center.copy(),
            size=self.size.copy(),
            manual_star_count=self.manual_star_count,
        )


@dataclass(slots=True)
class AppState:
    active_tool: CanvasTool = CanvasTool.SELECT
    placement_circle_size: ClusterSize = field(default_factory=ClusterSize)
    placement_rectangle_size: ClusterSize = field(default_factory=ClusterSize)
    clusters: list[ClusterInstance] = field(default_factory=list)
    selected_cluster_ids: list[int] = field(default_factory=list)
    next_cluster_id: int = 1
    total_cluster_stars: int = field(default_factory=lambda: get_app_config().defaults.total_cluster_stars)
    distribution_mode: DistributionMode = DistributionMode.EQUAL
    deviation_percent: float = field(default_factory=lambda: get_app_config().defaults.deviation_percent)
    star_parameter: StarParameterConfig = field(default_factory=StarParameterConfig)
    trash_star_count: int = field(default_factory=lambda: get_app_config().defaults.trash_star_count)
    trash_min_distance: float = field(default_factory=lambda: get_app_config().defaults.trash_min_distance)
    viewport_scale: float = field(default_factory=lambda: get_app_config().defaults.viewport_scale)
    viewport_offset: Point = field(default_factory=lambda: Point(0.0, 0.0))

    def placement_size_for_shape(self, shape_kind: ShapeKind) -> ClusterSize:
        if shape_kind is ShapeKind.CIRCLE:
            return self.placement_circle_size
        if shape_kind is ShapeKind.POLYGON:
            return ClusterSize()
        return self.placement_rectangle_size

    def selected_clusters(self) -> list[ClusterInstance]:
        selected_ids = set(self.selected_cluster_ids)
        return [cluster for cluster in self.clusters if cluster.cluster_id in selected_ids]

    def cluster_by_id(self, cluster_id: int) -> ClusterInstance | None:
        for cluster in self.clusters:
            if cluster.cluster_id == cluster_id:
                return cluster
        return None

    def cluster_index_by_id(self, cluster_id: int) -> int | None:
        for index, cluster in enumerate(self.clusters):
            if cluster.cluster_id == cluster_id:
                return index
        return None

    def is_selected(self, cluster_id: int) -> bool:
        return cluster_id in self.selected_cluster_ids

    def clear_selection(self) -> None:
        self.selected_cluster_ids.clear()

    def select_only(self, cluster_id: int) -> None:
        self.selected_cluster_ids = [cluster_id]

    def toggle_selection(self, cluster_id: int) -> None:
        if cluster_id in self.selected_cluster_ids:
            self.selected_cluster_ids = [selected_id for selected_id in self.selected_cluster_ids if selected_id != cluster_id]
            return
        self.selected_cluster_ids.append(cluster_id)

    def prune_selection(self) -> None:
        valid_ids = {cluster.cluster_id for cluster in self.clusters}
        self.selected_cluster_ids = [cluster_id for cluster_id in self.selected_cluster_ids if cluster_id in valid_ids]

    def add_cluster(self, shape_kind: ShapeKind, center: Point, size: ClusterSize | None = None) -> ClusterInstance:
        cluster = ClusterInstance(
            cluster_id=self.next_cluster_id,
            shape_kind=shape_kind,
            center=center,
            size=(size or self.placement_size_for_shape(shape_kind)).copy(),
        )
        self.next_cluster_id += 1
        self.clusters.append(cluster)
        return cluster

    def delete_selected_clusters(self) -> None:
        selected_ids = set(self.selected_cluster_ids)
        if not selected_ids:
            return
        self.clusters = [cluster for cluster in self.clusters if cluster.cluster_id not in selected_ids]
        self.selected_cluster_ids.clear()

    def selection_shape_kind(self) -> ShapeKind | None:
        selected = self.selected_clusters()
        if not selected:
            return None
        first_kind = selected[0].shape_kind
        if all(cluster.shape_kind is first_kind for cluster in selected):
            return first_kind
        return None

    def to_editable_snapshot(self) -> "EditableStateSnapshot":
        from .history import (
            ClusterSizeSnapshot,
            ClusterSnapshot,
            EditableStateSnapshot,
            PointSnapshot,
            StarParameterSnapshot,
        )

        return EditableStateSnapshot(
            placement_circle_size=ClusterSizeSnapshot.from_model(self.placement_circle_size),
            placement_rectangle_size=ClusterSizeSnapshot.from_model(self.placement_rectangle_size),
            clusters=tuple(ClusterSnapshot.from_model(cluster) for cluster in self.clusters),
            selected_cluster_ids=tuple(self.selected_cluster_ids),
            next_cluster_id=self.next_cluster_id,
            total_cluster_stars=self.total_cluster_stars,
            distribution_mode=self.distribution_mode,
            deviation_percent=self.deviation_percent,
            star_parameter=StarParameterSnapshot.from_model(self.star_parameter),
            trash_star_count=self.trash_star_count,
            trash_min_distance=self.trash_min_distance,
        )

    def apply_editable_snapshot(self, snapshot: "EditableStateSnapshot") -> None:
        self.placement_circle_size = snapshot.placement_circle_size.to_model()
        self.placement_rectangle_size = snapshot.placement_rectangle_size.to_model()
        self.clusters = [cluster.to_model() for cluster in snapshot.clusters]
        self.selected_cluster_ids = list(snapshot.selected_cluster_ids)
        self.next_cluster_id = snapshot.next_cluster_id
        self.total_cluster_stars = snapshot.total_cluster_stars
        self.distribution_mode = snapshot.distribution_mode
        self.deviation_percent = snapshot.deviation_percent
        self.star_parameter = snapshot.star_parameter.to_model()
        self.trash_star_count = snapshot.trash_star_count
        self.trash_min_distance = snapshot.trash_min_distance

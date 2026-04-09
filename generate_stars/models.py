from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .config import get_app_config


class ShapeKind(StrEnum):
    CIRCLE = "circle"
    RECTANGLE = "rectangle"


class DistributionMode(StrEnum):
    EQUAL = "equal"
    DEVIATION = "deviation"
    MANUAL = "manual"


class CanvasTool(StrEnum):
    SELECT = "select"
    CIRCLE = "circle"
    RECTANGLE = "rectangle"

    def shape_kind(self) -> ShapeKind | None:
        if self is CanvasTool.CIRCLE:
            return ShapeKind.CIRCLE
        if self is CanvasTool.RECTANGLE:
            return ShapeKind.RECTANGLE
        return None


@dataclass(slots=True)
class Point:
    x: float
    y: float


@dataclass(slots=True)
class StarParameterConfig:
    enabled: bool = field(default_factory=lambda: get_app_config().defaults.star_parameter_enabled)
    name: str = field(default_factory=lambda: get_app_config().defaults.star_parameter_name)
    min_value: float = field(default_factory=lambda: get_app_config().defaults.star_parameter_min_value)
    max_value: float = field(default_factory=lambda: get_app_config().defaults.star_parameter_max_value)


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

    def copy(self) -> "ClusterSize":
        return ClusterSize(radius=self.radius, width=self.width, height=self.height)

    def max_span(self, shape_kind: ShapeKind) -> float:
        if shape_kind is ShapeKind.CIRCLE:
            return self.radius * 2.0
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

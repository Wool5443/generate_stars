from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

from .config import get_app_config


class ShapeKind(StrEnum):
    CIRCLE = "circle"
    RECTANGLE = "rectangle"
    POLYGON = "polygon"
    FUNCTION = "function"


class DistributionMode(StrEnum):
    EQUAL = "equal"
    DEVIATION = "deviation"
    MANUAL = "manual"


class CanvasTool(StrEnum):
    SELECT = "select"
    CIRCLE = "circle"
    RECTANGLE = "rectangle"
    POLYGON = "polygon"
    FUNCTION = "function"

    def shape_kind(self) -> ShapeKind | None:
        if self is CanvasTool.CIRCLE:
            return ShapeKind.CIRCLE
        if self is CanvasTool.RECTANGLE:
            return ShapeKind.RECTANGLE
        if self is CanvasTool.POLYGON:
            return ShapeKind.POLYGON
        if self is CanvasTool.FUNCTION:
            return ShapeKind.FUNCTION
        return None


class FunctionOrientation(StrEnum):
    Y_OF_X = "y_of_x"
    X_OF_Y = "x_of_y"

    def variable_name(self) -> str:
        return "x" if self is FunctionOrientation.Y_OF_X else "y"


class StarParameterMode(StrEnum):
    RANDOM = "random"
    FUNCTION = "function"


@dataclass(slots=True)
class Point:
    x: float
    y: float

    def copy(self) -> "Point":
        return Point(self.x, self.y)


def _polygon_spans(vertices: list[Point]) -> tuple[float, float]:
    if not vertices:
        return 0.0, 0.0
    min_x = min(vertex.x for vertex in vertices)
    max_x = max(vertex.x for vertex in vertices)
    min_y = min(vertex.y for vertex in vertices)
    max_y = max(vertex.y for vertex in vertices)
    return max_x - min_x, max_y - min_y


class ClusterSize(ABC):
    @property
    @abstractmethod
    def shape_kind(self) -> ShapeKind:
        raise NotImplementedError

    @abstractmethod
    def copy(self) -> "ClusterSize":
        raise NotImplementedError

    @abstractmethod
    def max_span(self) -> float:
        raise NotImplementedError


@dataclass(slots=True)
class CircleSize(ClusterSize):
    radius: float = field(default_factory=lambda: get_app_config().defaults.cluster_radius)

    @property
    def shape_kind(self) -> ShapeKind:
        return ShapeKind.CIRCLE

    @property
    def width(self) -> float:
        return self.radius * 2.0

    @property
    def height(self) -> float:
        return self.radius * 2.0

    def copy(self) -> "CircleSize":
        return CircleSize(radius=self.radius)

    def max_span(self) -> float:
        return self.radius * 2.0


@dataclass(slots=True)
class RectangleSize(ClusterSize):
    width: float = field(default_factory=lambda: get_app_config().defaults.cluster_width)
    height: float = field(default_factory=lambda: get_app_config().defaults.cluster_height)

    @property
    def shape_kind(self) -> ShapeKind:
        return ShapeKind.RECTANGLE

    @property
    def radius(self) -> float:
        return max(self.width, self.height) / 2.0

    def copy(self) -> "RectangleSize":
        return RectangleSize(
            width=self.width,
            height=self.height,
        )

    def max_span(self) -> float:
        return max(self.width, self.height)


@dataclass(slots=True)
class PolygonSize(ClusterSize):
    vertices_local: list[Point] = field(default_factory=list)
    polygon_scale: float = 100.0

    @property
    def shape_kind(self) -> ShapeKind:
        return ShapeKind.POLYGON

    @property
    def width(self) -> float:
        width, _ = _polygon_spans(self.vertices_local)
        return width

    @property
    def height(self) -> float:
        _, height = _polygon_spans(self.vertices_local)
        return height

    @property
    def radius(self) -> float:
        return max(self.width, self.height) / 2.0

    def copy(self) -> "PolygonSize":
        return PolygonSize(
            vertices_local=[Point(vertex.x, vertex.y) for vertex in self.vertices_local],
            polygon_scale=self.polygon_scale,
        )

    def max_span(self) -> float:
        return max(self.width, self.height)


@dataclass(slots=True)
class FunctionSize(ClusterSize):
    function_expression: str = field(default_factory=lambda: get_app_config().defaults.function_expression)
    function_orientation: FunctionOrientation = field(
        default_factory=lambda: FunctionOrientation(get_app_config().defaults.function_orientation)
    )
    function_range_start: float = field(default_factory=lambda: get_app_config().defaults.function_range_start)
    function_range_end: float = field(default_factory=lambda: get_app_config().defaults.function_range_end)
    function_thickness: float = field(default_factory=lambda: get_app_config().defaults.function_thickness)
    vertices_local: list[Point] = field(default_factory=list)

    @property
    def shape_kind(self) -> ShapeKind:
        return ShapeKind.FUNCTION

    @property
    def width(self) -> float:
        width, _ = _polygon_spans(self.vertices_local)
        return width

    @property
    def height(self) -> float:
        _, height = _polygon_spans(self.vertices_local)
        return height

    @property
    def radius(self) -> float:
        return max(self.width, self.height) / 2.0

    def copy(self) -> "FunctionSize":
        return FunctionSize(
            function_expression=self.function_expression,
            function_orientation=self.function_orientation,
            function_range_start=self.function_range_start,
            function_range_end=self.function_range_end,
            function_thickness=self.function_thickness,
            vertices_local=[Point(vertex.x, vertex.y) for vertex in self.vertices_local],
        )

    def max_span(self) -> float:
        return max(self.width, self.height)


class StarParameterValue(ABC):
    @property
    @abstractmethod
    def mode(self) -> StarParameterMode:
        raise NotImplementedError

    @abstractmethod
    def copy(self) -> "StarParameterValue":
        raise NotImplementedError


@dataclass(slots=True)
class RandomStarParameterValue(StarParameterValue):
    min_value: float = field(default_factory=lambda: get_app_config().defaults.star_parameter_min_value)
    max_value: float = field(default_factory=lambda: get_app_config().defaults.star_parameter_max_value)

    @property
    def mode(self) -> StarParameterMode:
        return StarParameterMode.RANDOM

    def copy(self) -> "RandomStarParameterValue":
        return RandomStarParameterValue(
            min_value=self.min_value,
            max_value=self.max_value,
        )


@dataclass(slots=True)
class FunctionStarParameterValue(StarParameterValue):
    function_body: str = field(default_factory=lambda: get_app_config().defaults.star_parameter_function_body)

    @property
    def mode(self) -> StarParameterMode:
        return StarParameterMode.FUNCTION

    def copy(self) -> "FunctionStarParameterValue":
        return FunctionStarParameterValue(function_body=self.function_body)


@dataclass(slots=True)
class StarParameterConfig:
    enabled: bool = field(default_factory=lambda: get_app_config().defaults.star_parameter_enabled)
    name: str = field(default_factory=lambda: get_app_config().defaults.star_parameter_name)
    value: StarParameterValue = field(default_factory=RandomStarParameterValue)

    @property
    def mode(self) -> StarParameterMode:
        return self.value.mode

    @mode.setter
    def mode(self, mode: StarParameterMode) -> None:
        if mode is StarParameterMode.RANDOM and self.mode is not StarParameterMode.RANDOM:
            self.value = RandomStarParameterValue()
        elif mode is StarParameterMode.FUNCTION and self.mode is not StarParameterMode.FUNCTION:
            self.value = FunctionStarParameterValue()

    @property
    def min_value(self) -> float:
        if isinstance(self.value, RandomStarParameterValue):
            return self.value.min_value
        return get_app_config().defaults.star_parameter_min_value

    @min_value.setter
    def min_value(self, value: float) -> None:
        if not isinstance(self.value, RandomStarParameterValue):
            self.value = RandomStarParameterValue()
        self.value.min_value = value

    @property
    def max_value(self) -> float:
        if isinstance(self.value, RandomStarParameterValue):
            return self.value.max_value
        return get_app_config().defaults.star_parameter_max_value

    @max_value.setter
    def max_value(self, value: float) -> None:
        if not isinstance(self.value, RandomStarParameterValue):
            self.value = RandomStarParameterValue()
        self.value.max_value = value

    @property
    def function_body(self) -> str:
        if isinstance(self.value, FunctionStarParameterValue):
            return self.value.function_body
        return get_app_config().defaults.star_parameter_function_body

    @function_body.setter
    def function_body(self, body: str) -> None:
        if not isinstance(self.value, FunctionStarParameterValue):
            self.value = FunctionStarParameterValue()
        self.value.function_body = body

    def copy(self) -> "StarParameterConfig":
        return StarParameterConfig(
            enabled=self.enabled,
            name=self.name,
            value=self.value.copy(),
        )


@dataclass(slots=True)
class StarRecord:
    x: float
    y: float
    parameter_value: float | str | None = None

    @property
    def point(self) -> Point:
        return Point(self.x, self.y)


@dataclass(slots=True)
class ClusterConfig:
    center: Point
    size: ClusterSize

    @property
    def shape_kind(self) -> ShapeKind:
        return self.size.shape_kind


@dataclass(slots=True)
class ClusterInstance:
    cluster_id: int
    center: Point
    size: ClusterSize
    manual_star_count: int = 0

    @property
    def shape_kind(self) -> ShapeKind:
        return self.size.shape_kind

    def to_config(self) -> ClusterConfig:
        return ClusterConfig(
            center=self.center.copy(),
            size=self.size.copy(),
        )

    def copy(self) -> "ClusterInstance":
        return ClusterInstance(
            cluster_id=self.cluster_id,
            center=self.center.copy(),
            size=self.size.copy(),
            manual_star_count=self.manual_star_count,
        )


@dataclass(slots=True)
class AppState:
    placement_circle_size: CircleSize = field(default_factory=CircleSize)
    placement_rectangle_size: RectangleSize = field(default_factory=RectangleSize)
    placement_function_size: FunctionSize = field(default_factory=FunctionSize)
    clusters: list[ClusterInstance] = field(default_factory=list)
    selected_cluster_ids: list[int] = field(default_factory=list)
    next_cluster_id: int = 1
    total_cluster_stars: int = field(default_factory=lambda: get_app_config().defaults.total_cluster_stars)
    distribution_mode: DistributionMode = DistributionMode.EQUAL
    deviation_percent: float = field(default_factory=lambda: get_app_config().defaults.deviation_percent)
    star_parameter: StarParameterConfig = field(default_factory=StarParameterConfig)
    trash_star_count: int = field(default_factory=lambda: get_app_config().defaults.trash_star_count)
    trash_min_distance: float = field(default_factory=lambda: get_app_config().defaults.trash_min_distance)

    def placement_size_for_shape(self, shape_kind: ShapeKind) -> ClusterSize:
        if shape_kind is ShapeKind.CIRCLE:
            return self.placement_circle_size
        if shape_kind is ShapeKind.POLYGON:
            return PolygonSize()
        if shape_kind is ShapeKind.FUNCTION:
            return self.placement_function_size
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
        resolved_size = (size or self.placement_size_for_shape(shape_kind)).copy()
        if resolved_size.shape_kind is not shape_kind:
            raise ValueError("Shape kind does not match cluster size type.")
        cluster = ClusterInstance(
            cluster_id=self.next_cluster_id,
            center=center.copy(),
            size=resolved_size,
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
            StarParameterSnapshot,
        )

        return EditableStateSnapshot(
            placement_circle_size=ClusterSizeSnapshot.from_model(self.placement_circle_size),
            placement_rectangle_size=ClusterSizeSnapshot.from_model(self.placement_rectangle_size),
            placement_function_size=ClusterSizeSnapshot.from_model(self.placement_function_size),
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
        self.placement_circle_size = snapshot.placement_circle_size.to_model()  # type: ignore[assignment]
        self.placement_rectangle_size = snapshot.placement_rectangle_size.to_model()  # type: ignore[assignment]
        self.placement_function_size = snapshot.placement_function_size.to_model()  # type: ignore[assignment]
        self.clusters = [cluster.to_model() for cluster in snapshot.clusters]
        self.selected_cluster_ids = list(snapshot.selected_cluster_ids)
        self.next_cluster_id = snapshot.next_cluster_id
        self.total_cluster_stars = snapshot.total_cluster_stars
        self.distribution_mode = snapshot.distribution_mode
        self.deviation_percent = snapshot.deviation_percent
        self.star_parameter = snapshot.star_parameter.to_model()
        self.trash_star_count = snapshot.trash_star_count
        self.trash_min_distance = snapshot.trash_min_distance

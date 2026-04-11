from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .models import (
    AppState,
    CircleSize,
    ClusterInstance,
    ClusterSize,
    DistributionMode,
    FunctionOrientation,
    FunctionSize,
    FunctionStarParameterValue,
    Point,
    PolygonSize,
    RandomStarParameterValue,
    RectangleSize,
    ShapeKind,
    StarParameterConfig,
    StarParameterValue,
)


@dataclass(frozen=True, slots=True)
class PointSnapshot:
    x: float
    y: float

    @classmethod
    def from_model(cls, point: Point) -> "PointSnapshot":
        return cls(point.x, point.y)

    def to_model(self) -> Point:
        return Point(self.x, self.y)


class ClusterSizeSnapshot(ABC):
    @property
    @abstractmethod
    def shape_kind(self) -> ShapeKind:
        raise NotImplementedError

    @abstractmethod
    def to_model(self) -> ClusterSize:
        raise NotImplementedError

    @staticmethod
    def from_model(size: ClusterSize) -> "ClusterSizeSnapshot":
        if isinstance(size, CircleSize):
            return CircleSizeSnapshot(radius=size.radius)
        if isinstance(size, RectangleSize):
            return RectangleSizeSnapshot(width=size.width, height=size.height)
        if isinstance(size, PolygonSize):
            return PolygonSizeSnapshot(
                vertices_local=tuple(PointSnapshot.from_model(vertex) for vertex in size.vertices_local),
                polygon_scale=size.polygon_scale,
            )
        if isinstance(size, FunctionSize):
            return FunctionSizeSnapshot(
                function_expression=size.function_expression,
                function_orientation=size.function_orientation,
                function_range_start=size.function_range_start,
                function_range_end=size.function_range_end,
                function_thickness=size.function_thickness,
                vertices_local=tuple(PointSnapshot.from_model(vertex) for vertex in size.vertices_local),
            )
        raise TypeError("Unsupported cluster size type.")


@dataclass(frozen=True, slots=True)
class CircleSizeSnapshot(ClusterSizeSnapshot):
    radius: float

    @property
    def shape_kind(self) -> ShapeKind:
        return ShapeKind.CIRCLE

    def to_model(self) -> CircleSize:
        return CircleSize(radius=self.radius)


@dataclass(frozen=True, slots=True)
class RectangleSizeSnapshot(ClusterSizeSnapshot):
    width: float
    height: float

    @property
    def shape_kind(self) -> ShapeKind:
        return ShapeKind.RECTANGLE

    def to_model(self) -> RectangleSize:
        return RectangleSize(width=self.width, height=self.height)


@dataclass(frozen=True, slots=True)
class PolygonSizeSnapshot(ClusterSizeSnapshot):
    vertices_local: tuple[PointSnapshot, ...]
    polygon_scale: float

    @property
    def shape_kind(self) -> ShapeKind:
        return ShapeKind.POLYGON

    def to_model(self) -> PolygonSize:
        return PolygonSize(
            vertices_local=[vertex.to_model() for vertex in self.vertices_local],
            polygon_scale=self.polygon_scale,
        )


@dataclass(frozen=True, slots=True)
class FunctionSizeSnapshot(ClusterSizeSnapshot):
    function_expression: str
    function_orientation: FunctionOrientation
    function_range_start: float
    function_range_end: float
    function_thickness: float
    vertices_local: tuple[PointSnapshot, ...]

    @property
    def shape_kind(self) -> ShapeKind:
        return ShapeKind.FUNCTION

    def to_model(self) -> FunctionSize:
        return FunctionSize(
            function_expression=self.function_expression,
            function_orientation=self.function_orientation,
            function_range_start=self.function_range_start,
            function_range_end=self.function_range_end,
            function_thickness=self.function_thickness,
            vertices_local=[vertex.to_model() for vertex in self.vertices_local],
        )


class StarParameterValueSnapshot(ABC):
    @abstractmethod
    def to_model(self) -> StarParameterValue:
        raise NotImplementedError

    @staticmethod
    def from_model(value: StarParameterValue) -> "StarParameterValueSnapshot":
        if isinstance(value, RandomStarParameterValue):
            return RandomStarParameterValueSnapshot(
                min_value=value.min_value,
                max_value=value.max_value,
            )
        if isinstance(value, FunctionStarParameterValue):
            return FunctionStarParameterValueSnapshot(function_body=value.function_body)
        raise TypeError("Unsupported star parameter value type.")


@dataclass(frozen=True, slots=True)
class RandomStarParameterValueSnapshot(StarParameterValueSnapshot):
    min_value: float
    max_value: float

    def to_model(self) -> RandomStarParameterValue:
        return RandomStarParameterValue(
            min_value=self.min_value,
            max_value=self.max_value,
        )


@dataclass(frozen=True, slots=True)
class FunctionStarParameterValueSnapshot(StarParameterValueSnapshot):
    function_body: str

    def to_model(self) -> FunctionStarParameterValue:
        return FunctionStarParameterValue(function_body=self.function_body)


@dataclass(frozen=True, slots=True)
class StarParameterSnapshot:
    enabled: bool
    name: str
    value: StarParameterValueSnapshot

    @classmethod
    def from_model(cls, parameter: StarParameterConfig) -> "StarParameterSnapshot":
        return cls(
            enabled=parameter.enabled,
            name=parameter.name,
            value=StarParameterValueSnapshot.from_model(parameter.value),
        )

    def to_model(self) -> StarParameterConfig:
        return StarParameterConfig(
            enabled=self.enabled,
            name=self.name,
            value=self.value.to_model(),
        )


@dataclass(frozen=True, slots=True)
class ClusterSnapshot:
    cluster_id: int
    center: PointSnapshot
    size: ClusterSizeSnapshot
    manual_star_count: int

    @property
    def shape_kind(self) -> ShapeKind:
        return self.size.shape_kind

    @classmethod
    def from_model(cls, cluster: ClusterInstance) -> "ClusterSnapshot":
        return cls(
            cluster_id=cluster.cluster_id,
            center=PointSnapshot.from_model(cluster.center),
            size=ClusterSizeSnapshot.from_model(cluster.size),
            manual_star_count=cluster.manual_star_count,
        )

    def to_model(self) -> ClusterInstance:
        return ClusterInstance(
            cluster_id=self.cluster_id,
            center=self.center.to_model(),
            size=self.size.to_model(),
            manual_star_count=self.manual_star_count,
        )


@dataclass(frozen=True, slots=True)
class EditableStateSnapshot:
    placement_circle_size: CircleSizeSnapshot
    placement_rectangle_size: RectangleSizeSnapshot
    placement_function_size: FunctionSizeSnapshot
    clusters: tuple[ClusterSnapshot, ...]
    selected_cluster_ids: tuple[int, ...]
    next_cluster_id: int
    total_cluster_stars: int
    distribution_mode: DistributionMode
    deviation_percent: float
    star_parameter: StarParameterSnapshot
    trash_star_count: int
    trash_min_distance: float


class HistoryManager:
    def __init__(self, limit: int = 100) -> None:
        self.limit = max(1, limit)
        self._undo_stack: list[EditableStateSnapshot] = []
        self._redo_stack: list[EditableStateSnapshot] = []
        self._pending_before: EditableStateSnapshot | None = None

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def begin(self, state: AppState) -> None:
        if self._pending_before is not None:
            return
        self._pending_before = state.to_editable_snapshot()

    def cancel_pending(self) -> None:
        self._pending_before = None

    def commit(self, state: AppState) -> bool:
        if self._pending_before is None:
            return False

        before = self._pending_before
        self._pending_before = None
        after = state.to_editable_snapshot()
        if before == after:
            return False

        self._undo_stack.append(before)
        if len(self._undo_stack) > self.limit:
            del self._undo_stack[0]
        self._redo_stack.clear()
        return True

    def undo(self, state: AppState) -> bool:
        self.cancel_pending()
        if not self._undo_stack:
            return False

        current = state.to_editable_snapshot()
        target = self._undo_stack.pop()
        self._redo_stack.append(current)
        if len(self._redo_stack) > self.limit:
            del self._redo_stack[0]
        state.apply_editable_snapshot(target)
        return True

    def redo(self, state: AppState) -> bool:
        self.cancel_pending()
        if not self._redo_stack:
            return False

        current = state.to_editable_snapshot()
        target = self._redo_stack.pop()
        self._undo_stack.append(current)
        if len(self._undo_stack) > self.limit:
            del self._undo_stack[0]
        state.apply_editable_snapshot(target)
        return True

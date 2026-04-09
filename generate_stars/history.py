from __future__ import annotations

from dataclasses import dataclass

from .models import AppState, ClusterInstance, ClusterSize, DistributionMode, Point, ShapeKind, StarParameterConfig


@dataclass(frozen=True, slots=True)
class PointSnapshot:
    x: float
    y: float

    @classmethod
    def from_model(cls, point: Point) -> "PointSnapshot":
        return cls(point.x, point.y)

    def to_model(self) -> Point:
        return Point(self.x, self.y)


@dataclass(frozen=True, slots=True)
class ClusterSizeSnapshot:
    radius: float
    width: float
    height: float
    polygon_scale: float
    vertices_local: tuple[PointSnapshot, ...]

    @classmethod
    def from_model(cls, size: ClusterSize) -> "ClusterSizeSnapshot":
        return cls(
            radius=size.radius,
            width=size.width,
            height=size.height,
            polygon_scale=size.polygon_scale,
            vertices_local=tuple(PointSnapshot.from_model(vertex) for vertex in size.vertices_local),
        )

    def to_model(self) -> ClusterSize:
        return ClusterSize(
            radius=self.radius,
            width=self.width,
            height=self.height,
            polygon_scale=self.polygon_scale,
            vertices_local=[vertex.to_model() for vertex in self.vertices_local],
        )


@dataclass(frozen=True, slots=True)
class StarParameterSnapshot:
    enabled: bool
    name: str
    min_value: float
    max_value: float

    @classmethod
    def from_model(cls, parameter: StarParameterConfig) -> "StarParameterSnapshot":
        return cls(
            enabled=parameter.enabled,
            name=parameter.name,
            min_value=parameter.min_value,
            max_value=parameter.max_value,
        )

    def to_model(self) -> StarParameterConfig:
        return StarParameterConfig(
            enabled=self.enabled,
            name=self.name,
            min_value=self.min_value,
            max_value=self.max_value,
        )


@dataclass(frozen=True, slots=True)
class ClusterSnapshot:
    cluster_id: int
    shape_kind: ShapeKind
    center: PointSnapshot
    size: ClusterSizeSnapshot
    manual_star_count: int

    @classmethod
    def from_model(cls, cluster: ClusterInstance) -> "ClusterSnapshot":
        return cls(
            cluster_id=cluster.cluster_id,
            shape_kind=cluster.shape_kind,
            center=PointSnapshot.from_model(cluster.center),
            size=ClusterSizeSnapshot.from_model(cluster.size),
            manual_star_count=cluster.manual_star_count,
        )

    def to_model(self) -> ClusterInstance:
        return ClusterInstance(
            cluster_id=self.cluster_id,
            shape_kind=self.shape_kind,
            center=self.center.to_model(),
            size=self.size.to_model(),
            manual_star_count=self.manual_star_count,
        )


@dataclass(frozen=True, slots=True)
class EditableStateSnapshot:
    placement_circle_size: ClusterSizeSnapshot
    placement_rectangle_size: ClusterSizeSnapshot
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

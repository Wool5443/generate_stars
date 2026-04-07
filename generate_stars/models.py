from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from . import constants


class ShapeKind(StrEnum):
    CIRCLE = "circle"
    RECTANGLE = "rectangle"


class DistributionMode(StrEnum):
    EQUAL = "equal"
    DEVIATION = "deviation"
    MANUAL = "manual"


@dataclass(slots=True)
class Point:
    x: float
    y: float


@dataclass(slots=True)
class ClusterSize:
    radius: float = constants.DEFAULT_CLUSTER_RADIUS
    width: float = constants.DEFAULT_CLUSTER_WIDTH
    height: float = constants.DEFAULT_CLUSTER_HEIGHT

    def copy(self) -> "ClusterSize":
        return ClusterSize(radius=self.radius, width=self.width, height=self.height)

    def max_span(self, shape_kind: ShapeKind) -> float:
        if shape_kind is ShapeKind.CIRCLE:
            return self.radius * 2.0
        return max(self.width, self.height)


@dataclass(slots=True)
class ClusterConfig:
    center: Point
    size: ClusterSize


@dataclass(slots=True)
class AppState:
    shape_kind: ShapeKind = ShapeKind.CIRCLE
    shared_size: ClusterSize = field(default_factory=ClusterSize)
    cluster_count: int = constants.DEFAULT_CLUSTER_COUNT
    cluster_centers: list[Point] = field(default_factory=list)
    positions_customized: bool = False
    size_overrides_enabled: list[bool] = field(default_factory=list)
    size_overrides: list[ClusterSize] = field(default_factory=list)
    total_cluster_stars: int = constants.DEFAULT_TOTAL_CLUSTER_STARS
    distribution_mode: DistributionMode = DistributionMode.EQUAL
    deviation_percent: float = constants.DEFAULT_DEVIATION_PERCENT
    manual_counts: list[int] = field(default_factory=list)
    trash_star_count: int = constants.DEFAULT_TRASH_STAR_COUNT
    trash_min_distance: float = constants.DEFAULT_TRASH_MIN_DISTANCE
    viewport_scale: float = constants.DEFAULT_VIEWPORT_SCALE
    viewport_offset: Point = field(default_factory=lambda: Point(0.0, 0.0))

    def resolved_size(self, index: int) -> ClusterSize:
        if 0 <= index < len(self.size_overrides_enabled) and self.size_overrides_enabled[index]:
            return self.size_overrides[index]
        return self.shared_size

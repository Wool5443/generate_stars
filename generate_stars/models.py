from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


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
    radius: float = 60.0
    width: float = 140.0
    height: float = 90.0

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
    cluster_count: int = 3
    cluster_centers: list[Point] = field(default_factory=list)
    size_overrides_enabled: list[bool] = field(default_factory=list)
    size_overrides: list[ClusterSize] = field(default_factory=list)
    total_cluster_stars: int = 300
    distribution_mode: DistributionMode = DistributionMode.EQUAL
    deviation_percent: float = 20.0
    manual_counts: list[int] = field(default_factory=list)
    trash_star_count: int = 40
    trash_min_distance: float = 25.0
    viewport_scale: float = 1.0
    viewport_offset: Point = field(default_factory=lambda: Point(0.0, 0.0))

    def resolved_size(self, index: int) -> ClusterSize:
        if 0 <= index < len(self.size_overrides_enabled) and self.size_overrides_enabled[index]:
            return self.size_overrides[index]
        return self.shared_size


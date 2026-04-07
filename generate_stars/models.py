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


@dataclass(slots=True)
class Point:
    x: float
    y: float


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
    center: Point
    size: ClusterSize


@dataclass(slots=True)
class AppState:
    shape_kind: ShapeKind = ShapeKind.CIRCLE
    shared_size: ClusterSize = field(default_factory=ClusterSize)
    cluster_count: int = field(default_factory=lambda: get_app_config().defaults.cluster_count)
    cluster_centers: list[Point] = field(default_factory=list)
    positions_customized: bool = False
    size_overrides_enabled: list[bool] = field(default_factory=list)
    size_overrides: list[ClusterSize] = field(default_factory=list)
    total_cluster_stars: int = field(default_factory=lambda: get_app_config().defaults.total_cluster_stars)
    distribution_mode: DistributionMode = DistributionMode.EQUAL
    deviation_percent: float = field(default_factory=lambda: get_app_config().defaults.deviation_percent)
    manual_counts: list[int] = field(default_factory=list)
    trash_star_count: int = field(default_factory=lambda: get_app_config().defaults.trash_star_count)
    trash_min_distance: float = field(default_factory=lambda: get_app_config().defaults.trash_min_distance)
    viewport_scale: float = field(default_factory=lambda: get_app_config().defaults.viewport_scale)
    viewport_offset: Point = field(default_factory=lambda: Point(0.0, 0.0))

    def resolved_size(self, index: int) -> ClusterSize:
        if 0 <= index < len(self.size_overrides_enabled) and self.size_overrides_enabled[index]:
            return self.size_overrides[index]
        return self.shared_size

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math
import random

import cairo

from .models import ClusterSize, Point, ShapeKind


@dataclass(frozen=True, slots=True)
class BoundingBox:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def expanded(self, padding: float) -> "BoundingBox":
        return BoundingBox(
            min_x=self.min_x - padding,
            min_y=self.min_y - padding,
            max_x=self.max_x + padding,
            max_y=self.max_y + padding,
        )


class ClusterShape(ABC):
    kind: ShapeKind
    label: str

    @abstractmethod
    def draw_outline(self, context: cairo.Context, center: Point, size: ClusterSize) -> None:
        raise NotImplementedError

    @abstractmethod
    def sample_point(self, center: Point, size: ClusterSize, rng: random.Random) -> Point:
        raise NotImplementedError

    @abstractmethod
    def edge_distance(self, point: Point, center: Point, size: ClusterSize) -> float:
        raise NotImplementedError

    @abstractmethod
    def bounding_box(self, center: Point, size: ClusterSize) -> BoundingBox:
        raise NotImplementedError


class CircleShape(ClusterShape):
    kind = ShapeKind.CIRCLE
    label = "Circle"

    def draw_outline(self, context: cairo.Context, center: Point, size: ClusterSize) -> None:
        context.arc(center.x, center.y, size.radius, 0.0, math.tau)

    def sample_point(self, center: Point, size: ClusterSize, rng: random.Random) -> Point:
        angle = rng.uniform(0.0, math.tau)
        distance = size.radius * math.sqrt(rng.random())
        return Point(
            x=center.x + math.cos(angle) * distance,
            y=center.y + math.sin(angle) * distance,
        )

    def edge_distance(self, point: Point, center: Point, size: ClusterSize) -> float:
        return math.hypot(point.x - center.x, point.y - center.y) - size.radius

    def bounding_box(self, center: Point, size: ClusterSize) -> BoundingBox:
        return BoundingBox(
            min_x=center.x - size.radius,
            min_y=center.y - size.radius,
            max_x=center.x + size.radius,
            max_y=center.y + size.radius,
        )


class RectangleShape(ClusterShape):
    kind = ShapeKind.RECTANGLE
    label = "Rectangle"

    def draw_outline(self, context: cairo.Context, center: Point, size: ClusterSize) -> None:
        context.rectangle(
            center.x - size.width / 2.0,
            center.y - size.height / 2.0,
            size.width,
            size.height,
        )

    def sample_point(self, center: Point, size: ClusterSize, rng: random.Random) -> Point:
        return Point(
            x=center.x + rng.uniform(-size.width / 2.0, size.width / 2.0),
            y=center.y + rng.uniform(-size.height / 2.0, size.height / 2.0),
        )

    def edge_distance(self, point: Point, center: Point, size: ClusterSize) -> float:
        dx = abs(point.x - center.x) - size.width / 2.0
        dy = abs(point.y - center.y) - size.height / 2.0
        outside = math.hypot(max(dx, 0.0), max(dy, 0.0))
        inside = min(max(dx, dy), 0.0)
        return outside + inside

    def bounding_box(self, center: Point, size: ClusterSize) -> BoundingBox:
        return BoundingBox(
            min_x=center.x - size.width / 2.0,
            min_y=center.y - size.height / 2.0,
            max_x=center.x + size.width / 2.0,
            max_y=center.y + size.height / 2.0,
        )


SHAPE_REGISTRY: dict[ShapeKind, ClusterShape] = {
    ShapeKind.CIRCLE: CircleShape(),
    ShapeKind.RECTANGLE: RectangleShape(),
}


def get_shape(shape_kind: ShapeKind) -> ClusterShape:
    return SHAPE_REGISTRY[shape_kind]

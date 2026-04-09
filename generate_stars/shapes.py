from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
import ast
import math
import random

import cairo

from .config import get_app_config
from .localization import get_localizer
from .models import ClusterSize, FunctionOrientation, Point, ShapeKind

POLYGON_EPSILON = 1e-6
SAFE_FUNCTIONS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "abs": abs,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "log10": math.log10,
    "floor": math.floor,
    "ceil": math.ceil,
}
SAFE_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}


class FunctionDefinitionError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


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


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _validate_expression_node(node: ast.AST, variable_name: str) -> None:
    if isinstance(node, ast.Expression):
        _validate_expression_node(node.body, variable_name)
        return
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            raise FunctionDefinitionError("expression")
        _validate_expression_node(node.left, variable_name)
        _validate_expression_node(node.right, variable_name)
        return
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, (ast.UAdd, ast.USub)):
            raise FunctionDefinitionError("expression")
        _validate_expression_node(node.operand, variable_name)
        return
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in SAFE_FUNCTIONS or node.keywords:
            raise FunctionDefinitionError("expression")
        for argument in node.args:
            _validate_expression_node(argument, variable_name)
        return
    if isinstance(node, ast.Name):
        if node.id != variable_name and node.id not in SAFE_CONSTANTS:
            raise FunctionDefinitionError("expression")
        return
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return
    raise FunctionDefinitionError("expression")


@lru_cache(maxsize=256)
def _compiled_function_expression(expression: str, variable_name: str):
    normalized = expression.strip().replace("^", "**")
    if not normalized:
        raise FunctionDefinitionError("expression")
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise FunctionDefinitionError("expression") from exc
    _validate_expression_node(tree, variable_name)
    return compile(tree, "<function-expression>", "eval")


def evaluate_function_expression(
    expression: str,
    orientation: FunctionOrientation,
    value: float,
) -> float:
    code = _compiled_function_expression(expression, orientation.variable_name())
    context = {orientation.variable_name(): value, **SAFE_CONSTANTS, **SAFE_FUNCTIONS}
    result = eval(code, {"__builtins__": {}}, context)
    if not isinstance(result, (int, float)):
        raise FunctionDefinitionError("evaluation")
    numeric = float(result)
    if not math.isfinite(numeric):
        raise FunctionDefinitionError("evaluation")
    return numeric


def normalize_polygon_vertices(vertices: list[Point], epsilon: float = POLYGON_EPSILON) -> list[Point]:
    normalized: list[Point] = []
    for vertex in vertices:
        if normalized and _distance(normalized[-1], vertex) <= epsilon:
            continue
        normalized.append(Point(vertex.x, vertex.y))

    if len(normalized) >= 2 and _distance(normalized[0], normalized[-1]) <= epsilon:
        normalized.pop()
    return normalized


def polygon_area(vertices: list[Point]) -> float:
    total = 0.0
    count = len(vertices)
    for index in range(count):
        current = vertices[index]
        next_vertex = vertices[(index + 1) % count]
        total += current.x * next_vertex.y - next_vertex.x * current.y
    return total / 2.0


def polygon_centroid(vertices: list[Point]) -> Point:
    normalized = normalize_polygon_vertices(vertices)
    area = polygon_area(normalized)
    if len(normalized) == 0:
        return Point(0.0, 0.0)
    if abs(area) <= POLYGON_EPSILON:
        return Point(
            x=sum(vertex.x for vertex in normalized) / len(normalized),
            y=sum(vertex.y for vertex in normalized) / len(normalized),
        )

    factor = 1.0 / (6.0 * area)
    cx = 0.0
    cy = 0.0
    for index, current in enumerate(normalized):
        next_vertex = normalized[(index + 1) % len(normalized)]
        cross = current.x * next_vertex.y - next_vertex.x * current.y
        cx += (current.x + next_vertex.x) * cross
        cy += (current.y + next_vertex.y) * cross
    return Point(cx * factor, cy * factor)


def centered_polygon_vertices(vertices: list[Point]) -> tuple[Point, list[Point]]:
    normalized = normalize_polygon_vertices(vertices)
    center = polygon_centroid(normalized)
    return (
        center,
        [Point(vertex.x - center.x, vertex.y - center.y) for vertex in normalized],
    )


def polygon_local_bounds(vertices: list[Point]) -> BoundingBox:
    normalized = normalize_polygon_vertices(vertices)
    if not normalized:
        return BoundingBox(0.0, 0.0, 0.0, 0.0)

    return BoundingBox(
        min_x=min(vertex.x for vertex in normalized),
        min_y=min(vertex.y for vertex in normalized),
        max_x=max(vertex.x for vertex in normalized),
        max_y=max(vertex.y for vertex in normalized),
    )


def polygon_world_vertices(center: Point, vertices_local: list[Point]) -> list[Point]:
    return [
        Point(center.x + vertex.x, center.y + vertex.y)
        for vertex in normalize_polygon_vertices(vertices_local)
    ]


def polygon_size_from_local_vertices(vertices_local: list[Point], polygon_scale: float = 100.0) -> ClusterSize:
    normalized = normalize_polygon_vertices(vertices_local)
    bounds = polygon_local_bounds(normalized)
    width = max(0.0, bounds.max_x - bounds.min_x)
    height = max(0.0, bounds.max_y - bounds.min_y)
    return ClusterSize(
        radius=max(width, height) / 2.0,
        width=width,
        height=height,
        polygon_scale=polygon_scale,
        vertices_local=[Point(vertex.x, vertex.y) for vertex in normalized],
    )


def polygon_geometry_from_world_vertices(
    vertices_world: list[Point],
    polygon_scale: float = 100.0,
) -> tuple[Point, ClusterSize]:
    center, vertices_local = centered_polygon_vertices(vertices_world)
    return center, polygon_size_from_local_vertices(vertices_local, polygon_scale=polygon_scale)


def _function_sample_count(sample_count: int | None = None) -> int:
    if sample_count is not None:
        return max(8, sample_count)
    return max(8, get_app_config().generation.function_sample_count)


def build_function_curve_local_points(
    size: ClusterSize,
    sample_count: int | None = None,
) -> list[Point]:
    if size.function_range_end <= size.function_range_start:
        raise FunctionDefinitionError("range")
    if size.function_thickness <= 0.0:
        raise FunctionDefinitionError("thickness")

    count = _function_sample_count(sample_count)
    points: list[Point] = []
    for index in range(count):
        ratio = index / (count - 1)
        independent = size.function_range_start + (size.function_range_end - size.function_range_start) * ratio
        dependent = evaluate_function_expression(
            size.function_expression,
            size.function_orientation,
            independent,
        )
        if size.function_orientation is FunctionOrientation.Y_OF_X:
            points.append(Point(independent, dependent))
        else:
            points.append(Point(dependent, independent))
    return points


def build_function_band_local_vertices(
    size: ClusterSize,
    sample_count: int | None = None,
) -> list[Point]:
    curve_points = build_function_curve_local_points(size, sample_count=sample_count)
    half_thickness = size.function_thickness / 2.0
    outer: list[Point] = []
    inner: list[Point] = []

    for index, point in enumerate(curve_points):
        if index == 0:
            tangent_x = curve_points[1].x - point.x
            tangent_y = curve_points[1].y - point.y
        elif index == len(curve_points) - 1:
            tangent_x = point.x - curve_points[index - 1].x
            tangent_y = point.y - curve_points[index - 1].y
        else:
            tangent_x = curve_points[index + 1].x - curve_points[index - 1].x
            tangent_y = curve_points[index + 1].y - curve_points[index - 1].y

        tangent_length = math.hypot(tangent_x, tangent_y)
        if tangent_length <= POLYGON_EPSILON:
            raise FunctionDefinitionError("geometry")

        normal_x = -tangent_y / tangent_length
        normal_y = tangent_x / tangent_length
        outer.append(Point(point.x + normal_x * half_thickness, point.y + normal_y * half_thickness))
        inner.append(Point(point.x - normal_x * half_thickness, point.y - normal_y * half_thickness))

    vertices = normalize_polygon_vertices(outer + list(reversed(inner)))
    if len(vertices) < 3 or not is_simple_polygon(vertices):
        raise FunctionDefinitionError("geometry")
    return vertices


def function_size_from_parameters(
    expression: str,
    orientation: FunctionOrientation,
    range_start: float,
    range_end: float,
    thickness: float,
    sample_count: int | None = None,
    fallback_vertices_local: list[Point] | None = None,
) -> ClusterSize:
    draft = ClusterSize(
        function_expression=expression,
        function_orientation=orientation,
        function_range_start=range_start,
        function_range_end=range_end,
        function_thickness=thickness,
        vertices_local=[Point(vertex.x, vertex.y) for vertex in fallback_vertices_local or []],
    )
    vertices_local = build_function_band_local_vertices(draft, sample_count=sample_count)
    bounds = polygon_local_bounds(vertices_local)
    width = max(bounds.max_x - bounds.min_x, 0.0)
    height = max(bounds.max_y - bounds.min_y, 0.0)
    return ClusterSize(
        radius=max(width, height) / 2.0,
        width=width,
        height=height,
        polygon_scale=100.0,
        vertices_local=vertices_local,
        function_expression=expression,
        function_orientation=orientation,
        function_range_start=range_start,
        function_range_end=range_end,
        function_thickness=thickness,
    )


def validate_function_cluster_size(size: ClusterSize) -> list[str]:
    localizer = get_localizer()
    try:
        build_function_band_local_vertices(size)
    except FunctionDefinitionError as exc:
        if exc.code == "range":
            return [localizer.text("error.function_range_invalid")]
        if exc.code == "thickness":
            return [localizer.text("error.function_thickness_positive")]
        if exc.code == "geometry":
            return [localizer.text("error.function_geometry_invalid")]
        return [localizer.text("error.function_expression_invalid")]
    return []


def _vertices_signature(vertices: list[Point]) -> tuple[tuple[float, float], ...]:
    normalized = normalize_polygon_vertices(vertices)
    return tuple((vertex.x, vertex.y) for vertex in normalized)


@lru_cache(maxsize=512)
def _triangulated_polygon_payload(
    signature: tuple[tuple[float, float], ...],
) -> tuple[tuple[tuple[Point, Point, Point], ...], tuple[float, ...], float]:
    vertices = [Point(x, y) for x, y in signature]
    triangles = tuple(triangulate_polygon(vertices))
    areas = tuple(abs(_cross(a, b, c)) / 2.0 for a, b, c in triangles)
    return triangles, areas, sum(areas)


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _point_on_segment(point: Point, a: Point, b: Point, epsilon: float = POLYGON_EPSILON) -> bool:
    if abs(_cross(a, b, point)) > epsilon:
        return False
    return (
        min(a.x, b.x) - epsilon <= point.x <= max(a.x, b.x) + epsilon
        and min(a.y, b.y) - epsilon <= point.y <= max(a.y, b.y) + epsilon
    )


def _orientation(a: Point, b: Point, c: Point, epsilon: float = POLYGON_EPSILON) -> int:
    value = _cross(a, b, c)
    if value > epsilon:
        return 1
    if value < -epsilon:
        return -1
    return 0


def _segments_intersect(a1: Point, a2: Point, b1: Point, b2: Point, epsilon: float = POLYGON_EPSILON) -> bool:
    o1 = _orientation(a1, a2, b1, epsilon)
    o2 = _orientation(a1, a2, b2, epsilon)
    o3 = _orientation(b1, b2, a1, epsilon)
    o4 = _orientation(b1, b2, a2, epsilon)

    if o1 != o2 and o3 != o4:
        return True

    if o1 == 0 and _point_on_segment(b1, a1, a2, epsilon):
        return True
    if o2 == 0 and _point_on_segment(b2, a1, a2, epsilon):
        return True
    if o3 == 0 and _point_on_segment(a1, b1, b2, epsilon):
        return True
    if o4 == 0 and _point_on_segment(a2, b1, b2, epsilon):
        return True
    return False


def is_simple_polygon(vertices: list[Point], epsilon: float = POLYGON_EPSILON) -> bool:
    normalized = normalize_polygon_vertices(vertices, epsilon)
    count = len(normalized)
    if count < 3:
        return False
    if abs(polygon_area(normalized)) <= epsilon:
        return False

    for left in range(count):
        for right in range(left + 1, count):
            if _distance(normalized[left], normalized[right]) <= epsilon:
                return False

    for left in range(count):
        a1 = normalized[left]
        a2 = normalized[(left + 1) % count]
        for right in range(left + 1, count):
            if left == right:
                continue
            if (left + 1) % count == right:
                continue
            if left == (right + 1) % count:
                continue
            b1 = normalized[right]
            b2 = normalized[(right + 1) % count]
            if _segments_intersect(a1, a2, b1, b2, epsilon):
                return False
    return True


def validate_polygon_vertices(vertices: list[Point]) -> list[str]:
    localizer = get_localizer()
    normalized = normalize_polygon_vertices(vertices)
    if len(normalized) < 3:
        return [localizer.text("error.polygon_vertex_count")]
    if not is_simple_polygon(normalized):
        return [localizer.text("error.polygon_simple")]
    return []


def _distance_point_to_segment(point: Point, a: Point, b: Point) -> float:
    dx = b.x - a.x
    dy = b.y - a.y
    length_squared = dx * dx + dy * dy
    if length_squared <= POLYGON_EPSILON:
        return _distance(point, a)
    projection = ((point.x - a.x) * dx + (point.y - a.y) * dy) / length_squared
    projection = max(0.0, min(1.0, projection))
    closest = Point(a.x + projection * dx, a.y + projection * dy)
    return _distance(point, closest)


def point_in_polygon(point: Point, vertices: list[Point]) -> bool:
    normalized = normalize_polygon_vertices(vertices)
    if len(normalized) < 3:
        return False

    inside = False
    for index, current in enumerate(normalized):
        next_vertex = normalized[(index + 1) % len(normalized)]
        if _point_on_segment(point, current, next_vertex):
            return True

        intersects = ((current.y > point.y) != (next_vertex.y > point.y)) and (
            point.x
            < (next_vertex.x - current.x) * (point.y - current.y) / (next_vertex.y - current.y + 1e-12) + current.x
        )
        if intersects:
            inside = not inside
    return inside


def _point_in_triangle(point: Point, a: Point, b: Point, c: Point) -> bool:
    c1 = _cross(a, b, point)
    c2 = _cross(b, c, point)
    c3 = _cross(c, a, point)
    has_negative = c1 < -POLYGON_EPSILON or c2 < -POLYGON_EPSILON or c3 < -POLYGON_EPSILON
    has_positive = c1 > POLYGON_EPSILON or c2 > POLYGON_EPSILON or c3 > POLYGON_EPSILON
    return not (has_negative and has_positive)


def triangulate_polygon(vertices: list[Point]) -> list[tuple[Point, Point, Point]]:
    normalized = normalize_polygon_vertices(vertices)
    if validate_polygon_vertices(normalized):
        return []

    orientation = 1.0 if polygon_area(normalized) > 0.0 else -1.0
    indices = list(range(len(normalized)))
    triangles: list[tuple[Point, Point, Point]] = []
    guard = 0

    while len(indices) > 3 and guard < len(normalized) * len(normalized):
        ear_found = False
        for position, vertex_index in enumerate(indices):
            prev_index = indices[position - 1]
            next_index = indices[(position + 1) % len(indices)]
            a = normalized[prev_index]
            b = normalized[vertex_index]
            c = normalized[next_index]

            if orientation * _cross(a, b, c) <= POLYGON_EPSILON:
                continue

            contains_other = False
            for other_index in indices:
                if other_index in (prev_index, vertex_index, next_index):
                    continue
                if _point_in_triangle(normalized[other_index], a, b, c):
                    contains_other = True
                    break
            if contains_other:
                continue

            triangles.append((a, b, c))
            del indices[position]
            ear_found = True
            break

        if not ear_found:
            return []
        guard += 1

    if len(indices) == 3:
        triangles.append(tuple(normalized[index] for index in indices))
    return triangles


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


class PolygonShape(ClusterShape):
    kind = ShapeKind.POLYGON
    label = "Polygon"

    def _world_vertices(self, center: Point, size: ClusterSize) -> list[Point]:
        return polygon_world_vertices(center, size.vertices_local)

    def draw_outline(self, context: cairo.Context, center: Point, size: ClusterSize) -> None:
        vertices = self._world_vertices(center, size)
        if len(vertices) < 2:
            return
        context.move_to(vertices[0].x, vertices[0].y)
        for vertex in vertices[1:]:
            context.line_to(vertex.x, vertex.y)
        context.close_path()

    def sample_point(self, center: Point, size: ClusterSize, rng: random.Random) -> Point:
        triangles = triangulate_polygon(size.vertices_local)
        if not triangles:
            return Point(center.x, center.y)

        areas = [abs(_cross(a, b, c)) / 2.0 for a, b, c in triangles]
        total_area = sum(areas)
        target = rng.uniform(0.0, total_area)
        cumulative = 0.0
        triangle = triangles[-1]
        for current_triangle, area in zip(triangles, areas, strict=True):
            cumulative += area
            if target <= cumulative:
                triangle = current_triangle
                break

        a, b, c = triangle
        r1 = math.sqrt(rng.random())
        r2 = rng.random()
        local_x = (1.0 - r1) * a.x + r1 * (1.0 - r2) * b.x + r1 * r2 * c.x
        local_y = (1.0 - r1) * a.y + r1 * (1.0 - r2) * b.y + r1 * r2 * c.y
        return Point(center.x + local_x, center.y + local_y)

    def edge_distance(self, point: Point, center: Point, size: ClusterSize) -> float:
        vertices = self._world_vertices(center, size)
        if len(vertices) < 2:
            return math.inf

        min_distance = min(
            _distance_point_to_segment(point, vertices[index], vertices[(index + 1) % len(vertices)])
            for index in range(len(vertices))
        )
        if point_in_polygon(point, vertices):
            return -min_distance
        return min_distance

    def bounding_box(self, center: Point, size: ClusterSize) -> BoundingBox:
        local_bounds = polygon_local_bounds(size.vertices_local)
        return BoundingBox(
            min_x=center.x + local_bounds.min_x,
            min_y=center.y + local_bounds.min_y,
            max_x=center.x + local_bounds.max_x,
            max_y=center.y + local_bounds.max_y,
        )


class FunctionShape(ClusterShape):
    kind = ShapeKind.FUNCTION
    label = "Function"

    def _local_vertices(self, size: ClusterSize) -> list[Point]:
        if size.vertices_local:
            return normalize_polygon_vertices(size.vertices_local)
        try:
            return build_function_band_local_vertices(size)
        except FunctionDefinitionError:
            return []

    def _world_vertices(self, center: Point, size: ClusterSize) -> list[Point]:
        return polygon_world_vertices(center, self._local_vertices(size))

    def draw_outline(self, context: cairo.Context, center: Point, size: ClusterSize) -> None:
        vertices = self._world_vertices(center, size)
        if len(vertices) < 2:
            return
        context.move_to(vertices[0].x, vertices[0].y)
        for vertex in vertices[1:]:
            context.line_to(vertex.x, vertex.y)
        context.close_path()

    def sample_point(self, center: Point, size: ClusterSize, rng: random.Random) -> Point:
        local_vertices = self._local_vertices(size)
        triangles, areas, total_area = _triangulated_polygon_payload(_vertices_signature(local_vertices))
        if not triangles or total_area <= 0.0:
            return Point(center.x, center.y)

        target = rng.uniform(0.0, total_area)
        cumulative = 0.0
        chosen = triangles[-1]
        for triangle, area in zip(triangles, areas, strict=True):
            cumulative += area
            if target <= cumulative:
                chosen = triangle
                break

        a, b, c = chosen
        r1 = math.sqrt(rng.random())
        r2 = rng.random()
        local_x = (1.0 - r1) * a.x + r1 * (1.0 - r2) * b.x + r1 * r2 * c.x
        local_y = (1.0 - r1) * a.y + r1 * (1.0 - r2) * b.y + r1 * r2 * c.y
        return Point(center.x + local_x, center.y + local_y)

    def edge_distance(self, point: Point, center: Point, size: ClusterSize) -> float:
        vertices = self._world_vertices(center, size)
        if len(vertices) < 2:
            return math.inf

        min_distance = min(
            _distance_point_to_segment(point, vertices[index], vertices[(index + 1) % len(vertices)])
            for index in range(len(vertices))
        )
        if point_in_polygon(point, vertices):
            return -min_distance
        return min_distance

    def bounding_box(self, center: Point, size: ClusterSize) -> BoundingBox:
        local_bounds = polygon_local_bounds(self._local_vertices(size))
        return BoundingBox(
            min_x=center.x + local_bounds.min_x,
            min_y=center.y + local_bounds.min_y,
            max_x=center.x + local_bounds.max_x,
            max_y=center.y + local_bounds.max_y,
        )


SHAPE_REGISTRY: dict[ShapeKind, ClusterShape] = {
    ShapeKind.CIRCLE: CircleShape(),
    ShapeKind.RECTANGLE: RectangleShape(),
    ShapeKind.POLYGON: PolygonShape(),
    ShapeKind.FUNCTION: FunctionShape(),
}


def get_shape(shape_kind: ShapeKind) -> ClusterShape:
    return SHAPE_REGISTRY[shape_kind]

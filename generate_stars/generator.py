from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import math
import random
import textwrap
from typing import Callable

from .config import AppConfig, get_app_config
from .localization import get_localizer
from .models import (
    AppState,
    CircleSize,
    ClusterConfig,
    ClusterInstance,
    ClusterSize,
    DistributionMode,
    FunctionSize,
    FunctionStarParameterValue,
    Point,
    PolygonSize,
    RandomStarParameterValue,
    RectangleSize,
    ShapeKind,
    StarParameterConfig,
    StarParameterMode,
    StarRecord,
)
from .shapes import BoundingBox, get_shape, validate_function_cluster_size, validate_polygon_vertices


class GenerationError(RuntimeError):
    """Raised when a valid star field cannot be generated."""


class ParameterFunctionDefinitionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class GeneratedField:
    cluster_configs: list[ClusterConfig]
    cluster_counts: list[int]
    stars: list[StarRecord]

    @property
    def points(self) -> list[Point]:
        return [star.point for star in self.stars]


def even_counts(total: int, buckets: int) -> list[int]:
    if buckets <= 0:
        return []
    base = total // buckets
    remainder = total % buckets
    return [base + (1 if index < remainder else 0) for index in range(buckets)]


def preview_cluster_counts(state: AppState) -> list[int] | None:
    if state.distribution_mode is DistributionMode.EQUAL:
        return even_counts(state.total_cluster_stars, len(state.clusters))
    if state.distribution_mode is DistributionMode.MANUAL:
        return [cluster.manual_star_count for cluster in state.clusters]
    return None


def ensure_cluster_storage(state: AppState) -> None:
    state.prune_selection()


def validate_cluster_size(shape_kind: ShapeKind, size: ClusterSize, label: str) -> list[str]:
    localizer = get_localizer()
    errors: list[str] = []
    if shape_kind is ShapeKind.CIRCLE:
        if not isinstance(size, CircleSize):
            errors.append(localizer.text("error.configuration_invalid"))
        elif size.radius <= 0.0:
            errors.append(localizer.text("error.radius_positive", label=label))
    if shape_kind is ShapeKind.RECTANGLE:
        if not isinstance(size, RectangleSize):
            errors.append(localizer.text("error.configuration_invalid"))
        else:
            if size.width <= 0.0:
                errors.append(localizer.text("error.width_positive", label=label))
            if size.height <= 0.0:
                errors.append(localizer.text("error.height_positive", label=label))
    if shape_kind is ShapeKind.POLYGON:
        if not isinstance(size, PolygonSize):
            errors.append(localizer.text("error.configuration_invalid"))
        else:
            for error in validate_polygon_vertices(size.vertices_local):
                errors.append(f"{label}: {error}")
    if shape_kind is ShapeKind.FUNCTION:
        if not isinstance(size, FunctionSize):
            errors.append(localizer.text("error.configuration_invalid"))
        else:
            for error in validate_function_cluster_size(size):
                errors.append(f"{label}: {error}")
    return errors


def validate_state(state: AppState) -> list[str]:
    ensure_cluster_storage(state)
    localizer = get_localizer()
    errors: list[str] = []
    if state.total_cluster_stars < 0:
        errors.append(localizer.text("error.cluster_total_negative"))
    if state.trash_star_count < 0:
        errors.append(localizer.text("error.trash_count_negative"))
    if state.trash_min_distance < 0.0:
        errors.append(localizer.text("error.trash_distance_negative"))
    if state.trash_max_distance < 0.0:
        errors.append(localizer.text("error.trash_max_distance_negative"))
    if state.trash_max_distance < state.trash_min_distance:
        errors.append(localizer.text("error.trash_distance_range_invalid"))

    errors.extend(
        validate_cluster_size(
            ShapeKind.CIRCLE,
            state.placement_circle_size,
            localizer.text("error.circle_placement"),
        )
    )
    errors.extend(
        validate_cluster_size(
            ShapeKind.RECTANGLE,
            state.placement_rectangle_size,
            localizer.text("error.rectangle_placement"),
        )
    )
    errors.extend(
        validate_cluster_size(
            ShapeKind.FUNCTION,
            state.placement_function_size,
            localizer.text("error.function_placement"),
        )
    )

    for index, cluster in enumerate(state.clusters):
        errors.extend(
            validate_cluster_size(
                cluster.shape_kind,
                cluster.size,
                localizer.text("error.cluster", index=index + 1),
            )
        )

    if not state.clusters and state.total_cluster_stars > 0:
        errors.append(localizer.text("error.cluster_required"))

    if state.distribution_mode is DistributionMode.DEVIATION and state.deviation_percent < 0.0:
        errors.append(localizer.text("error.deviation_negative"))

    if state.star_parameter.enabled:
        if not state.star_parameter.name.strip():
            errors.append(localizer.text("error.parameter_name_empty"))
        if state.star_parameter.mode is StarParameterMode.RANDOM:
            if not isinstance(state.star_parameter.value, RandomStarParameterValue):
                errors.append(localizer.text("error.configuration_invalid"))
            elif state.star_parameter.value.max_value < state.star_parameter.value.min_value:
                errors.append(localizer.text("error.parameter_range_invalid"))
        if state.star_parameter.mode is StarParameterMode.FUNCTION:
            if not isinstance(state.star_parameter.value, FunctionStarParameterValue):
                errors.append(localizer.text("error.configuration_invalid"))
            else:
                try:
                    compile_parameter_function(state.star_parameter.value.function_body)
                except ParameterFunctionDefinitionError:
                    errors.append(localizer.text("error.parameter_function_invalid"))

    if state.distribution_mode is DistributionMode.MANUAL:
        if any(cluster.manual_star_count < 0 for cluster in state.clusters):
            errors.append(localizer.text("error.manual_counts_negative"))
        if sum(cluster.manual_star_count for cluster in state.clusters) != state.total_cluster_stars:
            errors.append(localizer.text("error.manual_counts_total"))

    return errors


def generate_ring_centers(
    shape_kind: ShapeKind,
    sizes: Sequence[ClusterSize],
    config: AppConfig | None = None,
) -> list[Point]:
    count = len(sizes)
    if count <= 0:
        return []

    config = config or get_app_config()
    spans = [size.max_span() for size in sizes]
    step = math.tau / count

    centers: list[Point] = []
    for index, span in enumerate(spans):
        radius = max(
            count * (span + config.generation.layout_ring_padding) / math.tau,
            span / 2.0 + config.generation.layout_origin_padding,
        )
        centers.append(
            Point(
                x=math.cos(step * index) * radius,
                y=math.sin(step * index) * radius,
            )
        )
    return centers


def resolve_cluster_configs(state: AppState) -> list[ClusterConfig]:
    ensure_cluster_storage(state)
    return [cluster.to_config() for cluster in state.clusters]


def cluster_configs_from_clusters(clusters: Sequence[ClusterInstance]) -> list[ClusterConfig]:
    return [cluster.to_config() for cluster in clusters]


def allocate_cluster_counts(
    total: int,
    cluster_count: int,
    mode: DistributionMode,
    manual_counts: list[int],
    deviation_percent: float,
    rng: random.Random,
) -> list[int]:
    localizer = get_localizer()
    if cluster_count <= 0:
        if total == 0:
            return []
        raise GenerationError(localizer.text("error.cluster_required"))

    if mode is DistributionMode.EQUAL:
        return even_counts(total, cluster_count)

    if mode is DistributionMode.MANUAL:
        if len(manual_counts) != cluster_count:
            raise GenerationError(localizer.text("error.manual_counts_sync"))
        if sum(manual_counts) != total:
            raise GenerationError(localizer.text("error.manual_counts_total"))
        return list(manual_counts)

    spread = max(0.0, deviation_percent) / 100.0
    low = max(0.0, 1.0 - spread)
    high = 1.0 + spread
    weights = [rng.uniform(low, high) for _ in range(cluster_count)]
    if not any(weight > 0.0 for weight in weights):
        return even_counts(total, cluster_count)

    scaled = [weight / sum(weights) * total for weight in weights]
    counts = [math.floor(value) for value in scaled]
    remainder = total - sum(counts)
    fractions = sorted(
        ((scaled[index] - counts[index], index) for index in range(cluster_count)),
        reverse=True,
    )
    for _, index in fractions[:remainder]:
        counts[index] += 1
    return counts


def combined_bounding_box(
    cluster_configs: list[ClusterConfig],
    config: AppConfig | None = None,
) -> BoundingBox:
    config = config or get_app_config()
    if not cluster_configs:
        return BoundingBox(
            -config.generation.empty_cluster_bounds_limit,
            -config.generation.empty_cluster_bounds_limit,
            config.generation.empty_cluster_bounds_limit,
            config.generation.empty_cluster_bounds_limit,
        )

    first_shape = get_shape(cluster_configs[0].shape_kind)
    first = first_shape.bounding_box(cluster_configs[0].center, cluster_configs[0].size)
    min_x, min_y, max_x, max_y = first.min_x, first.min_y, first.max_x, first.max_y
    for config in cluster_configs[1:]:
        shape = get_shape(config.shape_kind)
        bounds = shape.bounding_box(config.center, config.size)
        min_x = min(min_x, bounds.min_x)
        min_y = min(min_y, bounds.min_y)
        max_x = max(max_x, bounds.max_x)
        max_y = max(max_y, bounds.max_y)
    return BoundingBox(min_x, min_y, max_x, max_y)


def generate_cluster_points(
    cluster_configs: list[ClusterConfig],
    cluster_counts: list[int],
    rng: random.Random,
) -> list[Point]:
    points: list[Point] = []
    for config, count in zip(cluster_configs, cluster_counts, strict=True):
        shape = get_shape(config.shape_kind)
        for _ in range(count):
            points.append(shape.sample_point(config.center, config.size, rng))
    return points


def generate_trash_points(
    cluster_configs: list[ClusterConfig],
    count: int,
    min_edge_distance: float,
    max_edge_distance: float,
    rng: random.Random,
    config: AppConfig | None = None,
) -> list[Point]:
    if count <= 0:
        return []

    config = config or get_app_config()
    base_bounds = combined_bounding_box(cluster_configs, config)
    base_padding = max(
        config.generation.trash_bounds_padding_min,
        min_edge_distance + config.generation.trash_bounds_padding_extra,
    )
    padding = min(base_padding, max_edge_distance) if cluster_configs else base_padding
    bounds = base_bounds.expanded(padding)

    points: list[Point] = []
    attempts = 0
    max_attempts = max(
        config.generation.trash_placement_attempts_min,
        count * config.generation.trash_placement_attempts_per_star,
    )
    while len(points) < count and attempts < max_attempts:
        attempts += 1
        candidate = Point(
            x=rng.uniform(bounds.min_x, bounds.max_x),
            y=rng.uniform(bounds.min_y, bounds.max_y),
        )
        if not cluster_configs:
            points.append(candidate)
            continue

        edge_distances = [
            get_shape(cluster_config.shape_kind).edge_distance(candidate, cluster_config.center, cluster_config.size)
            for cluster_config in cluster_configs
        ]
        if all(distance >= min_edge_distance for distance in edge_distances) and min(edge_distances) <= max_edge_distance:
            points.append(candidate)

    if len(points) != count:
        raise GenerationError(get_localizer().text("error.trash_placement_failed"))
    return points


def generate_star_records(
    points: Sequence[Point],
    parameter: StarParameterConfig,
    rng: random.Random,
) -> list[StarRecord]:
    if not parameter.enabled:
        return [StarRecord(point.x, point.y) for point in points]

    if parameter.mode is StarParameterMode.FUNCTION:
        evaluator = _build_parameter_function_evaluator(parameter.function_body)
        return [
            StarRecord(
                point.x,
                point.y,
                evaluator(),
            )
            for point in points
        ]

    return [
        StarRecord(
            point.x,
            point.y,
            rng.uniform(parameter.min_value, parameter.max_value),
        )
        for point in points
    ]


def _parameter_function_source(function_body: str) -> str:
    normalized_body = function_body.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized_body.strip():
        raise ParameterFunctionDefinitionError("empty")
    return f"def _third_parameter_value():\n{textwrap.indent(normalized_body, '    ')}\n"


def compile_parameter_function(function_body: str) -> Callable[[], object]:
    source = _parameter_function_source(function_body)
    namespace: dict[str, object] = {}
    try:
        code = compile(source, "<star-parameter-function>", "exec")
        exec(code, namespace, namespace)
    except Exception as exc:
        raise ParameterFunctionDefinitionError("invalid") from exc

    candidate = namespace.get("_third_parameter_value")
    if not callable(candidate):
        raise ParameterFunctionDefinitionError("invalid")
    return candidate


def _build_parameter_function_evaluator(function_body: str) -> Callable[[], str]:
    localizer = get_localizer()
    try:
        parameter_function = compile_parameter_function(function_body)
    except ParameterFunctionDefinitionError as exc:
        raise GenerationError(localizer.text("error.parameter_function_invalid")) from exc

    def evaluate() -> str:
        try:
            value = parameter_function()
        except Exception as exc:
            raise GenerationError(localizer.text("error.parameter_function_runtime")) from exc
        if not isinstance(value, str):
            raise GenerationError(localizer.text("error.parameter_function_return_type"))
        if not value or any(character.isspace() for character in value):
            raise GenerationError(localizer.text("error.parameter_string_token_invalid"))
        return value

    return evaluate


def preview_parameter_function_result(function_body: str) -> tuple[str, bool]:
    try:
        evaluator = _build_parameter_function_evaluator(function_body)
        return evaluator(), False
    except GenerationError as exc:
        return str(exc), True


def generate_star_field(state: AppState, rng: random.Random | None = None) -> GeneratedField:
    errors = validate_state(state)
    if errors:
        raise GenerationError(errors[0])

    config = get_app_config()
    rng = rng or random.Random()
    cluster_configs = resolve_cluster_configs(state)
    cluster_counts = allocate_cluster_counts(
        total=state.total_cluster_stars,
        cluster_count=len(state.clusters),
        mode=state.distribution_mode,
        manual_counts=[cluster.manual_star_count for cluster in state.clusters],
        deviation_percent=state.deviation_percent,
        rng=rng,
    )

    points = generate_cluster_points(cluster_configs, cluster_counts, rng)
    points.extend(
        generate_trash_points(
            cluster_configs=cluster_configs,
            count=state.trash_star_count,
            min_edge_distance=state.trash_min_distance,
            max_edge_distance=state.trash_max_distance,
            rng=rng,
            config=config,
        )
    )
    stars = generate_star_records(points, state.star_parameter, rng)
    rng.shuffle(stars)
    return GeneratedField(
        cluster_configs=cluster_configs,
        cluster_counts=cluster_counts,
        stars=stars,
    )


def format_points_for_export(
    stars: Sequence[Point | StarRecord],
    parameter_name: str | None = None,
    precision: int | None = None,
) -> str:
    if precision is None:
        precision = get_app_config().generation.export_coordinate_precision

    export_parameter_name = parameter_name.strip() if parameter_name and parameter_name.strip() else None
    has_parameter_values = any(isinstance(star, StarRecord) and star.parameter_value is not None for star in stars)
    if export_parameter_name is None and has_parameter_values:
        export_parameter_name = get_app_config().defaults.star_parameter_name

    lines = [f"X Y {export_parameter_name}" if export_parameter_name else "X Y"]
    for star in stars:
        if isinstance(star, StarRecord):
            x = star.x
            y = star.y
            parameter_value = star.parameter_value
        else:
            x = star.x
            y = star.y
            parameter_value = None

        x_value = f"{x:.{precision}f}".replace(".", ",")
        y_value = f"{y:.{precision}f}".replace(".", ",")
        if export_parameter_name:
            if parameter_value is None:
                raise ValueError(get_localizer().text("error.parameter_export_requires_value"))
            if isinstance(parameter_value, str):
                if not parameter_value or any(character.isspace() for character in parameter_value):
                    raise ValueError(get_localizer().text("error.parameter_string_token_invalid"))
                parameter_text = parameter_value
            else:
                parameter_text = f"{parameter_value:.{precision}f}".replace(".", ",")
            lines.append(f"{x_value} {y_value} {parameter_text}")
            continue

        lines.append(f"{x_value} {y_value}")
    return "\n".join(lines) + "\n"

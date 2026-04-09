from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import math
import random

from .config import AppConfig, get_app_config
from .models import AppState, ClusterConfig, ClusterInstance, ClusterSize, DistributionMode, Point, ShapeKind, StarParameterConfig, StarRecord
from .shapes import BoundingBox, get_shape, validate_polygon_vertices


class GenerationError(RuntimeError):
    """Raised when a valid star field cannot be generated."""


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
    errors: list[str] = []
    if shape_kind is ShapeKind.CIRCLE and size.radius <= 0.0:
        errors.append(f"{label} radius must be greater than zero.")
    if shape_kind is ShapeKind.RECTANGLE:
        if size.width <= 0.0:
            errors.append(f"{label} width must be greater than zero.")
        if size.height <= 0.0:
            errors.append(f"{label} height must be greater than zero.")
    if shape_kind is ShapeKind.POLYGON:
        for error in validate_polygon_vertices(size.vertices_local):
            errors.append(f"{label}: {error}")
    return errors


def validate_state(state: AppState) -> list[str]:
    ensure_cluster_storage(state)
    errors: list[str] = []
    if state.total_cluster_stars < 0:
        errors.append("Total cluster stars cannot be negative.")
    if state.trash_star_count < 0:
        errors.append("Trash star count cannot be negative.")
    if state.trash_min_distance < 0.0:
        errors.append("Trash star minimum distance cannot be negative.")

    errors.extend(validate_cluster_size(ShapeKind.CIRCLE, state.placement_circle_size, "Circle placement"))
    errors.extend(validate_cluster_size(ShapeKind.RECTANGLE, state.placement_rectangle_size, "Rectangle placement"))

    for index, cluster in enumerate(state.clusters):
        errors.extend(validate_cluster_size(cluster.shape_kind, cluster.size, f"Cluster {index + 1}"))

    if not state.clusters and state.total_cluster_stars > 0:
        errors.append("Cluster stars require at least one cluster.")

    if state.distribution_mode is DistributionMode.DEVIATION and state.deviation_percent < 0.0:
        errors.append("Deviation percent cannot be negative.")

    if state.star_parameter.enabled:
        if not state.star_parameter.name.strip():
            errors.append("Star parameter name cannot be empty.")
        if state.star_parameter.max_value < state.star_parameter.min_value:
            errors.append("Star parameter max must be greater than or equal to min.")

    if state.distribution_mode is DistributionMode.MANUAL:
        if any(cluster.manual_star_count < 0 for cluster in state.clusters):
            errors.append("Manual cluster counts cannot be negative.")
        if sum(cluster.manual_star_count for cluster in state.clusters) != state.total_cluster_stars:
            errors.append("Manual cluster counts must sum to the total cluster stars.")

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
    spans = [size.max_span(shape_kind) for size in sizes]
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
    if cluster_count <= 0:
        if total == 0:
            return []
        raise GenerationError("Cluster stars require at least one cluster.")

    if mode is DistributionMode.EQUAL:
        return even_counts(total, cluster_count)

    if mode is DistributionMode.MANUAL:
        if len(manual_counts) != cluster_count:
            raise GenerationError("Manual counts are out of sync with the cluster count.")
        if sum(manual_counts) != total:
            raise GenerationError("Manual cluster counts must sum to the total cluster stars.")
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
    rng: random.Random,
    config: AppConfig | None = None,
) -> list[Point]:
    if count <= 0:
        return []

    config = config or get_app_config()
    base_bounds = combined_bounding_box(cluster_configs, config)
    padding = max(
        config.generation.trash_bounds_padding_min,
        min_edge_distance + config.generation.trash_bounds_padding_extra,
    )
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
        if all(
            get_shape(cluster_config.shape_kind).edge_distance(candidate, cluster_config.center, cluster_config.size)
            >= min_edge_distance
            for cluster_config in cluster_configs
        ):
            points.append(candidate)

    if len(points) != count:
        raise GenerationError(
            "Could not place all trash stars with the requested minimum distance. "
            "Reduce the trash-star count or the minimum distance."
        )
    return points


def generate_star_records(
    points: Sequence[Point],
    parameter: StarParameterConfig,
    rng: random.Random,
) -> list[StarRecord]:
    if not parameter.enabled:
        return [StarRecord(point.x, point.y) for point in points]

    return [
        StarRecord(
            point.x,
            point.y,
            rng.uniform(parameter.min_value, parameter.max_value),
        )
        for point in points
    ]


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
                raise ValueError("Parameter export requires a value for every star.")
            parameter_text = f"{parameter_value:.{precision}f}".replace(".", ",")
            lines.append(f"{x_value} {y_value} {parameter_text}")
            continue

        lines.append(f"{x_value} {y_value}")
    return "\n".join(lines) + "\n"

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import math
import random

from .config import AppConfig, get_app_config
from .models import AppState, ClusterConfig, ClusterSize, DistributionMode, Point, ShapeKind
from .shapes import BoundingBox, get_shape


class GenerationError(RuntimeError):
    """Raised when a valid star field cannot be generated."""


@dataclass(frozen=True, slots=True)
class GeneratedField:
    cluster_configs: list[ClusterConfig]
    cluster_counts: list[int]
    points: list[Point]


def even_counts(total: int, buckets: int) -> list[int]:
    if buckets <= 0:
        return []
    base = total // buckets
    remainder = total % buckets
    return [base + (1 if index < remainder else 0) for index in range(buckets)]


def preview_cluster_counts(state: AppState) -> list[int] | None:
    ensure_cluster_storage(state)
    if state.distribution_mode is DistributionMode.EQUAL:
        return even_counts(state.total_cluster_stars, state.cluster_count)
    if state.distribution_mode is DistributionMode.MANUAL:
        return list(state.manual_counts[: state.cluster_count])
    return None


def ensure_cluster_storage(state: AppState) -> None:
    current = len(state.cluster_centers)
    if current < state.cluster_count:
        state.cluster_centers.extend(Point(0.0, 0.0) for _ in range(state.cluster_count - current))
    else:
        del state.cluster_centers[state.cluster_count :]

    override_current = len(state.size_overrides_enabled)
    if override_current < state.cluster_count:
        state.size_overrides_enabled.extend(False for _ in range(state.cluster_count - override_current))
    else:
        del state.size_overrides_enabled[state.cluster_count :]

    size_current = len(state.size_overrides)
    if size_current < state.cluster_count:
        state.size_overrides.extend(state.shared_size.copy() for _ in range(state.cluster_count - size_current))
    else:
        del state.size_overrides[state.cluster_count :]

    manual_current = len(state.manual_counts)
    if manual_current < state.cluster_count:
        state.manual_counts.extend(0 for _ in range(state.cluster_count - manual_current))
    else:
        del state.manual_counts[state.cluster_count :]


def validate_cluster_size(shape_kind: ShapeKind, size: ClusterSize, label: str) -> list[str]:
    errors: list[str] = []
    if shape_kind is ShapeKind.CIRCLE and size.radius <= 0.0:
        errors.append(f"{label} radius must be greater than zero.")
    if shape_kind is ShapeKind.RECTANGLE:
        if size.width <= 0.0:
            errors.append(f"{label} width must be greater than zero.")
        if size.height <= 0.0:
            errors.append(f"{label} height must be greater than zero.")
    return errors


def validate_state(state: AppState) -> list[str]:
    ensure_cluster_storage(state)
    errors: list[str] = []
    if state.cluster_count < 0:
        errors.append("Cluster count cannot be negative.")
    if state.total_cluster_stars < 0:
        errors.append("Total cluster stars cannot be negative.")
    if state.trash_star_count < 0:
        errors.append("Trash star count cannot be negative.")
    if state.trash_min_distance < 0.0:
        errors.append("Trash star minimum distance cannot be negative.")
    errors.extend(validate_cluster_size(state.shape_kind, state.shared_size, "Shared"))

    for index in range(state.cluster_count):
        if state.size_overrides_enabled[index]:
            errors.extend(
                validate_cluster_size(
                    state.shape_kind,
                    state.size_overrides[index],
                    f"Cluster {index + 1}",
                )
            )

    if state.cluster_count == 0 and state.total_cluster_stars > 0:
        errors.append("Cluster stars require at least one cluster.")

    if state.distribution_mode is DistributionMode.DEVIATION and state.deviation_percent < 0.0:
        errors.append("Deviation percent cannot be negative.")

    if state.distribution_mode is DistributionMode.MANUAL:
        if any(count < 0 for count in state.manual_counts):
            errors.append("Manual cluster counts cannot be negative.")
        if sum(state.manual_counts) != state.total_cluster_stars:
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
    return [
        ClusterConfig(center=state.cluster_centers[index], size=state.resolved_size(index).copy())
        for index in range(state.cluster_count)
    ]


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
    shape_kind: ShapeKind,
    config: AppConfig | None = None,
) -> BoundingBox:
    config = config or get_app_config()
    shape = get_shape(shape_kind)
    if not cluster_configs:
        return BoundingBox(
            -config.generation.empty_cluster_bounds_limit,
            -config.generation.empty_cluster_bounds_limit,
            config.generation.empty_cluster_bounds_limit,
            config.generation.empty_cluster_bounds_limit,
        )

    first = shape.bounding_box(cluster_configs[0].center, cluster_configs[0].size)
    min_x, min_y, max_x, max_y = first.min_x, first.min_y, first.max_x, first.max_y
    for config in cluster_configs[1:]:
        bounds = shape.bounding_box(config.center, config.size)
        min_x = min(min_x, bounds.min_x)
        min_y = min(min_y, bounds.min_y)
        max_x = max(max_x, bounds.max_x)
        max_y = max(max_y, bounds.max_y)
    return BoundingBox(min_x, min_y, max_x, max_y)


def generate_cluster_points(
    cluster_configs: list[ClusterConfig],
    shape_kind: ShapeKind,
    cluster_counts: list[int],
    rng: random.Random,
) -> list[Point]:
    shape = get_shape(shape_kind)
    points: list[Point] = []
    for config, count in zip(cluster_configs, cluster_counts, strict=True):
        for _ in range(count):
            points.append(shape.sample_point(config.center, config.size, rng))
    return points


def generate_trash_points(
    cluster_configs: list[ClusterConfig],
    shape_kind: ShapeKind,
    count: int,
    min_edge_distance: float,
    rng: random.Random,
    config: AppConfig | None = None,
) -> list[Point]:
    if count <= 0:
        return []

    config = config or get_app_config()
    shape = get_shape(shape_kind)
    base_bounds = combined_bounding_box(cluster_configs, shape_kind, config)
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
            shape.edge_distance(candidate, config.center, config.size) >= min_edge_distance
            for config in cluster_configs
        ):
            points.append(candidate)

    if len(points) != count:
        raise GenerationError(
            "Could not place all trash stars with the requested minimum distance. "
            "Reduce the trash-star count or the minimum distance."
        )
    return points


def generate_star_field(state: AppState, rng: random.Random | None = None) -> GeneratedField:
    errors = validate_state(state)
    if errors:
        raise GenerationError(errors[0])

    config = get_app_config()
    rng = rng or random.Random()
    cluster_configs = resolve_cluster_configs(state)
    cluster_counts = allocate_cluster_counts(
        total=state.total_cluster_stars,
        cluster_count=state.cluster_count,
        mode=state.distribution_mode,
        manual_counts=state.manual_counts,
        deviation_percent=state.deviation_percent,
        rng=rng,
    )

    points = generate_cluster_points(cluster_configs, state.shape_kind, cluster_counts, rng)
    points.extend(
        generate_trash_points(
            cluster_configs=cluster_configs,
            shape_kind=state.shape_kind,
            count=state.trash_star_count,
            min_edge_distance=state.trash_min_distance,
            rng=rng,
            config=config,
        )
    )
    rng.shuffle(points)
    return GeneratedField(
        cluster_configs=cluster_configs,
        cluster_counts=cluster_counts,
        points=points,
    )


def format_points_for_export(
    points: list[Point],
    precision: int | None = None,
) -> str:
    if precision is None:
        precision = get_app_config().generation.export_coordinate_precision
    lines = ["X Y"]
    for point in points:
        x_value = f"{point.x:.{precision}f}".replace(".", ",")
        y_value = f"{point.y:.{precision}f}".replace(".", ",")
        lines.append(f"{x_value} {y_value}")
    return "\n".join(lines) + "\n"

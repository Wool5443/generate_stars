from __future__ import annotations

import json
from pathlib import Path

from .generator import validate_cluster_size
from .localization import get_localizer
from .models import AppState, ClusterInstance, ClusterSize, FunctionOrientation, Point, ShapeKind


FORMAT_NAME = "generate_stars_cluster_configuration"
FORMAT_VERSION = 2
DEFAULT_CLUSTER_CONFIGURATION_FILENAME = "cluster_configuration.json"


class ClusterConfigurationError(RuntimeError):
    """Raised when a cluster configuration file cannot be parsed or used."""


def _point_payload(point: Point) -> dict[str, float]:
    return {
        "x": point.x,
        "y": point.y,
    }


def _cluster_size_payload(size: ClusterSize) -> dict[str, object]:
    return {
        "radius": size.radius,
        "width": size.width,
        "height": size.height,
        "polygon_scale": size.polygon_scale,
        "vertices_local": [_point_payload(vertex) for vertex in size.vertices_local],
        "function_expression": size.function_expression,
        "function_orientation": size.function_orientation.value,
        "function_range_start": size.function_range_start,
        "function_range_end": size.function_range_end,
        "function_thickness": size.function_thickness,
    }


def _cluster_payload(cluster: ClusterInstance) -> dict[str, object]:
    return {
        "shape_kind": cluster.shape_kind.value,
        "center": _point_payload(cluster.center),
        "size": _cluster_size_payload(cluster.size),
        "manual_star_count": cluster.manual_star_count,
    }


def cluster_configuration_payload(state: AppState) -> dict[str, object]:
    return {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "clusters": [_cluster_payload(cluster) for cluster in state.clusters],
    }


def format_cluster_configuration(state: AppState) -> str:
    return f"{json.dumps(cluster_configuration_payload(state), indent=2, ensure_ascii=False)}\n"


def save_cluster_configuration(state: AppState, output_path: Path) -> None:
    output_path.write_text(format_cluster_configuration(state), encoding="utf-8")


def load_cluster_configuration(path: Path) -> list[ClusterInstance]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ClusterConfigurationError(str(exc)) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ClusterConfigurationError(f"{get_localizer().text('error.configuration_invalid')}: {exc}") from exc
    return parse_cluster_configuration_payload(payload)


def parse_cluster_configuration_payload(payload: object) -> list[ClusterInstance]:
    root = _require_mapping(payload, "root")
    format_name = root.get("format")
    if format_name is not None and format_name != FORMAT_NAME:
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))

    clusters_payload = root.get("clusters")
    if not isinstance(clusters_payload, list):
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))

    clusters: list[ClusterInstance] = []
    for index, cluster_payload in enumerate(clusters_payload, start=1):
        clusters.append(_cluster_from_payload(cluster_payload, index=index))
    return clusters


def _cluster_from_payload(payload: object, *, index: int) -> ClusterInstance:
    localizer = get_localizer()
    mapping = _require_mapping(payload, f"clusters[{index - 1}]")

    shape_value = mapping.get("shape_kind")
    if not isinstance(shape_value, str):
        raise ClusterConfigurationError(localizer.text("error.configuration_invalid"))
    try:
        shape_kind = ShapeKind(shape_value)
    except ValueError as exc:
        raise ClusterConfigurationError(localizer.text("error.configuration_invalid")) from exc

    center = _point_from_payload(mapping.get("center"), f"clusters[{index - 1}].center")
    size = _cluster_size_from_payload(mapping.get("size"), shape_kind=shape_kind, index=index)

    manual_star_count = mapping.get("manual_star_count", 0)
    if not _is_number(manual_star_count):
        raise ClusterConfigurationError(localizer.text("error.configuration_invalid"))

    errors = validate_cluster_size(
        shape_kind,
        size,
        localizer.text("error.cluster", index=index),
    )
    if errors:
        raise ClusterConfigurationError(errors[0])

    return ClusterInstance(
        cluster_id=index,
        shape_kind=shape_kind,
        center=center,
        size=size,
        manual_star_count=int(manual_star_count),
    )


def _cluster_size_from_payload(payload: object, *, shape_kind: ShapeKind, index: int) -> ClusterSize:
    localizer = get_localizer()
    mapping = _require_mapping(payload, f"clusters[{index - 1}].size")

    vertices_payload = mapping.get("vertices_local", [])
    if not isinstance(vertices_payload, list):
        raise ClusterConfigurationError(localizer.text("error.configuration_invalid"))

    orientation_value = mapping.get("function_orientation", FunctionOrientation.Y_OF_X.value)
    if not isinstance(orientation_value, str):
        raise ClusterConfigurationError(localizer.text("error.configuration_invalid"))
    try:
        function_orientation = FunctionOrientation(orientation_value)
    except ValueError as exc:
        raise ClusterConfigurationError(localizer.text("error.configuration_invalid")) from exc

    return ClusterSize(
        radius=_float_value(mapping.get("radius", 10.0)),
        width=_float_value(mapping.get("width", 10.0)),
        height=_float_value(mapping.get("height", 10.0)),
        polygon_scale=_float_value(mapping.get("polygon_scale", 100.0)),
        vertices_local=[
            _point_from_payload(vertex, f"clusters[{index - 1}].size.vertices_local[{vertex_index}]")
            for vertex_index, vertex in enumerate(vertices_payload)
        ],
        function_expression=_string_value(mapping.get("function_expression", "0")),
        function_orientation=function_orientation,
        function_range_start=_float_value(mapping.get("function_range_start", -10.0)),
        function_range_end=_float_value(mapping.get("function_range_end", 10.0)),
        function_thickness=_float_value(mapping.get("function_thickness", 0.1)),
    )


def _point_from_payload(payload: object, label: str) -> Point:
    mapping = _require_mapping(payload, label)
    return Point(
        x=_float_value(mapping.get("x")),
        y=_float_value(mapping.get("y")),
    )


def _require_mapping(payload: object, label: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
    return payload


def _float_value(value: object) -> float:
    if not _is_number(value):
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
    return float(value)


def _string_value(value: object) -> str:
    if not isinstance(value, str):
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
    return value


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .generator import validate_cluster_size
from .localization import get_localizer
from .models import (
    AppState,
    CircleSize,
    ClusterInstance,
    ClusterSize,
    DistributionMode,
    FunctionOrientation,
    FunctionSize,
    FunctionStarParameterValue,
    Point,
    PolygonSize,
    RandomStarParameterValue,
    RectangleSize,
    ShapeKind,
    StarParameterConfig,
    StarParameterMode,
)
from .shapes import function_size_from_parameters


FORMAT_NAME = "generate_stars_cluster_configuration"
FORMAT_VERSION = 4
DEFAULT_CLUSTER_CONFIGURATION_FILENAME = "cluster_configuration.json"


class ClusterConfigurationError(RuntimeError):
    """Raised when a cluster configuration file cannot be parsed or used."""


@dataclass(slots=True)
class LoadedClusterConfiguration:
    clusters: list[ClusterInstance]
    placement_circle_size: CircleSize | None = None
    placement_rectangle_size: RectangleSize | None = None
    placement_function_size: FunctionSize | None = None
    selected_cluster_ids: list[int] | None = None
    next_cluster_id: int | None = None
    total_cluster_stars: int | None = None
    distribution_mode: DistributionMode | None = None
    deviation_percent: float | None = None
    star_parameter: StarParameterConfig | None = None
    trash_star_count: int | None = None
    trash_min_distance: float | None = None
    trash_max_distance: float | None = None
    star_parameter_function_body: str | None = None


def _point_payload(point: Point) -> dict[str, float]:
    return {
        "x": point.x,
        "y": point.y,
    }


def _cluster_size_payload(size: ClusterSize, shape_kind: ShapeKind) -> dict[str, object]:
    if shape_kind is ShapeKind.CIRCLE:
        if not isinstance(size, CircleSize):
            raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
        return {
            "radius": size.radius,
        }
    if shape_kind is ShapeKind.RECTANGLE:
        if not isinstance(size, RectangleSize):
            raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
        return {
            "width": size.width,
            "height": size.height,
        }
    if shape_kind is ShapeKind.FUNCTION:
        if not isinstance(size, FunctionSize):
            raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
        return {
            "function_expression": size.function_expression,
            "function_orientation": size.function_orientation.value,
            "function_range_start": size.function_range_start,
            "function_range_end": size.function_range_end,
            "function_thickness": size.function_thickness,
        }
    if not isinstance(size, PolygonSize):
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
    return {
        "polygon_scale": size.polygon_scale,
        "vertices_local": [_point_payload(vertex) for vertex in size.vertices_local],
    }


def _cluster_payload(cluster: ClusterInstance) -> dict[str, object]:
    return {
        "shape_kind": cluster.shape_kind.value,
        "center": _point_payload(cluster.center),
        "size": _cluster_size_payload(cluster.size, cluster.shape_kind),
        "manual_star_count": cluster.manual_star_count,
        "cluster_id": cluster.cluster_id,
    }


def cluster_configuration_payload(state: AppState) -> dict[str, object]:
    return {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "placement_circle_size": _cluster_size_payload(state.placement_circle_size, ShapeKind.CIRCLE),
        "placement_rectangle_size": _cluster_size_payload(state.placement_rectangle_size, ShapeKind.RECTANGLE),
        "placement_function_size": _cluster_size_payload(state.placement_function_size, ShapeKind.FUNCTION),
        "clusters": [_cluster_payload(cluster) for cluster in state.clusters],
        "selected_cluster_ids": list(state.selected_cluster_ids),
        "next_cluster_id": state.next_cluster_id,
        "total_cluster_stars": state.total_cluster_stars,
        "distribution_mode": state.distribution_mode.value,
        "deviation_percent": state.deviation_percent,
        "star_parameter": {
            "enabled": state.star_parameter.enabled,
            "name": state.star_parameter.name,
            "value": (
                {
                    "mode": "random",
                    "min_value": state.star_parameter.value.min_value,
                    "max_value": state.star_parameter.value.max_value,
                }
                if isinstance(state.star_parameter.value, RandomStarParameterValue)
                else {
                    "mode": "function",
                    "function_body": state.star_parameter.value.function_body,
                }
            ),
        },
        "trash_star_count": state.trash_star_count,
        "trash_min_distance": state.trash_min_distance,
        "trash_max_distance": state.trash_max_distance,
    }


def format_cluster_configuration(state: AppState) -> str:
    return f"{json.dumps(cluster_configuration_payload(state), indent=2, ensure_ascii=False)}\n"


def save_cluster_configuration(state: AppState, output_path: Path) -> None:
    output_path.write_text(format_cluster_configuration(state), encoding="utf-8")


def load_cluster_configuration(path: Path) -> LoadedClusterConfiguration:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ClusterConfigurationError(str(exc)) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ClusterConfigurationError(f"{get_localizer().text('error.configuration_invalid')}: {exc}") from exc
    return parse_cluster_configuration_payload(payload)


def parse_cluster_configuration_payload(payload: object) -> LoadedClusterConfiguration:
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
    cluster_ids = [cluster.cluster_id for cluster in clusters]
    if len(set(cluster_ids)) != len(cluster_ids):
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))

    placement_circle_size = _optional_cluster_size(
        root.get("placement_circle_size"),
        shape_kind=ShapeKind.CIRCLE,
    )
    placement_rectangle_size = _optional_cluster_size(
        root.get("placement_rectangle_size"),
        shape_kind=ShapeKind.RECTANGLE,
    )
    placement_function_size = _optional_cluster_size(
        root.get("placement_function_size"),
        shape_kind=ShapeKind.FUNCTION,
    )
    selected_cluster_ids = _optional_int_list(root.get("selected_cluster_ids"))
    next_cluster_id = _optional_int_value(root.get("next_cluster_id"), minimum=1)
    total_cluster_stars = _optional_int_value(root.get("total_cluster_stars"), minimum=0)
    distribution_mode = _optional_distribution_mode(root.get("distribution_mode"))
    deviation_percent = _optional_float_value(root.get("deviation_percent"))
    star_parameter = _optional_star_parameter(root.get("star_parameter"))
    trash_star_count = _optional_int_value(root.get("trash_star_count"), minimum=0)
    trash_min_distance = _optional_float_value(root.get("trash_min_distance"))
    trash_max_distance = _optional_float_value(root.get("trash_max_distance"))

    function_body_payload = root.get("star_parameter_function_body")
    if function_body_payload is None:
        star_parameter_function_body = None
    elif isinstance(function_body_payload, str):
        star_parameter_function_body = function_body_payload
    else:
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))

    return LoadedClusterConfiguration(
        clusters=clusters,
        placement_circle_size=placement_circle_size,
        placement_rectangle_size=placement_rectangle_size,
        placement_function_size=placement_function_size,
        selected_cluster_ids=selected_cluster_ids,
        next_cluster_id=next_cluster_id,
        total_cluster_stars=total_cluster_stars,
        distribution_mode=distribution_mode,
        deviation_percent=deviation_percent,
        star_parameter=star_parameter,
        trash_star_count=trash_star_count,
        trash_min_distance=trash_min_distance,
        trash_max_distance=trash_max_distance,
        star_parameter_function_body=star_parameter_function_body,
    )


def _cluster_from_payload(payload: object, *, index: int) -> ClusterInstance:
    localizer = get_localizer()
    mapping = _require_mapping(payload, f"clusters[{index - 1}]")

    cluster_id = _int_value(mapping.get("cluster_id", index), minimum=1)

    shape_value = mapping.get("shape_kind")
    if not isinstance(shape_value, str):
        raise ClusterConfigurationError(localizer.text("error.configuration_invalid"))
    try:
        shape_kind = ShapeKind(shape_value)
    except ValueError as exc:
        raise ClusterConfigurationError(localizer.text("error.configuration_invalid")) from exc

    center = _point_from_payload(mapping.get("center"), f"clusters[{index - 1}].center")
    size = _cluster_size_from_payload(mapping.get("size"), shape_kind=shape_kind, index=index)

    manual_star_count = _int_value(mapping.get("manual_star_count", 0), minimum=0)

    errors = validate_cluster_size(
        shape_kind,
        size,
        localizer.text("error.cluster", index=index),
    )
    if errors:
        raise ClusterConfigurationError(errors[0])

    return ClusterInstance(
        cluster_id=cluster_id,
        center=center,
        size=size,
        manual_star_count=manual_star_count,
    )


def _cluster_size_from_payload(payload: object, *, shape_kind: ShapeKind, index: int) -> ClusterSize:
    localizer = get_localizer()
    mapping = _require_mapping(payload, f"clusters[{index - 1}].size")

    if shape_kind is ShapeKind.CIRCLE:
        return CircleSize(
            radius=_float_value(mapping.get("radius", 10.0)),
        )

    if shape_kind is ShapeKind.RECTANGLE:
        return RectangleSize(
            width=_float_value(mapping.get("width", 10.0)),
            height=_float_value(mapping.get("height", 10.0)),
        )

    if shape_kind is ShapeKind.POLYGON:
        vertices_payload = mapping.get("vertices_local", [])
        if not isinstance(vertices_payload, list):
            raise ClusterConfigurationError(localizer.text("error.configuration_invalid"))
        return PolygonSize(
            polygon_scale=_float_value(mapping.get("polygon_scale", 100.0)),
            vertices_local=[
                _point_from_payload(vertex, f"clusters[{index - 1}].size.vertices_local[{vertex_index}]")
                for vertex_index, vertex in enumerate(vertices_payload)
            ],
        )

    orientation_value = mapping.get("function_orientation", FunctionOrientation.Y_OF_X.value)
    if not isinstance(orientation_value, str):
        raise ClusterConfigurationError(localizer.text("error.configuration_invalid"))
    try:
        function_orientation = FunctionOrientation(orientation_value)
    except ValueError as exc:
        raise ClusterConfigurationError(localizer.text("error.configuration_invalid")) from exc

    function_expression = _string_value(mapping.get("function_expression", "0"))
    function_range_start = _float_value(mapping.get("function_range_start", -10.0))
    function_range_end = _float_value(mapping.get("function_range_end", 10.0))
    function_thickness = _float_value(mapping.get("function_thickness", 0.1))

    if shape_kind is ShapeKind.FUNCTION:
        vertices_payload = mapping.get("vertices_local", [])
        if not isinstance(vertices_payload, list):
            raise ClusterConfigurationError(localizer.text("error.configuration_invalid"))
        fallback_vertices = [
            _point_from_payload(vertex, f"clusters[{index - 1}].size.vertices_local[{vertex_index}]")
            for vertex_index, vertex in enumerate(vertices_payload)
        ]
        try:
            return function_size_from_parameters(
                function_expression,
                function_orientation,
                function_range_start,
                function_range_end,
                function_thickness,
                fallback_vertices_local=fallback_vertices or None,
            )
        except ValueError:
            return FunctionSize(
                vertices_local=fallback_vertices,
                function_expression=function_expression,
                function_orientation=function_orientation,
                function_range_start=function_range_start,
                function_range_end=function_range_end,
                function_thickness=function_thickness,
            )

    raise ClusterConfigurationError(localizer.text("error.configuration_invalid"))


def _optional_cluster_size(payload: object, *, shape_kind: ShapeKind):
    if payload is None:
        return None
    size = _cluster_size_from_payload(payload, shape_kind=shape_kind, index=1)
    errors = validate_cluster_size(
        shape_kind,
        size,
        get_localizer().text("error.cluster", index=1),
    )
    if errors:
        raise ClusterConfigurationError(errors[0])
    return size


def _optional_int_list(payload: object) -> list[int] | None:
    if payload is None:
        return None
    if not isinstance(payload, list):
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
    return [_int_value(value, minimum=1) for value in payload]


def _optional_int_value(value: object, *, minimum: int | None = None) -> int | None:
    if value is None:
        return None
    return _int_value(value, minimum=minimum)


def _optional_float_value(value: object) -> float | None:
    if value is None:
        return None
    return _float_value(value)


def _optional_distribution_mode(value: object) -> DistributionMode | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
    try:
        return DistributionMode(value)
    except ValueError as exc:
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid")) from exc


def _optional_star_parameter(value: object) -> StarParameterConfig | None:
    if value is None:
        return None
    mapping = _require_mapping(value, "star_parameter")
    enabled = _bool_value(mapping.get("enabled"))
    name = _string_value(mapping.get("name"))
    if "value" in mapping:
        value_payload = _require_mapping(mapping.get("value"), "star_parameter.value")
        mode_raw = value_payload.get("mode")
        if not isinstance(mode_raw, str):
            raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
        if mode_raw == "random":
            parameter_value = RandomStarParameterValue(
                min_value=_float_value(value_payload.get("min_value")),
                max_value=_float_value(value_payload.get("max_value")),
            )
        elif mode_raw == "function":
            parameter_value = FunctionStarParameterValue(
                function_body=_string_value(value_payload.get("function_body")),
            )
        else:
            raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
    else:
        mode_raw = mapping.get("mode")
        if not isinstance(mode_raw, str):
            raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
        try:
            mode = StarParameterMode(mode_raw)
        except ValueError as exc:
            raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid")) from exc
        if mode is StarParameterMode.RANDOM:
            parameter_value = RandomStarParameterValue(
                min_value=_float_value(mapping.get("min_value")),
                max_value=_float_value(mapping.get("max_value")),
            )
        else:
            parameter_value = FunctionStarParameterValue(
                function_body=_string_value(mapping.get("function_body")),
            )
    return StarParameterConfig(
        enabled=enabled,
        name=name,
        value=parameter_value,
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


def _int_value(value: object, *, minimum: int | None = None) -> int:
    if not _is_number(value):
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
    numeric_value = float(value)
    if not numeric_value.is_integer():
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
    integer_value = int(numeric_value)
    if minimum is not None and integer_value < minimum:
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
    return integer_value


def _bool_value(value: object) -> bool:
    if not isinstance(value, bool):
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
    return value


def _string_value(value: object) -> str:
    if not isinstance(value, str):
        raise ClusterConfigurationError(get_localizer().text("error.configuration_invalid"))
    return value


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)

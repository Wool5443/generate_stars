from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
import copy
import sys
import tomllib
from typing import Any


RUNTIME_CONFIG_FILENAME = "config.toml"
DEFAULT_CONFIG_RESOURCE = "default_config.toml"
PREFERENCES_DIR_NAME = "generate_stars"
PREFERENCES_FILENAME = "settings.json"
LAST_SAVE_PATH_KEY = "last_save_path"


@dataclass(frozen=True, slots=True)
class ConfigIssue:
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class AppSection:
    application_id: str
    title: str
    css: str


@dataclass(frozen=True, slots=True)
class WindowConfig:
    default_width: int
    default_height: int


@dataclass(frozen=True, slots=True)
class DefaultsConfig:
    cluster_radius: float
    cluster_width: float
    cluster_height: float
    cluster_count: int
    total_cluster_stars: int
    deviation_percent: float
    trash_star_count: int
    trash_min_distance: float
    viewport_scale: float
    default_save_filename: str


@dataclass(frozen=True, slots=True)
class LimitsConfig:
    cluster_count_min: int
    cluster_count_max: int
    size_min: float
    size_max: float
    total_stars_min: int
    total_stars_max: int
    deviation_percent_min: float
    deviation_percent_max: float
    trash_star_count_min: int
    trash_star_count_max: int
    trash_distance_min: float
    trash_distance_max: float


@dataclass(frozen=True, slots=True)
class TextConfig:
    ready_status: str
    reset_positions_status: str
    save_dialog_title: str
    shape_interaction_hint: str
    trash_note: str
    manual_counts_note: str


@dataclass(frozen=True, slots=True)
class UiConfig:
    sidebar_width: int
    sidebar_spacing: int
    sidebar_content_spacing: int
    sidebar_footer_spacing: int
    sidebar_margin: int
    panel_spacing: int
    row_spacing: int
    cluster_section_spacing: int
    spin_page_multiplier: float
    integer_spin_width_chars: int
    decimal_spin_width_chars: int


@dataclass(frozen=True, slots=True)
class CanvasConfig:
    default_width: int
    default_height: int
    center_marker_radius_px: float
    cluster_hit_tolerance_px: float
    zoom_factor: float
    min_viewport_scale: float
    max_viewport_scale: float
    grid_target_spacing_px: float
    axis_label_font_size: float
    axis_label_margin_px: float
    axis_label_edge_margin_px: float
    origin_marker_radius: float
    grid_line_width: float
    axis_line_width: float
    cluster_outline_width: float
    hover_info_margin_px: float
    hover_info_padding_px: float
    hover_info_font_size: float
    hover_info_line_spacing_px: float


@dataclass(frozen=True, slots=True)
class ColorConfig:
    canvas_background: tuple[float, float, float]
    grid: tuple[float, float, float, float]
    axis: tuple[float, float, float, float]
    axis_label: tuple[float, float, float, float]
    active_cluster_outline: tuple[float, float, float, float]
    inactive_cluster_outline: tuple[float, float, float, float]
    active_cluster_marker: tuple[float, float, float, float]
    inactive_cluster_marker: tuple[float, float, float, float]
    hover_info_background: tuple[float, float, float, float]
    hover_info_title: tuple[float, float, float, float]
    hover_info_text: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    layout_ring_padding: float
    layout_origin_padding: float
    empty_cluster_bounds_limit: float
    trash_bounds_padding_min: float
    trash_bounds_padding_extra: float
    trash_placement_attempts_min: int
    trash_placement_attempts_per_star: int
    export_coordinate_precision: int


@dataclass(frozen=True, slots=True)
class AppConfig:
    app: AppSection
    window: WindowConfig
    defaults: DefaultsConfig
    limits: LimitsConfig
    text: TextConfig
    ui: UiConfig
    canvas: CanvasConfig
    colors: ColorConfig
    generation: GenerationConfig


_CACHED_CONFIG: AppConfig | None = None
_CACHED_ISSUES: tuple[ConfigIssue, ...] = ()


def packaged_default_config_text() -> str:
    return files("generate_stars").joinpath(DEFAULT_CONFIG_RESOURCE).read_text(encoding="utf-8")


def app_root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def runtime_config_path(path: Path | None = None) -> Path:
    return path or app_root_dir() / RUNTIME_CONFIG_FILENAME


def ensure_runtime_config_file(path: Path | None = None) -> list[ConfigIssue]:
    target_path = runtime_config_path(path)
    if target_path.exists():
        return []

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(packaged_default_config_text(), encoding="utf-8")
    except OSError as exc:
        return [
            ConfigIssue(
                RUNTIME_CONFIG_FILENAME,
                f"Could not create runtime config file at {target_path}: {exc}",
            )
        ]
    return []


def load_app_config(path: Path | None = None, *, create_missing: bool = False) -> tuple[AppConfig, list[ConfigIssue]]:
    issues: list[ConfigIssue] = []
    defaults = copy.deepcopy(_default_config_data())
    runtime_path = runtime_config_path(path)

    if create_missing:
        issues.extend(ensure_runtime_config_file(runtime_path))

    user_data: dict[str, Any] = {}
    if runtime_path.exists():
        try:
            user_text = runtime_path.read_text(encoding="utf-8")
        except OSError as exc:
            issues.append(ConfigIssue(RUNTIME_CONFIG_FILENAME, f"Could not read {runtime_path}: {exc}"))
        else:
            user_data = _parse_toml(user_text, str(runtime_path), issues)

    merged = _merge_known(defaults, user_data, issues)
    config = _build_app_config(merged, defaults, issues)
    return config, issues


def initialize_app_config(*, create_missing: bool = True) -> tuple[AppConfig, list[ConfigIssue]]:
    global _CACHED_CONFIG, _CACHED_ISSUES
    config, issues = load_app_config(create_missing=create_missing)
    _CACHED_CONFIG = config
    _CACHED_ISSUES = tuple(issues)
    return config, list(_CACHED_ISSUES)


def get_app_config() -> AppConfig:
    global _CACHED_CONFIG, _CACHED_ISSUES
    if _CACHED_CONFIG is None:
        _CACHED_CONFIG, issues = load_app_config(create_missing=False)
        _CACHED_ISSUES = tuple(issues)
    return _CACHED_CONFIG


def get_config_issues() -> tuple[ConfigIssue, ...]:
    if _CACHED_CONFIG is None:
        get_app_config()
    return _CACHED_ISSUES


@lru_cache(maxsize=1)
def _default_config_data() -> dict[str, Any]:
    try:
        payload = tomllib.loads(packaged_default_config_text())
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeError(f"Packaged default config is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Packaged default config must be a TOML table.")
    return payload


def _parse_toml(text: str, source: str, issues: list[ConfigIssue]) -> dict[str, Any]:
    try:
        payload = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        issues.append(ConfigIssue(source, f"Invalid TOML: {exc}"))
        return {}

    if not isinstance(payload, dict):
        issues.append(ConfigIssue(source, "Config file must contain a top-level table."))
        return {}
    return payload


def _merge_known(defaults: Any, overrides: Any, issues: list[ConfigIssue], path: str = "") -> Any:
    if isinstance(defaults, dict):
        if not isinstance(overrides, dict):
            if overrides not in ({}, None):
                issues.append(ConfigIssue(path or RUNTIME_CONFIG_FILENAME, "Expected a TOML table."))
            return copy.deepcopy(defaults)

        merged: dict[str, Any] = {}
        for key, default_value in defaults.items():
            item_path = f"{path}.{key}" if path else key
            if key in overrides:
                merged[key] = _merge_known(default_value, overrides[key], issues, item_path)
            else:
                merged[key] = copy.deepcopy(default_value)

        for key in overrides.keys() - defaults.keys():
            item_path = f"{path}.{key}" if path else key
            issues.append(ConfigIssue(item_path, "Unknown config key."))
        return merged

    return overrides


def _build_app_config(values: dict[str, Any], defaults: dict[str, Any], issues: list[ConfigIssue]) -> AppConfig:
    app_values = values["app"]
    app_defaults = defaults["app"]
    app = AppSection(
        application_id=_string_value(app_values, app_defaults, "application_id", issues, "app.application_id"),
        title=_string_value(app_values, app_defaults, "title", issues, "app.title"),
        css=_string_value(app_values, app_defaults, "css", issues, "app.css"),
    )

    window_values = values["window"]
    window_defaults = defaults["window"]
    window = WindowConfig(
        default_width=_int_value(window_values, window_defaults, "default_width", issues, "window.default_width", 1),
        default_height=_int_value(
            window_values,
            window_defaults,
            "default_height",
            issues,
            "window.default_height",
            1,
        ),
    )

    default_values = values["defaults"]
    default_defaults = defaults["defaults"]
    defaults_config = DefaultsConfig(
        cluster_radius=_float_value(
            default_values,
            default_defaults,
            "cluster_radius",
            issues,
            "defaults.cluster_radius",
            0.0,
            exclusive_min=True,
        ),
        cluster_width=_float_value(
            default_values,
            default_defaults,
            "cluster_width",
            issues,
            "defaults.cluster_width",
            0.0,
            exclusive_min=True,
        ),
        cluster_height=_float_value(
            default_values,
            default_defaults,
            "cluster_height",
            issues,
            "defaults.cluster_height",
            0.0,
            exclusive_min=True,
        ),
        cluster_count=_int_value(default_values, default_defaults, "cluster_count", issues, "defaults.cluster_count", 0),
        total_cluster_stars=_int_value(
            default_values,
            default_defaults,
            "total_cluster_stars",
            issues,
            "defaults.total_cluster_stars",
            0,
        ),
        deviation_percent=_float_value(
            default_values,
            default_defaults,
            "deviation_percent",
            issues,
            "defaults.deviation_percent",
            0.0,
        ),
        trash_star_count=_int_value(
            default_values,
            default_defaults,
            "trash_star_count",
            issues,
            "defaults.trash_star_count",
            0,
        ),
        trash_min_distance=_float_value(
            default_values,
            default_defaults,
            "trash_min_distance",
            issues,
            "defaults.trash_min_distance",
            0.0,
        ),
        viewport_scale=_float_value(
            default_values,
            default_defaults,
            "viewport_scale",
            issues,
            "defaults.viewport_scale",
            0.0,
            exclusive_min=True,
        ),
        default_save_filename=_string_value(
            default_values,
            default_defaults,
            "default_save_filename",
            issues,
            "defaults.default_save_filename",
        ),
    )

    limit_values = values["limits"]
    limit_defaults = defaults["limits"]
    limits = LimitsConfig(
        cluster_count_min=_int_value(
            limit_values,
            limit_defaults,
            "cluster_count_min",
            issues,
            "limits.cluster_count_min",
            0,
        ),
        cluster_count_max=_int_value(
            limit_values,
            limit_defaults,
            "cluster_count_max",
            issues,
            "limits.cluster_count_max",
            0,
        ),
        size_min=_float_value(limit_values, limit_defaults, "size_min", issues, "limits.size_min", 0.0, exclusive_min=True),
        size_max=_float_value(limit_values, limit_defaults, "size_max", issues, "limits.size_max", 0.0, exclusive_min=True),
        total_stars_min=_int_value(limit_values, limit_defaults, "total_stars_min", issues, "limits.total_stars_min", 0),
        total_stars_max=_int_value(limit_values, limit_defaults, "total_stars_max", issues, "limits.total_stars_max", 0),
        deviation_percent_min=_float_value(
            limit_values,
            limit_defaults,
            "deviation_percent_min",
            issues,
            "limits.deviation_percent_min",
            0.0,
        ),
        deviation_percent_max=_float_value(
            limit_values,
            limit_defaults,
            "deviation_percent_max",
            issues,
            "limits.deviation_percent_max",
            0.0,
        ),
        trash_star_count_min=_int_value(
            limit_values,
            limit_defaults,
            "trash_star_count_min",
            issues,
            "limits.trash_star_count_min",
            0,
        ),
        trash_star_count_max=_int_value(
            limit_values,
            limit_defaults,
            "trash_star_count_max",
            issues,
            "limits.trash_star_count_max",
            0,
        ),
        trash_distance_min=_float_value(
            limit_values,
            limit_defaults,
            "trash_distance_min",
            issues,
            "limits.trash_distance_min",
            0.0,
        ),
        trash_distance_max=_float_value(
            limit_values,
            limit_defaults,
            "trash_distance_max",
            issues,
            "limits.trash_distance_max",
            0.0,
        ),
    )
    limits = _validate_limits(limits, limit_defaults, issues)

    text_values = values["text"]
    text_defaults = defaults["text"]
    text = TextConfig(
        ready_status=_string_value(text_values, text_defaults, "ready_status", issues, "text.ready_status"),
        reset_positions_status=_string_value(
            text_values,
            text_defaults,
            "reset_positions_status",
            issues,
            "text.reset_positions_status",
        ),
        save_dialog_title=_string_value(
            text_values,
            text_defaults,
            "save_dialog_title",
            issues,
            "text.save_dialog_title",
        ),
        shape_interaction_hint=_string_value(
            text_values,
            text_defaults,
            "shape_interaction_hint",
            issues,
            "text.shape_interaction_hint",
        ),
        trash_note=_string_value(text_values, text_defaults, "trash_note", issues, "text.trash_note"),
        manual_counts_note=_string_value(
            text_values,
            text_defaults,
            "manual_counts_note",
            issues,
            "text.manual_counts_note",
        ),
    )

    ui_values = values["ui"]
    ui_defaults = defaults["ui"]
    ui = UiConfig(
        sidebar_width=_int_value(ui_values, ui_defaults, "sidebar_width", issues, "ui.sidebar_width", 1),
        sidebar_spacing=_int_value(ui_values, ui_defaults, "sidebar_spacing", issues, "ui.sidebar_spacing", 0),
        sidebar_content_spacing=_int_value(
            ui_values,
            ui_defaults,
            "sidebar_content_spacing",
            issues,
            "ui.sidebar_content_spacing",
            0,
        ),
        sidebar_footer_spacing=_int_value(
            ui_values,
            ui_defaults,
            "sidebar_footer_spacing",
            issues,
            "ui.sidebar_footer_spacing",
            0,
        ),
        sidebar_margin=_int_value(ui_values, ui_defaults, "sidebar_margin", issues, "ui.sidebar_margin", 0),
        panel_spacing=_int_value(ui_values, ui_defaults, "panel_spacing", issues, "ui.panel_spacing", 0),
        row_spacing=_int_value(ui_values, ui_defaults, "row_spacing", issues, "ui.row_spacing", 0),
        cluster_section_spacing=_int_value(
            ui_values,
            ui_defaults,
            "cluster_section_spacing",
            issues,
            "ui.cluster_section_spacing",
            0,
        ),
        spin_page_multiplier=_float_value(
            ui_values,
            ui_defaults,
            "spin_page_multiplier",
            issues,
            "ui.spin_page_multiplier",
            0.0,
            exclusive_min=True,
        ),
        integer_spin_width_chars=_int_value(
            ui_values,
            ui_defaults,
            "integer_spin_width_chars",
            issues,
            "ui.integer_spin_width_chars",
            1,
        ),
        decimal_spin_width_chars=_int_value(
            ui_values,
            ui_defaults,
            "decimal_spin_width_chars",
            issues,
            "ui.decimal_spin_width_chars",
            1,
        ),
    )

    canvas_values = values["canvas"]
    canvas_defaults = defaults["canvas"]
    canvas = CanvasConfig(
        default_width=_int_value(canvas_values, canvas_defaults, "default_width", issues, "canvas.default_width", 1),
        default_height=_int_value(canvas_values, canvas_defaults, "default_height", issues, "canvas.default_height", 1),
        center_marker_radius_px=_float_value(
            canvas_values,
            canvas_defaults,
            "center_marker_radius_px",
            issues,
            "canvas.center_marker_radius_px",
            0.0,
            exclusive_min=True,
        ),
        cluster_hit_tolerance_px=_float_value(
            canvas_values,
            canvas_defaults,
            "cluster_hit_tolerance_px",
            issues,
            "canvas.cluster_hit_tolerance_px",
            0.0,
        ),
        zoom_factor=_float_value(
            canvas_values,
            canvas_defaults,
            "zoom_factor",
            issues,
            "canvas.zoom_factor",
            0.0,
            exclusive_min=True,
        ),
        min_viewport_scale=_float_value(
            canvas_values,
            canvas_defaults,
            "min_viewport_scale",
            issues,
            "canvas.min_viewport_scale",
            0.0,
            exclusive_min=True,
        ),
        max_viewport_scale=_float_value(
            canvas_values,
            canvas_defaults,
            "max_viewport_scale",
            issues,
            "canvas.max_viewport_scale",
            0.0,
            exclusive_min=True,
        ),
        grid_target_spacing_px=_float_value(
            canvas_values,
            canvas_defaults,
            "grid_target_spacing_px",
            issues,
            "canvas.grid_target_spacing_px",
            0.0,
            exclusive_min=True,
        ),
        axis_label_font_size=_float_value(
            canvas_values,
            canvas_defaults,
            "axis_label_font_size",
            issues,
            "canvas.axis_label_font_size",
            0.0,
            exclusive_min=True,
        ),
        axis_label_margin_px=_float_value(
            canvas_values,
            canvas_defaults,
            "axis_label_margin_px",
            issues,
            "canvas.axis_label_margin_px",
            0.0,
        ),
        axis_label_edge_margin_px=_float_value(
            canvas_values,
            canvas_defaults,
            "axis_label_edge_margin_px",
            issues,
            "canvas.axis_label_edge_margin_px",
            0.0,
        ),
        origin_marker_radius=_float_value(
            canvas_values,
            canvas_defaults,
            "origin_marker_radius",
            issues,
            "canvas.origin_marker_radius",
            0.0,
            exclusive_min=True,
        ),
        grid_line_width=_float_value(
            canvas_values,
            canvas_defaults,
            "grid_line_width",
            issues,
            "canvas.grid_line_width",
            0.0,
            exclusive_min=True,
        ),
        axis_line_width=_float_value(
            canvas_values,
            canvas_defaults,
            "axis_line_width",
            issues,
            "canvas.axis_line_width",
            0.0,
            exclusive_min=True,
        ),
        cluster_outline_width=_float_value(
            canvas_values,
            canvas_defaults,
            "cluster_outline_width",
            issues,
            "canvas.cluster_outline_width",
            0.0,
            exclusive_min=True,
        ),
        hover_info_margin_px=_float_value(
            canvas_values,
            canvas_defaults,
            "hover_info_margin_px",
            issues,
            "canvas.hover_info_margin_px",
            0.0,
        ),
        hover_info_padding_px=_float_value(
            canvas_values,
            canvas_defaults,
            "hover_info_padding_px",
            issues,
            "canvas.hover_info_padding_px",
            0.0,
        ),
        hover_info_font_size=_float_value(
            canvas_values,
            canvas_defaults,
            "hover_info_font_size",
            issues,
            "canvas.hover_info_font_size",
            0.0,
            exclusive_min=True,
        ),
        hover_info_line_spacing_px=_float_value(
            canvas_values,
            canvas_defaults,
            "hover_info_line_spacing_px",
            issues,
            "canvas.hover_info_line_spacing_px",
            0.0,
        ),
    )
    if canvas.max_viewport_scale < canvas.min_viewport_scale:
        issues.append(ConfigIssue("canvas.max_viewport_scale", "Must be greater than or equal to canvas.min_viewport_scale."))
        canvas = replace(
            canvas,
            min_viewport_scale=float(canvas_defaults["min_viewport_scale"]),
            max_viewport_scale=float(canvas_defaults["max_viewport_scale"]),
        )

    color_values = values["colors"]
    color_defaults = defaults["colors"]
    colors = ColorConfig(
        canvas_background=_color_value(
            color_values,
            color_defaults,
            "canvas_background",
            issues,
            "colors.canvas_background",
            3,
        ),
        grid=_color_value(color_values, color_defaults, "grid", issues, "colors.grid", 4),
        axis=_color_value(color_values, color_defaults, "axis", issues, "colors.axis", 4),
        axis_label=_color_value(color_values, color_defaults, "axis_label", issues, "colors.axis_label", 4),
        active_cluster_outline=_color_value(
            color_values,
            color_defaults,
            "active_cluster_outline",
            issues,
            "colors.active_cluster_outline",
            4,
        ),
        inactive_cluster_outline=_color_value(
            color_values,
            color_defaults,
            "inactive_cluster_outline",
            issues,
            "colors.inactive_cluster_outline",
            4,
        ),
        active_cluster_marker=_color_value(
            color_values,
            color_defaults,
            "active_cluster_marker",
            issues,
            "colors.active_cluster_marker",
            4,
        ),
        inactive_cluster_marker=_color_value(
            color_values,
            color_defaults,
            "inactive_cluster_marker",
            issues,
            "colors.inactive_cluster_marker",
            4,
        ),
        hover_info_background=_color_value(
            color_values,
            color_defaults,
            "hover_info_background",
            issues,
            "colors.hover_info_background",
            4,
        ),
        hover_info_title=_color_value(
            color_values,
            color_defaults,
            "hover_info_title",
            issues,
            "colors.hover_info_title",
            4,
        ),
        hover_info_text=_color_value(color_values, color_defaults, "hover_info_text", issues, "colors.hover_info_text", 4),
    )

    generation_values = values["generation"]
    generation_defaults = defaults["generation"]
    generation = GenerationConfig(
        layout_ring_padding=_float_value(
            generation_values,
            generation_defaults,
            "layout_ring_padding",
            issues,
            "generation.layout_ring_padding",
            0.0,
        ),
        layout_origin_padding=_float_value(
            generation_values,
            generation_defaults,
            "layout_origin_padding",
            issues,
            "generation.layout_origin_padding",
            0.0,
        ),
        empty_cluster_bounds_limit=_float_value(
            generation_values,
            generation_defaults,
            "empty_cluster_bounds_limit",
            issues,
            "generation.empty_cluster_bounds_limit",
            0.0,
            exclusive_min=True,
        ),
        trash_bounds_padding_min=_float_value(
            generation_values,
            generation_defaults,
            "trash_bounds_padding_min",
            issues,
            "generation.trash_bounds_padding_min",
            0.0,
        ),
        trash_bounds_padding_extra=_float_value(
            generation_values,
            generation_defaults,
            "trash_bounds_padding_extra",
            issues,
            "generation.trash_bounds_padding_extra",
            0.0,
        ),
        trash_placement_attempts_min=_int_value(
            generation_values,
            generation_defaults,
            "trash_placement_attempts_min",
            issues,
            "generation.trash_placement_attempts_min",
            1,
        ),
        trash_placement_attempts_per_star=_int_value(
            generation_values,
            generation_defaults,
            "trash_placement_attempts_per_star",
            issues,
            "generation.trash_placement_attempts_per_star",
            1,
        ),
        export_coordinate_precision=_int_value(
            generation_values,
            generation_defaults,
            "export_coordinate_precision",
            issues,
            "generation.export_coordinate_precision",
            0,
        ),
    )

    return AppConfig(
        app=app,
        window=window,
        defaults=defaults_config,
        limits=limits,
        text=text,
        ui=ui,
        canvas=canvas,
        colors=colors,
        generation=generation,
    )


def _validate_limits(limits: LimitsConfig, defaults: dict[str, Any], issues: list[ConfigIssue]) -> LimitsConfig:
    result = limits
    comparisons = (
        ("cluster_count_min", "cluster_count_max"),
        ("size_min", "size_max"),
        ("total_stars_min", "total_stars_max"),
        ("deviation_percent_min", "deviation_percent_max"),
        ("trash_star_count_min", "trash_star_count_max"),
        ("trash_distance_min", "trash_distance_max"),
    )
    for lower_name, upper_name in comparisons:
        lower_value = getattr(result, lower_name)
        upper_value = getattr(result, upper_name)
        if upper_value < lower_value:
            issues.append(ConfigIssue(f"limits.{upper_name}", f"Must be greater than or equal to limits.{lower_name}."))
            result = replace(
                result,
                **{
                    lower_name: defaults[lower_name],
                    upper_name: defaults[upper_name],
                },
            )
    return result


def _string_value(
    values: dict[str, Any],
    defaults: dict[str, Any],
    key: str,
    issues: list[ConfigIssue],
    path: str,
) -> str:
    value = values.get(key, defaults[key])
    if isinstance(value, str) and value:
        return value
    issues.append(ConfigIssue(path, "Expected a non-empty string."))
    return str(defaults[key])


def _int_value(
    values: dict[str, Any],
    defaults: dict[str, Any],
    key: str,
    issues: list[ConfigIssue],
    path: str,
    minimum: int | None = None,
) -> int:
    value = values.get(key, defaults[key])
    if isinstance(value, bool) or not isinstance(value, int):
        issues.append(ConfigIssue(path, "Expected an integer."))
        return int(defaults[key])
    if minimum is not None and value < minimum:
        comparator = "greater than or equal to"
        issues.append(ConfigIssue(path, f"Expected a value {comparator} {minimum}."))
        return int(defaults[key])
    return value


def _float_value(
    values: dict[str, Any],
    defaults: dict[str, Any],
    key: str,
    issues: list[ConfigIssue],
    path: str,
    minimum: float | None = None,
    *,
    exclusive_min: bool = False,
) -> float:
    value = values.get(key, defaults[key])
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        issues.append(ConfigIssue(path, "Expected a number."))
        return float(defaults[key])

    numeric_value = float(value)
    if minimum is None:
        return numeric_value

    invalid = numeric_value <= minimum if exclusive_min else numeric_value < minimum
    if invalid:
        qualifier = "greater than" if exclusive_min else "greater than or equal to"
        issues.append(ConfigIssue(path, f"Expected a value {qualifier} {minimum}."))
        return float(defaults[key])
    return numeric_value


def _color_value(
    values: dict[str, Any],
    defaults: dict[str, Any],
    key: str,
    issues: list[ConfigIssue],
    path: str,
    length: int,
) -> tuple[float, ...]:
    value = values.get(key, defaults[key])
    default_value = tuple(float(item) for item in defaults[key])
    if not isinstance(value, list) or len(value) != length:
        issues.append(ConfigIssue(path, f"Expected a list of {length} numeric color components."))
        return default_value

    result: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            issues.append(ConfigIssue(path, "Expected numeric color components."))
            return default_value
        numeric_item = float(item)
        if numeric_item < 0.0 or numeric_item > 1.0:
            issues.append(ConfigIssue(path, "Color components must be between 0.0 and 1.0."))
            return default_value
        result.append(numeric_item)
    return tuple(result)

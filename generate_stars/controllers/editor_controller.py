from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from ..cluster_configuration import ClusterConfigurationError, load_cluster_configuration, save_cluster_configuration
from ..config import AppConfig
from ..generator import (
    GenerationError,
    even_counts,
    format_points_for_export,
    generate_star_field,
    preview_parameter_function_result,
    validate_cluster_size,
    validate_state,
)
from ..history import HistoryManager
from ..localization import get_localizer
from ..models import AppState, CanvasTool, ClusterSize, DistributionMode, FunctionOrientation, Point, ShapeKind, StarParameterMode
from ..preferences import (
    load_last_config_save_path,
    load_last_save_path,
    save_last_config_save_path,
    save_last_save_path,
)
from ..shapes import (
    function_size_from_parameters,
    get_shape,
    polygon_geometry_from_world_vertices,
    polygon_local_bounds,
    polygon_size_from_local_vertices,
    validate_polygon_vertices,
)
from .view_models import (
    ClusterPanelViewModel,
    DistributionPanelViewModel,
    FunctionEditorViewModel,
    ManualCountRowViewModel,
    ParameterPanelViewModel,
    PlacementViewModel,
    SelectionViewModel,
    StatusViewModel,
    ToolbarViewModel,
    TrashPanelViewModel,
    WindowViewModel,
)


@dataclass(slots=True)
class EditorSessionState:
    active_tool: CanvasTool = CanvasTool.SELECT
    snap_to_integer_grid: bool = False
    clipboard_clusters: tuple = field(default_factory=tuple)
    clipboard_offset: Point = field(default_factory=lambda: Point(1.0, -1.0))
    clipboard_paste_count: int = 0
    status_text: str = ""
    status_kind: str = "neutral"


class EditorController:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state = AppState()
        self.session = EditorSessionState(status_text="")
        self._history = HistoryManager(limit=100)
        self._last_save_path = load_last_save_path()
        self._last_config_save_path = load_last_config_save_path()
        self._continuous_history_source: object | None = None
        self._change_listener: Callable[[], None] | None = None
        self._refresh_function_size(self.state.placement_function_size)

    @property
    def active_tool(self) -> CanvasTool:
        return self.session.active_tool

    @property
    def last_save_path(self) -> Path | None:
        return self._last_save_path

    @property
    def last_config_save_path(self) -> Path | None:
        return self._last_config_save_path

    @property
    def can_undo(self) -> bool:
        return self._history.can_undo

    @property
    def can_redo(self) -> bool:
        return self._history.can_redo

    @property
    def snap_to_integer_grid(self) -> bool:
        return self.session.snap_to_integer_grid

    def set_change_listener(self, listener: Callable[[], None]) -> None:
        self._change_listener = listener

    def refresh_view(self) -> None:
        self._notify()

    def _notify(self) -> None:
        if self._change_listener is not None:
            self._change_listener()

    def set_status(self, text: str, kind: str = "neutral", *, notify: bool = True) -> None:
        self.session.status_text = text
        self.session.status_kind = kind
        if notify:
            self._notify()

    def clear_status(self, *, notify: bool = False) -> None:
        if self.session.status_kind != "error":
            self.session.status_text = ""
            self.session.status_kind = "neutral"
        if notify:
            self._notify()

    def ensure_continuous_history(self, source: object) -> None:
        if self._continuous_history_source is source:
            return
        self.finalize_history_transaction()
        self._continuous_history_source = source
        self._history.begin(self.state)

    def finalize_history_transaction(self, *, notify_on_change: bool = True) -> bool:
        changed = self._history.commit(self.state)
        self._continuous_history_source = None
        if changed and notify_on_change:
            self._notify()
        return changed

    def cancel_history_transaction(self) -> None:
        self._history.cancel_pending()
        self._continuous_history_source = None

    def finish_continuous_history(self, source: object) -> None:
        if self._continuous_history_source is source:
            self.finalize_history_transaction()

    def prepare_for_canvas_interaction(self) -> None:
        self.finalize_history_transaction()

    def begin_canvas_edit(self) -> None:
        self.finalize_history_transaction()
        self._history.begin(self.state)

    def finish_canvas_edit(self, *, cluster_list_changed: bool) -> None:
        if self.state.distribution_mode is DistributionMode.MANUAL:
            self._sync_total_stars_for_manual_mode()
        self.clear_status()
        self.finalize_history_transaction(notify_on_change=False)
        self._notify()

    def _run_immediate_edit(self, mutator: Callable[[], None]) -> None:
        self.finalize_history_transaction()
        self._history.begin(self.state)
        mutator()
        if self.state.distribution_mode is DistributionMode.MANUAL:
            self._sync_total_stars_for_manual_mode()
        self.clear_status()
        self.finalize_history_transaction(notify_on_change=False)
        self._notify()

    def undo(self) -> bool:
        self.finalize_history_transaction()
        if not self._history.undo(self.state):
            return False
        self.clear_status()
        self._notify()
        return True

    def redo(self) -> bool:
        self.finalize_history_transaction()
        if not self._history.redo(self.state):
            return False
        self.clear_status()
        self._notify()
        return True

    def set_active_tool(self, tool: CanvasTool) -> None:
        if self.session.active_tool is tool:
            return
        self.finalize_history_transaction()
        self.session.active_tool = tool
        self._notify()

    def set_snap_to_integer_grid(self, enabled: bool) -> None:
        if self.session.snap_to_integer_grid == enabled:
            return
        self.finalize_history_transaction()
        self.session.snap_to_integer_grid = enabled
        self._notify()

    def select_only(self, cluster_id: int) -> None:
        self.finalize_history_transaction()
        self.state.select_only(cluster_id)
        self.clear_status()
        self._notify()

    def toggle_selection(self, cluster_id: int) -> None:
        self.finalize_history_transaction()
        self.state.toggle_selection(cluster_id)
        self.clear_status()
        self._notify()

    def set_selected_cluster_ids(self, cluster_ids: Sequence[int]) -> None:
        self.finalize_history_transaction()
        self.state.selected_cluster_ids = list(cluster_ids)
        self.clear_status()
        self._notify()

    def clear_selected_clusters(self) -> None:
        if not self.state.selected_cluster_ids:
            return
        self.finalize_history_transaction()
        self.state.clear_selection()
        self.clear_status()
        self._notify()

    def select_all_clusters(self) -> None:
        if not self.state.clusters:
            return
        self.finalize_history_transaction()
        self.state.selected_cluster_ids = [cluster.cluster_id for cluster in self.state.clusters]
        self.clear_status()
        self._notify()

    def delete_selected_clusters(self) -> None:
        if not self.state.selected_cluster_ids:
            return
        self._run_immediate_edit(self.state.delete_selected_clusters)

    def copy_selected_clusters(self) -> int:
        localizer = get_localizer()
        self.finalize_history_transaction()
        selected = self.state.selected_clusters()
        if not selected:
            self.set_status(localizer.text("status.nothing_selected_to_copy"))
            return 0

        self.session.clipboard_clusters = tuple(cluster.copy() for cluster in selected)
        self.session.clipboard_offset = self._clipboard_offset(selected)
        self.session.clipboard_paste_count = 0
        self.set_status(localizer.text("status.copied_clusters", count=len(selected)))
        return len(selected)

    def paste_copied_clusters(self) -> int:
        localizer = get_localizer()
        self.finalize_history_transaction()
        if not self.session.clipboard_clusters:
            self.set_status(localizer.text("status.nothing_to_paste"))
            return 0

        paste_step = self.session.clipboard_paste_count + 1
        offset = Point(
            self.session.clipboard_offset.x * paste_step,
            self.session.clipboard_offset.y * paste_step,
        )
        clipboard_clusters = tuple(cluster.copy() for cluster in self.session.clipboard_clusters)
        pasted_cluster_ids: list[int] = []

        def mutate() -> None:
            for copied_cluster in clipboard_clusters:
                center = Point(
                    copied_cluster.center.x + offset.x,
                    copied_cluster.center.y + offset.y,
                )
                cluster = self.state.add_cluster(
                    copied_cluster.shape_kind,
                    center,
                    copied_cluster.size.copy(),
                )
                cluster.manual_star_count = copied_cluster.manual_star_count
                pasted_cluster_ids.append(cluster.cluster_id)
            self.state.selected_cluster_ids = pasted_cluster_ids

        self._run_immediate_edit(mutate)
        self.session.clipboard_paste_count = paste_step
        self.set_status(localizer.text("status.pasted_clusters", count=len(pasted_cluster_ids)))
        return len(pasted_cluster_ids)

    def place_cluster(self, shape_kind: ShapeKind, center: Point) -> int | None:
        localizer = get_localizer()
        placement_size = self.state.placement_size_for_shape(shape_kind).copy()
        label_key = {
            ShapeKind.CIRCLE: "error.circle_placement",
            ShapeKind.RECTANGLE: "error.rectangle_placement",
            ShapeKind.FUNCTION: "error.function_placement",
        }.get(shape_kind)
        if label_key is not None:
            errors = validate_cluster_size(shape_kind, placement_size, localizer.text(label_key))
            if errors:
                self.set_status(errors[0], "error")
                return None

        cluster_id = 0

        def mutate() -> None:
            nonlocal cluster_id
            cluster = self.state.add_cluster(shape_kind, center, placement_size)
            self.state.select_only(cluster.cluster_id)
            cluster_id = cluster.cluster_id

        self._run_immediate_edit(mutate)
        return cluster_id

    def complete_polygon_draft(self, vertices: list[Point]) -> tuple[int | None, str | None]:
        errors = validate_polygon_vertices(vertices)
        if errors:
            return None, errors[0]

        cluster_id = 0
        center, size = polygon_geometry_from_world_vertices(vertices)

        def mutate() -> None:
            nonlocal cluster_id
            cluster = self.state.add_cluster(ShapeKind.POLYGON, center, size)
            self.state.select_only(cluster.cluster_id)
            cluster_id = cluster.cluster_id

        self._run_immediate_edit(mutate)
        return cluster_id, None

    def move_selected_by(self, delta_x: float, delta_y: float) -> None:
        selected_ids = set(self.state.selected_cluster_ids)
        for cluster in self.state.clusters:
            if cluster.cluster_id not in selected_ids:
                continue
            cluster.center.x += delta_x
            cluster.center.y += delta_y

    def translate_selected_from_origins(
        self,
        original_centers: dict[int, Point],
        delta_x: float,
        delta_y: float,
    ) -> None:
        selected_ids = set(self.state.selected_cluster_ids)
        for cluster in self.state.clusters:
            if cluster.cluster_id not in selected_ids:
                continue
            origin = original_centers.get(cluster.cluster_id)
            if origin is None:
                continue
            cluster.center.x = origin.x + delta_x
            cluster.center.y = origin.y + delta_y

    def set_cluster_center(self, cluster_id: int, center: Point) -> None:
        cluster = self.state.cluster_by_id(cluster_id)
        if cluster is None:
            return
        cluster.center.x = center.x
        cluster.center.y = center.y

    def move_polygon_vertex_to(self, cluster_id: int, vertex_index: int, world_point: Point) -> bool:
        cluster = self.state.cluster_by_id(cluster_id)
        if cluster is None or cluster.shape_kind is not ShapeKind.POLYGON:
            return False

        vertices = [
            Point(cluster.center.x + vertex.x, cluster.center.y + vertex.y)
            for vertex in cluster.size.vertices_local
        ]
        if vertex_index >= len(vertices):
            return False

        vertices[vertex_index] = world_point
        if validate_polygon_vertices(vertices):
            return False

        center, size = polygon_geometry_from_world_vertices(
            vertices,
            polygon_scale=cluster.size.polygon_scale,
        )
        cluster.center = center
        cluster.size = size
        return True

    def set_placement_radius(self, value: float, source: object) -> None:
        self.ensure_continuous_history(source)
        self.state.placement_circle_size.radius = value
        self.state.placement_circle_size.width = value * 2.0
        self.state.placement_circle_size.height = value * 2.0
        self.clear_status()
        self._notify()

    def set_placement_width(self, value: float, source: object) -> None:
        self.ensure_continuous_history(source)
        self.state.placement_rectangle_size.width = value
        self.clear_status()
        self._notify()

    def set_placement_height(self, value: float, source: object) -> None:
        self.ensure_continuous_history(source)
        self.state.placement_rectangle_size.height = value
        self.clear_status()
        self._notify()

    def set_placement_function_orientation(self, orientation: FunctionOrientation) -> None:
        def mutate() -> None:
            self.state.placement_function_size.function_orientation = orientation
            self._refresh_function_size(self.state.placement_function_size)

        self._run_immediate_edit(mutate)

    def set_placement_function_expression(self, expression: str, source: object) -> None:
        self.ensure_continuous_history(source)
        self.state.placement_function_size.function_expression = expression
        self._refresh_function_size(self.state.placement_function_size)
        self.clear_status()
        self._notify()

    def set_placement_function_range_start(self, value: float, source: object) -> None:
        self.ensure_continuous_history(source)
        self.state.placement_function_size.function_range_start = value
        self._refresh_function_size(self.state.placement_function_size)
        self.clear_status()
        self._notify()

    def set_placement_function_range_end(self, value: float, source: object) -> None:
        self.ensure_continuous_history(source)
        self.state.placement_function_size.function_range_end = value
        self._refresh_function_size(self.state.placement_function_size)
        self.clear_status()
        self._notify()

    def set_placement_function_thickness(self, value: float, source: object) -> None:
        self.ensure_continuous_history(source)
        self.state.placement_function_size.function_thickness = value
        self._refresh_function_size(self.state.placement_function_size)
        self.clear_status()
        self._notify()

    def set_selection_shape(self, target_shape: ShapeKind) -> None:
        if target_shape is ShapeKind.FUNCTION or not self.state.selected_clusters():
            return
        self._run_immediate_edit(lambda: self._apply_selection_shape_change(target_shape))

    def set_selection_radius(self, value: float, source: object) -> None:
        self.ensure_continuous_history(source)
        self._apply_selection_radius(value)
        self.clear_status()
        self._notify()

    def set_selection_width(self, value: float, source: object) -> None:
        self.ensure_continuous_history(source)
        self._apply_selection_width(value)
        self.clear_status()
        self._notify()

    def set_selection_height(self, value: float, source: object) -> None:
        self.ensure_continuous_history(source)
        self._apply_selection_height(value)
        self.clear_status()
        self._notify()

    def set_selection_polygon_scale(self, value: float, source: object) -> None:
        self.ensure_continuous_history(source)
        self._apply_selection_polygon_scale(value)
        self.clear_status()
        self._notify()

    def set_selection_function_orientation(self, orientation: FunctionOrientation) -> None:
        if not self._selected_function_clusters():
            return

        def mutate() -> None:
            for cluster in self._selected_function_clusters():
                cluster.size.function_orientation = orientation
                self._refresh_function_size(cluster.size)

        self._run_immediate_edit(mutate)

    def set_selection_function_expression(self, expression: str, source: object) -> None:
        selected = self._selected_function_clusters()
        if len(selected) != 1:
            return
        self.ensure_continuous_history(source)
        selected[0].size.function_expression = expression
        self._refresh_function_size(selected[0].size)
        self.clear_status()
        self._notify()

    def set_selection_function_range_start(self, value: float, source: object) -> None:
        if not self._selected_function_clusters():
            return
        self.ensure_continuous_history(source)
        for cluster in self._selected_function_clusters():
            cluster.size.function_range_start = value
            self._refresh_function_size(cluster.size)
        self.clear_status()
        self._notify()

    def set_selection_function_range_end(self, value: float, source: object) -> None:
        if not self._selected_function_clusters():
            return
        self.ensure_continuous_history(source)
        for cluster in self._selected_function_clusters():
            cluster.size.function_range_end = value
            self._refresh_function_size(cluster.size)
        self.clear_status()
        self._notify()

    def set_selection_function_thickness(self, value: float, source: object) -> None:
        if not self._selected_function_clusters():
            return
        self.ensure_continuous_history(source)
        for cluster in self._selected_function_clusters():
            cluster.size.function_thickness = value
            self._refresh_function_size(cluster.size)
        self.clear_status()
        self._notify()

    def set_total_cluster_stars(self, value: int, source: object) -> None:
        self.ensure_continuous_history(source)
        self.state.total_cluster_stars = value
        self.clear_status()
        self._notify()

    def set_distribution_mode(self, mode: DistributionMode) -> None:
        def mutate() -> None:
            self.state.distribution_mode = mode
            if self.state.distribution_mode is DistributionMode.MANUAL:
                if sum(cluster.manual_star_count for cluster in self.state.clusters) != self.state.total_cluster_stars:
                    self._apply_even_manual_counts()
                self._sync_total_stars_for_manual_mode()

        self._run_immediate_edit(mutate)

    def set_deviation_percent(self, value: float, source: object) -> None:
        self.ensure_continuous_history(source)
        self.state.deviation_percent = value
        self.clear_status()
        self._notify()

    def set_parameter_enabled(self, enabled: bool) -> None:
        self._run_immediate_edit(lambda: setattr(self.state.star_parameter, "enabled", enabled))

    def set_parameter_name(self, name: str, source: object) -> None:
        self.ensure_continuous_history(source)
        self.state.star_parameter.name = name
        self.clear_status()
        self._notify()

    def set_parameter_min(self, value: float, source: object) -> None:
        self.ensure_continuous_history(source)
        self.state.star_parameter.min_value = value
        self.clear_status()
        self._notify()

    def set_parameter_max(self, value: float, source: object) -> None:
        self.ensure_continuous_history(source)
        self.state.star_parameter.max_value = value
        self.clear_status()
        self._notify()

    def set_parameter_mode(self, mode: StarParameterMode) -> None:
        self._run_immediate_edit(lambda: setattr(self.state.star_parameter, "mode", mode))

    def set_parameter_function_body(self, body: str, source: object) -> None:
        self.ensure_continuous_history(source)
        self.state.star_parameter.function_body = body
        self.clear_status()
        self._notify()

    def set_trash_star_count(self, value: int, source: object) -> None:
        self.ensure_continuous_history(source)
        self.state.trash_star_count = value
        self.clear_status()
        self._notify()

    def set_trash_min_distance(self, value: float, source: object) -> None:
        self.ensure_continuous_history(source)
        self.state.trash_min_distance = value
        self.clear_status()
        self._notify()

    def set_manual_count(self, cluster_id: int, value: int, source: object) -> None:
        cluster = self.state.cluster_by_id(cluster_id)
        if cluster is None:
            return
        self.ensure_continuous_history(source)
        cluster.manual_star_count = value
        self._sync_total_stars_for_manual_mode()
        self.clear_status()
        self._notify()

    def export_to_path(self, output_path: Path) -> int:
        localizer = get_localizer()
        errors = validate_state(self.state)
        if errors:
            raise GenerationError(errors[0])

        generated = generate_star_field(self.state)
        parameter_name = self.state.star_parameter.name.strip() if self.state.star_parameter.enabled else None
        output_path.write_text(
            format_points_for_export(generated.stars, parameter_name=parameter_name),
            encoding="utf-8",
        )
        self._last_save_path = output_path
        try:
            save_last_save_path(output_path)
        except OSError:
            pass
        self.session.status_text = localizer.text(
            "status.saved",
            count=len(generated.stars),
            filename=output_path.name,
        )
        self.session.status_kind = "success"
        self._notify()
        return len(generated.stars)

    def export_cluster_configuration_to_path(self, output_path: Path) -> None:
        localizer = get_localizer()
        save_cluster_configuration(self.state, output_path)
        self._last_config_save_path = output_path
        try:
            save_last_config_save_path(output_path)
        except OSError:
            pass
        self.session.status_text = localizer.text(
            "status.configuration_saved",
            filename=output_path.name,
        )
        self.session.status_kind = "success"
        self._notify()

    def import_cluster_configuration_from_path(self, input_path: Path) -> int:
        localizer = get_localizer()
        try:
            loaded_configuration = load_cluster_configuration(input_path)
        except ClusterConfigurationError as exc:
            raise GenerationError(str(exc)) from exc

        def mutate() -> None:
            self.state.clusters = [cluster.copy() for cluster in loaded_configuration.clusters]
            loaded_cluster_ids = {cluster.cluster_id for cluster in self.state.clusters}
            max_cluster_id = max(loaded_cluster_ids) if loaded_cluster_ids else 0

            if loaded_configuration.selected_cluster_ids is None:
                self.state.selected_cluster_ids = []
            else:
                self.state.selected_cluster_ids = [
                    cluster_id
                    for cluster_id in loaded_configuration.selected_cluster_ids
                    if cluster_id in loaded_cluster_ids
                ]

            if loaded_configuration.next_cluster_id is None:
                self.state.next_cluster_id = max_cluster_id + 1
            else:
                self.state.next_cluster_id = max(
                    loaded_configuration.next_cluster_id,
                    max_cluster_id + 1,
                )

            if loaded_configuration.placement_circle_size is not None:
                self.state.placement_circle_size = loaded_configuration.placement_circle_size.copy()
            if loaded_configuration.placement_rectangle_size is not None:
                self.state.placement_rectangle_size = loaded_configuration.placement_rectangle_size.copy()
            if loaded_configuration.placement_function_size is not None:
                self.state.placement_function_size = loaded_configuration.placement_function_size.copy()
            if loaded_configuration.total_cluster_stars is not None:
                self.state.total_cluster_stars = loaded_configuration.total_cluster_stars
            if loaded_configuration.distribution_mode is not None:
                self.state.distribution_mode = loaded_configuration.distribution_mode
            if loaded_configuration.deviation_percent is not None:
                self.state.deviation_percent = loaded_configuration.deviation_percent
            if loaded_configuration.star_parameter is not None:
                self.state.star_parameter = loaded_configuration.star_parameter.copy()
            elif loaded_configuration.star_parameter_function_body is not None:
                self.state.star_parameter.function_body = loaded_configuration.star_parameter_function_body
            if loaded_configuration.trash_star_count is not None:
                self.state.trash_star_count = loaded_configuration.trash_star_count
            if loaded_configuration.trash_min_distance is not None:
                self.state.trash_min_distance = loaded_configuration.trash_min_distance

        self._run_immediate_edit(mutate)
        self._last_config_save_path = input_path
        try:
            save_last_config_save_path(input_path)
        except OSError:
            pass
        self.session.status_text = localizer.text(
            "status.configuration_loaded",
            count=len(loaded_configuration.clusters),
            filename=input_path.name,
        )
        self.session.status_kind = "success"
        self._notify()
        return len(loaded_configuration.clusters)

    def _sync_total_stars_for_manual_mode(self) -> None:
        if self.state.distribution_mode is not DistributionMode.MANUAL:
            return
        self.state.total_cluster_stars = sum(cluster.manual_star_count for cluster in self.state.clusters)

    def _clipboard_offset(self, clusters: Sequence) -> Point:
        first_bounds = get_shape(clusters[0].shape_kind).bounding_box(clusters[0].center, clusters[0].size)
        min_x, min_y, max_x, max_y = first_bounds.min_x, first_bounds.min_y, first_bounds.max_x, first_bounds.max_y
        for cluster in clusters[1:]:
            bounds = get_shape(cluster.shape_kind).bounding_box(cluster.center, cluster.size)
            min_x = min(min_x, bounds.min_x)
            min_y = min(min_y, bounds.min_y)
            max_x = max(max_x, bounds.max_x)
            max_y = max(max_y, bounds.max_y)

        width = max_x - min_x
        height = max_y - min_y
        dx = max(1.0, float(round(width * 0.1)))
        dy = max(1.0, float(round(height * 0.1)))
        return Point(dx, -dy)

    def _apply_even_manual_counts(self, total: int | None = None) -> None:
        total_value = self.state.total_cluster_stars if total is None else total
        counts = even_counts(total_value, len(self.state.clusters))
        for cluster, count in zip(self.state.clusters, counts, strict=False):
            cluster.manual_star_count = count

    def _selected_function_clusters(self):
        return [cluster for cluster in self.state.selected_clusters() if cluster.shape_kind is ShapeKind.FUNCTION]

    def _refresh_function_size(self, size: ClusterSize) -> None:
        fallback_vertices = size.vertices_local
        try:
            refreshed = function_size_from_parameters(
                size.function_expression,
                size.function_orientation,
                size.function_range_start,
                size.function_range_end,
                size.function_thickness,
                fallback_vertices_local=fallback_vertices,
            )
        except ValueError:
            return

        size.radius = refreshed.radius
        size.width = refreshed.width
        size.height = refreshed.height
        size.vertices_local = [Point(vertex.x, vertex.y) for vertex in refreshed.vertices_local]

    def _function_editor_view_model(self, size: ClusterSize, *, visible: bool, show_expression: bool) -> FunctionEditorViewModel:
        return FunctionEditorViewModel(
            visible=visible,
            show_expression=show_expression,
            expression=size.function_expression,
            orientation_id=size.function_orientation.value,
            range_start=size.function_range_start,
            range_end=size.function_range_end,
            thickness=size.function_thickness,
        )

    def _rectangle_polygon_vertices(self, width: float, height: float) -> list[Point]:
        half_width = width / 2.0
        half_height = height / 2.0
        return [
            Point(-half_width, -half_height),
            Point(half_width, -half_height),
            Point(half_width, half_height),
            Point(-half_width, half_height),
        ]

    def _convert_cluster_geometry(self, cluster, target_shape: ShapeKind) -> tuple[Point, ClusterSize]:
        current_center = Point(cluster.center.x, cluster.center.y)
        current_size = cluster.size

        if cluster.shape_kind is ShapeKind.FUNCTION or target_shape is ShapeKind.FUNCTION:
            return current_center, current_size.copy()

        if cluster.shape_kind is target_shape:
            return current_center, current_size.copy()

        if target_shape is ShapeKind.POLYGON:
            if cluster.shape_kind is ShapeKind.CIRCLE:
                span = max(current_size.radius * 2.0, self.config.limits.size_min)
                return (
                    current_center,
                    polygon_size_from_local_vertices(self._rectangle_polygon_vertices(span, span)),
                )

            width = max(current_size.width, self.config.limits.size_min)
            height = max(current_size.height, self.config.limits.size_min)
            return (
                current_center,
                polygon_size_from_local_vertices(self._rectangle_polygon_vertices(width, height)),
            )

        if cluster.shape_kind is ShapeKind.POLYGON:
            bounds = polygon_local_bounds(current_size.vertices_local)
            width = max(bounds.max_x - bounds.min_x, self.config.limits.size_min)
            height = max(bounds.max_y - bounds.min_y, self.config.limits.size_min)
            bounds_center = Point(
                cluster.center.x + (bounds.min_x + bounds.max_x) / 2.0,
                cluster.center.y + (bounds.min_y + bounds.max_y) / 2.0,
            )
            if target_shape is ShapeKind.CIRCLE:
                span = max(width, height)
                return bounds_center, ClusterSize(radius=span / 2.0, width=span, height=span)
            return bounds_center, ClusterSize(radius=max(width, height) / 2.0, width=width, height=height)

        if cluster.shape_kind is ShapeKind.CIRCLE and target_shape is ShapeKind.RECTANGLE:
            span = current_size.radius * 2.0
            return current_center, ClusterSize(radius=span / 2.0, width=span, height=span)
        if cluster.shape_kind is ShapeKind.RECTANGLE and target_shape is ShapeKind.CIRCLE:
            span = max(current_size.width, current_size.height)
            return current_center, ClusterSize(radius=span / 2.0, width=span, height=span)
        return current_center, current_size.copy()

    def _apply_selection_shape_change(self, target_shape: ShapeKind) -> None:
        for cluster in self.state.selected_clusters():
            if cluster.shape_kind is ShapeKind.FUNCTION:
                continue
            cluster.center, cluster.size = self._convert_cluster_geometry(cluster, target_shape)
            cluster.shape_kind = target_shape

    def _apply_selection_radius(self, radius: float) -> None:
        for cluster in self.state.selected_clusters():
            if cluster.shape_kind is not ShapeKind.CIRCLE:
                continue
            cluster.size.radius = radius
            cluster.size.width = radius * 2.0
            cluster.size.height = radius * 2.0

    def _apply_selection_width(self, width: float) -> None:
        for cluster in self.state.selected_clusters():
            if cluster.shape_kind is not ShapeKind.RECTANGLE:
                continue
            cluster.size.width = width
            cluster.size.radius = max(cluster.size.width, cluster.size.height) / 2.0

    def _apply_selection_height(self, height: float) -> None:
        for cluster in self.state.selected_clusters():
            if cluster.shape_kind is not ShapeKind.RECTANGLE:
                continue
            cluster.size.height = height
            cluster.size.radius = max(cluster.size.width, cluster.size.height) / 2.0

    def _apply_selection_polygon_scale(self, percent: float) -> None:
        for cluster in self.state.selected_clusters():
            if cluster.shape_kind is not ShapeKind.POLYGON:
                continue
            current_scale = max(cluster.size.polygon_scale, self.config.limits.size_min)
            factor = percent / current_scale
            if abs(factor - 1.0) <= 1e-9:
                cluster.size.polygon_scale = percent
                continue
            scaled_vertices = [
                Point(vertex.x * factor, vertex.y * factor)
                for vertex in cluster.size.vertices_local
            ]
            cluster.size = polygon_size_from_local_vertices(scaled_vertices, polygon_scale=percent)

    def _build_cluster_panel_view_model(self) -> ClusterPanelViewModel:
        localizer = get_localizer()
        placement_shape = self.active_tool.shape_kind()
        default_function_editor = self._function_editor_view_model(
            self.state.placement_function_size,
            visible=False,
            show_expression=False,
        )
        if placement_shape is None:
            placement = PlacementViewModel(
                info_text=localizer.text("controller.placement.none"),
                show_radius=False,
                radius=self.state.placement_circle_size.radius,
                show_width=False,
                width=self.state.placement_rectangle_size.width,
                show_height=False,
                height=self.state.placement_rectangle_size.height,
                function_editor=default_function_editor,
            )
        elif placement_shape is ShapeKind.POLYGON:
            placement = PlacementViewModel(
                info_text=localizer.text("controller.placement.polygon"),
                show_radius=False,
                radius=self.state.placement_circle_size.radius,
                show_width=False,
                width=self.state.placement_rectangle_size.width,
                show_height=False,
                height=self.state.placement_rectangle_size.height,
                function_editor=default_function_editor,
            )
        elif placement_shape is ShapeKind.FUNCTION:
            placement = PlacementViewModel(
                info_text=localizer.text(
                    "controller.placement.shape_defaults",
                    shape_name=localizer.shape_name(placement_shape),
                ),
                show_radius=False,
                radius=self.state.placement_circle_size.radius,
                show_width=False,
                width=self.state.placement_rectangle_size.width,
                show_height=False,
                height=self.state.placement_rectangle_size.height,
                function_editor=self._function_editor_view_model(
                    self.state.placement_function_size,
                    visible=True,
                    show_expression=True,
                ),
            )
        else:
            placement_size = self.state.placement_size_for_shape(placement_shape)
            placement = PlacementViewModel(
                info_text=localizer.text(
                    "controller.placement.shape_defaults",
                    shape_name=localizer.shape_name(placement_shape),
                ),
                show_radius=placement_shape is ShapeKind.CIRCLE,
                radius=placement_size.radius,
                show_width=placement_shape is ShapeKind.RECTANGLE,
                width=placement_size.width,
                show_height=placement_shape is ShapeKind.RECTANGLE,
                height=placement_size.height,
                function_editor=default_function_editor,
            )

        selected = self.state.selected_clusters()
        selection_shape = self.state.selection_shape_kind()
        reference_size = selected[0].size if selected else ClusterSize()
        contains_function = any(cluster.shape_kind is ShapeKind.FUNCTION for cluster in selected)

        if not selected:
            selection = SelectionViewModel(
                info_text=localizer.text("controller.selection.none"),
                show_shape_selector=False,
                active_shape_id=None,
                show_radius=False,
                radius=reference_size.radius,
                show_width=False,
                width=reference_size.width,
                show_height=False,
                height=reference_size.height,
                show_polygon_scale=False,
                polygon_scale=100.0,
                function_editor=default_function_editor,
                size_hint=None,
            )
            return ClusterPanelViewModel(placement=placement, selection=selection)

        info_text = (
            localizer.text("controller.selection.one")
            if len(selected) == 1
            else localizer.text("controller.selection.many", count=len(selected))
        )
        if selection_shape is None:
            size_hint = (
                localizer.text("controller.selection.function_mixed_hint")
                if contains_function
                else localizer.text("controller.selection.mixed_shape_hint")
            )
            selection = SelectionViewModel(
                info_text=info_text,
                show_shape_selector=not contains_function,
                active_shape_id=None,
                show_radius=False,
                radius=reference_size.radius,
                show_width=False,
                width=reference_size.width,
                show_height=False,
                height=reference_size.height,
                show_polygon_scale=False,
                polygon_scale=100.0,
                function_editor=default_function_editor,
                size_hint=size_hint,
            )
            return ClusterPanelViewModel(placement=placement, selection=selection)

        size_hint: str | None = None
        if selection_shape is ShapeKind.POLYGON:
            if len(selected) == 1:
                size_hint = localizer.text("controller.selection.polygon_single_hint")
            else:
                size_hint = localizer.text("controller.selection.polygon_multi_hint")
        elif selection_shape is ShapeKind.FUNCTION:
            if len(selected) == 1:
                size_hint = localizer.text("controller.selection.function_single_hint")
            else:
                size_hint = localizer.text("controller.selection.function_multi_hint")
        elif len(selected) > 1:
            size_hint = localizer.text("controller.selection.multi_size_hint")

        show_function = selection_shape is ShapeKind.FUNCTION
        selection = SelectionViewModel(
            info_text=info_text,
            show_shape_selector=selection_shape is not ShapeKind.FUNCTION,
            active_shape_id=selection_shape.value if selection_shape is not ShapeKind.FUNCTION else None,
            show_radius=selection_shape is ShapeKind.CIRCLE,
            radius=reference_size.radius,
            show_width=selection_shape is ShapeKind.RECTANGLE,
            width=reference_size.width,
            show_height=selection_shape is ShapeKind.RECTANGLE,
            height=reference_size.height,
            show_polygon_scale=selection_shape is ShapeKind.POLYGON,
            polygon_scale=reference_size.polygon_scale,
            function_editor=self._function_editor_view_model(
                reference_size,
                visible=show_function,
                show_expression=show_function and len(selected) == 1,
            ),
            size_hint=size_hint,
        )
        return ClusterPanelViewModel(placement=placement, selection=selection)

    def _build_distribution_panel_view_model(self) -> DistributionPanelViewModel:
        localizer = get_localizer()
        manual_mode = self.state.distribution_mode is DistributionMode.MANUAL
        manual_rows = tuple(
            ManualCountRowViewModel(
                cluster_id=cluster.cluster_id,
                label=localizer.text("controller.manual_cluster_label", index=index + 1),
                value=cluster.manual_star_count,
            )
            for index, cluster in enumerate(self.state.clusters)
        )
        return DistributionPanelViewModel(
            total_stars=self.state.total_cluster_stars,
            distribution_mode=self.state.distribution_mode,
            deviation_percent=self.state.deviation_percent,
            show_deviation=self.state.distribution_mode is DistributionMode.DEVIATION,
            show_manual_counts=manual_mode,
            total_stars_sensitive=not manual_mode,
            manual_note=self.config.text.manual_counts_note,
            manual_rows=manual_rows,
        )

    def _effective_status(self) -> tuple[bool, StatusViewModel]:
        localizer = get_localizer()
        errors = validate_state(self.state)
        status_text = self.session.status_text
        status_kind = self.session.status_kind
        generate_enabled = not errors

        if errors:
            generate_enabled = False
            if not self.state.clusters and errors[0] == localizer.text("error.cluster_required"):
                status_text = ""
                status_kind = "neutral"
            else:
                status_text = errors[0]
                status_kind = "error"
        elif status_kind == "error":
            status_text = ""
            status_kind = "neutral"

        return generate_enabled, StatusViewModel(text=status_text, kind=status_kind)

    def build_window_view_model(self) -> WindowViewModel:
        generate_enabled, status = self._effective_status()
        show_function_preview, function_preview_text, function_preview_is_error = self._parameter_function_preview()
        return WindowViewModel(
            toolbar=ToolbarViewModel(
                active_tool=self.active_tool,
                can_undo=self.can_undo,
                can_redo=self.can_redo,
                snap_to_integer_grid=self.snap_to_integer_grid,
                active_tool_description=self._tool_description(self.active_tool),
            ),
            cluster_panel=self._build_cluster_panel_view_model(),
            distribution_panel=self._build_distribution_panel_view_model(),
            parameter_panel=ParameterPanelViewModel(
                enabled=self.state.star_parameter.enabled,
                name=self.state.star_parameter.name,
                min_value=self.state.star_parameter.min_value,
                max_value=self.state.star_parameter.max_value,
                mode=self.state.star_parameter.mode,
                function_body=self.state.star_parameter.function_body,
                show_random_range=self.state.star_parameter.mode is StarParameterMode.RANDOM,
                show_function_body=self.state.star_parameter.mode is StarParameterMode.FUNCTION,
                show_function_preview=show_function_preview,
                function_preview_text=function_preview_text,
                function_preview_is_error=function_preview_is_error,
            ),
            trash_panel=TrashPanelViewModel(
                count=self.state.trash_star_count,
                min_distance=self.state.trash_min_distance,
                note=self.config.text.trash_note,
            ),
            status=status,
            generate_enabled=generate_enabled,
        )

    def _parameter_function_preview(self) -> tuple[bool, str, bool]:
        if not self.state.star_parameter.enabled:
            return False, "", False
        if self.state.star_parameter.mode is not StarParameterMode.FUNCTION:
            return False, "", False

        preview_text, is_error = preview_parameter_function_result(self.state.star_parameter.function_body)
        if is_error:
            return True, preview_text, True
        localizer = get_localizer()
        return True, localizer.text("ui.parameter_preview_value", value=preview_text), False

    def _tool_description(self, tool: CanvasTool) -> str:
        if tool is CanvasTool.SELECT:
            return self.config.text.select_tool_description
        if tool is CanvasTool.CIRCLE:
            return self.config.text.circle_tool_description
        if tool is CanvasTool.RECTANGLE:
            return self.config.text.rectangle_tool_description
        if tool is CanvasTool.POLYGON:
            return self.config.text.polygon_tool_description
        return self.config.text.function_tool_description

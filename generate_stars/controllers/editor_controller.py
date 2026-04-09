from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from ..config import AppConfig
from ..generator import GenerationError, even_counts, format_points_for_export, generate_star_field, validate_state
from ..history import HistoryManager
from ..models import AppState, CanvasTool, ClusterSize, DistributionMode, Point, ShapeKind
from ..preferences import load_last_save_path, save_last_save_path
from ..shapes import polygon_geometry_from_world_vertices, polygon_local_bounds, polygon_size_from_local_vertices, validate_polygon_vertices
from .view_models import (
    ClusterPanelViewModel,
    DistributionPanelViewModel,
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
    status_text: str = ""
    status_kind: str = "neutral"


class EditorController:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state = AppState()
        self.session = EditorSessionState(status_text=config.text.ready_status)
        self._history = HistoryManager(limit=100)
        self._last_save_path = load_last_save_path()
        self._continuous_history_source: object | None = None
        self._change_listener: Callable[[], None] | None = None

    @property
    def active_tool(self) -> CanvasTool:
        return self.session.active_tool

    @property
    def last_save_path(self) -> Path | None:
        return self._last_save_path

    @property
    def can_undo(self) -> bool:
        return self._history.can_undo

    @property
    def can_redo(self) -> bool:
        return self._history.can_redo

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
            self.session.status_text = self.config.text.ready_status
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

    def place_cluster(self, shape_kind: ShapeKind, center: Point) -> int:
        cluster_id = 0

        def mutate() -> None:
            nonlocal cluster_id
            cluster = self.state.add_cluster(shape_kind, center)
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

    def set_selection_shape(self, target_shape: ShapeKind) -> None:
        if not self.state.selected_clusters():
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
        save_last_save_path(output_path)
        self.session.status_text = f"Saved {len(generated.stars)} stars to {output_path.name}."
        self.session.status_kind = "success"
        self._notify()
        return len(generated.stars)

    def _sync_total_stars_for_manual_mode(self) -> None:
        if self.state.distribution_mode is not DistributionMode.MANUAL:
            return
        self.state.total_cluster_stars = sum(cluster.manual_star_count for cluster in self.state.clusters)

    def _apply_even_manual_counts(self, total: int | None = None) -> None:
        total_value = self.state.total_cluster_stars if total is None else total
        counts = even_counts(total_value, len(self.state.clusters))
        for cluster, count in zip(self.state.clusters, counts, strict=False):
            cluster.manual_star_count = count

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
        placement_shape = self.active_tool.shape_kind()
        if placement_shape is None:
            placement = PlacementViewModel(
                info_text="Choose Circle, Rectangle, or Polygon from the toolbar to place new clusters.",
                show_radius=False,
                radius=self.state.placement_circle_size.radius,
                show_width=False,
                width=self.state.placement_rectangle_size.width,
                show_height=False,
                height=self.state.placement_rectangle_size.height,
            )
        elif placement_shape is ShapeKind.POLYGON:
            placement = PlacementViewModel(
                info_text="Click to add polygon vertices. Click the first vertex to finish, and press Escape to cancel the draft.",
                show_radius=False,
                radius=self.state.placement_circle_size.radius,
                show_width=False,
                width=self.state.placement_rectangle_size.width,
                show_height=False,
                height=self.state.placement_rectangle_size.height,
            )
        else:
            placement_size = self.state.placement_size_for_shape(placement_shape)
            placement = PlacementViewModel(
                info_text=f"New {placement_shape.value} clusters use these placement defaults.",
                show_radius=placement_shape is ShapeKind.CIRCLE,
                radius=placement_size.radius,
                show_width=placement_shape is ShapeKind.RECTANGLE,
                width=placement_size.width,
                show_height=placement_shape is ShapeKind.RECTANGLE,
                height=placement_size.height,
            )

        selected = self.state.selected_clusters()
        selection_shape = self.state.selection_shape_kind()
        reference_size = selected[0].size if selected else ClusterSize()

        if not selected:
            selection = SelectionViewModel(
                info_text="No cluster selected.",
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
                size_hint=None,
            )
            return ClusterPanelViewModel(placement=placement, selection=selection)

        info_text = "1 cluster selected." if len(selected) == 1 else f"{len(selected)} clusters selected."
        if selection_shape is None:
            selection = SelectionViewModel(
                info_text=info_text,
                show_shape_selector=True,
                active_shape_id=None,
                show_radius=False,
                radius=reference_size.radius,
                show_width=False,
                width=reference_size.width,
                show_height=False,
                height=reference_size.height,
                show_polygon_scale=False,
                polygon_scale=100.0,
                size_hint="Shape changes apply to all selected clusters. Size editing requires the same shape.",
            )
            return ClusterPanelViewModel(placement=placement, selection=selection)

        size_hint: str | None = None
        if selection_shape is ShapeKind.POLYGON:
            if len(selected) == 1:
                size_hint = "Drag polygon vertices on the canvas to edit the shape. Scale applies around the polygon center."
            else:
                size_hint = "Scale applies to all selected polygons around their own centers."
        elif len(selected) > 1:
            size_hint = "Size changes apply to all selected clusters."

        selection = SelectionViewModel(
            info_text=info_text,
            show_shape_selector=True,
            active_shape_id=selection_shape.value,
            show_radius=selection_shape is ShapeKind.CIRCLE,
            radius=reference_size.radius,
            show_width=selection_shape is ShapeKind.RECTANGLE,
            width=reference_size.width,
            show_height=selection_shape is ShapeKind.RECTANGLE,
            height=reference_size.height,
            show_polygon_scale=selection_shape is ShapeKind.POLYGON,
            polygon_scale=reference_size.polygon_scale,
            size_hint=size_hint,
        )
        return ClusterPanelViewModel(placement=placement, selection=selection)

    def _build_distribution_panel_view_model(self) -> DistributionPanelViewModel:
        manual_mode = self.state.distribution_mode is DistributionMode.MANUAL
        manual_rows = tuple(
            ManualCountRowViewModel(
                cluster_id=cluster.cluster_id,
                label=f"Cluster {index + 1}",
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
        errors = validate_state(self.state)
        status_text = self.session.status_text
        status_kind = self.session.status_kind
        generate_enabled = not errors

        if errors:
            generate_enabled = False
            if not self.state.clusters and errors[0] == "Cluster stars require at least one cluster.":
                status_text = self.config.text.shape_interaction_hint
                status_kind = "neutral"
            else:
                status_text = errors[0]
                status_kind = "error"
        elif status_kind == "error":
            status_text = self.config.text.ready_status
            status_kind = "neutral"

        return generate_enabled, StatusViewModel(text=status_text, kind=status_kind)

    def build_window_view_model(self) -> WindowViewModel:
        generate_enabled, status = self._effective_status()
        return WindowViewModel(
            toolbar=ToolbarViewModel(
                active_tool=self.active_tool,
                can_undo=self.can_undo,
                can_redo=self.can_redo,
                active_tool_description=self._tool_description(self.active_tool),
            ),
            cluster_panel=self._build_cluster_panel_view_model(),
            distribution_panel=self._build_distribution_panel_view_model(),
            parameter_panel=ParameterPanelViewModel(
                enabled=self.state.star_parameter.enabled,
                name=self.state.star_parameter.name,
                min_value=self.state.star_parameter.min_value,
                max_value=self.state.star_parameter.max_value,
            ),
            trash_panel=TrashPanelViewModel(
                count=self.state.trash_star_count,
                min_distance=self.state.trash_min_distance,
                note=self.config.text.trash_note,
            ),
            status=status,
            generate_enabled=generate_enabled,
        )

    def _tool_description(self, tool: CanvasTool) -> str:
        if tool is CanvasTool.SELECT:
            return self.config.text.select_tool_description
        if tool is CanvasTool.CIRCLE:
            return self.config.text.circle_tool_description
        if tool is CanvasTool.RECTANGLE:
            return self.config.text.rectangle_tool_description
        return self.config.text.polygon_tool_description

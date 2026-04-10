from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gtk

from ..config import AppConfig
from ..controllers.editor_controller import EditorController
from ..generator import preview_cluster_counts
from ..localization import get_localizer
from ..models import CanvasTool, Point, ShapeKind
from ..shapes import get_shape, polygon_world_vertices


@dataclass(slots=True)
class CanvasViewportState:
    scale: float
    offset: Point


def snap_coordinate_to_integer(value: float, enabled: bool) -> float:
    if not enabled:
        return value
    if value >= 0.0:
        return float(math.floor(value + 0.5))
    return float(math.ceil(value - 0.5))


def snap_world_point(point: Point, enabled: bool) -> Point:
    return Point(
        snap_coordinate_to_integer(point.x, enabled),
        snap_coordinate_to_integer(point.y, enabled),
    )


def snap_translation_delta(delta_x: float, delta_y: float, enabled: bool) -> Point:
    return Point(
        snap_coordinate_to_integer(delta_x, enabled),
        snap_coordinate_to_integer(delta_y, enabled),
    )


def snap_drag_center(current_world: Point, pointer_offset: Point, enabled: bool) -> Point:
    return snap_world_point(
        Point(
            current_world.x - pointer_offset.x,
            current_world.y - pointer_offset.y,
        ),
        enabled,
    )


class StarCanvas(Gtk.DrawingArea):
    def __init__(
        self,
        controller: EditorController,
        is_space_pressed: Callable[[], bool],
        config: AppConfig,
    ) -> None:
        super().__init__()
        self.controller = controller
        self.config = config
        self._is_space_pressed = is_space_pressed
        self.viewport = CanvasViewportState(
            scale=config.defaults.viewport_scale,
            offset=Point(0.0, 0.0),
        )
        self._pointer_position = Point(0.0, 0.0)
        self._press_position = Point(0.0, 0.0)
        self._last_drag_position = Point(0.0, 0.0)
        self._primary_button_down = False
        self._middle_button_down = False
        self._drag_mode: str | None = None
        self._active_cluster_id: int | None = None
        self._active_vertex_cluster_id: int | None = None
        self._active_vertex_index: int | None = None
        self._hovered_cluster_id: int | None = None
        self._hovered_vertex_cluster_id: int | None = None
        self._hovered_vertex_index: int | None = None
        self._press_cluster_id: int | None = None
        self._press_vertex_cluster_id: int | None = None
        self._press_vertex_index: int | None = None
        self._press_ctrl = False
        self._selection_box_start: Point | None = None
        self._selection_box_end: Point | None = None
        self._polygon_draft_vertices: list[Point] = []
        self._polygon_draft_preview: Point | None = None
        self._move_drag_start_world: Point | None = None
        self._move_drag_pointer_offset: Point | None = None
        self._move_drag_original_centers: dict[int, Point] = {}
        self._drag_threshold_px = max(4.0, self.config.canvas.cluster_hit_tolerance_px)
        self._marker_radius_px = self.config.canvas.center_marker_radius_px

        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_focusable(True)
        self.set_content_width(self.config.canvas.default_width)
        self.set_content_height(self.config.canvas.default_height)
        self.set_draw_func(self._on_draw)
        self.add_css_class("canvas")

        click = Gtk.GestureClick.new()
        click.set_button(Gdk.BUTTON_PRIMARY)
        click.connect("pressed", self._on_pressed)
        click.connect("released", self._on_released)
        self.add_controller(click)

        middle_click = Gtk.GestureClick.new()
        middle_click.set_button(Gdk.BUTTON_MIDDLE)
        middle_click.connect("pressed", self._on_middle_pressed)
        middle_click.connect("released", self._on_middle_released)
        self.add_controller(middle_click)

        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)

        scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", self._on_scroll)
        self.add_controller(scroll)

    @property
    def state(self):
        return self.controller.state

    def has_polygon_draft(self) -> bool:
        return bool(self._polygon_draft_vertices)

    def cancel_polygon_draft(self) -> bool:
        if not self._polygon_draft_vertices:
            return False
        self._clear_polygon_draft()
        self.queue_draw()
        return True

    def complete_polygon_draft(self) -> str | None:
        if not self._polygon_draft_vertices:
            return None

        cluster_id, error = self.controller.complete_polygon_draft(self._polygon_draft_vertices)
        if error is not None:
            self.controller.set_status(error, "error")
            return error

        self._clear_polygon_draft()
        self._hovered_cluster_id = cluster_id
        self.queue_draw()
        return None

    def _clear_polygon_draft(self) -> None:
        self._polygon_draft_vertices.clear()
        self._polygon_draft_preview = None

    def _screen_center(self) -> Point:
        return Point(self.get_allocated_width() / 2.0, self.get_allocated_height() / 2.0)

    def world_to_screen(self, point: Point) -> Point:
        center = self._screen_center()
        return Point(
            x=center.x + self.viewport.offset.x + point.x * self.viewport.scale,
            y=center.y + self.viewport.offset.y - point.y * self.viewport.scale,
        )

    def screen_to_world(self, x: float, y: float) -> Point:
        center = self._screen_center()
        scale = max(self.viewport.scale, 1e-6)
        return Point(
            x=(x - center.x - self.viewport.offset.x) / scale,
            y=-(y - center.y - self.viewport.offset.y) / scale,
        )

    def _current_world_bounds(self) -> tuple[float, float, float, float]:
        top_left = self.screen_to_world(0.0, 0.0)
        bottom_right = self.screen_to_world(self.get_allocated_width(), self.get_allocated_height())
        min_x = min(top_left.x, bottom_right.x)
        max_x = max(top_left.x, bottom_right.x)
        min_y = min(top_left.y, bottom_right.y)
        max_y = max(top_left.y, bottom_right.y)
        return min_x, max_x, min_y, max_y

    def _modifier_state_is_ctrl(self, state: Gdk.ModifierType) -> bool:
        return bool(state & Gdk.ModifierType.CONTROL_MASK)

    def _press_moved_far_enough(self, x: float, y: float) -> bool:
        return math.hypot(x - self._press_position.x, y - self._press_position.y) >= self._drag_threshold_px

    def _world_hit_tolerance(self) -> float:
        return self.config.canvas.cluster_hit_tolerance_px / max(self.viewport.scale, 1e-6)

    def _snap_enabled(self) -> bool:
        return self.controller.snap_to_integer_grid

    def _editable_world_point(self, x: float, y: float) -> Point:
        return snap_world_point(self.screen_to_world(x, y), self._snap_enabled())

    def _selected_polygon_for_vertex_edit(self):
        if self.controller.active_tool is not CanvasTool.SELECT or self.has_polygon_draft():
            return None

        selected = self.state.selected_clusters()
        if len(selected) != 1 or selected[0].shape_kind is not ShapeKind.POLYGON:
            return None
        return selected[0]

    def _hit_test_cluster(self, x: float, y: float) -> int | None:
        world_point = self.screen_to_world(x, y)
        tolerance = self._world_hit_tolerance()

        for cluster in reversed(self.state.clusters):
            shape = get_shape(cluster.shape_kind)
            if shape.edge_distance(world_point, cluster.center, cluster.size) <= tolerance:
                return cluster.cluster_id
        return None

    def _hit_test_polygon_vertex(self, x: float, y: float) -> tuple[int, int] | None:
        cluster = self._selected_polygon_for_vertex_edit()
        if cluster is None:
            return None

        world_point = self.screen_to_world(x, y)
        tolerance = max(self._marker_radius_px, self.config.canvas.cluster_hit_tolerance_px) / max(
            self.viewport.scale,
            1e-6,
        )
        vertices = polygon_world_vertices(cluster.center, cluster.size.vertices_local)
        closest_index: int | None = None
        closest_distance = tolerance
        for index, vertex in enumerate(vertices):
            distance = math.hypot(world_point.x - vertex.x, world_point.y - vertex.y)
            if distance <= closest_distance:
                closest_distance = distance
                closest_index = index

        if closest_index is None:
            return None
        return cluster.cluster_id, closest_index

    def _set_hovered_cluster(self, cluster_id: int | None) -> None:
        if self._hovered_cluster_id == cluster_id:
            return
        self._hovered_cluster_id = cluster_id
        self.queue_draw()

    def _set_hovered_vertex(self, cluster_id: int | None, vertex_index: int | None) -> None:
        if self._hovered_vertex_cluster_id == cluster_id and self._hovered_vertex_index == vertex_index:
            return
        self._hovered_vertex_cluster_id = cluster_id
        self._hovered_vertex_index = vertex_index
        self.queue_draw()

    def _update_hover_state(self, x: float, y: float) -> None:
        if self.has_polygon_draft() and self.controller.active_tool is CanvasTool.POLYGON:
            self._set_hovered_vertex(None, None)
            self._set_hovered_cluster(None)
            self._polygon_draft_preview = self._editable_world_point(x, y)
            self.queue_draw()
            return

        vertex_hit = self._hit_test_polygon_vertex(x, y)
        if vertex_hit is not None:
            cluster_id, vertex_index = vertex_hit
            self._set_hovered_vertex(cluster_id, vertex_index)
            self._set_hovered_cluster(cluster_id)
            return

        self._set_hovered_vertex(None, None)
        self._set_hovered_cluster(self._hit_test_cluster(x, y))

    def _cluster_ids_in_selection_box(self) -> list[int]:
        if self._selection_box_start is None or self._selection_box_end is None:
            return []

        start_world = self.screen_to_world(self._selection_box_start.x, self._selection_box_start.y)
        end_world = self.screen_to_world(self._selection_box_end.x, self._selection_box_end.y)
        min_x = min(start_world.x, end_world.x)
        max_x = max(start_world.x, end_world.x)
        min_y = min(start_world.y, end_world.y)
        max_y = max(start_world.y, end_world.y)

        selected_ids: list[int] = []
        for cluster in self.state.clusters:
            bounds = get_shape(cluster.shape_kind).bounding_box(cluster.center, cluster.size)
            enclosed = (
                bounds.min_x >= min_x
                and bounds.max_x <= max_x
                and bounds.min_y >= min_y
                and bounds.max_y <= max_y
            )
            if enclosed:
                selected_ids.append(cluster.cluster_id)
        return selected_ids

    def _start_drag_if_needed(self, x: float, y: float) -> None:
        if self._drag_mode is not None:
            return
        if not self._press_moved_far_enough(x, y):
            return

        if self._is_space_pressed():
            self._drag_mode = "pan"
            return

        if self.controller.active_tool is not CanvasTool.SELECT:
            return

        if self._press_vertex_cluster_id is not None and not self._press_ctrl:
            self._active_vertex_cluster_id = self._press_vertex_cluster_id
            self._active_vertex_index = self._press_vertex_index
            self.controller.begin_canvas_edit()
            self._drag_mode = "vertex"
            self._set_hovered_cluster(self._press_vertex_cluster_id)
            self._set_hovered_vertex(self._press_vertex_cluster_id, self._press_vertex_index)
            return

        if self._press_cluster_id is not None and not self._press_ctrl:
            if not self.state.is_selected(self._press_cluster_id):
                self.controller.select_only(self._press_cluster_id)
            self._active_cluster_id = self._press_cluster_id
            self._move_drag_start_world = self.screen_to_world(self._press_position.x, self._press_position.y)
            self._move_drag_original_centers = {
                cluster.cluster_id: cluster.center.copy()
                for cluster in self.state.selected_clusters()
            }
            self._move_drag_pointer_offset = None
            selected = self.state.selected_clusters()
            if len(selected) == 1 and self._active_cluster_id is not None:
                cluster = selected[0]
                self._move_drag_pointer_offset = Point(
                    self._move_drag_start_world.x - cluster.center.x,
                    self._move_drag_start_world.y - cluster.center.y,
                )
            self.controller.begin_canvas_edit()
            self._drag_mode = "move"
            self._set_hovered_cluster(self._press_cluster_id)
            return

        if self._press_cluster_id is None and self._press_vertex_cluster_id is None:
            self._drag_mode = "box"
            self._selection_box_start = Point(self._press_position.x, self._press_position.y)
            self._selection_box_end = Point(x, y)
            self._set_hovered_vertex(None, None)
            self._set_hovered_cluster(None)
            self.queue_draw()

    def _place_cluster_at(self, x: float, y: float) -> None:
        shape_kind = self.controller.active_tool.shape_kind()
        if shape_kind is None or shape_kind is ShapeKind.POLYGON:
            return
        cluster_id = self.controller.place_cluster(shape_kind, self._editable_world_point(x, y))
        self._set_hovered_cluster(cluster_id)

    def _append_polygon_draft_vertex(self, world_point: Point) -> None:
        tolerance = self._world_hit_tolerance()
        if self._polygon_draft_vertices:
            last = self._polygon_draft_vertices[-1]
            if math.hypot(world_point.x - last.x, world_point.y - last.y) <= tolerance:
                return
        snapped_point = snap_world_point(world_point, self._snap_enabled())
        self._polygon_draft_vertices.append(snapped_point)
        self._polygon_draft_preview = snapped_point

    def _polygon_draft_close_hit(self, x: float, y: float) -> bool:
        if len(self._polygon_draft_vertices) < 3:
            return False

        first_vertex = self._polygon_draft_vertices[0]
        world_point = self._editable_world_point(x, y)
        return math.hypot(world_point.x - first_vertex.x, world_point.y - first_vertex.y) <= self._world_hit_tolerance()

    def _apply_vertex_drag(self, x: float, y: float) -> None:
        if self._active_vertex_cluster_id is None or self._active_vertex_index is None:
            return
        if not self.controller.move_polygon_vertex_to(
            self._active_vertex_cluster_id,
            self._active_vertex_index,
            self._editable_world_point(x, y),
        ):
            return

        self._set_hovered_cluster(self._active_vertex_cluster_id)
        self._set_hovered_vertex(self._active_vertex_cluster_id, self._active_vertex_index)
        self.queue_draw()

    def _on_pressed(self, gesture: Gtk.GestureClick, n_press: int, x: float, y: float) -> None:
        self.controller.prepare_for_canvas_interaction()
        self.grab_focus()
        self._pointer_position = Point(x, y)
        self._press_position = Point(x, y)
        self._last_drag_position = Point(x, y)
        self._primary_button_down = True
        self._drag_mode = "pan" if self._is_space_pressed() else None
        self._active_cluster_id = None
        self._active_vertex_cluster_id = None
        self._active_vertex_index = None
        self._press_cluster_id = self._hit_test_cluster(x, y)
        self._press_vertex_cluster_id = None
        self._press_vertex_index = None
        self._press_ctrl = self._modifier_state_is_ctrl(gesture.get_current_event_state())
        self._selection_box_start = None
        self._selection_box_end = None
        self._move_drag_start_world = None
        self._move_drag_pointer_offset = None
        self._move_drag_original_centers = {}

        if self.controller.active_tool is CanvasTool.SELECT and not self._is_space_pressed():
            vertex_hit = self._hit_test_polygon_vertex(x, y)
            if vertex_hit is not None:
                self._press_vertex_cluster_id, self._press_vertex_index = vertex_hit
                self._press_cluster_id = self._press_vertex_cluster_id

        if self.controller.active_tool is CanvasTool.POLYGON and self.has_polygon_draft():
            self._polygon_draft_preview = self._editable_world_point(x, y)

    def _on_middle_pressed(self, gesture: Gtk.GestureClick, n_press: int, x: float, y: float) -> None:
        self.controller.prepare_for_canvas_interaction()
        self.grab_focus()
        self._pointer_position = Point(x, y)
        self._press_position = Point(x, y)
        self._last_drag_position = Point(x, y)
        self._middle_button_down = True
        self._drag_mode = "pan"
        self._set_hovered_vertex(None, None)
        self._set_hovered_cluster(None)

    def _on_released(self, gesture: Gtk.GestureClick, n_press: int, x: float, y: float) -> None:
        self._pointer_position = Point(x, y)
        self._last_drag_position = Point(x, y)
        self._primary_button_down = False

        if self._drag_mode == "box":
            self.controller.set_selected_cluster_ids(self._cluster_ids_in_selection_box())
            self._selection_box_start = None
            self._selection_box_end = None
        elif self._drag_mode in {"move", "vertex"}:
            self.controller.finish_canvas_edit(cluster_list_changed=False)
        elif self._drag_mode is None:
            if not self._is_space_pressed():
                if self.controller.active_tool is CanvasTool.SELECT:
                    if self._press_vertex_cluster_id is not None:
                        if self._press_ctrl:
                            self.controller.toggle_selection(self._press_vertex_cluster_id)
                    elif self._press_cluster_id is not None:
                        if self._press_ctrl:
                            self.controller.toggle_selection(self._press_cluster_id)
                        else:
                            self.controller.select_only(self._press_cluster_id)
                    elif not self._press_ctrl:
                        self.controller.clear_selected_clusters()
                elif self.controller.active_tool is CanvasTool.POLYGON:
                    if not self._press_moved_far_enough(x, y):
                        if self._polygon_draft_close_hit(x, y):
                            self.complete_polygon_draft()
                        else:
                            self._append_polygon_draft_vertex(self._editable_world_point(x, y))
                elif self._press_cluster_id is None and not self._press_moved_far_enough(x, y):
                    self._place_cluster_at(x, y)

        self._drag_mode = None
        self._active_cluster_id = None
        self._active_vertex_cluster_id = None
        self._active_vertex_index = None
        self._press_cluster_id = None
        self._press_vertex_cluster_id = None
        self._press_vertex_index = None
        self._press_ctrl = False
        self._move_drag_start_world = None
        self._move_drag_pointer_offset = None
        self._move_drag_original_centers = {}

        if self.controller.active_tool is CanvasTool.POLYGON and self.has_polygon_draft():
            self._polygon_draft_preview = self._editable_world_point(x, y)
            self._set_hovered_vertex(None, None)
            self._set_hovered_cluster(None)
        else:
            self._update_hover_state(x, y)
        self.queue_draw()

    def _on_middle_released(self, gesture: Gtk.GestureClick, n_press: int, x: float, y: float) -> None:
        self._pointer_position = Point(x, y)
        self._last_drag_position = Point(x, y)
        self._middle_button_down = False
        if self._drag_mode == "pan" and not self._primary_button_down:
            self._drag_mode = None
        self._update_hover_state(x, y)
        self.queue_draw()

    def _on_motion(self, controller: Gtk.EventControllerMotion, x: float, y: float) -> None:
        self._pointer_position = Point(x, y)

        if self._middle_button_down:
            dx = x - self._last_drag_position.x
            dy = y - self._last_drag_position.y
            self._last_drag_position = Point(x, y)
            self.viewport.offset.x += dx
            self.viewport.offset.y += dy
            self._set_hovered_vertex(None, None)
            self._set_hovered_cluster(None)
            self.queue_draw()
            return

        if not self._primary_button_down:
            self._update_hover_state(x, y)
            return

        self._start_drag_if_needed(x, y)
        if self._drag_mode is None:
            if self.controller.active_tool is CanvasTool.POLYGON and self.has_polygon_draft():
                self._polygon_draft_preview = self._editable_world_point(x, y)
                self.queue_draw()
            return

        dx = x - self._last_drag_position.x
        dy = y - self._last_drag_position.y
        self._last_drag_position = Point(x, y)

        if self._drag_mode == "pan":
            self.viewport.offset.x += dx
            self.viewport.offset.y += dy
            self._set_hovered_vertex(None, None)
            self._set_hovered_cluster(None)
            self.queue_draw()
            return

        if self._drag_mode == "move":
            current_world = self.screen_to_world(x, y)
            if (
                self._active_cluster_id is not None
                and self._move_drag_pointer_offset is not None
                and len(self.state.selected_clusters()) == 1
            ):
                self.controller.set_cluster_center(
                    self._active_cluster_id,
                    snap_drag_center(current_world, self._move_drag_pointer_offset, self._snap_enabled()),
                )
            elif self._move_drag_start_world is not None:
                delta = snap_translation_delta(
                    current_world.x - self._move_drag_start_world.x,
                    current_world.y - self._move_drag_start_world.y,
                    self._snap_enabled(),
                )
                self.controller.translate_selected_from_origins(
                    self._move_drag_original_centers,
                    delta.x,
                    delta.y,
                )
            self._set_hovered_cluster(self._active_cluster_id)
            self.queue_draw()
            return

        if self._drag_mode == "vertex":
            self._apply_vertex_drag(x, y)
            return

        if self._drag_mode == "box":
            self._selection_box_end = Point(x, y)
            self.queue_draw()

    def _on_leave(self, controller: Gtk.EventControllerMotion) -> None:
        self._pointer_position = self._screen_center()
        if self.has_polygon_draft() and self.controller.active_tool is CanvasTool.POLYGON:
            self._polygon_draft_preview = None
            self.queue_draw()
        if not self._primary_button_down:
            self._set_hovered_vertex(None, None)
            self._set_hovered_cluster(None)

    def _format_hover_value(self, value: float) -> str:
        text = f"{value:.2f}".rstrip("0").rstrip(".")
        return "0" if text == "-0" else text

    def _hover_info_lines(self) -> list[str]:
        if self._hovered_cluster_id is None:
            return []

        localizer = get_localizer()
        counts = preview_cluster_counts(self.state)
        for index, cluster in enumerate(self.state.clusters):
            if cluster.cluster_id != self._hovered_cluster_id:
                continue

            lines = [localizer.text("canvas.hover.cluster", index=index + 1)]
            lines.append(
                localizer.text(
                    "canvas.hover.center",
                    x=self._format_hover_value(cluster.center.x),
                    y=self._format_hover_value(cluster.center.y),
                )
            )

            if cluster.shape_kind is ShapeKind.CIRCLE:
                lines.append(
                    localizer.text(
                        "canvas.hover.radius",
                        value=self._format_hover_value(cluster.size.radius),
                    )
                )
            elif cluster.shape_kind is ShapeKind.RECTANGLE:
                lines.append(
                    localizer.text(
                        "canvas.hover.width",
                        value=self._format_hover_value(cluster.size.width),
                    )
                )
                lines.append(
                    localizer.text(
                        "canvas.hover.height",
                        value=self._format_hover_value(cluster.size.height),
                    )
                )
            elif cluster.shape_kind is ShapeKind.FUNCTION:
                lines.append(
                    localizer.text(
                        "canvas.hover.orientation",
                        value=localizer.function_orientation_name(cluster.size.function_orientation),
                    )
                )
                lines.append(
                    localizer.text(
                        "canvas.hover.range",
                        start=self._format_hover_value(cluster.size.function_range_start),
                        end=self._format_hover_value(cluster.size.function_range_end),
                    )
                )
                lines.append(
                    localizer.text(
                        "canvas.hover.thickness",
                        value=self._format_hover_value(cluster.size.function_thickness),
                    )
                )
            else:
                lines.append(
                    localizer.text(
                        "canvas.hover.vertices",
                        count=len(cluster.size.vertices_local),
                    )
                )
            if counts is not None and index < len(counts):
                lines.append(localizer.text("canvas.hover.stars", count=counts[index]))
            else:
                lines.append(localizer.text("canvas.hover.randomized"))
            return lines
        return []

    def _draw_hover_info(self, context: cairo.Context) -> None:
        lines = self._hover_info_lines()
        if not lines:
            return

        context.save()
        context.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(self.config.canvas.hover_info_font_size)

        line_extents = [context.text_extents(line) for line in lines]
        max_width = max(extents.width for extents in line_extents)
        line_height = max(extents.height for extents in line_extents)
        panel_width = max_width + self.config.canvas.hover_info_padding_px * 2.0
        panel_height = (
            line_height * len(lines)
            + self.config.canvas.hover_info_line_spacing_px * max(0, len(lines) - 1)
            + self.config.canvas.hover_info_padding_px * 2.0
        )

        x = self.config.canvas.hover_info_margin_px
        y = self.config.canvas.hover_info_margin_px
        context.set_source_rgba(*self.config.colors.hover_info_background)
        context.rectangle(x, y, panel_width, panel_height)
        context.fill()

        baseline = y + self.config.canvas.hover_info_padding_px + line_height
        for index, line in enumerate(lines):
            color = self.config.colors.hover_info_title if index == 0 else self.config.colors.hover_info_text
            context.set_source_rgba(*color)
            context.move_to(x + self.config.canvas.hover_info_padding_px, baseline)
            context.show_text(line)
            baseline += line_height + self.config.canvas.hover_info_line_spacing_px

        context.restore()

    def _on_scroll(self, controller: Gtk.EventControllerScroll, _dx: float, dy: float) -> bool:
        if dy == 0.0:
            return False

        zoom_factor = self.config.canvas.zoom_factor if dy < 0.0 else 1.0 / self.config.canvas.zoom_factor
        old_scale = self.viewport.scale
        new_scale = max(
            self.config.canvas.min_viewport_scale,
            min(self.config.canvas.max_viewport_scale, old_scale * zoom_factor),
        )
        if math.isclose(old_scale, new_scale):
            return True

        anchor = self._pointer_position
        world_anchor = self.screen_to_world(anchor.x, anchor.y)
        self.viewport.scale = new_scale

        center = self._screen_center()
        self.viewport.offset.x = anchor.x - center.x - world_anchor.x * new_scale
        self.viewport.offset.y = anchor.y - center.y + world_anchor.y * new_scale
        self.queue_draw()
        return True

    def _grid_step(self) -> float:
        scale = max(self.viewport.scale, 1e-6)
        raw = self.config.canvas.grid_target_spacing_px / scale
        exponent = math.floor(math.log10(max(raw, 1e-6)))
        base = 10.0**exponent
        for multiplier in (1.0, 2.0, 5.0, 10.0):
            candidate = base * multiplier
            if candidate >= raw:
                return candidate
        return base * 10.0

    def _format_axis_value(self, value: float, step: float) -> str:
        if math.isclose(value, 0.0, abs_tol=step * 0.001):
            return "0"

        if step >= 1.0:
            rounded = round(value)
            return str(int(rounded))

        precision = min(6, max(0, int(math.ceil(-math.log10(step)))))
        text = f"{value:.{precision}f}".rstrip("0").rstrip(".")
        return "0" if text == "-0" else text

    def _draw_axis_labels(self, context: cairo.Context) -> None:
        min_x, max_x, min_y, max_y = self._current_world_bounds()
        step = self._grid_step()
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        origin_screen = self.world_to_screen(Point(0.0, 0.0))
        axis_x = origin_screen.x
        axis_y = origin_screen.y

        context.save()
        context.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(self.config.canvas.axis_label_font_size)
        context.set_source_rgba(*self.config.colors.axis_label)

        if 0.0 <= axis_y <= height:
            x = math.floor(min_x / step) * step
            while x <= max_x + step * 0.5:
                if not math.isclose(x, 0.0, abs_tol=step * 0.05):
                    label = self._format_axis_value(x, step)
                    screen = self.world_to_screen(Point(x, 0.0))
                    extents = context.text_extents(label)
                    label_x = screen.x - extents.width / 2.0 - extents.x_bearing
                    baseline = axis_y - self.config.canvas.axis_label_margin_px
                    if baseline - extents.height < self.config.canvas.axis_label_edge_margin_px:
                        baseline = axis_y + extents.height + self.config.canvas.axis_label_margin_px
                    if (
                        self.config.canvas.axis_label_edge_margin_px <= label_x
                        and label_x + extents.width <= width - self.config.canvas.axis_label_edge_margin_px
                    ):
                        context.move_to(label_x, baseline)
                        context.show_text(label)
                x += step

        if 0.0 <= axis_x <= width:
            y = math.floor(min_y / step) * step
            while y <= max_y + step * 0.5:
                if not math.isclose(y, 0.0, abs_tol=step * 0.05):
                    label = self._format_axis_value(y, step)
                    screen = self.world_to_screen(Point(0.0, y))
                    extents = context.text_extents(label)
                    label_x = axis_x + self.config.canvas.axis_label_margin_px
                    if label_x + extents.width > width - self.config.canvas.axis_label_edge_margin_px:
                        label_x = axis_x - extents.width - self.config.canvas.axis_label_margin_px
                    baseline = screen.y + extents.height / 2.0
                    if (
                        self.config.canvas.axis_label_edge_margin_px <= label_x
                        and baseline - extents.height >= self.config.canvas.axis_label_edge_margin_px
                        and baseline <= height - self.config.canvas.axis_label_edge_margin_px
                    ):
                        context.move_to(label_x, baseline)
                        context.show_text(label)
                y += step

        if 0.0 <= axis_x <= width and 0.0 <= axis_y <= height:
            label = "0"
            extents = context.text_extents(label)
            label_x = axis_x + self.config.canvas.axis_label_margin_px
            if label_x + extents.width > width - self.config.canvas.axis_label_edge_margin_px:
                label_x = axis_x - extents.width - self.config.canvas.axis_label_margin_px
            baseline = axis_y - self.config.canvas.axis_label_margin_px
            if baseline - extents.height < self.config.canvas.axis_label_edge_margin_px:
                baseline = axis_y + extents.height + self.config.canvas.axis_label_margin_px
            context.move_to(label_x, baseline)
            context.show_text(label)

        context.restore()

    def _draw_grid(self, context: cairo.Context) -> None:
        min_x, max_x, min_y, max_y = self._current_world_bounds()
        step = self._grid_step()

        context.set_line_width(self.config.canvas.grid_line_width / self.viewport.scale)
        context.set_source_rgba(*self.config.colors.grid)
        start_x = math.floor(min_x / step) * step
        start_y = math.floor(min_y / step) * step

        x = start_x
        while x <= max_x:
            context.move_to(x, min_y)
            context.line_to(x, max_y)
            x += step

        y = start_y
        while y <= max_y:
            context.move_to(min_x, y)
            context.line_to(max_x, y)
            y += step
        context.stroke()

        context.set_source_rgba(*self.config.colors.axis)
        context.set_line_width(self.config.canvas.axis_line_width / self.viewport.scale)
        context.move_to(min_x, 0.0)
        context.line_to(max_x, 0.0)
        context.move_to(0.0, min_y)
        context.line_to(0.0, max_y)
        context.stroke()
        context.arc(0.0, 0.0, self.config.canvas.origin_marker_radius / self.viewport.scale, 0.0, math.tau)
        context.fill()

    def _draw_clusters(self, context: cairo.Context) -> None:
        selected_ids = set(self.state.selected_cluster_ids)
        hovered_id = self._hovered_cluster_id

        for cluster in self.state.clusters:
            shape = get_shape(cluster.shape_kind)
            context.new_path()
            shape.draw_outline(context, cluster.center, cluster.size)

            is_active = cluster.cluster_id in selected_ids or cluster.cluster_id == hovered_id
            if is_active:
                context.set_source_rgba(*self.config.colors.active_cluster_outline)
            else:
                context.set_source_rgba(*self.config.colors.inactive_cluster_outline)
            context.set_line_width(self.config.canvas.cluster_outline_width / self.viewport.scale)
            context.stroke()

            context.new_path()
            context.arc(
                cluster.center.x,
                cluster.center.y,
                self._marker_radius_px / self.viewport.scale,
                0.0,
                math.tau,
            )
            if is_active:
                context.set_source_rgba(*self.config.colors.active_cluster_marker)
            else:
                context.set_source_rgba(*self.config.colors.inactive_cluster_marker)
            context.fill()

    def _draw_polygon_handles(self, context: cairo.Context) -> None:
        cluster = self._selected_polygon_for_vertex_edit()
        if cluster is None:
            return

        vertices = polygon_world_vertices(cluster.center, cluster.size.vertices_local)
        radius = self._marker_radius_px / self.viewport.scale
        line_width = self.config.canvas.cluster_outline_width / self.viewport.scale

        for index, vertex in enumerate(vertices):
            is_active = (
                self._hovered_vertex_cluster_id == cluster.cluster_id
                and self._hovered_vertex_index == index
            ) or (
                self._active_vertex_cluster_id == cluster.cluster_id
                and self._active_vertex_index == index
            )
            context.new_path()
            context.arc(vertex.x, vertex.y, radius, 0.0, math.tau)
            if is_active:
                context.set_source_rgba(*self.config.colors.active_cluster_marker)
            else:
                context.set_source_rgba(*self.config.colors.inactive_cluster_marker)
            context.fill_preserve()
            if is_active:
                context.set_source_rgba(*self.config.colors.active_cluster_outline)
            else:
                context.set_source_rgba(*self.config.colors.inactive_cluster_outline)
            context.set_line_width(line_width)
            context.stroke()

    def _draw_polygon_draft(self, context: cairo.Context) -> None:
        if not self._polygon_draft_vertices:
            return

        context.save()
        context.set_line_width(self.config.canvas.cluster_outline_width / self.viewport.scale)
        context.set_source_rgba(*self.config.colors.active_cluster_outline)
        context.move_to(self._polygon_draft_vertices[0].x, self._polygon_draft_vertices[0].y)
        for vertex in self._polygon_draft_vertices[1:]:
            context.line_to(vertex.x, vertex.y)
        if self._polygon_draft_preview is not None:
            context.line_to(self._polygon_draft_preview.x, self._polygon_draft_preview.y)
        context.stroke()

        radius = self._marker_radius_px / self.viewport.scale
        for index, vertex in enumerate(self._polygon_draft_vertices):
            context.new_path()
            context.arc(vertex.x, vertex.y, radius, 0.0, math.tau)
            if len(self._polygon_draft_vertices) >= 3 and index == 0:
                context.set_source_rgba(*self.config.colors.active_cluster_outline)
            elif index == len(self._polygon_draft_vertices) - 1:
                context.set_source_rgba(*self.config.colors.active_cluster_marker)
            else:
                context.set_source_rgba(*self.config.colors.inactive_cluster_marker)
            context.fill()
        context.restore()

    def _draw_selection_box(self, context: cairo.Context) -> None:
        if self._drag_mode != "box" or self._selection_box_start is None or self._selection_box_end is None:
            return

        x = min(self._selection_box_start.x, self._selection_box_end.x)
        y = min(self._selection_box_start.y, self._selection_box_end.y)
        width = abs(self._selection_box_end.x - self._selection_box_start.x)
        height = abs(self._selection_box_end.y - self._selection_box_start.y)

        outline = self.config.colors.active_cluster_outline
        context.save()
        context.set_source_rgba(outline[0], outline[1], outline[2], min(outline[3], 1.0) * 0.18)
        context.rectangle(x, y, width, height)
        context.fill_preserve()
        context.set_source_rgba(*outline)
        context.set_line_width(max(1.0, self.config.canvas.cluster_outline_width))
        context.stroke()
        context.restore()

    def _on_draw(self, area: Gtk.DrawingArea, context: cairo.Context, width: int, height: int) -> None:
        context.set_source_rgb(*self.config.colors.canvas_background)
        context.paint()

        context.save()
        center = self._screen_center()
        context.translate(center.x + self.viewport.offset.x, center.y + self.viewport.offset.y)
        context.scale(self.viewport.scale, -self.viewport.scale)
        self._draw_grid(context)
        self._draw_clusters(context)
        self._draw_polygon_handles(context)
        self._draw_polygon_draft(context)
        context.restore()
        self._draw_axis_labels(context)
        self._draw_hover_info(context)
        self._draw_selection_box(context)

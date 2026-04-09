from __future__ import annotations

import math
from typing import Callable

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gtk

from .config import AppConfig
from .generator import preview_cluster_counts, resolve_cluster_configs
from .models import AppState, CanvasTool, Point, ShapeKind
from .shapes import get_shape


class StarCanvas(Gtk.DrawingArea):
    def __init__(
        self,
        state: AppState,
        is_space_pressed: Callable[[], bool],
        config: AppConfig,
        on_state_changed: Callable[[bool], None],
    ) -> None:
        super().__init__()
        self.state = state
        self.config = config
        self._is_space_pressed = is_space_pressed
        self._on_state_changed = on_state_changed
        self._pointer_position = Point(0.0, 0.0)
        self._press_position = Point(0.0, 0.0)
        self._last_drag_position = Point(0.0, 0.0)
        self._primary_button_down = False
        self._drag_mode: str | None = None
        self._active_cluster_id: int | None = None
        self._hovered_cluster_id: int | None = None
        self._press_cluster_id: int | None = None
        self._press_ctrl = False
        self._selection_box_start: Point | None = None
        self._selection_box_end: Point | None = None
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

        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)

        scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", self._on_scroll)
        self.add_controller(scroll)

    def _screen_center(self) -> Point:
        return Point(self.get_allocated_width() / 2.0, self.get_allocated_height() / 2.0)

    def world_to_screen(self, point: Point) -> Point:
        center = self._screen_center()
        return Point(
            x=center.x + self.state.viewport_offset.x + point.x * self.state.viewport_scale,
            y=center.y + self.state.viewport_offset.y - point.y * self.state.viewport_scale,
        )

    def screen_to_world(self, x: float, y: float) -> Point:
        center = self._screen_center()
        scale = max(self.state.viewport_scale, 1e-6)
        return Point(
            x=(x - center.x - self.state.viewport_offset.x) / scale,
            y=-(y - center.y - self.state.viewport_offset.y) / scale,
        )

    def _current_world_bounds(self) -> tuple[float, float, float, float]:
        top_left = self.screen_to_world(0.0, 0.0)
        bottom_right = self.screen_to_world(self.get_allocated_width(), self.get_allocated_height())
        min_x = min(top_left.x, bottom_right.x)
        max_x = max(top_left.x, bottom_right.x)
        min_y = min(top_left.y, bottom_right.y)
        max_y = max(top_left.y, bottom_right.y)
        return min_x, max_x, min_y, max_y

    def _selection_shape_kind(self) -> ShapeKind | None:
        return self.state.selection_shape_kind()

    def _modifier_state_is_ctrl(self, state: Gdk.ModifierType) -> bool:
        return bool(state & Gdk.ModifierType.CONTROL_MASK)

    def _press_moved_far_enough(self, x: float, y: float) -> bool:
        return math.hypot(x - self._press_position.x, y - self._press_position.y) >= self._drag_threshold_px

    def _hit_test_cluster(self, x: float, y: float) -> int | None:
        world_point = self.screen_to_world(x, y)
        tolerance = self.config.canvas.cluster_hit_tolerance_px / max(self.state.viewport_scale, 1e-6)

        for cluster in reversed(self.state.clusters):
            shape = get_shape(cluster.shape_kind)
            if shape.edge_distance(world_point, cluster.center, cluster.size) <= tolerance:
                return cluster.cluster_id
        return None

    def _set_hovered_cluster(self, cluster_id: int | None) -> None:
        if self._hovered_cluster_id == cluster_id:
            return
        self._hovered_cluster_id = cluster_id
        self.queue_draw()

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
            intersects = not (
                bounds.max_x < min_x
                or bounds.min_x > max_x
                or bounds.max_y < min_y
                or bounds.min_y > max_y
            )
            if intersects:
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

        if self.state.active_tool is CanvasTool.SELECT:
            if self._press_cluster_id is not None and not self._press_ctrl:
                if not self.state.is_selected(self._press_cluster_id):
                    self.state.select_only(self._press_cluster_id)
                    self._on_state_changed(False)
                self._active_cluster_id = self._press_cluster_id
                self._drag_mode = "move"
                self._set_hovered_cluster(self._press_cluster_id)
                return

            if self._press_cluster_id is None:
                self._drag_mode = "box"
                self._selection_box_start = Point(self._press_position.x, self._press_position.y)
                self._selection_box_end = Point(x, y)
                self._set_hovered_cluster(None)
                self.queue_draw()
                return
            return

    def _place_cluster_at(self, x: float, y: float) -> None:
        shape_kind = self.state.active_tool.shape_kind()
        if shape_kind is None:
            return
        cluster = self.state.add_cluster(shape_kind, self.screen_to_world(x, y))
        self.state.select_only(cluster.cluster_id)
        self._set_hovered_cluster(cluster.cluster_id)
        self._on_state_changed(True)

    def _on_pressed(self, gesture: Gtk.GestureClick, _: int, x: float, y: float) -> None:
        self.grab_focus()
        self._pointer_position = Point(x, y)
        self._press_position = Point(x, y)
        self._last_drag_position = Point(x, y)
        self._primary_button_down = True
        self._drag_mode = "pan" if self._is_space_pressed() else None
        self._active_cluster_id = None
        self._press_cluster_id = self._hit_test_cluster(x, y)
        self._press_ctrl = self._modifier_state_is_ctrl(gesture.get_current_event_state())
        self._selection_box_start = None
        self._selection_box_end = None

    def _on_released(self, gesture: Gtk.GestureClick, _: int, x: float, y: float) -> None:
        self._pointer_position = Point(x, y)
        self._last_drag_position = Point(x, y)
        self._primary_button_down = False

        if self._drag_mode == "box":
            self.state.selected_cluster_ids = self._cluster_ids_in_selection_box()
            self._selection_box_start = None
            self._selection_box_end = None
            self._on_state_changed(False)
        elif self._drag_mode is None:
            if not self._is_space_pressed():
                if self.state.active_tool is CanvasTool.SELECT:
                    if self._press_cluster_id is not None:
                        if self._press_ctrl:
                            self.state.toggle_selection(self._press_cluster_id)
                        else:
                            self.state.select_only(self._press_cluster_id)
                        self._on_state_changed(False)
                    elif not self._press_ctrl:
                        self.state.clear_selection()
                        self._on_state_changed(False)
                elif self._press_cluster_id is None and not self._press_moved_far_enough(x, y):
                    self._place_cluster_at(x, y)

        self._drag_mode = None
        self._active_cluster_id = None
        self._press_cluster_id = None
        self._press_ctrl = False
        self._set_hovered_cluster(self._hit_test_cluster(x, y))
        self.queue_draw()

    def _on_motion(self, controller: Gtk.EventControllerMotion, x: float, y: float) -> None:
        self._pointer_position = Point(x, y)
        if not self._primary_button_down:
            self._set_hovered_cluster(self._hit_test_cluster(x, y))
            return

        self._start_drag_if_needed(x, y)
        if self._drag_mode is None:
            return

        dx = x - self._last_drag_position.x
        dy = y - self._last_drag_position.y
        self._last_drag_position = Point(x, y)

        if self._drag_mode == "pan":
            self.state.viewport_offset.x += dx
            self.state.viewport_offset.y += dy
            self._set_hovered_cluster(None)
            self.queue_draw()
            return

        if self._drag_mode == "move":
            scale = max(self.state.viewport_scale, 1e-6)
            selected_ids = set(self.state.selected_cluster_ids)
            for cluster in self.state.clusters:
                if cluster.cluster_id in selected_ids:
                    cluster.center.x += dx / scale
                    cluster.center.y -= dy / scale
            self._set_hovered_cluster(self._active_cluster_id)
            self.queue_draw()
            return

        if self._drag_mode == "box":
            self._selection_box_end = Point(x, y)
            self.queue_draw()

    def _on_leave(self, controller: Gtk.EventControllerMotion) -> None:
        self._pointer_position = self._screen_center()
        if not self._primary_button_down:
            self._set_hovered_cluster(None)

    def _format_hover_value(self, value: float) -> str:
        text = f"{value:.2f}".rstrip("0").rstrip(".")
        return "0" if text == "-0" else text

    def _hover_info_lines(self) -> list[str]:
        if self._hovered_cluster_id is None:
            return []

        counts = preview_cluster_counts(self.state)
        for index, cluster in enumerate(self.state.clusters):
            if cluster.cluster_id != self._hovered_cluster_id:
                continue

            lines = [f"Cluster {index + 1}"]
            lines.append(
                "Center: "
                f"{self._format_hover_value(cluster.center.x)}, {self._format_hover_value(cluster.center.y)}"
            )

            if cluster.shape_kind is ShapeKind.CIRCLE:
                lines.append(f"Radius: {self._format_hover_value(cluster.size.radius)}")
            else:
                lines.append(f"Width: {self._format_hover_value(cluster.size.width)}")
                lines.append(f"Height: {self._format_hover_value(cluster.size.height)}")

            if counts is not None and index < len(counts):
                lines.append(f"Stars: {counts[index]}")
            else:
                lines.append("Stars: randomized")
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
        old_scale = self.state.viewport_scale
        new_scale = max(self.config.canvas.min_viewport_scale, min(self.config.canvas.max_viewport_scale, old_scale * zoom_factor))
        if math.isclose(old_scale, new_scale):
            return True

        anchor = self._pointer_position
        world_anchor = self.screen_to_world(anchor.x, anchor.y)
        self.state.viewport_scale = new_scale

        center = self._screen_center()
        self.state.viewport_offset.x = anchor.x - center.x - world_anchor.x * new_scale
        self.state.viewport_offset.y = anchor.y - center.y + world_anchor.y * new_scale
        self.queue_draw()
        return True

    def _grid_step(self) -> float:
        scale = max(self.state.viewport_scale, 1e-6)
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

        context.set_line_width(self.config.canvas.grid_line_width / self.state.viewport_scale)
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
        context.set_line_width(self.config.canvas.axis_line_width / self.state.viewport_scale)
        context.move_to(min_x, 0.0)
        context.line_to(max_x, 0.0)
        context.move_to(0.0, min_y)
        context.line_to(0.0, max_y)
        context.stroke()
        context.arc(0.0, 0.0, self.config.canvas.origin_marker_radius / self.state.viewport_scale, 0.0, math.tau)
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
            context.set_line_width(self.config.canvas.cluster_outline_width / self.state.viewport_scale)
            context.stroke()

            context.new_path()
            context.arc(
                cluster.center.x,
                cluster.center.y,
                self._marker_radius_px / self.state.viewport_scale,
                0.0,
                math.tau,
            )
            if is_active:
                context.set_source_rgba(*self.config.colors.active_cluster_marker)
            else:
                context.set_source_rgba(*self.config.colors.inactive_cluster_marker)
            context.fill()

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
        context.translate(center.x + self.state.viewport_offset.x, center.y + self.state.viewport_offset.y)
        context.scale(self.state.viewport_scale, -self.state.viewport_scale)
        self._draw_grid(context)
        self._draw_clusters(context)
        context.restore()
        self._draw_axis_labels(context)
        self._draw_hover_info(context)
        self._draw_selection_box(context)

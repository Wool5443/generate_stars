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
from .models import AppState, DistributionMode, Point, ShapeKind
from .shapes import get_shape


class StarCanvas(Gtk.DrawingArea):
    def __init__(self, state: AppState, is_space_pressed: Callable[[], bool], config: AppConfig) -> None:
        super().__init__()
        self.state = state
        self.config = config
        self._is_space_pressed = is_space_pressed
        self._pointer_position = Point(0.0, 0.0)
        self._last_drag_position = Point(0.0, 0.0)
        self._primary_button_down = False
        self._drag_mode: str | None = None
        self._active_center_index: int | None = None
        self._hovered_cluster_index: int | None = None
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

    def _hit_test_cluster(self, x: float, y: float) -> int | None:
        world_point = self.screen_to_world(x, y)
        shape = get_shape(self.state.shape_kind)
        configs = resolve_cluster_configs(self.state)
        tolerance = self.config.canvas.cluster_hit_tolerance_px / max(self.state.viewport_scale, 1e-6)

        for index in range(len(configs) - 1, -1, -1):
            if shape.edge_distance(world_point, configs[index].center, configs[index].size) <= tolerance:
                return index
        return None

    def _set_hovered_cluster(self, index: int | None) -> None:
        if self._hovered_cluster_index == index:
            return
        self._hovered_cluster_index = index
        self.queue_draw()

    def _on_pressed(self, gesture: Gtk.GestureClick, _: int, x: float, y: float) -> None:
        self.grab_focus()
        self._pointer_position = Point(x, y)
        self._last_drag_position = Point(x, y)
        self._primary_button_down = True
        self._active_center_index = None

        if self._is_space_pressed():
            self._drag_mode = "pan"
            return

        hit_index = self._hit_test_cluster(x, y)
        if hit_index is not None:
            self._drag_mode = "center"
            self._active_center_index = hit_index
            self._set_hovered_cluster(hit_index)
        else:
            self._drag_mode = None
            self._set_hovered_cluster(None)

    def _on_released(self, gesture: Gtk.GestureClick, _: int, x: float, y: float) -> None:
        self._pointer_position = Point(x, y)
        self._last_drag_position = Point(x, y)
        self._primary_button_down = False
        self._drag_mode = None
        self._active_center_index = None
        self._set_hovered_cluster(self._hit_test_cluster(x, y))
        self.queue_draw()

    def _on_motion(self, controller: Gtk.EventControllerMotion, x: float, y: float) -> None:
        self._pointer_position = Point(x, y)
        if not self._primary_button_down or self._drag_mode is None:
            self._set_hovered_cluster(self._hit_test_cluster(x, y))
            return

        dx = x - self._last_drag_position.x
        dy = y - self._last_drag_position.y
        self._last_drag_position = Point(x, y)

        if self._drag_mode == "pan":
            self._set_hovered_cluster(None)
            self.state.viewport_offset.x += dx
            self.state.viewport_offset.y += dy
            self.queue_draw()
            return

        if self._drag_mode == "center" and self._active_center_index is not None:
            scale = max(self.state.viewport_scale, 1e-6)
            center = self.state.cluster_centers[self._active_center_index]
            center.x += dx / scale
            center.y -= dy / scale
            if dx != 0.0 or dy != 0.0:
                self.state.positions_customized = True
            self._set_hovered_cluster(self._active_center_index)
            self.queue_draw()

    def _on_leave(self, controller: Gtk.EventControllerMotion) -> None:
        self._pointer_position = self._screen_center()
        self._set_hovered_cluster(None)

    def _format_hover_value(self, value: float) -> str:
        text = f"{value:.2f}".rstrip("0").rstrip(".")
        return "0" if text == "-0" else text

    def _hover_info_lines(self) -> list[str]:
        if self._hovered_cluster_index is None:
            return []

        configs = resolve_cluster_configs(self.state)
        if self._hovered_cluster_index >= len(configs):
            return []

        config = configs[self._hovered_cluster_index]
        lines = [f"Cluster {self._hovered_cluster_index + 1}"]
        lines.append(
            "Center: "
            f"{self._format_hover_value(config.center.x)}, {self._format_hover_value(config.center.y)}"
        )

        if self.state.shape_kind is ShapeKind.CIRCLE:
            lines.append(f"Radius: {self._format_hover_value(config.size.radius)}")
        else:
            lines.append(f"Width: {self._format_hover_value(config.size.width)}")
            lines.append(f"Height: {self._format_hover_value(config.size.height)}")

        counts = preview_cluster_counts(self.state)
        if counts is not None and self._hovered_cluster_index < len(counts):
            lines.append(f"Stars: {counts[self._hovered_cluster_index]}")
        elif self.state.distribution_mode is DistributionMode.DEVIATION:
            lines.append(f"Stars: randomized ({self._format_hover_value(self.state.deviation_percent)}% deviation)")

        return lines

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
        shape = get_shape(self.state.shape_kind)
        configs = resolve_cluster_configs(self.state)

        for index, config in enumerate(configs):
            context.new_path()
            shape.draw_outline(context, config.center, config.size)
            if self._active_center_index == index and self._drag_mode == "center":
                context.set_source_rgba(*self.config.colors.active_cluster_outline)
            else:
                context.set_source_rgba(*self.config.colors.inactive_cluster_outline)
            context.set_line_width(self.config.canvas.cluster_outline_width / self.state.viewport_scale)
            context.stroke()

            context.new_path()
            context.arc(
                config.center.x,
                config.center.y,
                self._marker_radius_px / self.state.viewport_scale,
                0.0,
                math.tau,
            )
            if self._active_center_index == index and self._drag_mode == "center":
                context.set_source_rgba(*self.config.colors.active_cluster_marker)
            else:
                context.set_source_rgba(*self.config.colors.inactive_cluster_marker)
            context.fill()

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

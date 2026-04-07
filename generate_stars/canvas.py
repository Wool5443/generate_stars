from __future__ import annotations

import math
from typing import Callable

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gtk

from .generator import resolve_cluster_configs
from .models import AppState, Point
from .shapes import get_shape


class StarCanvas(Gtk.DrawingArea):
    def __init__(self, state: AppState, is_space_pressed: Callable[[], bool]) -> None:
        super().__init__()
        self.state = state
        self._is_space_pressed = is_space_pressed
        self._pointer_position = Point(0.0, 0.0)
        self._last_drag_position = Point(0.0, 0.0)
        self._primary_button_down = False
        self._drag_mode: str | None = None
        self._active_center_index: int | None = None
        self._marker_radius_px = 7.0

        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_focusable(True)
        self.set_content_width(900)
        self.set_content_height(720)
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

    def _hit_test_center(self, x: float, y: float) -> int | None:
        for index in range(len(self.state.cluster_centers) - 1, -1, -1):
            screen_point = self.world_to_screen(self.state.cluster_centers[index])
            if math.hypot(screen_point.x - x, screen_point.y - y) <= self._marker_radius_px + 3.0:
                return index
        return None

    def _on_pressed(self, gesture: Gtk.GestureClick, _: int, x: float, y: float) -> None:
        self.grab_focus()
        self._pointer_position = Point(x, y)
        self._last_drag_position = Point(x, y)
        self._primary_button_down = True
        self._active_center_index = None

        if self._is_space_pressed():
            self._drag_mode = "pan"
            return

        hit_index = self._hit_test_center(x, y)
        if hit_index is not None:
            self._drag_mode = "center"
            self._active_center_index = hit_index
        else:
            self._drag_mode = None

    def _on_released(self, gesture: Gtk.GestureClick, _: int, x: float, y: float) -> None:
        self._pointer_position = Point(x, y)
        self._last_drag_position = Point(x, y)
        self._primary_button_down = False
        self._drag_mode = None
        self._active_center_index = None
        self.queue_draw()

    def _on_motion(self, controller: Gtk.EventControllerMotion, x: float, y: float) -> None:
        self._pointer_position = Point(x, y)
        if not self._primary_button_down or self._drag_mode is None:
            return

        dx = x - self._last_drag_position.x
        dy = y - self._last_drag_position.y
        self._last_drag_position = Point(x, y)

        if self._drag_mode == "pan":
            self.state.viewport_offset.x += dx
            self.state.viewport_offset.y += dy
            self.queue_draw()
            return

        if self._drag_mode == "center" and self._active_center_index is not None:
            scale = max(self.state.viewport_scale, 1e-6)
            center = self.state.cluster_centers[self._active_center_index]
            center.x += dx / scale
            center.y -= dy / scale
            self.queue_draw()

    def _on_leave(self, controller: Gtk.EventControllerMotion) -> None:
        self._pointer_position = self._screen_center()

    def _on_scroll(self, controller: Gtk.EventControllerScroll, _dx: float, dy: float) -> bool:
        if dy == 0.0:
            return False

        zoom_factor = 1.12 if dy < 0.0 else 1.0 / 1.12
        old_scale = self.state.viewport_scale
        new_scale = max(0.1, min(10.0, old_scale * zoom_factor))
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
        target_px = 90.0
        raw = target_px / scale
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
        context.set_font_size(11.0)
        context.set_source_rgba(0.86, 0.89, 0.94, 0.82)

        if 0.0 <= axis_y <= height:
            x = math.floor(min_x / step) * step
            while x <= max_x + step * 0.5:
                if not math.isclose(x, 0.0, abs_tol=step * 0.05):
                    label = self._format_axis_value(x, step)
                    screen = self.world_to_screen(Point(x, 0.0))
                    extents = context.text_extents(label)
                    label_x = screen.x - extents.width / 2.0 - extents.x_bearing
                    baseline = axis_y - 8.0
                    if baseline - extents.height < 4.0:
                        baseline = axis_y + extents.height + 8.0
                    if 4.0 <= label_x and label_x + extents.width <= width - 4.0:
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
                    label_x = axis_x + 8.0
                    if label_x + extents.width > width - 4.0:
                        label_x = axis_x - extents.width - 8.0
                    baseline = screen.y + extents.height / 2.0
                    if 4.0 <= label_x and baseline - extents.height >= 4.0 and baseline <= height - 4.0:
                        context.move_to(label_x, baseline)
                        context.show_text(label)
                y += step

        if 0.0 <= axis_x <= width and 0.0 <= axis_y <= height:
            label = "0"
            extents = context.text_extents(label)
            label_x = axis_x + 8.0
            if label_x + extents.width > width - 4.0:
                label_x = axis_x - extents.width - 8.0
            baseline = axis_y - 8.0
            if baseline - extents.height < 4.0:
                baseline = axis_y + extents.height + 8.0
            context.move_to(label_x, baseline)
            context.show_text(label)

        context.restore()

    def _draw_grid(self, context: cairo.Context) -> None:
        min_x, max_x, min_y, max_y = self._current_world_bounds()
        step = self._grid_step()

        context.set_line_width(1.0 / self.state.viewport_scale)
        context.set_source_rgba(0.7, 0.72, 0.78, 0.08)
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

        context.set_source_rgba(0.85, 0.88, 0.92, 0.24)
        context.set_line_width(1.4 / self.state.viewport_scale)
        context.move_to(min_x, 0.0)
        context.line_to(max_x, 0.0)
        context.move_to(0.0, min_y)
        context.line_to(0.0, max_y)
        context.stroke()
        context.arc(0.0, 0.0, 3.0 / self.state.viewport_scale, 0.0, math.tau)
        context.fill()

    def _draw_clusters(self, context: cairo.Context) -> None:
        shape = get_shape(self.state.shape_kind)
        configs = resolve_cluster_configs(self.state)

        for index, config in enumerate(configs):
            context.new_path()
            shape.draw_outline(context, config.center, config.size)
            if self._active_center_index == index and self._drag_mode == "center":
                context.set_source_rgba(0.48, 0.72, 0.98, 0.9)
            else:
                context.set_source_rgba(0.87, 0.89, 0.94, 0.72)
            context.set_line_width(2.0 / self.state.viewport_scale)
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
                context.set_source_rgba(0.48, 0.72, 0.98, 0.95)
            else:
                context.set_source_rgba(0.96, 0.98, 1.0, 0.95)
            context.fill()

    def _on_draw(self, area: Gtk.DrawingArea, context: cairo.Context, width: int, height: int) -> None:
        context.set_source_rgb(0.06, 0.08, 0.11)
        context.paint()

        context.save()
        center = self._screen_center()
        context.translate(center.x + self.state.viewport_offset.x, center.y + self.state.viewport_offset.y)
        context.scale(self.state.viewport_scale, -self.state.viewport_scale)
        self._draw_grid(context)
        self._draw_clusters(context)
        context.restore()
        self._draw_axis_labels(context)

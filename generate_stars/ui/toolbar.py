from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from ..config import AppConfig
from ..controllers.view_models import ToolbarViewModel
from ..localization import get_localizer
from ..models import CanvasTool


class CanvasToolbarView(Gtk.Box):
    def __init__(self, config: AppConfig) -> None:
        localizer = get_localizer()
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=config.ui.panel_spacing)
        self.add_css_class("panel")
        self._syncing = False

        button_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.ui.row_spacing)

        self.undo_button = Gtk.Button(label=localizer.text("ui.toolbar.undo"))
        self.redo_button = Gtk.Button(label=localizer.text("ui.toolbar.redo"))

        self.select_tool_button = Gtk.ToggleButton(label=f"{localizer.text('ui.tool.select')} (V)")
        self.circle_tool_button = Gtk.ToggleButton(label=f"{localizer.text('ui.tool.circle')} (C)")
        self.rectangle_tool_button = Gtk.ToggleButton(label=f"{localizer.text('ui.tool.rectangle')} (R)")
        self.polygon_tool_button = Gtk.ToggleButton(label=f"{localizer.text('ui.tool.polygon')} (P)")
        self.function_tool_button = Gtk.ToggleButton(label=f"{localizer.text('ui.tool.function')} (F)")
        self.snap_button = Gtk.ToggleButton(label=localizer.text("ui.toolbar.snap"))

        self.circle_tool_button.set_group(self.select_tool_button)
        self.rectangle_tool_button.set_group(self.select_tool_button)
        self.polygon_tool_button.set_group(self.select_tool_button)
        self.function_tool_button.set_group(self.select_tool_button)

        button_row.append(self.undo_button)
        button_row.append(self.redo_button)
        button_row.append(self.select_tool_button)
        button_row.append(self.circle_tool_button)
        button_row.append(self.rectangle_tool_button)
        button_row.append(self.polygon_tool_button)
        button_row.append(self.function_tool_button)
        button_row.append(self.snap_button)
        self.append(button_row)

        self.description_label = Gtk.Label(xalign=0.0)
        self.description_label.set_wrap(True)
        self.description_label.add_css_class("dim-label")
        self.append(self.description_label)

    def apply(self, view_model: ToolbarViewModel) -> None:
        self._syncing = True
        try:
            self.undo_button.set_sensitive(view_model.can_undo)
            self.redo_button.set_sensitive(view_model.can_redo)
            self.select_tool_button.set_active(view_model.active_tool is CanvasTool.SELECT)
            self.circle_tool_button.set_active(view_model.active_tool is CanvasTool.CIRCLE)
            self.rectangle_tool_button.set_active(view_model.active_tool is CanvasTool.RECTANGLE)
            self.polygon_tool_button.set_active(view_model.active_tool is CanvasTool.POLYGON)
            self.function_tool_button.set_active(view_model.active_tool is CanvasTool.FUNCTION)
            self.snap_button.set_active(view_model.snap_to_integer_grid)
            self.description_label.set_text(view_model.active_tool_description)
        finally:
            self._syncing = False

    @property
    def syncing(self) -> bool:
        return self._syncing

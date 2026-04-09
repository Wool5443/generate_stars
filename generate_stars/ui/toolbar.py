from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from ..config import AppConfig
from ..controllers.view_models import ToolbarViewModel
from ..models import CanvasTool


class CanvasToolbarView(Gtk.Box):
    def __init__(self, config: AppConfig) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.ui.row_spacing)
        self.add_css_class("panel")
        self._syncing = False

        self.undo_button = Gtk.Button(label="Undo")
        self.redo_button = Gtk.Button(label="Redo")

        self.select_tool_button = Gtk.ToggleButton(label="Select (V)")
        self.circle_tool_button = Gtk.ToggleButton(label="Circle (C)")
        self.rectangle_tool_button = Gtk.ToggleButton(label="Rectangle (R)")
        self.polygon_tool_button = Gtk.ToggleButton(label="Polygon (P)")

        self.circle_tool_button.set_group(self.select_tool_button)
        self.rectangle_tool_button.set_group(self.select_tool_button)
        self.polygon_tool_button.set_group(self.select_tool_button)

        self.append(self.undo_button)
        self.append(self.redo_button)
        self.append(self.select_tool_button)
        self.append(self.circle_tool_button)
        self.append(self.rectangle_tool_button)
        self.append(self.polygon_tool_button)

    def apply(self, view_model: ToolbarViewModel) -> None:
        self._syncing = True
        try:
            self.undo_button.set_sensitive(view_model.can_undo)
            self.redo_button.set_sensitive(view_model.can_redo)
            self.select_tool_button.set_active(view_model.active_tool is CanvasTool.SELECT)
            self.circle_tool_button.set_active(view_model.active_tool is CanvasTool.CIRCLE)
            self.rectangle_tool_button.set_active(view_model.active_tool is CanvasTool.RECTANGLE)
            self.polygon_tool_button.set_active(view_model.active_tool is CanvasTool.POLYGON)
        finally:
            self._syncing = False

    @property
    def syncing(self) -> bool:
        return self._syncing

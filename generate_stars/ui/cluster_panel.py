from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from ..config import AppConfig
from ..controllers.view_models import ClusterPanelViewModel
from ..localization import get_localizer
from ..models import ShapeKind
from .widgets import PanelView


class ClusterPanelView(PanelView):
    def __init__(self, config: AppConfig, attach_continuous_history: Callable[[Gtk.Widget], None]) -> None:
        super().__init__(get_localizer().text("ui.panel.clusters"), config)

        self.placement_info = Gtk.Label(xalign=0.0)
        self.placement_info.set_wrap(True)
        self.append(self.placement_info)

        self.placement_radius_spin = self.make_spin(config.limits.size_min, config.limits.size_max, 1, digits=1)
        attach_continuous_history(self.placement_radius_spin)
        self.placement_radius_row = self.build_row(self.localizer.text("ui.label.radius"), self.placement_radius_spin)
        self.append(self.placement_radius_row)

        self.placement_width_spin = self.make_spin(config.limits.size_min, config.limits.size_max, 1, digits=1)
        attach_continuous_history(self.placement_width_spin)
        self.placement_width_row = self.build_row(self.localizer.text("ui.label.width"), self.placement_width_spin)
        self.append(self.placement_width_row)

        self.placement_height_spin = self.make_spin(config.limits.size_min, config.limits.size_max, 1, digits=1)
        attach_continuous_history(self.placement_height_spin)
        self.placement_height_row = self.build_row(self.localizer.text("ui.label.height"), self.placement_height_spin)
        self.append(self.placement_height_row)

        self.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self.selection_info = Gtk.Label(xalign=0.0)
        self.selection_info.set_wrap(True)
        self.append(self.selection_info)

        self.selection_shape_combo = Gtk.ComboBoxText()
        self.selection_shape_combo.append(ShapeKind.CIRCLE.value, self.localizer.text("shape.circle"))
        self.selection_shape_combo.append(ShapeKind.RECTANGLE.value, self.localizer.text("shape.rectangle"))
        self.selection_shape_combo.append(ShapeKind.POLYGON.value, self.localizer.text("shape.polygon"))
        self.selection_shape_row = self.build_row(self.localizer.text("ui.label.shape"), self.selection_shape_combo)
        self.append(self.selection_shape_row)

        self.selection_radius_spin = self.make_spin(config.limits.size_min, config.limits.size_max, 1, digits=1)
        attach_continuous_history(self.selection_radius_spin)
        self.selection_radius_row = self.build_row(self.localizer.text("ui.label.radius"), self.selection_radius_spin)
        self.append(self.selection_radius_row)

        self.selection_width_spin = self.make_spin(config.limits.size_min, config.limits.size_max, 1, digits=1)
        attach_continuous_history(self.selection_width_spin)
        self.selection_width_row = self.build_row(self.localizer.text("ui.label.width"), self.selection_width_spin)
        self.append(self.selection_width_row)

        self.selection_height_spin = self.make_spin(config.limits.size_min, config.limits.size_max, 1, digits=1)
        attach_continuous_history(self.selection_height_spin)
        self.selection_height_row = self.build_row(self.localizer.text("ui.label.height"), self.selection_height_spin)
        self.append(self.selection_height_row)

        self.selection_polygon_scale_spin = self.make_spin(config.limits.size_min, config.limits.size_max, 1, digits=1)
        attach_continuous_history(self.selection_polygon_scale_spin)
        self.selection_polygon_scale_row = self.build_row(self.localizer.text("ui.label.scale"), self.selection_polygon_scale_spin)
        self.append(self.selection_polygon_scale_row)

        self.selection_size_hint = Gtk.Label(xalign=0.0)
        self.selection_size_hint.set_wrap(True)
        self.selection_size_hint.add_css_class("dim-label")
        self.append(self.selection_size_hint)

        self.interaction_hint = Gtk.Label(label=config.text.shape_interaction_hint, xalign=0.0)
        self.interaction_hint.set_wrap(True)
        self.interaction_hint.add_css_class("dim-label")
        self.append(self.interaction_hint)

    def apply(self, view_model: ClusterPanelViewModel) -> None:
        placement = view_model.placement
        selection = view_model.selection

        self.placement_info.set_text(placement.info_text)
        self.placement_radius_row.set_visible(placement.show_radius)
        self.placement_width_row.set_visible(placement.show_width)
        self.placement_height_row.set_visible(placement.show_height)
        self.placement_radius_spin.set_value(placement.radius)
        self.placement_width_spin.set_value(placement.width)
        self.placement_height_spin.set_value(placement.height)

        self.selection_info.set_text(selection.info_text)
        self.selection_shape_row.set_visible(selection.show_shape_selector)
        if selection.active_shape_id is None:
            self.selection_shape_combo.set_active(-1)
        else:
            self.selection_shape_combo.set_active_id(selection.active_shape_id)

        self.selection_radius_row.set_visible(selection.show_radius)
        self.selection_width_row.set_visible(selection.show_width)
        self.selection_height_row.set_visible(selection.show_height)
        self.selection_polygon_scale_row.set_visible(selection.show_polygon_scale)
        self.selection_radius_spin.set_value(selection.radius)
        self.selection_width_spin.set_value(selection.width)
        self.selection_height_spin.set_value(selection.height)
        self.selection_polygon_scale_spin.set_value(selection.polygon_scale)

        self.selection_size_hint.set_visible(bool(selection.size_hint))
        self.selection_size_hint.set_text(selection.size_hint or "")

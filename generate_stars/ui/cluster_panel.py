from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from ..config import AppConfig
from ..controllers.view_models import ClusterPanelViewModel, FunctionEditorViewModel
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

        self.placement_function_orientation_combo = Gtk.ComboBoxText()
        self.placement_function_orientation_combo.append("y_of_x", self.localizer.text("ui.option.y_of_x"))
        self.placement_function_orientation_combo.append("x_of_y", self.localizer.text("ui.option.x_of_y"))
        self.placement_function_orientation_row = self.build_row(
            self.localizer.text("ui.label.orientation"),
            self.placement_function_orientation_combo,
        )
        self.append(self.placement_function_orientation_row)

        self.placement_function_expression_entry = self._make_formula_entry()
        attach_continuous_history(self.placement_function_expression_entry)
        self.placement_function_expression_row = self.build_row(
            self.localizer.text("ui.label.expression"),
            self.placement_function_expression_entry,
        )
        self.append(self.placement_function_expression_row)

        self.placement_function_range_start_spin = self.make_spin(
            config.limits.function_range_min,
            config.limits.function_range_max,
            1,
            digits=1,
        )
        attach_continuous_history(self.placement_function_range_start_spin)
        self.placement_function_range_start_row = self.build_row(
            self.localizer.text("ui.label.range_start"),
            self.placement_function_range_start_spin,
        )
        self.append(self.placement_function_range_start_row)

        self.placement_function_range_end_spin = self.make_spin(
            config.limits.function_range_min,
            config.limits.function_range_max,
            1,
            digits=1,
        )
        attach_continuous_history(self.placement_function_range_end_spin)
        self.placement_function_range_end_row = self.build_row(
            self.localizer.text("ui.label.range_end"),
            self.placement_function_range_end_spin,
        )
        self.append(self.placement_function_range_end_row)

        self.placement_function_thickness_spin = self.make_spin(
            config.limits.function_thickness_min,
            config.limits.function_thickness_max,
            1,
            digits=1,
        )
        attach_continuous_history(self.placement_function_thickness_spin)
        self.placement_function_thickness_row = self.build_row(
            self.localizer.text("ui.label.thickness"),
            self.placement_function_thickness_spin,
        )
        self.append(self.placement_function_thickness_row)

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

        self.selection_function_orientation_combo = Gtk.ComboBoxText()
        self.selection_function_orientation_combo.append("y_of_x", self.localizer.text("ui.option.y_of_x"))
        self.selection_function_orientation_combo.append("x_of_y", self.localizer.text("ui.option.x_of_y"))
        self.selection_function_orientation_row = self.build_row(
            self.localizer.text("ui.label.orientation"),
            self.selection_function_orientation_combo,
        )
        self.append(self.selection_function_orientation_row)

        self.selection_function_expression_entry = self._make_formula_entry()
        attach_continuous_history(self.selection_function_expression_entry)
        self.selection_function_expression_row = self.build_row(
            self.localizer.text("ui.label.expression"),
            self.selection_function_expression_entry,
        )
        self.append(self.selection_function_expression_row)

        self.selection_function_range_start_spin = self.make_spin(
            config.limits.function_range_min,
            config.limits.function_range_max,
            1,
            digits=1,
        )
        attach_continuous_history(self.selection_function_range_start_spin)
        self.selection_function_range_start_row = self.build_row(
            self.localizer.text("ui.label.range_start"),
            self.selection_function_range_start_spin,
        )
        self.append(self.selection_function_range_start_row)

        self.selection_function_range_end_spin = self.make_spin(
            config.limits.function_range_min,
            config.limits.function_range_max,
            1,
            digits=1,
        )
        attach_continuous_history(self.selection_function_range_end_spin)
        self.selection_function_range_end_row = self.build_row(
            self.localizer.text("ui.label.range_end"),
            self.selection_function_range_end_spin,
        )
        self.append(self.selection_function_range_end_row)

        self.selection_function_thickness_spin = self.make_spin(
            config.limits.function_thickness_min,
            config.limits.function_thickness_max,
            1,
            digits=1,
        )
        attach_continuous_history(self.selection_function_thickness_spin)
        self.selection_function_thickness_row = self.build_row(
            self.localizer.text("ui.label.thickness"),
            self.selection_function_thickness_spin,
        )
        self.append(self.selection_function_thickness_row)

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
        self._apply_function_editor(
            placement.function_editor,
            orientation_combo=self.placement_function_orientation_combo,
            expression_entry=self.placement_function_expression_entry,
            range_start_spin=self.placement_function_range_start_spin,
            range_end_spin=self.placement_function_range_end_spin,
            thickness_spin=self.placement_function_thickness_spin,
            orientation_row=self.placement_function_orientation_row,
            expression_row=self.placement_function_expression_row,
            range_start_row=self.placement_function_range_start_row,
            range_end_row=self.placement_function_range_end_row,
            thickness_row=self.placement_function_thickness_row,
        )

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
        self._apply_function_editor(
            selection.function_editor,
            orientation_combo=self.selection_function_orientation_combo,
            expression_entry=self.selection_function_expression_entry,
            range_start_spin=self.selection_function_range_start_spin,
            range_end_spin=self.selection_function_range_end_spin,
            thickness_spin=self.selection_function_thickness_spin,
            orientation_row=self.selection_function_orientation_row,
            expression_row=self.selection_function_expression_row,
            range_start_row=self.selection_function_range_start_row,
            range_end_row=self.selection_function_range_end_row,
            thickness_row=self.selection_function_thickness_row,
        )

        self.selection_size_hint.set_visible(bool(selection.size_hint))
        self.selection_size_hint.set_text(selection.size_hint or "")

    def _make_formula_entry(self) -> Gtk.Entry:
        entry = Gtk.Entry()
        entry.set_alignment(0.0)
        entry.set_direction(Gtk.TextDirection.LTR)
        return entry

    def _set_entry_text_if_changed(self, entry: Gtk.Entry, text: str) -> None:
        if entry.get_text() != text:
            entry.set_text(text)

    def _apply_function_editor(
        self,
        editor: FunctionEditorViewModel,
        *,
        orientation_combo: Gtk.ComboBoxText,
        expression_entry: Gtk.Entry,
        range_start_spin: Gtk.SpinButton,
        range_end_spin: Gtk.SpinButton,
        thickness_spin: Gtk.SpinButton,
        orientation_row: Gtk.Widget,
        expression_row: Gtk.Widget,
        range_start_row: Gtk.Widget,
        range_end_row: Gtk.Widget,
        thickness_row: Gtk.Widget,
    ) -> None:
        orientation_row.set_visible(editor.visible)
        expression_row.set_visible(editor.visible and editor.show_expression)
        range_start_row.set_visible(editor.visible)
        range_end_row.set_visible(editor.visible)
        thickness_row.set_visible(editor.visible)
        if editor.visible:
            orientation_combo.set_active_id(editor.orientation_id)
            self._set_entry_text_if_changed(expression_entry, editor.expression)
            range_start_spin.set_value(editor.range_start)
            range_end_spin.set_value(editor.range_end)
            thickness_spin.set_value(editor.thickness)

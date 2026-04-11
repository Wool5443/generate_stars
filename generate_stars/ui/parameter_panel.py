from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from ..config import AppConfig
from ..controllers.view_models import ParameterPanelViewModel
from ..localization import get_localizer
from ..models import StarParameterMode
from .widgets import PanelView


class ParameterPanelView(PanelView):
    def __init__(self, config: AppConfig, attach_continuous_history: Callable[[Gtk.Widget], None]) -> None:
        localizer = get_localizer()
        super().__init__(localizer.text("ui.panel.star_parameter"), config)

        self.parameter_enabled_check = Gtk.CheckButton(label=localizer.text("ui.checkbox.enable_third_parameter"))
        self.append(self.parameter_enabled_check)

        self.parameter_fields_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.ui.cluster_section_spacing)
        self.append(self.parameter_fields_box)

        self.parameter_name_entry = Gtk.Entry()
        self.parameter_name_entry.set_width_chars(max(12, config.ui.decimal_spin_width_chars))
        attach_continuous_history(self.parameter_name_entry)
        self.parameter_fields_box.append(self.build_row(localizer.text("ui.label.name"), self.parameter_name_entry))

        self.parameter_mode_combo = Gtk.ComboBoxText()
        self.parameter_mode_combo.append(StarParameterMode.RANDOM.value, localizer.text("ui.option.parameter_random"))
        self.parameter_mode_combo.append(StarParameterMode.FUNCTION.value, localizer.text("ui.option.parameter_function"))
        self.parameter_fields_box.append(self.build_row(localizer.text("ui.label.parameter_mode"), self.parameter_mode_combo))

        self.parameter_min_spin = self.make_spin(
            config.limits.star_parameter_value_min,
            config.limits.star_parameter_value_max,
            0.1,
            digits=3,
        )
        attach_continuous_history(self.parameter_min_spin)
        self.parameter_min_row = self.build_row(localizer.text("ui.label.min"), self.parameter_min_spin)
        self.parameter_fields_box.append(self.parameter_min_row)

        self.parameter_max_spin = self.make_spin(
            config.limits.star_parameter_value_min,
            config.limits.star_parameter_value_max,
            0.1,
            digits=3,
        )
        attach_continuous_history(self.parameter_max_spin)
        self.parameter_max_row = self.build_row(localizer.text("ui.label.max"), self.parameter_max_spin)
        self.parameter_fields_box.append(self.parameter_max_row)

        self.parameter_function_editor_button = Gtk.Button(label=localizer.text("ui.button.edit_parameter_function"))
        self.parameter_function_editor_row = self.build_row(
            localizer.text("ui.label.parameter_function_editor"),
            self.parameter_function_editor_button,
        )
        self.parameter_fields_box.append(self.parameter_function_editor_row)

        self.parameter_function_editor_window = Gtk.Window(title=localizer.text("ui.window.parameter_function_editor_title"))
        self.parameter_function_editor_window.set_default_size(720, 460)
        self.parameter_function_editor_window.set_modal(True)
        self.parameter_function_editor_window.set_hide_on_close(True)
        self.parameter_function_editor_window.connect("close-request", self._on_function_editor_close_request)

        self.parameter_function_editor_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.ui.row_spacing)
        self.parameter_function_editor_content.set_margin_top(config.ui.sidebar_margin)
        self.parameter_function_editor_content.set_margin_bottom(config.ui.sidebar_margin)
        self.parameter_function_editor_content.set_margin_start(config.ui.sidebar_margin)
        self.parameter_function_editor_content.set_margin_end(config.ui.sidebar_margin)
        self.parameter_function_editor_window.set_child(self.parameter_function_editor_content)

        editor_title = Gtk.Label(label=localizer.text("ui.label.parameter_function_body"), xalign=0.0)
        editor_title.add_css_class("panel-title")
        self.parameter_function_editor_content.append(editor_title)

        self.parameter_function_body_view = Gtk.TextView()
        self.parameter_function_body_view.set_monospace(True)
        self.parameter_function_body_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.parameter_function_body_view.set_top_margin(6)
        self.parameter_function_body_view.set_bottom_margin(6)
        self.parameter_function_body_view.set_left_margin(6)
        self.parameter_function_body_view.set_right_margin(6)
        self.parameter_function_body_buffer = self.parameter_function_body_view.get_buffer()
        attach_continuous_history(self.parameter_function_body_view)

        function_body_scroller = Gtk.ScrolledWindow()
        function_body_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        function_body_scroller.set_min_content_height(150)
        function_body_scroller.set_min_content_width(460)
        function_body_scroller.set_hexpand(True)
        function_body_scroller.set_vexpand(True)
        function_body_scroller.set_child(self.parameter_function_body_view)
        self.parameter_function_editor_content.append(function_body_scroller)

        self.parameter_preview_label = Gtk.Label(xalign=0.0)
        self.parameter_preview_label.set_wrap(True)
        self.parameter_preview_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=config.ui.row_spacing)
        preview_title = Gtk.Label(label=localizer.text("ui.label.parameter_preview"), xalign=0.0)
        preview_title.set_hexpand(False)
        self.parameter_preview_label.set_hexpand(True)
        self.parameter_preview_row.append(preview_title)
        self.parameter_preview_row.append(self.parameter_preview_label)
        self.parameter_function_editor_content.append(self.parameter_preview_row)
        self.parameter_function_editor_button.connect("clicked", self._on_open_function_editor)

    def apply(self, view_model: ParameterPanelViewModel) -> None:
        self.parameter_enabled_check.set_active(view_model.enabled)
        self.parameter_fields_box.set_sensitive(view_model.enabled)
        if self.parameter_name_entry.get_text() != view_model.name:
            self.parameter_name_entry.set_text(view_model.name)
        self.parameter_mode_combo.set_active_id(view_model.mode.value)
        self.parameter_min_spin.set_value(view_model.min_value)
        self.parameter_max_spin.set_value(view_model.max_value)
        self.parameter_min_row.set_visible(view_model.show_random_range)
        self.parameter_max_row.set_visible(view_model.show_random_range)
        self.parameter_function_editor_row.set_visible(view_model.show_function_body)
        self.parameter_preview_row.set_visible(view_model.show_function_preview)
        self.parameter_preview_label.set_text(view_model.function_preview_text)
        self.parameter_preview_label.remove_css_class("status-error")
        if view_model.function_preview_is_error:
            self.parameter_preview_label.add_css_class("status-error")
        if self._buffer_text(self.parameter_function_body_buffer) != view_model.function_body:
            self.parameter_function_body_buffer.set_text(view_model.function_body)
        if not view_model.show_function_body:
            self.parameter_function_editor_window.hide()

    def _buffer_text(self, buffer: Gtk.TextBuffer) -> str:
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        return buffer.get_text(start, end, True)

    def _on_open_function_editor(self, button: Gtk.Button) -> None:
        root = self.get_root()
        if isinstance(root, Gtk.Window):
            self.parameter_function_editor_window.set_transient_for(root)
        self.parameter_function_editor_window.present()

    def _on_function_editor_close_request(self, window: Gtk.Window) -> bool:
        window.hide()
        return True

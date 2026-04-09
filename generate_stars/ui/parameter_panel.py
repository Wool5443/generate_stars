from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from ..config import AppConfig
from ..controllers.view_models import ParameterPanelViewModel
from ..localization import get_localizer
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

        self.parameter_min_spin = self.make_spin(
            config.limits.star_parameter_value_min,
            config.limits.star_parameter_value_max,
            0.1,
            digits=3,
        )
        attach_continuous_history(self.parameter_min_spin)
        self.parameter_fields_box.append(self.build_row(localizer.text("ui.label.min"), self.parameter_min_spin))

        self.parameter_max_spin = self.make_spin(
            config.limits.star_parameter_value_min,
            config.limits.star_parameter_value_max,
            0.1,
            digits=3,
        )
        attach_continuous_history(self.parameter_max_spin)
        self.parameter_fields_box.append(self.build_row(localizer.text("ui.label.max"), self.parameter_max_spin))

    def apply(self, view_model: ParameterPanelViewModel) -> None:
        self.parameter_enabled_check.set_active(view_model.enabled)
        self.parameter_fields_box.set_sensitive(view_model.enabled)
        self.parameter_name_entry.set_text(view_model.name)
        self.parameter_min_spin.set_value(view_model.min_value)
        self.parameter_max_spin.set_value(view_model.max_value)

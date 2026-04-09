from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from ..config import AppConfig
from ..controllers.view_models import ParameterPanelViewModel
from .widgets import PanelView


class ParameterPanelView(PanelView):
    def __init__(self, config: AppConfig, attach_continuous_history: Callable[[Gtk.Widget], None]) -> None:
        super().__init__("Star Parameter", config)

        self.parameter_enabled_check = Gtk.CheckButton(label="Enable third parameter")
        self.append(self.parameter_enabled_check)

        self.parameter_fields_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.ui.cluster_section_spacing)
        self.append(self.parameter_fields_box)

        self.parameter_name_entry = Gtk.Entry()
        self.parameter_name_entry.set_width_chars(max(12, config.ui.decimal_spin_width_chars))
        attach_continuous_history(self.parameter_name_entry)
        self.parameter_fields_box.append(self.build_row("Name", self.parameter_name_entry))

        self.parameter_min_spin = self.make_spin(
            config.limits.star_parameter_value_min,
            config.limits.star_parameter_value_max,
            0.1,
            digits=3,
        )
        attach_continuous_history(self.parameter_min_spin)
        self.parameter_fields_box.append(self.build_row("Min", self.parameter_min_spin))

        self.parameter_max_spin = self.make_spin(
            config.limits.star_parameter_value_min,
            config.limits.star_parameter_value_max,
            0.1,
            digits=3,
        )
        attach_continuous_history(self.parameter_max_spin)
        self.parameter_fields_box.append(self.build_row("Max", self.parameter_max_spin))

    def apply(self, view_model: ParameterPanelViewModel) -> None:
        self.parameter_enabled_check.set_active(view_model.enabled)
        self.parameter_fields_box.set_sensitive(view_model.enabled)
        self.parameter_name_entry.set_text(view_model.name)
        self.parameter_min_spin.set_value(view_model.min_value)
        self.parameter_max_spin.set_value(view_model.max_value)

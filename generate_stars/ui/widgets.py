from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from ..config import AppConfig


class PanelView(Gtk.Box):
    def __init__(self, title: str, config: AppConfig) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=config.ui.panel_spacing)
        self.config = config
        self.add_css_class("panel")

        heading = Gtk.Label(label=title, xalign=0.0)
        heading.add_css_class("panel-title")
        self.append(heading)

    def build_row(self, label_text: str, widget: Gtk.Widget) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=self.config.ui.row_spacing)
        label = Gtk.Label(label=label_text, xalign=0.0)
        label.set_hexpand(True)
        row.append(label)
        row.append(widget)
        return row

    def make_spin(
        self,
        lower: float,
        upper: float,
        step: float,
        digits: int = 0,
    ) -> Gtk.SpinButton:
        adjustment = Gtk.Adjustment(
            value=lower,
            lower=lower,
            upper=upper,
            step_increment=step,
            page_increment=step * self.config.ui.spin_page_multiplier,
        )
        spin = Gtk.SpinButton(adjustment=adjustment, digits=digits)
        spin.set_numeric(True)
        spin.set_hexpand(False)
        spin.set_width_chars(
            self.config.ui.integer_spin_width_chars if digits == 0 else self.config.ui.decimal_spin_width_chars
        )
        return spin

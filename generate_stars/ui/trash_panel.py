from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from ..config import AppConfig
from ..controllers.view_models import TrashPanelViewModel
from ..localization import get_localizer
from .widgets import PanelView


class TrashPanelView(PanelView):
    def __init__(self, config: AppConfig, attach_continuous_history: Callable[[Gtk.Widget], None]) -> None:
        localizer = get_localizer()
        super().__init__(localizer.text("ui.panel.trash_stars"), config)

        self.trash_count_spin = self.make_spin(
            config.limits.trash_star_count_min,
            config.limits.trash_star_count_max,
            1,
        )
        attach_continuous_history(self.trash_count_spin)
        self.append(self.build_row(localizer.text("ui.label.trash_star_count"), self.trash_count_spin))

        self.trash_distance_spin = self.make_spin(
            config.limits.trash_distance_min,
            config.limits.trash_distance_max,
            1,
            digits=1,
        )
        attach_continuous_history(self.trash_distance_spin)
        self.append(self.build_row(localizer.text("ui.label.min_edge_distance"), self.trash_distance_spin))

        self.note = Gtk.Label(xalign=0.0)
        self.note.set_wrap(True)
        self.note.add_css_class("dim-label")
        self.append(self.note)

    def apply(self, view_model: TrashPanelViewModel) -> None:
        self.trash_count_spin.set_value(view_model.count)
        self.trash_distance_spin.set_value(view_model.min_distance)
        self.note.set_text(view_model.note)

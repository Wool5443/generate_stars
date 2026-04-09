from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from ..config import AppConfig
from ..controllers.view_models import DistributionPanelViewModel
from ..localization import get_localizer
from ..models import DistributionMode
from .widgets import PanelView


class DistributionPanelView(PanelView):
    def __init__(
        self,
        config: AppConfig,
        attach_continuous_history: Callable[[Gtk.Widget], None],
        manual_count_changed: Callable[[Gtk.SpinButton, int], None],
    ) -> None:
        localizer = get_localizer()
        super().__init__(localizer.text("ui.panel.stars"), config)
        self._attach_continuous_history = attach_continuous_history
        self._manual_count_changed = manual_count_changed
        self._manual_signature: tuple[tuple[int, str], ...] = ()
        self._manual_spins: dict[int, Gtk.SpinButton] = {}

        self.total_stars_spin = self.make_spin(config.limits.total_stars_min, config.limits.total_stars_max, 1)
        attach_continuous_history(self.total_stars_spin)
        self.append(self.build_row(localizer.text("ui.label.total_cluster_stars"), self.total_stars_spin))

        self.distribution_combo = Gtk.ComboBoxText()
        self.distribution_combo.append(DistributionMode.EQUAL.value, localizer.text("ui.option.equal"))
        self.distribution_combo.append(DistributionMode.DEVIATION.value, localizer.text("ui.option.deviation"))
        self.distribution_combo.append(DistributionMode.MANUAL.value, localizer.text("ui.option.manual"))
        self.append(self.build_row(localizer.text("ui.label.distribution"), self.distribution_combo))

        self.deviation_spin = self.make_spin(
            config.limits.deviation_percent_min,
            config.limits.deviation_percent_max,
            1,
            digits=1,
        )
        attach_continuous_history(self.deviation_spin)
        self.deviation_row = self.build_row(localizer.text("ui.label.deviation_percent"), self.deviation_spin)
        self.append(self.deviation_row)

        self.manual_counts_note = Gtk.Label(xalign=0.0)
        self.manual_counts_note.set_wrap(True)
        self.manual_counts_note.add_css_class("dim-label")
        self.append(self.manual_counts_note)

        self.manual_counts_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.ui.cluster_section_spacing)
        self.append(self.manual_counts_box)

    def apply(self, view_model: DistributionPanelViewModel) -> None:
        self.total_stars_spin.set_value(view_model.total_stars)
        self.total_stars_spin.set_sensitive(view_model.total_stars_sensitive)
        self.distribution_combo.set_active_id(view_model.distribution_mode.value)
        self.deviation_spin.set_value(view_model.deviation_percent)
        self.deviation_row.set_visible(view_model.show_deviation)
        self.manual_counts_note.set_text(view_model.manual_note)
        self.manual_counts_note.set_visible(view_model.show_manual_counts)
        self.manual_counts_box.set_visible(view_model.show_manual_counts)
        self._apply_manual_rows(view_model)

    def _apply_manual_rows(self, view_model: DistributionPanelViewModel) -> None:
        signature = tuple((row.cluster_id, row.label) for row in view_model.manual_rows)
        if signature != self._manual_signature:
            self._manual_signature = signature
            self._manual_spins = {}
            while (child := self.manual_counts_box.get_first_child()) is not None:
                self.manual_counts_box.remove(child)

            for row_view_model in view_model.manual_rows:
                spin = self.make_spin(self.config.limits.total_stars_min, self.config.limits.total_stars_max, 1)
                self._attach_continuous_history(spin)
                spin.connect("value-changed", self._manual_count_changed, row_view_model.cluster_id)
                self.manual_counts_box.append(self.build_row(row_view_model.label, spin))
                self._manual_spins[row_view_model.cluster_id] = spin

        for row_view_model in view_model.manual_rows:
            spin = self._manual_spins.get(row_view_model.cluster_id)
            if spin is None:
                continue
            if spin.get_value_as_int() != row_view_model.value:
                spin.set_value(row_view_model.value)

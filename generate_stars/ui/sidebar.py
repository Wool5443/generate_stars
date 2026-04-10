from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from ..config import AppConfig
from ..controllers.view_models import WindowViewModel
from ..localization import get_localizer
from .cluster_panel import ClusterPanelView
from .distribution_panel import DistributionPanelView
from .parameter_panel import ParameterPanelView
from .trash_panel import TrashPanelView


class SidebarView(Gtk.Box):
    def __init__(
        self,
        config: AppConfig,
        attach_continuous_history: Callable[[Gtk.Widget], None],
        manual_count_changed: Callable[[Gtk.SpinButton, int], None],
    ) -> None:
        localizer = get_localizer()
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=config.ui.sidebar_spacing)
        self.config = config
        self.set_size_request(config.ui.sidebar_width, -1)
        self.add_css_class("sidebar")

        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_vexpand(True)
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(self.scroller)

        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.ui.sidebar_content_spacing)
        self.content.set_margin_top(config.ui.sidebar_margin)
        self.content.set_margin_bottom(config.ui.sidebar_margin)
        self.content.set_margin_start(config.ui.sidebar_margin)
        self.content.set_margin_end(config.ui.sidebar_margin)
        self.scroller.set_child(self.content)

        self.cluster_panel = ClusterPanelView(config, attach_continuous_history)
        self.distribution_panel = DistributionPanelView(config, attach_continuous_history, manual_count_changed)
        self.parameter_panel = ParameterPanelView(config, attach_continuous_history)
        self.trash_panel = TrashPanelView(config, attach_continuous_history)

        self.content.append(self.cluster_panel)
        self.content.append(self.distribution_panel)
        self.content.append(self.parameter_panel)
        self.content.append(self.trash_panel)

        self.footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=config.ui.sidebar_footer_spacing)
        self.footer.set_margin_start(config.ui.sidebar_margin)
        self.footer.set_margin_end(config.ui.sidebar_margin)
        self.footer.set_margin_bottom(config.ui.sidebar_margin)
        self.append(self.footer)

        self.generate_button = Gtk.Button(label=localizer.text("ui.generate"))
        self.generate_button.add_css_class("suggested-action")
        self.generate_button.add_css_class("generate-button")
        self.save_config_button = Gtk.Button(label=localizer.text("ui.save_configuration"))
        self.load_config_button = Gtk.Button(label=localizer.text("ui.load_configuration"))
        self.footer.append(self.save_config_button)
        self.footer.append(self.load_config_button)
        self.footer.append(self.generate_button)

        self.status_label = Gtk.Label(xalign=0.0)
        self.status_label.set_wrap(True)
        self.footer.append(self.status_label)

    def apply(self, view_model: WindowViewModel) -> None:
        self.cluster_panel.apply(view_model.cluster_panel)
        self.distribution_panel.apply(view_model.distribution_panel)
        self.parameter_panel.apply(view_model.parameter_panel)
        self.trash_panel.apply(view_model.trash_panel)

        self.generate_button.set_sensitive(view_model.generate_enabled)
        self.status_label.set_text(view_model.status.text)
        self.status_label.remove_css_class("status-error")
        self.status_label.remove_css_class("status-success")
        if view_model.status.kind == "error":
            self.status_label.add_css_class("status-error")
        elif view_model.status.kind == "success":
            self.status_label.add_css_class("status-success")

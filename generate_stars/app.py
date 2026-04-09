from __future__ import annotations

import sys

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gtk

from .config import AppConfig, ConfigIssue, initialize_app_config
from .controllers.editor_controller import EditorController
from .ui.window import StarClusterWindow


class StarClusterApplication(Gtk.Application):
    def __init__(self, config: AppConfig, config_issues: list[ConfigIssue]) -> None:
        self.config = config
        self._config_issues = list(config_issues)
        super().__init__(application_id=config.app.application_id)

    def do_activate(self) -> None:
        settings = Gtk.Settings.get_default()
        if settings is not None:
            settings.set_property("gtk-application-prefer-dark-theme", True)

        display = Gdk.Display.get_default()
        if display is not None:
            provider = Gtk.CssProvider()
            provider.load_from_data(self.config.app.css)
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

        window = self.props.active_window
        if window is None:
            controller = EditorController(self.config)
            window = StarClusterWindow(self, controller, self.config, self._config_issues)
        window.present()
        if isinstance(window, StarClusterWindow):
            window.focus_canvas()
            window.show_startup_config_issues()
        self._config_issues.clear()


def main(argv: list[str] | None = None) -> int:
    config, config_issues = initialize_app_config(create_missing=True)
    app = StarClusterApplication(config, config_issues)
    return app.run(argv or sys.argv)

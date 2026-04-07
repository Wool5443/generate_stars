from __future__ import annotations

from pathlib import Path
import sys

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gio, Gtk

from .canvas import StarCanvas
from .config import AppConfig, ConfigIssue, initialize_app_config
from .generator import (
    GenerationError,
    ensure_cluster_storage,
    even_counts,
    format_points_for_export,
    generate_ring_centers,
    generate_star_field,
    validate_state,
)
from .models import AppState, DistributionMode, ShapeKind
from .preferences import load_last_save_path, save_last_save_path

class StarClusterWindow(Gtk.ApplicationWindow):
    def __init__(self, application: Gtk.Application, config: AppConfig, config_issues: list[ConfigIssue]) -> None:
        self.config = config
        self._startup_config_issues = list(config_issues)
        super().__init__(application=application, title=config.app.title)
        self.set_default_size(config.window.default_width, config.window.default_height)

        self.state = AppState()
        self._last_save_path = load_last_save_path()
        ensure_cluster_storage(self.state)
        self._reset_cluster_positions()
        self.state.manual_counts = even_counts(self.state.total_cluster_stars, self.state.cluster_count)
        ensure_cluster_storage(self.state)

        self._syncing_ui = False
        self._space_pressed = False
        self._status_text = self.config.text.ready_status
        self._status_kind = "neutral"

        self._install_key_controller()
        self._build_ui()
        self._load_initial_widget_values()
        self._refresh_ui(rebuild_cluster_rows=True)

    def _install_key_controller(self) -> None:
        controller = Gtk.EventControllerKey.new()
        controller.connect("key-pressed", self._on_key_pressed)
        controller.connect("key-released", self._on_key_released)
        self.add_controller(controller)

    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.set_child(root)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.config.ui.sidebar_spacing)
        sidebar.set_size_request(self.config.ui.sidebar_width, -1)
        sidebar.add_css_class("sidebar")
        root.append(sidebar)

        sidebar_scroller = Gtk.ScrolledWindow()
        sidebar_scroller.set_vexpand(True)
        sidebar_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar.append(sidebar_scroller)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.config.ui.sidebar_content_spacing)
        content.set_margin_top(self.config.ui.sidebar_margin)
        content.set_margin_bottom(self.config.ui.sidebar_margin)
        content.set_margin_start(self.config.ui.sidebar_margin)
        content.set_margin_end(self.config.ui.sidebar_margin)
        sidebar_scroller.set_child(content)

        content.append(self._build_shape_section())
        content.append(self._build_distribution_section())
        content.append(self._build_trash_section())
        content.append(self._build_cluster_editor_section())

        footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.config.ui.sidebar_footer_spacing)
        footer.set_margin_start(self.config.ui.sidebar_margin)
        footer.set_margin_end(self.config.ui.sidebar_margin)
        footer.set_margin_bottom(self.config.ui.sidebar_margin)
        sidebar.append(footer)

        self.generate_button = Gtk.Button(label="Generate")
        self.generate_button.add_css_class("suggested-action")
        self.generate_button.add_css_class("generate-button")
        self.generate_button.connect("clicked", self._on_generate_clicked)
        footer.append(self.generate_button)

        self.status_label = Gtk.Label(xalign=0.0)
        self.status_label.set_wrap(True)
        footer.append(self.status_label)

        canvas_shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        canvas_shell.set_hexpand(True)
        canvas_shell.set_vexpand(True)
        canvas_shell.add_css_class("canvas-shell")
        root.append(canvas_shell)

        self.canvas = StarCanvas(self.state, self._is_space_pressed, self.config)
        canvas_shell.append(self.canvas)

    def _build_panel(self, title: str) -> Gtk.Box:
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.config.ui.panel_spacing)
        panel.add_css_class("panel")

        heading = Gtk.Label(label=title, xalign=0.0)
        heading.add_css_class("panel-title")
        panel.append(heading)
        return panel

    def _build_row(self, label_text: str, widget: Gtk.Widget) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=self.config.ui.row_spacing)
        label = Gtk.Label(label=label_text, xalign=0.0)
        label.set_hexpand(True)
        row.append(label)
        row.append(widget)
        return row

    def _make_spin(
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

    def _build_shape_section(self) -> Gtk.Box:
        panel = self._build_panel("Clusters")

        self.shape_combo = Gtk.ComboBoxText()
        self.shape_combo.append(ShapeKind.CIRCLE.value, "Circle")
        self.shape_combo.append(ShapeKind.RECTANGLE.value, "Rectangle")
        self.shape_combo.connect("changed", self._on_shape_changed)
        panel.append(self._build_row("Shape", self.shape_combo))

        self.cluster_count_spin = self._make_spin(self.config.limits.cluster_count_min, self.config.limits.cluster_count_max, 1)
        self.cluster_count_spin.connect("value-changed", self._on_cluster_count_changed)
        panel.append(self._build_row("Cluster count", self.cluster_count_spin))

        self.reset_positions_button = Gtk.Button(label="Reset Positions")
        self.reset_positions_button.connect("clicked", self._on_reset_positions_clicked)
        panel.append(self.reset_positions_button)

        self.shared_radius_spin = self._make_spin(self.config.limits.size_min, self.config.limits.size_max, 1, digits=1)
        self.shared_radius_spin.connect("value-changed", self._on_shared_radius_changed)
        self.shared_radius_row = self._build_row("Radius", self.shared_radius_spin)
        panel.append(self.shared_radius_row)

        self.shared_width_spin = self._make_spin(self.config.limits.size_min, self.config.limits.size_max, 1, digits=1)
        self.shared_width_spin.connect("value-changed", self._on_shared_width_changed)
        self.shared_width_row = self._build_row("Width", self.shared_width_spin)
        panel.append(self.shared_width_row)

        self.shared_height_spin = self._make_spin(self.config.limits.size_min, self.config.limits.size_max, 1, digits=1)
        self.shared_height_spin.connect("value-changed", self._on_shared_height_changed)
        self.shared_height_row = self._build_row("Height", self.shared_height_spin)
        panel.append(self.shared_height_row)

        hint = Gtk.Label(
            label=self.config.text.shape_interaction_hint,
            xalign=0.0,
        )
        hint.set_wrap(True)
        hint.add_css_class("dim-label")
        panel.append(hint)
        return panel

    def _build_distribution_section(self) -> Gtk.Box:
        panel = self._build_panel("Stars")

        self.total_stars_spin = self._make_spin(self.config.limits.total_stars_min, self.config.limits.total_stars_max, 1)
        self.total_stars_spin.connect("value-changed", self._on_total_stars_changed)
        panel.append(self._build_row("Total cluster stars", self.total_stars_spin))

        self.distribution_combo = Gtk.ComboBoxText()
        self.distribution_combo.append(DistributionMode.EQUAL.value, "Equal")
        self.distribution_combo.append(DistributionMode.DEVIATION.value, "Deviation")
        self.distribution_combo.append(DistributionMode.MANUAL.value, "Manual")
        self.distribution_combo.connect("changed", self._on_distribution_changed)
        panel.append(self._build_row("Distribution", self.distribution_combo))

        self.deviation_spin = self._make_spin(
            self.config.limits.deviation_percent_min,
            self.config.limits.deviation_percent_max,
            1,
            digits=1,
        )
        self.deviation_spin.connect("value-changed", self._on_deviation_changed)
        self.deviation_row = self._build_row("Deviation %", self.deviation_spin)
        panel.append(self.deviation_row)

        self.manual_counts_note = Gtk.Label(label=self.config.text.manual_counts_note, xalign=0.0)
        self.manual_counts_note.set_wrap(True)
        self.manual_counts_note.add_css_class("dim-label")
        panel.append(self.manual_counts_note)

        self.manual_counts_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.config.ui.cluster_section_spacing)
        panel.append(self.manual_counts_box)
        return panel

    def _build_trash_section(self) -> Gtk.Box:
        panel = self._build_panel("Trash Stars")

        self.trash_count_spin = self._make_spin(
            self.config.limits.trash_star_count_min,
            self.config.limits.trash_star_count_max,
            1,
        )
        self.trash_count_spin.connect("value-changed", self._on_trash_count_changed)
        panel.append(self._build_row("Trash star count", self.trash_count_spin))

        self.trash_distance_spin = self._make_spin(
            self.config.limits.trash_distance_min,
            self.config.limits.trash_distance_max,
            1,
            digits=1,
        )
        self.trash_distance_spin.connect("value-changed", self._on_trash_distance_changed)
        panel.append(self._build_row("Min edge distance", self.trash_distance_spin))

        note = Gtk.Label(
            label=self.config.text.trash_note,
            xalign=0.0,
        )
        note.set_wrap(True)
        note.add_css_class("dim-label")
        panel.append(note)
        return panel

    def _build_cluster_editor_section(self) -> Gtk.Box:
        panel = self._build_panel("Per-Cluster Overrides")

        self.cluster_editor_info = Gtk.Label(xalign=0.0)
        self.cluster_editor_info.set_wrap(True)
        panel.append(self.cluster_editor_info)

        self.cluster_rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.config.ui.cluster_section_spacing)
        panel.append(self.cluster_rows_box)
        return panel

    def _load_initial_widget_values(self) -> None:
        self._syncing_ui = True
        try:
            self.shape_combo.set_active_id(self.state.shape_kind.value)
            self.cluster_count_spin.set_value(self.state.cluster_count)
            self.shared_radius_spin.set_value(self.state.shared_size.radius)
            self.shared_width_spin.set_value(self.state.shared_size.width)
            self.shared_height_spin.set_value(self.state.shared_size.height)
            self.total_stars_spin.set_value(self.state.total_cluster_stars)
            self.distribution_combo.set_active_id(self.state.distribution_mode.value)
            self.deviation_spin.set_value(self.state.deviation_percent)
            self.trash_count_spin.set_value(self.state.trash_star_count)
            self.trash_distance_spin.set_value(self.state.trash_min_distance)
        finally:
            self._syncing_ui = False

    def _set_status(self, text: str, kind: str = "neutral") -> None:
        self._status_text = text
        self._status_kind = kind
        self._update_status_label()

    def _clear_status(self) -> None:
        if self._status_kind != "error":
            self._status_text = self.config.text.ready_status
            self._status_kind = "neutral"

    def _update_status_label(self) -> None:
        self.status_label.set_text(self._status_text)
        self.status_label.remove_css_class("status-error")
        self.status_label.remove_css_class("status-success")
        if self._status_kind == "error":
            self.status_label.add_css_class("status-error")
        elif self._status_kind == "success":
            self.status_label.add_css_class("status-success")

    def _is_space_pressed(self) -> bool:
        return self._space_pressed

    def _reset_cluster_positions(self) -> None:
        ensure_cluster_storage(self.state)
        self.state.cluster_centers = generate_ring_centers(
            self.state.shape_kind,
            [self.state.resolved_size(index) for index in range(self.state.cluster_count)],
        )
        self.state.positions_customized = False

    def _sync_positions_for_size_change(self) -> None:
        if not self.state.positions_customized:
            self._reset_cluster_positions()

    def _sync_total_stars_for_manual_mode(self) -> None:
        if self.state.distribution_mode is not DistributionMode.MANUAL:
            return

        ensure_cluster_storage(self.state)
        self.state.total_cluster_stars = sum(self.state.manual_counts)

        syncing_ui = self._syncing_ui
        self._syncing_ui = True
        try:
            self.total_stars_spin.set_value(self.state.total_cluster_stars)
        finally:
            self._syncing_ui = syncing_ui

    def _refresh_ui(self, rebuild_cluster_rows: bool = False) -> None:
        circle_mode = self.state.shape_kind is ShapeKind.CIRCLE
        manual_mode = self.state.distribution_mode is DistributionMode.MANUAL
        self.shared_radius_row.set_visible(circle_mode)
        self.shared_width_row.set_visible(not circle_mode)
        self.shared_height_row.set_visible(not circle_mode)
        self.deviation_row.set_visible(self.state.distribution_mode is DistributionMode.DEVIATION)
        self.manual_counts_note.set_visible(manual_mode)
        self.manual_counts_box.set_visible(manual_mode)
        self.reset_positions_button.set_sensitive(self.state.cluster_count > 0)
        self.total_stars_spin.set_sensitive(not manual_mode)

        if rebuild_cluster_rows:
            self._rebuild_cluster_rows()
            self._rebuild_manual_count_rows()

        if manual_mode:
            self._sync_total_stars_for_manual_mode()

        errors = validate_state(self.state)
        if errors:
            self.generate_button.set_sensitive(False)
            self._status_text = errors[0]
            self._status_kind = "error"
        else:
            self.generate_button.set_sensitive(True)
            if self._status_kind == "error":
                self._status_text = self.config.text.ready_status
                self._status_kind = "neutral"

        self.cluster_editor_info.set_text(
            f"{self.state.cluster_count} clusters. Size overrides are optional."
        )
        self._update_status_label()
        self.canvas.queue_draw()

    def _rebuild_cluster_rows(self) -> None:
        while (child := self.cluster_rows_box.get_first_child()) is not None:
            self.cluster_rows_box.remove(child)

        ensure_cluster_storage(self.state)
        circle_mode = self.state.shape_kind is ShapeKind.CIRCLE

        for index in range(self.state.cluster_count):
            section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.config.ui.cluster_section_spacing)

            title = Gtk.Label(label=f"Cluster {index + 1}", xalign=0.0)
            title.add_css_class("panel-title")
            section.append(title)

            override_toggle = Gtk.CheckButton(label="Override shared size")
            override_toggle.set_active(self.state.size_overrides_enabled[index])
            override_toggle.connect("toggled", self._on_override_toggled, index)
            section.append(override_toggle)

            size_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            size_box.set_sensitive(self.state.size_overrides_enabled[index])
            section.append(size_box)

            override_size = self.state.size_overrides[index]
            if circle_mode:
                radius_spin = self._make_spin(self.config.limits.size_min, self.config.limits.size_max, 1, digits=1)
                radius_spin.set_value(override_size.radius)
                radius_spin.connect("value-changed", self._on_override_radius_changed, index)
                size_box.append(self._build_row("Radius", radius_spin))
            else:
                width_spin = self._make_spin(self.config.limits.size_min, self.config.limits.size_max, 1, digits=1)
                width_spin.set_value(override_size.width)
                width_spin.connect("value-changed", self._on_override_width_changed, index)
                size_box.append(self._build_row("Width", width_spin))

                height_spin = self._make_spin(self.config.limits.size_min, self.config.limits.size_max, 1, digits=1)
                height_spin.set_value(override_size.height)
                height_spin.connect("value-changed", self._on_override_height_changed, index)
                size_box.append(self._build_row("Height", height_spin))

            self.cluster_rows_box.append(section)
            if index != self.state.cluster_count - 1:
                self.cluster_rows_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

    def _rebuild_manual_count_rows(self) -> None:
        while (child := self.manual_counts_box.get_first_child()) is not None:
            self.manual_counts_box.remove(child)

        ensure_cluster_storage(self.state)
        for index in range(self.state.cluster_count):
            manual_spin = self._make_spin(self.config.limits.total_stars_min, self.config.limits.total_stars_max, 1)
            manual_spin.set_value(self.state.manual_counts[index])
            manual_spin.connect("value-changed", self._on_manual_count_changed, index)
            self.manual_counts_box.append(self._build_row(f"Cluster {index + 1}", manual_spin))

    def _on_key_pressed(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_space:
            self._space_pressed = True
        return False

    def _on_key_released(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> None:
        if keyval == Gdk.KEY_space:
            self._space_pressed = False

    def _on_shape_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self._syncing_ui:
            return
        active_id = combo.get_active_id()
        if not active_id:
            return
        self.state.shape_kind = ShapeKind(active_id)
        self._reset_cluster_positions()
        self._clear_status()
        self._refresh_ui(rebuild_cluster_rows=True)

    def _on_cluster_count_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.state.cluster_count = spin.get_value_as_int()
        self._reset_cluster_positions()
        if self.state.distribution_mode is DistributionMode.MANUAL:
            ensure_cluster_storage(self.state)
            self._sync_total_stars_for_manual_mode()
        else:
            self.state.manual_counts = even_counts(self.state.total_cluster_stars, self.state.cluster_count)
            ensure_cluster_storage(self.state)
        self._clear_status()
        self._refresh_ui(rebuild_cluster_rows=True)

    def _on_reset_positions_clicked(self, button: Gtk.Button) -> None:
        self._reset_cluster_positions()
        self._set_status(self.config.text.reset_positions_status, "neutral")
        self._refresh_ui()

    def _on_shared_radius_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.state.shared_size.radius = spin.get_value()
        self._sync_positions_for_size_change()
        self._clear_status()
        self._refresh_ui()

    def _on_shared_width_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.state.shared_size.width = spin.get_value()
        self._sync_positions_for_size_change()
        self._clear_status()
        self._refresh_ui()

    def _on_shared_height_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.state.shared_size.height = spin.get_value()
        self._sync_positions_for_size_change()
        self._clear_status()
        self._refresh_ui()

    def _on_total_stars_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.state.total_cluster_stars = spin.get_value_as_int()
        self._clear_status()
        self._refresh_ui()

    def _on_distribution_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self._syncing_ui:
            return
        active_id = combo.get_active_id()
        if not active_id:
            return
        self.state.distribution_mode = DistributionMode(active_id)
        if self.state.distribution_mode is DistributionMode.MANUAL:
            ensure_cluster_storage(self.state)
            if sum(self.state.manual_counts) != self.state.total_cluster_stars:
                self.state.manual_counts = even_counts(self.state.total_cluster_stars, self.state.cluster_count)
                ensure_cluster_storage(self.state)
            self._sync_total_stars_for_manual_mode()
        self._clear_status()
        self._refresh_ui(rebuild_cluster_rows=True)

    def _on_deviation_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.state.deviation_percent = spin.get_value()
        self._clear_status()
        self._refresh_ui()

    def _on_trash_count_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.state.trash_star_count = spin.get_value_as_int()
        self._clear_status()
        self._refresh_ui()

    def _on_trash_distance_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.state.trash_min_distance = spin.get_value()
        self._clear_status()
        self._refresh_ui()

    def _on_override_toggled(self, button: Gtk.CheckButton, index: int) -> None:
        if self._syncing_ui:
            return
        self.state.size_overrides_enabled[index] = button.get_active()
        self._sync_positions_for_size_change()
        self._clear_status()
        self._refresh_ui(rebuild_cluster_rows=True)

    def _on_override_radius_changed(self, spin: Gtk.SpinButton, index: int) -> None:
        self.state.size_overrides[index].radius = spin.get_value()
        self._sync_positions_for_size_change()
        self._clear_status()
        self._refresh_ui()

    def _on_override_width_changed(self, spin: Gtk.SpinButton, index: int) -> None:
        self.state.size_overrides[index].width = spin.get_value()
        self._sync_positions_for_size_change()
        self._clear_status()
        self._refresh_ui()

    def _on_override_height_changed(self, spin: Gtk.SpinButton, index: int) -> None:
        self.state.size_overrides[index].height = spin.get_value()
        self._sync_positions_for_size_change()
        self._clear_status()
        self._refresh_ui()

    def _on_manual_count_changed(self, spin: Gtk.SpinButton, index: int) -> None:
        self.state.manual_counts[index] = spin.get_value_as_int()
        self._sync_total_stars_for_manual_mode()
        self._clear_status()
        self._refresh_ui()

    def _show_error_dialog(self, message: str) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            buttons=Gtk.ButtonsType.OK,
            message_type=Gtk.MessageType.ERROR,
            text=message,
        )
        dialog.connect("response", lambda dialog, _: dialog.destroy())
        dialog.show()

    def show_startup_config_issues(self) -> None:
        if not self._startup_config_issues:
            return
        message = "Some config values were ignored and defaults were used:\n\n" + "\n".join(
            f"{issue.path}: {issue.message}" for issue in self._startup_config_issues
        )
        self._startup_config_issues.clear()
        self._show_error_dialog(message)

    def _on_generate_clicked(self, button: Gtk.Button) -> None:
        errors = validate_state(self.state)
        if errors:
            self._set_status(errors[0], "error")
            return

        dialog = Gtk.FileChooserNative.new(
            self.config.text.save_dialog_title,
            self,
            Gtk.FileChooserAction.SAVE,
            "_Save",
            "_Cancel",
        )
        dialog.set_modal(True)
        self._configure_save_dialog(dialog)
        dialog.connect("response", self._on_save_response)
        dialog.show()

    def _configure_save_dialog(self, dialog: Gtk.FileChooserNative) -> None:
        default_path = self._last_save_path
        if default_path is None:
            dialog.set_current_name(self.config.defaults.default_save_filename)
            return

        if default_path.is_dir():
            folder = default_path
            filename = self.config.defaults.default_save_filename
        else:
            folder = default_path.parent
            filename = default_path.name

        if folder.exists():
            dialog.set_current_folder(Gio.File.new_for_path(str(folder)))
        dialog.set_current_name(filename or self.config.defaults.default_save_filename)

    def _on_save_response(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        try:
            if response != Gtk.ResponseType.ACCEPT:
                self._clear_status()
                self._refresh_ui()
                return

            file = dialog.get_file()
            if file is None or file.get_path() is None:
                raise GenerationError("Please choose a local file path.")

            output_path = Path(file.get_path())
            if output_path.suffix.lower() != ".txt":
                output_path = output_path.with_suffix(".txt") if output_path.suffix else Path(f"{output_path}.txt")

            generated = generate_star_field(self.state)
            output_path.write_text(format_points_for_export(generated.points), encoding="utf-8")
            self._last_save_path = output_path
            save_last_save_path(output_path)
            self._set_status(f"Saved {len(generated.points)} stars to {output_path.name}.", "success")
        except (GenerationError, OSError) as exc:
            self._set_status(str(exc), "error")
            self._show_error_dialog(str(exc))
        finally:
            dialog.destroy()
            self._refresh_ui()


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
            window = StarClusterWindow(self, self.config, self._config_issues)
        window.present()
        if isinstance(window, StarClusterWindow):
            window.show_startup_config_issues()
        self._config_issues.clear()


def main(argv: list[str] | None = None) -> int:
    config, config_issues = initialize_app_config(create_missing=True)
    app = StarClusterApplication(config, config_issues)
    return app.run(argv or sys.argv)

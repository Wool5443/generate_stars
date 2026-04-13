from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gio, GLib, Gtk

from ..cluster_configuration import DEFAULT_CLUSTER_CONFIGURATION_FILENAME
from ..config import AppConfig, ConfigIssue
from ..controllers.editor_controller import EditorController
from ..generator import GenerationError
from ..localization import get_localizer
from ..models import CanvasTool, DistributionMode, FunctionOrientation, ShapeKind, StarParameterMode
from .canvas import StarCanvas
from .sidebar import SidebarView
from .toolbar import CanvasToolbarView


class StarClusterWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application,
        controller: EditorController,
        config: AppConfig,
        config_issues: list[ConfigIssue],
    ) -> None:
        self.config = config
        self.controller = controller
        self._startup_config_issues = list(config_issues)
        self._syncing_ui = False
        self._space_pressed = False
        super().__init__(application=application, title=config.app.title)
        self.set_default_size(config.window.default_width, config.window.default_height)

        self._install_key_controller()
        self._build_ui()
        self.controller.set_change_listener(self._refresh_from_controller)
        self._refresh_from_controller()

    def _build_ui(self) -> None:
        self._build_header_bar()
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.set_child(root)

        self.sidebar_view = SidebarView(self.config, self._attach_continuous_history, self._on_manual_count_changed)
        root.append(self.sidebar_view)

        canvas_shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.config.ui.panel_spacing)
        canvas_shell.set_hexpand(True)
        canvas_shell.set_vexpand(True)
        canvas_shell.add_css_class("canvas-shell")
        canvas_shell.set_margin_top(self.config.ui.sidebar_margin)
        canvas_shell.set_margin_bottom(self.config.ui.sidebar_margin)
        canvas_shell.set_margin_start(self.config.ui.sidebar_margin)
        canvas_shell.set_margin_end(self.config.ui.sidebar_margin)
        root.append(canvas_shell)

        self.toolbar_view = CanvasToolbarView(self.config)
        canvas_shell.append(self.toolbar_view)

        self.canvas = StarCanvas(self.controller, self._is_space_pressed, self.config)
        canvas_shell.append(self.canvas)

        self._connect_signals()

    def _build_header_bar(self) -> None:
        localizer = get_localizer()
        self.header_bar = Gtk.HeaderBar()
        self.set_titlebar(self.header_bar)

        self.help_button = Gtk.Button(label=localizer.text("ui.help"))
        self.header_bar.pack_end(self.help_button)

        self.config_menu_button = Gtk.MenuButton(label=localizer.text("ui.config"))
        self.config_popover = Gtk.Popover()
        self.config_popover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.config.ui.row_spacing)
        self.config_popover_box.set_margin_top(self.config.ui.sidebar_margin)
        self.config_popover_box.set_margin_bottom(self.config.ui.sidebar_margin)
        self.config_popover_box.set_margin_start(self.config.ui.sidebar_margin)
        self.config_popover_box.set_margin_end(self.config.ui.sidebar_margin)
        self.config_save_button = Gtk.Button(label=localizer.text("ui.save_configuration"))
        self.config_load_button = Gtk.Button(label=localizer.text("ui.load_configuration"))
        self.config_popover_box.append(self.config_save_button)
        self.config_popover_box.append(self.config_load_button)
        self.config_popover.set_child(self.config_popover_box)
        self.config_menu_button.set_popover(self.config_popover)
        self.header_bar.pack_end(self.config_menu_button)

    def _connect_signals(self) -> None:
        self.toolbar_view.undo_button.connect("clicked", lambda _: self.controller.undo())
        self.toolbar_view.redo_button.connect("clicked", lambda _: self.controller.redo())
        self.toolbar_view.select_tool_button.connect("toggled", self._on_tool_button_toggled, CanvasTool.SELECT)
        self.toolbar_view.circle_tool_button.connect("toggled", self._on_tool_button_toggled, CanvasTool.CIRCLE)
        self.toolbar_view.rectangle_tool_button.connect("toggled", self._on_tool_button_toggled, CanvasTool.RECTANGLE)
        self.toolbar_view.polygon_tool_button.connect("toggled", self._on_tool_button_toggled, CanvasTool.POLYGON)
        self.toolbar_view.function_tool_button.connect("toggled", self._on_tool_button_toggled, CanvasTool.FUNCTION)
        self.toolbar_view.snap_button.connect("toggled", self._on_snap_toggled)

        cluster_panel = self.sidebar_view.cluster_panel
        cluster_panel.placement_radius_spin.connect("value-changed", self._on_placement_radius_changed)
        cluster_panel.placement_width_spin.connect("value-changed", self._on_placement_width_changed)
        cluster_panel.placement_height_spin.connect("value-changed", self._on_placement_height_changed)
        cluster_panel.placement_function_orientation_combo.connect("changed", self._on_placement_function_orientation_changed)
        cluster_panel.placement_function_expression_entry.connect("changed", self._on_placement_function_expression_changed)
        cluster_panel.placement_function_range_start_spin.connect("value-changed", self._on_placement_function_range_start_changed)
        cluster_panel.placement_function_range_end_spin.connect("value-changed", self._on_placement_function_range_end_changed)
        cluster_panel.placement_function_thickness_spin.connect("value-changed", self._on_placement_function_thickness_changed)
        cluster_panel.selection_shape_combo.connect("changed", self._on_selection_shape_changed)
        cluster_panel.selection_radius_spin.connect("value-changed", self._on_selection_radius_changed)
        cluster_panel.selection_width_spin.connect("value-changed", self._on_selection_width_changed)
        cluster_panel.selection_height_spin.connect("value-changed", self._on_selection_height_changed)
        cluster_panel.selection_polygon_scale_spin.connect("value-changed", self._on_selection_polygon_scale_changed)
        cluster_panel.selection_function_orientation_combo.connect("changed", self._on_selection_function_orientation_changed)
        cluster_panel.selection_function_expression_entry.connect("changed", self._on_selection_function_expression_changed)
        cluster_panel.selection_function_range_start_spin.connect("value-changed", self._on_selection_function_range_start_changed)
        cluster_panel.selection_function_range_end_spin.connect("value-changed", self._on_selection_function_range_end_changed)
        cluster_panel.selection_function_thickness_spin.connect("value-changed", self._on_selection_function_thickness_changed)

        distribution_panel = self.sidebar_view.distribution_panel
        distribution_panel.total_stars_spin.connect("value-changed", self._on_total_stars_changed)
        distribution_panel.distribution_combo.connect("changed", self._on_distribution_changed)
        distribution_panel.deviation_spin.connect("value-changed", self._on_deviation_changed)

        parameter_panel = self.sidebar_view.parameter_panel
        parameter_panel.parameter_enabled_check.connect("toggled", self._on_parameter_enabled_toggled)
        parameter_panel.parameter_name_entry.connect("changed", self._on_parameter_name_changed)
        parameter_panel.parameter_mode_combo.connect("changed", self._on_parameter_mode_changed)
        parameter_panel.parameter_min_spin.connect("value-changed", self._on_parameter_min_changed)
        parameter_panel.parameter_max_spin.connect("value-changed", self._on_parameter_max_changed)
        parameter_panel.parameter_function_body_buffer.connect("changed", self._on_parameter_function_body_changed)

        trash_panel = self.sidebar_view.trash_panel
        trash_panel.trash_count_spin.connect("value-changed", self._on_trash_count_changed)
        trash_panel.trash_distance_spin.connect("value-changed", self._on_trash_distance_changed)
        trash_panel.trash_max_distance_spin.connect("value-changed", self._on_trash_max_distance_changed)
        trash_panel.trash_min_star_distance_spin.connect("value-changed", self._on_trash_min_star_distance_changed)

        self.help_button.connect("clicked", self._on_help_clicked)
        self.config_save_button.connect("clicked", self._on_save_config_clicked)
        self.config_load_button.connect("clicked", self._on_load_config_clicked)
        self.sidebar_view.generate_button.connect("clicked", self._on_generate_clicked)

    def focus_canvas(self) -> None:
        GLib.idle_add(self._focus_canvas_idle)

    def _focus_canvas_idle(self) -> bool:
        self.set_focus(self.canvas)
        self.canvas.grab_focus()
        self._clear_text_selection()
        return False

    def _walk_widgets(self, widget: Gtk.Widget):
        current = widget
        while current is not None:
            yield current
            child = current.get_first_child()
            if child is not None:
                yield from self._walk_widgets(child)
            current = current.get_next_sibling()

    def _clear_text_selection(self) -> None:
        root = self.get_child()
        if root is None:
            return

        for widget in self._walk_widgets(root):
            if isinstance(widget, Gtk.Editable):
                widget.select_region(0, 0)

    def _attach_continuous_history(self, widget: Gtk.Widget) -> None:
        focus = Gtk.EventControllerFocus.new()
        focus.connect("leave", self._on_continuous_history_leave, widget)
        widget.add_controller(focus)

    def _on_continuous_history_leave(self, controller: Gtk.EventControllerFocus, widget: Gtk.Widget) -> None:
        self.controller.finish_continuous_history(widget)

    def _refresh_from_controller(self) -> None:
        view_model = self.controller.build_window_view_model()
        self._syncing_ui = True
        try:
            self.toolbar_view.apply(view_model.toolbar)
            self.sidebar_view.apply(view_model)
        finally:
            self._syncing_ui = False
        self.canvas.queue_draw()

    def _install_key_controller(self) -> None:
        controller = Gtk.EventControllerKey.new()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.connect("key-pressed", self._on_key_pressed)
        controller.connect("key-released", self._on_key_released)
        self.add_controller(controller)

    def _is_space_pressed(self) -> bool:
        return self._space_pressed

    def _focus_blocks_shortcuts(self) -> bool:
        widget = self.get_focus()
        while widget is not None:
            if isinstance(widget, Gtk.SpinButton):
                return False
            if isinstance(widget, Gtk.Entry) or isinstance(widget, Gtk.TextView):
                return True
            widget = widget.get_parent()
        return False

    def _set_active_tool(self, tool: CanvasTool) -> None:
        if self.controller.active_tool is tool:
            return
        if self.controller.active_tool is CanvasTool.POLYGON and tool is not CanvasTool.POLYGON:
            self.canvas.cancel_polygon_draft()
        self.controller.set_active_tool(tool)

    def _on_key_pressed(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        if self._focus_blocks_shortcuts():
            return False

        if state & Gdk.ModifierType.CONTROL_MASK and state & Gdk.ModifierType.SHIFT_MASK and keyval in (Gdk.KEY_z, Gdk.KEY_Z):
            self.controller.redo()
            return True

        if state & Gdk.ModifierType.CONTROL_MASK and keyval in (Gdk.KEY_c, Gdk.KEY_C):
            self.controller.copy_selected_clusters()
            return True

        if state & Gdk.ModifierType.CONTROL_MASK and keyval in (Gdk.KEY_v, Gdk.KEY_V):
            self.canvas.cancel_polygon_draft()
            self.controller.paste_copied_clusters()
            return True

        if state & Gdk.ModifierType.CONTROL_MASK and keyval in (Gdk.KEY_z, Gdk.KEY_Z):
            self.controller.undo()
            return True

        if state & Gdk.ModifierType.CONTROL_MASK and keyval in (Gdk.KEY_y, Gdk.KEY_Y):
            self.controller.redo()
            return True

        if state & Gdk.ModifierType.CONTROL_MASK and keyval in (Gdk.KEY_a, Gdk.KEY_A):
            self.controller.select_all_clusters()
            return True

        if keyval == Gdk.KEY_space:
            self._space_pressed = True
            return False

        if keyval in (Gdk.KEY_v, Gdk.KEY_V):
            self._set_active_tool(CanvasTool.SELECT)
            return True
        if keyval in (Gdk.KEY_c, Gdk.KEY_C):
            self._set_active_tool(CanvasTool.CIRCLE)
            return True
        if keyval in (Gdk.KEY_r, Gdk.KEY_R):
            self._set_active_tool(CanvasTool.RECTANGLE)
            return True
        if keyval in (Gdk.KEY_p, Gdk.KEY_P):
            self._set_active_tool(CanvasTool.POLYGON)
            return True
        if keyval in (Gdk.KEY_f, Gdk.KEY_F):
            self._set_active_tool(CanvasTool.FUNCTION)
            return True
        if keyval == Gdk.KEY_Escape:
            if self.canvas.cancel_polygon_draft():
                self.controller.clear_status(notify=True)
                return True
            self.controller.clear_selected_clusters()
            return True
        if keyval == Gdk.KEY_Delete:
            self.controller.delete_selected_clusters()
            return True
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

    def _on_tool_button_toggled(self, button: Gtk.ToggleButton, tool: CanvasTool) -> None:
        if self._syncing_ui or self.toolbar_view.syncing or not button.get_active():
            return
        self._set_active_tool(tool)

    def _on_snap_toggled(self, button: Gtk.ToggleButton) -> None:
        if self._syncing_ui or self.toolbar_view.syncing:
            return
        self.controller.set_snap_to_integer_grid(button.get_active())

    def _on_placement_radius_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_placement_radius(spin.get_value(), spin)

    def _on_placement_width_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_placement_width(spin.get_value(), spin)

    def _on_placement_height_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_placement_height(spin.get_value(), spin)

    def _on_placement_function_orientation_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self._syncing_ui:
            return
        active_id = combo.get_active_id()
        if active_id:
            self.controller.set_placement_function_orientation(FunctionOrientation(active_id))

    def _on_placement_function_expression_changed(self, entry: Gtk.Entry) -> None:
        if self._syncing_ui:
            return
        self.controller.set_placement_function_expression(entry.get_text(), entry)

    def _on_placement_function_range_start_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_placement_function_range_start(spin.get_value(), spin)

    def _on_placement_function_range_end_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_placement_function_range_end(spin.get_value(), spin)

    def _on_placement_function_thickness_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_placement_function_thickness(spin.get_value(), spin)

    def _on_selection_shape_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self._syncing_ui:
            return
        active_id = combo.get_active_id()
        if active_id:
            self.controller.set_selection_shape(ShapeKind(active_id))

    def _on_selection_radius_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_selection_radius(spin.get_value(), spin)

    def _on_selection_width_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_selection_width(spin.get_value(), spin)

    def _on_selection_height_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_selection_height(spin.get_value(), spin)

    def _on_selection_polygon_scale_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_selection_polygon_scale(spin.get_value(), spin)

    def _on_selection_function_orientation_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self._syncing_ui:
            return
        active_id = combo.get_active_id()
        if active_id:
            self.controller.set_selection_function_orientation(FunctionOrientation(active_id))

    def _on_selection_function_expression_changed(self, entry: Gtk.Entry) -> None:
        if self._syncing_ui:
            return
        self.controller.set_selection_function_expression(entry.get_text(), entry)

    def _on_selection_function_range_start_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_selection_function_range_start(spin.get_value(), spin)

    def _on_selection_function_range_end_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_selection_function_range_end(spin.get_value(), spin)

    def _on_selection_function_thickness_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_selection_function_thickness(spin.get_value(), spin)

    def _on_total_stars_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_total_cluster_stars(spin.get_value_as_int(), spin)

    def _on_distribution_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self._syncing_ui:
            return
        active_id = combo.get_active_id()
        if active_id:
            self.controller.set_distribution_mode(DistributionMode(active_id))

    def _on_deviation_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_deviation_percent(spin.get_value(), spin)

    def _on_parameter_enabled_toggled(self, button: Gtk.CheckButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_parameter_enabled(button.get_active())

    def _on_parameter_name_changed(self, entry: Gtk.Entry) -> None:
        if self._syncing_ui:
            return
        self.controller.set_parameter_name(entry.get_text(), entry)

    def _on_parameter_min_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_parameter_min(spin.get_value(), spin)

    def _on_parameter_max_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_parameter_max(spin.get_value(), spin)

    def _on_parameter_mode_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self._syncing_ui:
            return
        active_id = combo.get_active_id()
        if not active_id:
            return
        self.controller.set_parameter_mode(StarParameterMode(active_id))

    def _on_parameter_function_body_changed(self, buffer: Gtk.TextBuffer) -> None:
        if self._syncing_ui:
            return
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        self.controller.set_parameter_function_body(
            buffer.get_text(start, end, True),
            self.sidebar_view.parameter_panel.parameter_function_body_view,
        )

    def _on_trash_count_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_trash_star_count(spin.get_value_as_int(), spin)

    def _on_trash_distance_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_trash_min_distance(spin.get_value(), spin)

    def _on_trash_max_distance_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_trash_max_distance(spin.get_value(), spin)

    def _on_trash_min_star_distance_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.controller.set_trash_min_star_distance(spin.get_value(), spin)

    def _on_manual_count_changed(self, spin: Gtk.SpinButton, cluster_id: int) -> None:
        if self._syncing_ui:
            return
        self.controller.set_manual_count(cluster_id, spin.get_value_as_int(), spin)

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

    def _show_help_dialog(self) -> None:
        localizer = get_localizer()
        dialog = Gtk.Dialog(transient_for=self, modal=True, title=localizer.text("window.help_dialog_title"))
        dialog.set_default_size(780, 520)
        dialog.add_button(localizer.text("window.close_button"), Gtk.ResponseType.CLOSE)
        dialog.connect("response", lambda dialog, _: dialog.destroy())

        content_area = dialog.get_content_area()
        content_area.set_margin_top(self.config.ui.sidebar_margin)
        content_area.set_margin_bottom(self.config.ui.sidebar_margin)
        content_area.set_margin_start(self.config.ui.sidebar_margin)
        content_area.set_margin_end(self.config.ui.sidebar_margin)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content_area.append(scroller)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.config.ui.row_spacing)
        content.set_margin_top(self.config.ui.row_spacing)
        content.set_margin_bottom(self.config.ui.row_spacing)
        content.set_margin_start(self.config.ui.row_spacing)
        content.set_margin_end(self.config.ui.row_spacing)
        scroller.set_child(content)

        intro_label = Gtk.Label(label=localizer.text("window.help_intro"), xalign=0.0)
        intro_label.set_wrap(True)
        content.append(intro_label)

        sections = (
            ("window.help_tools_title", "window.help_tools_body"),
            ("window.help_selection_title", "window.help_selection_body"),
            ("window.help_panning_title", "window.help_panning_body"),
            ("window.help_polygon_title", "window.help_polygon_body"),
            ("window.help_function_title", "window.help_function_body"),
        )
        for title_key, body_key in sections:
            title_label = Gtk.Label(label=localizer.text(title_key), xalign=0.0)
            title_label.add_css_class("panel-title")
            content.append(title_label)

            body_label = Gtk.Label(label=localizer.text(body_key), xalign=0.0)
            body_label.set_wrap(True)
            content.append(body_label)

        dialog.show()

    def show_startup_config_issues(self) -> None:
        if not self._startup_config_issues:
            return
        localizer = get_localizer()
        message = localizer.text("window.config_issues_header") + "\n".join(
            f"{issue.path}: {issue.message}" for issue in self._startup_config_issues
        )
        self._startup_config_issues.clear()
        self._show_error_dialog(message)

    def _on_generate_clicked(self, button: Gtk.Button) -> None:
        self.controller.finalize_history_transaction()
        localizer = get_localizer()
        dialog = Gtk.FileChooserNative.new(
            localizer.text("text.save_dialog_title"),
            self,
            Gtk.FileChooserAction.SAVE,
            localizer.text("window.save_button"),
            localizer.text("window.cancel_button"),
        )
        dialog.set_modal(True)
        self._configure_save_dialog(
            dialog,
            self.controller.last_save_path,
            self.config.defaults.default_save_filename,
        )
        dialog.connect("response", self._on_save_response)
        dialog.show()

    def _on_save_config_clicked(self, button: Gtk.Button) -> None:
        self.config_popover.popdown()
        self.controller.finalize_history_transaction()
        localizer = get_localizer()
        dialog = Gtk.FileChooserNative.new(
            localizer.text("window.save_config_dialog_title"),
            self,
            Gtk.FileChooserAction.SAVE,
            localizer.text("window.save_button"),
            localizer.text("window.cancel_button"),
        )
        dialog.set_modal(True)
        self._configure_save_dialog(
            dialog,
            self.controller.last_config_save_path,
            DEFAULT_CLUSTER_CONFIGURATION_FILENAME,
        )
        dialog.connect("response", self._on_save_config_response)
        dialog.show()

    def _on_load_config_clicked(self, button: Gtk.Button) -> None:
        self.config_popover.popdown()
        self.controller.finalize_history_transaction()
        localizer = get_localizer()
        dialog = Gtk.FileChooserNative.new(
            localizer.text("window.load_config_dialog_title"),
            self,
            Gtk.FileChooserAction.OPEN,
            localizer.text("window.open_button"),
            localizer.text("window.cancel_button"),
        )
        dialog.set_modal(True)
        self._configure_open_dialog(dialog, self.controller.last_config_save_path)
        dialog.connect("response", self._on_load_config_response)
        dialog.show()

    def _on_help_clicked(self, button: Gtk.Button) -> None:
        self._show_help_dialog()

    def _configure_save_dialog(
        self,
        dialog: Gtk.FileChooserNative,
        default_path: Path | None,
        fallback_filename: str,
    ) -> None:
        if default_path is None:
            dialog.set_current_name(fallback_filename)
            return

        if default_path.is_dir():
            folder = default_path
            filename = fallback_filename
        else:
            folder = default_path.parent
            filename = default_path.name

        if folder.exists():
            dialog.set_current_folder(Gio.File.new_for_path(str(folder)))
        dialog.set_current_name(filename or fallback_filename)

    def _configure_open_dialog(self, dialog: Gtk.FileChooserNative, default_path: Path | None) -> None:
        if default_path is None:
            return

        if default_path.is_file() and default_path.exists():
            dialog.set_file(Gio.File.new_for_path(str(default_path)))
            return

        folder = default_path if default_path.is_dir() else default_path.parent
        if folder.exists():
            dialog.set_current_folder(Gio.File.new_for_path(str(folder)))

    def _on_save_response(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        try:
            if response != Gtk.ResponseType.ACCEPT:
                self.controller.clear_status(notify=True)
                return

            file = dialog.get_file()
            if file is None or file.get_path() is None:
                raise GenerationError(get_localizer().text("window.choose_local_path"))

            output_path = Path(file.get_path())
            if output_path.suffix.lower() != ".txt":
                output_path = output_path.with_suffix(".txt") if output_path.suffix else Path(f"{output_path}.txt")

            self.controller.export_to_path(output_path)
        except (GenerationError, OSError) as exc:
            self.controller.set_status(str(exc), "error")
            self._show_error_dialog(str(exc))
        finally:
            dialog.destroy()

    def _on_save_config_response(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        try:
            if response != Gtk.ResponseType.ACCEPT:
                self.controller.clear_status(notify=True)
                return

            file = dialog.get_file()
            if file is None or file.get_path() is None:
                raise GenerationError(get_localizer().text("window.choose_local_path"))

            output_path = Path(file.get_path())
            if output_path.suffix.lower() != ".json":
                output_path = output_path.with_suffix(".json") if output_path.suffix else Path(f"{output_path}.json")

            self.controller.export_cluster_configuration_to_path(output_path)
        except (GenerationError, OSError) as exc:
            self.controller.set_status(str(exc), "error")
            self._show_error_dialog(str(exc))
        finally:
            dialog.destroy()

    def _on_load_config_response(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        try:
            if response != Gtk.ResponseType.ACCEPT:
                self.controller.clear_status(notify=True)
                return

            file = dialog.get_file()
            if file is None or file.get_path() is None:
                raise GenerationError(get_localizer().text("window.choose_local_path"))

            self.canvas.cancel_polygon_draft()
            self.controller.import_cluster_configuration_from_path(Path(file.get_path()))
            self.focus_canvas()
        except (GenerationError, OSError) as exc:
            self.controller.set_status(str(exc), "error")
            self._show_error_dialog(str(exc))
        finally:
            dialog.destroy()

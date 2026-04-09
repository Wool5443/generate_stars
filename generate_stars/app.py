from __future__ import annotations

from pathlib import Path
import sys

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gio, GLib, Gtk

from .canvas import StarCanvas
from .config import AppConfig, ConfigIssue, initialize_app_config
from .generator import GenerationError, even_counts, format_points_for_export, generate_star_field, validate_state
from .models import AppState, CanvasTool, ClusterSize, DistributionMode, ShapeKind
from .preferences import load_last_save_path, save_last_save_path


class StarClusterWindow(Gtk.ApplicationWindow):
    def __init__(self, application: Gtk.Application, config: AppConfig, config_issues: list[ConfigIssue]) -> None:
        self.config = config
        self._startup_config_issues = list(config_issues)
        super().__init__(application=application, title=config.app.title)
        self.set_default_size(config.window.default_width, config.window.default_height)

        self.state = AppState()
        self._last_save_path = load_last_save_path()
        self._syncing_ui = False
        self._space_pressed = False
        self._status_text = self.config.text.ready_status
        self._status_kind = "neutral"

        self._install_key_controller()
        self._build_ui()
        self._load_initial_widget_values()
        self._refresh_ui(rebuild_manual_rows=True)

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

    def _install_key_controller(self) -> None:
        controller = Gtk.EventControllerKey.new()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
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

        content.append(self._build_cluster_section())
        content.append(self._build_distribution_section())
        content.append(self._build_parameter_section())
        content.append(self._build_trash_section())

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

        canvas_shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=self.config.ui.panel_spacing)
        canvas_shell.set_hexpand(True)
        canvas_shell.set_vexpand(True)
        canvas_shell.add_css_class("canvas-shell")
        canvas_shell.set_margin_top(self.config.ui.sidebar_margin)
        canvas_shell.set_margin_bottom(self.config.ui.sidebar_margin)
        canvas_shell.set_margin_start(self.config.ui.sidebar_margin)
        canvas_shell.set_margin_end(self.config.ui.sidebar_margin)
        root.append(canvas_shell)

        canvas_shell.append(self._build_canvas_toolbar())

        self.canvas = StarCanvas(
            self.state,
            self._is_space_pressed,
            self.config,
            self._on_canvas_state_changed,
        )
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

    def _build_canvas_toolbar(self) -> Gtk.Box:
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=self.config.ui.row_spacing)
        toolbar.add_css_class("panel")

        self.select_tool_button = Gtk.ToggleButton(label="Select (V)")
        self.circle_tool_button = Gtk.ToggleButton(label="Circle (C)")
        self.rectangle_tool_button = Gtk.ToggleButton(label="Rectangle (R)")

        self.circle_tool_button.set_group(self.select_tool_button)
        self.rectangle_tool_button.set_group(self.select_tool_button)

        self.select_tool_button.connect("toggled", self._on_tool_button_toggled, CanvasTool.SELECT)
        self.circle_tool_button.connect("toggled", self._on_tool_button_toggled, CanvasTool.CIRCLE)
        self.rectangle_tool_button.connect("toggled", self._on_tool_button_toggled, CanvasTool.RECTANGLE)

        toolbar.append(self.select_tool_button)
        toolbar.append(self.circle_tool_button)
        toolbar.append(self.rectangle_tool_button)
        return toolbar

    def _build_cluster_section(self) -> Gtk.Box:
        panel = self._build_panel("Clusters")

        self.placement_info = Gtk.Label(xalign=0.0)
        self.placement_info.set_wrap(True)
        panel.append(self.placement_info)

        self.placement_radius_spin = self._make_spin(self.config.limits.size_min, self.config.limits.size_max, 1, digits=1)
        self.placement_radius_spin.connect("value-changed", self._on_placement_radius_changed)
        self.placement_radius_row = self._build_row("Radius", self.placement_radius_spin)
        panel.append(self.placement_radius_row)

        self.placement_width_spin = self._make_spin(self.config.limits.size_min, self.config.limits.size_max, 1, digits=1)
        self.placement_width_spin.connect("value-changed", self._on_placement_width_changed)
        self.placement_width_row = self._build_row("Width", self.placement_width_spin)
        panel.append(self.placement_width_row)

        self.placement_height_spin = self._make_spin(self.config.limits.size_min, self.config.limits.size_max, 1, digits=1)
        self.placement_height_spin.connect("value-changed", self._on_placement_height_changed)
        self.placement_height_row = self._build_row("Height", self.placement_height_spin)
        panel.append(self.placement_height_row)

        panel.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self.selection_info = Gtk.Label(xalign=0.0)
        self.selection_info.set_wrap(True)
        panel.append(self.selection_info)

        self.selection_shape_combo = Gtk.ComboBoxText()
        self.selection_shape_combo.append(ShapeKind.CIRCLE.value, "Circle")
        self.selection_shape_combo.append(ShapeKind.RECTANGLE.value, "Rectangle")
        self.selection_shape_combo.connect("changed", self._on_selection_shape_changed)
        self.selection_shape_row = self._build_row("Shape", self.selection_shape_combo)
        panel.append(self.selection_shape_row)

        self.selection_radius_spin = self._make_spin(self.config.limits.size_min, self.config.limits.size_max, 1, digits=1)
        self.selection_radius_spin.connect("value-changed", self._on_selection_radius_changed)
        self.selection_radius_row = self._build_row("Radius", self.selection_radius_spin)
        panel.append(self.selection_radius_row)

        self.selection_width_spin = self._make_spin(self.config.limits.size_min, self.config.limits.size_max, 1, digits=1)
        self.selection_width_spin.connect("value-changed", self._on_selection_width_changed)
        self.selection_width_row = self._build_row("Width", self.selection_width_spin)
        panel.append(self.selection_width_row)

        self.selection_height_spin = self._make_spin(self.config.limits.size_min, self.config.limits.size_max, 1, digits=1)
        self.selection_height_spin.connect("value-changed", self._on_selection_height_changed)
        self.selection_height_row = self._build_row("Height", self.selection_height_spin)
        panel.append(self.selection_height_row)

        self.selection_size_hint = Gtk.Label(xalign=0.0)
        self.selection_size_hint.set_wrap(True)
        self.selection_size_hint.add_css_class("dim-label")
        panel.append(self.selection_size_hint)

        hint = Gtk.Label(label=self.config.text.shape_interaction_hint, xalign=0.0)
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

    def _build_parameter_section(self) -> Gtk.Box:
        panel = self._build_panel("Star Parameter")

        self.parameter_enabled_check = Gtk.CheckButton(label="Enable third parameter")
        self.parameter_enabled_check.connect("toggled", self._on_parameter_enabled_toggled)
        panel.append(self.parameter_enabled_check)

        self.parameter_fields_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=self.config.ui.cluster_section_spacing,
        )
        panel.append(self.parameter_fields_box)

        self.parameter_name_entry = Gtk.Entry()
        self.parameter_name_entry.set_width_chars(max(12, self.config.ui.decimal_spin_width_chars))
        self.parameter_name_entry.connect("changed", self._on_parameter_name_changed)
        self.parameter_fields_box.append(self._build_row("Name", self.parameter_name_entry))

        self.parameter_min_spin = self._make_spin(
            self.config.limits.star_parameter_value_min,
            self.config.limits.star_parameter_value_max,
            0.1,
            digits=3,
        )
        self.parameter_min_spin.connect("value-changed", self._on_parameter_min_changed)
        self.parameter_fields_box.append(self._build_row("Min", self.parameter_min_spin))

        self.parameter_max_spin = self._make_spin(
            self.config.limits.star_parameter_value_min,
            self.config.limits.star_parameter_value_max,
            0.1,
            digits=3,
        )
        self.parameter_max_spin.connect("value-changed", self._on_parameter_max_changed)
        self.parameter_fields_box.append(self._build_row("Max", self.parameter_max_spin))
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

        note = Gtk.Label(label=self.config.text.trash_note, xalign=0.0)
        note.set_wrap(True)
        note.add_css_class("dim-label")
        panel.append(note)
        return panel

    def _load_initial_widget_values(self) -> None:
        self._syncing_ui = True
        try:
            self.total_stars_spin.set_value(self.state.total_cluster_stars)
            self.distribution_combo.set_active_id(self.state.distribution_mode.value)
            self.deviation_spin.set_value(self.state.deviation_percent)
            self.parameter_enabled_check.set_active(self.state.star_parameter.enabled)
            self.parameter_name_entry.set_text(self.state.star_parameter.name)
            self.parameter_min_spin.set_value(self.state.star_parameter.min_value)
            self.parameter_max_spin.set_value(self.state.star_parameter.max_value)
            self.trash_count_spin.set_value(self.state.trash_star_count)
            self.trash_distance_spin.set_value(self.state.trash_min_distance)
            self._sync_tool_buttons()
        finally:
            self._syncing_ui = False

    def _selected_clusters(self):
        return self.state.selected_clusters()

    def _selected_shape_kind(self) -> ShapeKind | None:
        return self.state.selection_shape_kind()

    def _selected_reference_size(self) -> ClusterSize | None:
        selected = self._selected_clusters()
        if not selected:
            return None
        return selected[0].size

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

    def _focus_blocks_shortcuts(self) -> bool:
        widget = self.get_focus()
        while widget is not None:
            if isinstance(widget, Gtk.SpinButton):
                return False
            if isinstance(widget, Gtk.Entry) or isinstance(widget, Gtk.TextView):
                return True
            widget = widget.get_parent()
        return False

    def _sync_tool_buttons(self) -> None:
        syncing = self._syncing_ui
        self._syncing_ui = True
        try:
            self.select_tool_button.set_active(self.state.active_tool is CanvasTool.SELECT)
            self.circle_tool_button.set_active(self.state.active_tool is CanvasTool.CIRCLE)
            self.rectangle_tool_button.set_active(self.state.active_tool is CanvasTool.RECTANGLE)
        finally:
            self._syncing_ui = syncing

    def _set_active_tool(self, tool: CanvasTool) -> None:
        if self.state.active_tool is tool:
            return
        self.state.active_tool = tool
        self._sync_tool_buttons()
        self._refresh_ui()

    def _sync_total_stars_for_manual_mode(self) -> None:
        if self.state.distribution_mode is not DistributionMode.MANUAL:
            return

        self.state.total_cluster_stars = sum(cluster.manual_star_count for cluster in self.state.clusters)
        syncing_ui = self._syncing_ui
        self._syncing_ui = True
        try:
            self.total_stars_spin.set_value(self.state.total_cluster_stars)
        finally:
            self._syncing_ui = syncing_ui

    def _apply_even_manual_counts(self, total: int | None = None) -> None:
        total_value = self.state.total_cluster_stars if total is None else total
        counts = even_counts(total_value, len(self.state.clusters))
        for cluster, count in zip(self.state.clusters, counts, strict=False):
            cluster.manual_star_count = count

    def _convert_size(self, size: ClusterSize, from_shape: ShapeKind, to_shape: ShapeKind) -> ClusterSize:
        if from_shape is to_shape:
            return size.copy()
        if from_shape is ShapeKind.CIRCLE and to_shape is ShapeKind.RECTANGLE:
            span = size.radius * 2.0
            return ClusterSize(radius=span / 2.0, width=span, height=span)
        if from_shape is ShapeKind.RECTANGLE and to_shape is ShapeKind.CIRCLE:
            span = max(size.width, size.height)
            return ClusterSize(radius=span / 2.0, width=span, height=span)
        return size.copy()

    def _apply_selection_shape_change(self, target_shape: ShapeKind) -> None:
        for cluster in self._selected_clusters():
            cluster.size = self._convert_size(cluster.size, cluster.shape_kind, target_shape)
            cluster.shape_kind = target_shape

    def _apply_selection_radius(self, radius: float) -> None:
        for cluster in self._selected_clusters():
            if cluster.shape_kind is ShapeKind.CIRCLE:
                cluster.size.radius = radius
                cluster.size.width = radius * 2.0
                cluster.size.height = radius * 2.0

    def _apply_selection_width(self, width: float) -> None:
        for cluster in self._selected_clusters():
            if cluster.shape_kind is ShapeKind.RECTANGLE:
                cluster.size.width = width

    def _apply_selection_height(self, height: float) -> None:
        for cluster in self._selected_clusters():
            if cluster.shape_kind is ShapeKind.RECTANGLE:
                cluster.size.height = height

    def _on_canvas_state_changed(self, cluster_list_changed: bool) -> None:
        if self.state.distribution_mode is DistributionMode.MANUAL:
            self._sync_total_stars_for_manual_mode()
        self._clear_status()
        self._refresh_ui(rebuild_manual_rows=cluster_list_changed)

    def _refresh_ui(self, rebuild_manual_rows: bool = False) -> None:
        self._refresh_cluster_panel()

        manual_mode = self.state.distribution_mode is DistributionMode.MANUAL
        self.deviation_row.set_visible(self.state.distribution_mode is DistributionMode.DEVIATION)
        self.manual_counts_note.set_visible(manual_mode)
        self.manual_counts_box.set_visible(manual_mode)
        self.parameter_fields_box.set_sensitive(self.state.star_parameter.enabled)
        self.total_stars_spin.set_sensitive(not manual_mode)

        if rebuild_manual_rows:
            self._rebuild_manual_count_rows()

        if manual_mode:
            self._sync_total_stars_for_manual_mode()

        errors = validate_state(self.state)
        if errors:
            self.generate_button.set_sensitive(False)
            if not self.state.clusters and errors[0] == "Cluster stars require at least one cluster.":
                self._status_text = self.config.text.shape_interaction_hint
                self._status_kind = "neutral"
            else:
                self._status_text = errors[0]
                self._status_kind = "error"
        else:
            self.generate_button.set_sensitive(True)
            if self._status_kind == "error":
                self._status_text = self.config.text.ready_status
                self._status_kind = "neutral"

        self._update_status_label()
        self.canvas.queue_draw()

    def _refresh_cluster_panel(self) -> None:
        self._syncing_ui = True
        try:
            placement_shape = self.state.active_tool.shape_kind()
            if placement_shape is None:
                self.placement_info.set_text("Choose Circle or Rectangle from the toolbar to place new clusters.")
                self.placement_radius_row.set_visible(False)
                self.placement_width_row.set_visible(False)
                self.placement_height_row.set_visible(False)
            else:
                placement_size = self.state.placement_size_for_shape(placement_shape)
                self.placement_info.set_text(f"New {placement_shape.value} clusters use these placement defaults.")
                self.placement_radius_row.set_visible(placement_shape is ShapeKind.CIRCLE)
                self.placement_width_row.set_visible(placement_shape is ShapeKind.RECTANGLE)
                self.placement_height_row.set_visible(placement_shape is ShapeKind.RECTANGLE)
                self.placement_radius_spin.set_value(placement_size.radius)
                self.placement_width_spin.set_value(placement_size.width)
                self.placement_height_spin.set_value(placement_size.height)

            selected = self._selected_clusters()
            selection_shape = self._selected_shape_kind()
            self.selection_shape_row.set_visible(bool(selected))
            self.selection_shape_row.set_sensitive(bool(selected))

            if not selected:
                self.selection_info.set_text("No cluster selected.")
                self.selection_shape_combo.set_active(-1)
                self.selection_radius_row.set_visible(False)
                self.selection_width_row.set_visible(False)
                self.selection_height_row.set_visible(False)
                self.selection_size_hint.set_visible(False)
                return

            if len(selected) == 1:
                self.selection_info.set_text("1 cluster selected.")
            else:
                self.selection_info.set_text(f"{len(selected)} clusters selected.")

            if selection_shape is None:
                self.selection_shape_combo.set_active(-1)
                self.selection_radius_row.set_visible(False)
                self.selection_width_row.set_visible(False)
                self.selection_height_row.set_visible(False)
                self.selection_size_hint.set_text("Shape changes apply to all selected clusters. Size editing requires the same shape.")
                self.selection_size_hint.set_visible(True)
                return

            reference_size = self._selected_reference_size()
            self.selection_shape_combo.set_active_id(selection_shape.value)
            self.selection_radius_row.set_visible(selection_shape is ShapeKind.CIRCLE)
            self.selection_width_row.set_visible(selection_shape is ShapeKind.RECTANGLE)
            self.selection_height_row.set_visible(selection_shape is ShapeKind.RECTANGLE)
            if reference_size is not None:
                self.selection_radius_spin.set_value(reference_size.radius)
                self.selection_width_spin.set_value(reference_size.width)
                self.selection_height_spin.set_value(reference_size.height)
            if len(selected) > 1:
                self.selection_size_hint.set_text("Size changes apply to all selected clusters.")
                self.selection_size_hint.set_visible(True)
            else:
                self.selection_size_hint.set_visible(False)
        finally:
            self._syncing_ui = False

    def _rebuild_manual_count_rows(self) -> None:
        while (child := self.manual_counts_box.get_first_child()) is not None:
            self.manual_counts_box.remove(child)

        for index, cluster in enumerate(self.state.clusters):
            manual_spin = self._make_spin(self.config.limits.total_stars_min, self.config.limits.total_stars_max, 1)
            manual_spin.set_value(cluster.manual_star_count)
            manual_spin.connect("value-changed", self._on_manual_count_changed, cluster.cluster_id)
            self.manual_counts_box.append(self._build_row(f"Cluster {index + 1}", manual_spin))

    def _on_key_pressed(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        if self._focus_blocks_shortcuts():
            return False

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
        if keyval == Gdk.KEY_Escape:
            self._clear_selected_clusters()
            return True
        if keyval == Gdk.KEY_Delete:
            self._delete_selected_clusters()
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

    def _delete_selected_clusters(self) -> None:
        if not self.state.selected_cluster_ids:
            return
        self.state.delete_selected_clusters()
        if self.state.distribution_mode is DistributionMode.MANUAL:
            self._sync_total_stars_for_manual_mode()
        self._clear_status()
        self._refresh_ui(rebuild_manual_rows=True)

    def _clear_selected_clusters(self) -> None:
        if not self.state.selected_cluster_ids:
            return
        self.state.clear_selection()
        self._clear_status()
        self._refresh_ui()

    def _on_tool_button_toggled(self, button: Gtk.ToggleButton, tool: CanvasTool) -> None:
        if self._syncing_ui or not button.get_active():
            return
        self._set_active_tool(tool)

    def _on_placement_radius_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        value = spin.get_value()
        self.state.placement_circle_size.radius = value
        self.state.placement_circle_size.width = value * 2.0
        self.state.placement_circle_size.height = value * 2.0
        self._clear_status()
        self._refresh_ui()

    def _on_placement_width_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.state.placement_rectangle_size.width = spin.get_value()
        self._clear_status()
        self._refresh_ui()

    def _on_placement_height_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.state.placement_rectangle_size.height = spin.get_value()
        self._clear_status()
        self._refresh_ui()

    def _on_selection_shape_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self._syncing_ui:
            return
        active_id = combo.get_active_id()
        if not active_id or not self._selected_clusters():
            return
        self._apply_selection_shape_change(ShapeKind(active_id))
        self._clear_status()
        self._refresh_ui()

    def _on_selection_radius_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self._apply_selection_radius(spin.get_value())
        self._clear_status()
        self._refresh_ui()

    def _on_selection_width_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self._apply_selection_width(spin.get_value())
        self._clear_status()
        self._refresh_ui()

    def _on_selection_height_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self._apply_selection_height(spin.get_value())
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
            if sum(cluster.manual_star_count for cluster in self.state.clusters) != self.state.total_cluster_stars:
                self._apply_even_manual_counts()
            self._sync_total_stars_for_manual_mode()
        self._clear_status()
        self._refresh_ui(rebuild_manual_rows=True)

    def _on_deviation_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.state.deviation_percent = spin.get_value()
        self._clear_status()
        self._refresh_ui()

    def _on_parameter_enabled_toggled(self, button: Gtk.CheckButton) -> None:
        if self._syncing_ui:
            return
        self.state.star_parameter.enabled = button.get_active()
        self._clear_status()
        self._refresh_ui()

    def _on_parameter_name_changed(self, entry: Gtk.Entry) -> None:
        if self._syncing_ui:
            return
        self.state.star_parameter.name = entry.get_text()
        self._clear_status()
        self._refresh_ui()

    def _on_parameter_min_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.state.star_parameter.min_value = spin.get_value()
        self._clear_status()
        self._refresh_ui()

    def _on_parameter_max_changed(self, spin: Gtk.SpinButton) -> None:
        if self._syncing_ui:
            return
        self.state.star_parameter.max_value = spin.get_value()
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

    def _on_manual_count_changed(self, spin: Gtk.SpinButton, cluster_id: int) -> None:
        cluster = self.state.cluster_by_id(cluster_id)
        if cluster is None:
            return
        cluster.manual_star_count = spin.get_value_as_int()
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
            parameter_name = self.state.star_parameter.name.strip() if self.state.star_parameter.enabled else None
            output_path.write_text(
                format_points_for_export(generated.stars, parameter_name=parameter_name),
                encoding="utf-8",
            )
            self._last_save_path = output_path
            save_last_save_path(output_path)
            self._set_status(f"Saved {len(generated.stars)} stars to {output_path.name}.", "success")
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
            window.focus_canvas()
            window.show_startup_config_issues()
        self._config_issues.clear()


def main(argv: list[str] | None = None) -> int:
    config, config_issues = initialize_app_config(create_missing=True)
    app = StarClusterApplication(config, config_issues)
    return app.run(argv or sys.argv)

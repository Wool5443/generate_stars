from __future__ import annotations

from dataclasses import dataclass

from ..models import CanvasTool, DistributionMode, StarParameterMode


@dataclass(frozen=True, slots=True)
class ToolbarViewModel:
    active_tool: CanvasTool
    can_undo: bool
    can_redo: bool
    snap_to_integer_grid: bool
    active_tool_description: str


@dataclass(frozen=True, slots=True)
class FunctionEditorViewModel:
    visible: bool
    show_expression: bool
    expression: str
    orientation_id: str
    range_start: float
    range_end: float
    thickness: float


@dataclass(frozen=True, slots=True)
class PlacementViewModel:
    info_text: str
    show_radius: bool
    radius: float
    show_width: bool
    width: float
    show_height: bool
    height: float
    function_editor: FunctionEditorViewModel


@dataclass(frozen=True, slots=True)
class SelectionViewModel:
    info_text: str
    show_shape_selector: bool
    active_shape_id: str | None
    show_radius: bool
    radius: float
    show_width: bool
    width: float
    show_height: bool
    height: float
    show_polygon_scale: bool
    polygon_scale: float
    function_editor: FunctionEditorViewModel
    size_hint: str | None


@dataclass(frozen=True, slots=True)
class ClusterPanelViewModel:
    placement: PlacementViewModel
    selection: SelectionViewModel


@dataclass(frozen=True, slots=True)
class ManualCountRowViewModel:
    cluster_id: int
    label: str
    value: int


@dataclass(frozen=True, slots=True)
class DistributionPanelViewModel:
    total_stars: int
    distribution_mode: DistributionMode
    deviation_percent: float
    show_deviation: bool
    show_manual_counts: bool
    total_stars_sensitive: bool
    manual_note: str
    manual_rows: tuple[ManualCountRowViewModel, ...]


@dataclass(frozen=True, slots=True)
class ParameterPanelViewModel:
    enabled: bool
    name: str
    min_value: float
    max_value: float
    mode: StarParameterMode
    function_body: str
    show_random_range: bool
    show_function_body: bool
    show_function_preview: bool
    function_preview_text: str
    function_preview_is_error: bool


@dataclass(frozen=True, slots=True)
class TrashPanelViewModel:
    count: int
    min_distance: float
    max_distance: float
    min_star_distance: float
    note: str


@dataclass(frozen=True, slots=True)
class StatusViewModel:
    text: str
    kind: str


@dataclass(frozen=True, slots=True)
class WindowViewModel:
    toolbar: ToolbarViewModel
    cluster_panel: ClusterPanelViewModel
    distribution_panel: DistributionPanelViewModel
    parameter_panel: ParameterPanelViewModel
    trash_panel: TrashPanelViewModel
    status: StatusViewModel
    generate_enabled: bool

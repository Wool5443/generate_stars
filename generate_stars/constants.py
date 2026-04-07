APP_ID = "com.twenty.generate-stars"
APP_TITLE = "Star Cluster Generator"

APP_CSS = """
window {
  background: #0b0f14;
  color: #e6ebf2;
}

.sidebar {
  background: #121821;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
}

.panel {
  background: #161d27;
  border-radius: 10px;
  padding: 12px;
}

.panel-title {
  font-weight: 700;
  font-size: 13px;
  letter-spacing: 0.04em;
  color: #f4f7fb;
}

entry selection,
entry selection:focus,
spinbutton text selection,
spinbutton text selection:focus,
textview text selection,
textview text selection:focus {
  background-color: #5d88e7;
  color: #fdfefe;
}

.canvas-shell {
  background: #0b0f14;
}

.canvas {
  background: #0b0f14;
}

.generate-button {
  min-height: 42px;
  font-weight: 700;
}

.status-error {
  color: #ff8d8d;
}

.status-success {
  color: #89d7a0;
}
"""

DEFAULT_CLUSTER_RADIUS = 10.0
DEFAULT_CLUSTER_WIDTH = 10.0
DEFAULT_CLUSTER_HEIGHT = 10.0
DEFAULT_CLUSTER_COUNT = 3
DEFAULT_TOTAL_CLUSTER_STARS = 1000
DEFAULT_DEVIATION_PERCENT = 20.0
DEFAULT_TRASH_STAR_COUNT = 40
DEFAULT_TRASH_MIN_DISTANCE = 10.0
DEFAULT_VIEWPORT_SCALE = 10.0

WINDOW_DEFAULT_WIDTH = 1320
WINDOW_DEFAULT_HEIGHT = 840
CANVAS_DEFAULT_WIDTH = 900
CANVAS_DEFAULT_HEIGHT = 720
SIDEBAR_WIDTH = 360
SIDEBAR_SPACING = 12
SIDEBAR_CONTENT_SPACING = 14
SIDEBAR_FOOTER_SPACING = 8
SIDEBAR_MARGIN = 18
PANEL_SPACING = 10
ROW_SPACING = 10
CLUSTER_SECTION_SPACING = 8
SPIN_PAGE_MULTIPLIER = 10.0
INTEGER_SPIN_WIDTH_CHARS = 8
DECIMAL_SPIN_WIDTH_CHARS = 10

CLUSTER_COUNT_MIN = 0
CLUSTER_COUNT_MAX = 200
SIZE_MIN = 1
SIZE_MAX = 5000
TOTAL_STARS_MIN = 0
TOTAL_STARS_MAX = 5_000_000
DEVIATION_PERCENT_MIN = 0
DEVIATION_PERCENT_MAX = 500
TRASH_STAR_COUNT_MIN = 0
TRASH_STAR_COUNT_MAX = 5_000_000
TRASH_DISTANCE_MIN = 0
TRASH_DISTANCE_MAX = 10_000

READY_STATUS_TEXT = "Ready to generate."
RESET_POSITIONS_STATUS_TEXT = "Cluster positions reset."
DEFAULT_SAVE_FILENAME = "stars.txt"
SAVE_DIALOG_TITLE = "Save Star Coordinates"
PREFERENCES_DIR_NAME = "generate_stars"
PREFERENCES_FILENAME = "settings.json"
LAST_SAVE_PATH_KEY = "last_save_path"
SHAPE_INTERACTION_HINT = (
    "Plain LMB drags a cluster from anywhere inside it. "
    "Hold Space and drag to pan. Use the mouse wheel to zoom."
)
TRASH_NOTE_TEXT = (
    "Trash stars are sampled from an automatic bounding box around all "
    "clusters and kept outside each cluster by the requested edge distance."
)
MANUAL_COUNTS_NOTE_TEXT = "Manual cluster star counts update the total automatically."

CENTER_MARKER_RADIUS_PX = 7.0
CLUSTER_HIT_TOLERANCE_PX = 6.0
ZOOM_FACTOR = 1.12
MIN_VIEWPORT_SCALE = 0.1
MAX_VIEWPORT_SCALE = 120.0
GRID_TARGET_SPACING_PX = 90.0
AXIS_LABEL_FONT_SIZE = 11.0
AXIS_LABEL_MARGIN_PX = 8.0
AXIS_LABEL_EDGE_MARGIN_PX = 4.0
ORIGIN_MARKER_RADIUS = 3.0
GRID_LINE_WIDTH = 1.0
AXIS_LINE_WIDTH = 1.4
CLUSTER_OUTLINE_WIDTH = 2.0
HOVER_INFO_MARGIN_PX = 14.0
HOVER_INFO_PADDING_PX = 12.0
HOVER_INFO_FONT_SIZE = 12.0
HOVER_INFO_LINE_SPACING_PX = 6.0

CANVAS_BACKGROUND_COLOR = (0.06, 0.08, 0.11)
GRID_COLOR = (0.7, 0.72, 0.78, 0.08)
AXIS_COLOR = (0.85, 0.88, 0.92, 0.24)
AXIS_LABEL_COLOR = (0.86, 0.89, 0.94, 0.82)
ACTIVE_CLUSTER_OUTLINE_COLOR = (0.48, 0.72, 0.98, 0.9)
INACTIVE_CLUSTER_OUTLINE_COLOR = (0.87, 0.89, 0.94, 0.72)
ACTIVE_CLUSTER_MARKER_COLOR = (0.48, 0.72, 0.98, 0.95)
INACTIVE_CLUSTER_MARKER_COLOR = (0.96, 0.98, 1.0, 0.95)
HOVER_INFO_BACKGROUND_COLOR = (0.08, 0.11, 0.15, 0.88)
HOVER_INFO_TITLE_COLOR = (0.48, 0.72, 0.98, 0.98)
HOVER_INFO_TEXT_COLOR = (0.95, 0.97, 1.0, 0.94)

LAYOUT_RING_PADDING = 10.0
LAYOUT_ORIGIN_PADDING = 5.0
EMPTY_CLUSTER_BOUNDS_LIMIT = 150.0
TRASH_BOUNDS_PADDING_MIN = 20.0
TRASH_BOUNDS_PADDING_EXTRA = 10.0
TRASH_PLACEMENT_ATTEMPTS_MIN = 5_000
TRASH_PLACEMENT_ATTEMPTS_PER_STAR = 2_000
EXPORT_COORDINATE_PRECISION = 6

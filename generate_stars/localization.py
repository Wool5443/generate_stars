from __future__ import annotations

from dataclasses import replace
import locale
import os

from .config import AppConfig
from .models import DistributionMode, FunctionOrientation, ShapeKind


ENGLISH_DEFAULT_TEXTS = {
    "app.title": "Star Cluster Generator",
    "defaults.star_parameter_name": "Value",
    "text.ready_status": "Ready to generate.",
    "text.reset_positions_status": "Cluster positions reset.",
    "text.save_dialog_title": "Save Star Coordinates",
    "text.shape_interaction_hint": "Use the toolbar or V/C/R/P/F to switch tools. Click to place circles, rectangles, and function clusters. Polygon mode adds vertices with each click; click the first vertex to finish and press Escape to cancel the draft. Drag empty space to box-select, Ctrl+click toggles selection, Delete removes the current selection, and use either middle mouse drag or Space+LMB to pan.",
    "text.select_tool_description": "Select tool: click a cluster to select it, Ctrl+click to toggle it, drag empty space to box-select, drag selected clusters to move them, and use either middle mouse drag or Space+LMB to pan.",
    "text.circle_tool_description": "Circle tool: click on the canvas to place a circle cluster using the current placement radius. Switch back to Select to move or edit placed circles.",
    "text.rectangle_tool_description": "Rectangle tool: click on the canvas to place a rectangle cluster using the current placement width and height. Switch back to Select to move or edit placed rectangles.",
    "text.polygon_tool_description": "Polygon tool: click to add polygon vertices, click the first vertex to finish the polygon, and press Escape to cancel the draft. Switch to Select to move the polygon or drag its vertices.",
    "text.function_tool_description": "Function tool: click on the canvas to place a function-shaped cluster using the current formula, range, orientation, and thickness. Switch back to Select to move or edit placed function clusters.",
    "text.trash_note": "Trash stars are sampled from an automatic bounding box around all clusters and kept outside each cluster by the requested edge distance.",
    "text.manual_counts_note": "Manual cluster star counts update the total automatically.",
}


TRANSLATIONS = {
    "en": {
        **ENGLISH_DEFAULT_TEXTS,
        "ui.toolbar.undo": "Undo",
        "ui.toolbar.redo": "Redo",
        "ui.toolbar.snap": "Snap",
        "ui.tool.select": "Select",
        "ui.tool.circle": "Circle",
        "ui.tool.rectangle": "Rectangle",
        "ui.tool.polygon": "Polygon",
        "ui.tool.function": "Function",
        "ui.help": "Help",
        "ui.config": "Config",
        "ui.generate": "Generate",
        "ui.save_configuration": "Save Configuration",
        "ui.load_configuration": "Load Configuration",
        "ui.panel.clusters": "Clusters",
        "ui.panel.stars": "Stars",
        "ui.panel.star_parameter": "Star Parameter",
        "ui.panel.trash_stars": "Trash Stars",
        "ui.checkbox.enable_third_parameter": "Enable third parameter",
        "ui.label.name": "Name",
        "ui.label.min": "Min",
        "ui.label.max": "Max",
        "ui.label.radius": "Radius",
        "ui.label.width": "Width",
        "ui.label.height": "Height",
        "ui.label.shape": "Shape",
        "ui.label.scale": "Scale %",
        "ui.label.orientation": "Orientation",
        "ui.label.expression": "Expression",
        "ui.label.range_start": "Range start",
        "ui.label.range_end": "Range end",
        "ui.label.thickness": "Thickness",
        "ui.label.total_cluster_stars": "Total cluster stars",
        "ui.label.distribution": "Distribution",
        "ui.label.deviation_percent": "Deviation %",
        "ui.label.trash_star_count": "Trash star count",
        "ui.label.min_edge_distance": "Min edge distance",
        "ui.option.equal": "Equal",
        "ui.option.deviation": "Deviation",
        "ui.option.manual": "Manual",
        "ui.option.y_of_x": "y = f(x)",
        "ui.option.x_of_y": "x = f(y)",
        "shape.circle": "Circle",
        "shape.rectangle": "Rectangle",
        "shape.polygon": "Polygon",
        "shape.function": "Function",
        "controller.placement.none": "Choose Circle, Rectangle, Polygon, or Function from the toolbar to place new clusters.",
        "controller.placement.polygon": "Click to add polygon vertices. Click the first vertex to finish, and press Escape to cancel the draft.",
        "controller.placement.shape_defaults": "New {shape_name} clusters use these placement defaults.",
        "controller.selection.none": "No cluster selected.",
        "controller.selection.one": "1 cluster selected.",
        "controller.selection.many": "{count} clusters selected.",
        "controller.selection.mixed_shape_hint": "Shape changes apply to all selected clusters. Size editing requires the same shape.",
        "controller.selection.polygon_single_hint": "Drag polygon vertices on the canvas to edit the shape. Scale applies around the polygon center.",
        "controller.selection.polygon_multi_hint": "Scale applies to all selected polygons around their own centers.",
        "controller.selection.function_single_hint": "Edit the function formula, orientation, range, and thickness here. Function clusters cannot be converted to other shapes.",
        "controller.selection.function_multi_hint": "Shared orientation, range, and thickness changes apply to all selected function clusters. Formula editing is available only for a single selection.",
        "controller.selection.function_mixed_hint": "Function clusters cannot be shape-converted. Shape-specific editing is hidden for mixed selections that include function clusters.",
        "controller.selection.multi_size_hint": "Size changes apply to all selected clusters.",
        "controller.manual_cluster_label": "Cluster {index}",
        "status.copied_clusters": "Copied {count} clusters.",
        "status.nothing_selected_to_copy": "Nothing selected to copy.",
        "status.nothing_to_paste": "Nothing to paste.",
        "status.pasted_clusters": "Pasted {count} clusters.",
        "status.saved": "Saved {count} stars to {filename}.",
        "status.configuration_saved": "Saved cluster configuration to {filename}.",
        "status.configuration_loaded": "Loaded {count} clusters from {filename}.",
        "window.config_issues_header": "Some config values were ignored and defaults were used:\n\n",
        "window.choose_local_path": "Please choose a local file path.",
        "window.save_config_dialog_title": "Save Cluster Configuration",
        "window.load_config_dialog_title": "Load Cluster Configuration",
        "window.help_dialog_title": "Help",
        "window.close_button": "_Close",
        "window.help_intro": "Use these controls to place and edit clusters quickly.",
        "window.help_tools_title": "Tools and shortcuts",
        "window.help_tools_body": "Use V for Select, C for Circle, R for Rectangle, P for Polygon, and F for Function. You can also click tool buttons in the toolbar.",
        "window.help_selection_title": "Selection and movement",
        "window.help_selection_body": "Click a cluster to select it, Ctrl+click to toggle selection, drag empty space to box-select, and drag selected clusters to move them.",
        "window.help_panning_title": "Panning",
        "window.help_panning_body": "Pan with Space+LMB or by dragging with the middle mouse button.",
        "window.help_polygon_title": "Polygon tool",
        "window.help_polygon_body": "Each click adds a vertex. Finish by clicking the first vertex. Press Escape to cancel the draft polygon.",
        "window.help_function_title": "Function tool",
        "window.help_function_body": "Click the canvas to place a function cluster using the current expression, orientation (y = f(x) or x = f(y)), range start/end, and thickness. Switch to Select to move the cluster or edit function settings in the left panel.",
        "window.open_button": "_Open",
        "window.save_button": "_Save",
        "window.cancel_button": "_Cancel",
        "canvas.hover.cluster": "Cluster {index}",
        "canvas.hover.center": "Center: {x}, {y}",
        "canvas.hover.radius": "Radius: {value}",
        "canvas.hover.width": "Width: {value}",
        "canvas.hover.height": "Height: {value}",
        "canvas.hover.vertices": "Vertices: {count}",
        "canvas.hover.orientation": "Orientation: {value}",
        "canvas.hover.range": "Range: {start} .. {end}",
        "canvas.hover.thickness": "Thickness: {value}",
        "canvas.hover.stars": "Stars: {count}",
        "canvas.hover.randomized": "Stars: randomized",
        "error.circle_placement": "Circle placement",
        "error.rectangle_placement": "Rectangle placement",
        "error.function_placement": "Function placement",
        "error.cluster": "Cluster {index}",
        "error.radius_positive": "{label} radius must be greater than zero.",
        "error.width_positive": "{label} width must be greater than zero.",
        "error.height_positive": "{label} height must be greater than zero.",
        "error.cluster_total_negative": "Total cluster stars cannot be negative.",
        "error.trash_count_negative": "Trash star count cannot be negative.",
        "error.trash_distance_negative": "Trash star minimum distance cannot be negative.",
        "error.cluster_required": "Cluster stars require at least one cluster.",
        "error.deviation_negative": "Deviation percent cannot be negative.",
        "error.parameter_name_empty": "Star parameter name cannot be empty.",
        "error.parameter_range_invalid": "Star parameter max must be greater than or equal to min.",
        "error.manual_counts_negative": "Manual cluster counts cannot be negative.",
        "error.manual_counts_total": "Manual cluster counts must sum to the total cluster stars.",
        "error.manual_counts_sync": "Manual counts are out of sync with the cluster count.",
        "error.trash_placement_failed": "Could not place all trash stars with the requested minimum distance. Reduce the trash-star count or the minimum distance.",
        "error.parameter_export_requires_value": "Parameter export requires a value for every star.",
        "error.configuration_invalid": "Cluster configuration file is invalid.",
        "error.polygon_vertex_count": "Polygon must have at least 3 distinct vertices.",
        "error.polygon_simple": "Polygon must be simple and non-self-intersecting.",
        "error.function_expression_invalid": "Function expression is invalid.",
        "error.function_range_invalid": "Function range end must be greater than range start.",
        "error.function_thickness_positive": "Function thickness must be greater than zero.",
        "error.function_geometry_invalid": "Function band geometry is invalid. Reduce the thickness or change the range/formula.",
    },
    "ru": {
        "app.title": "Генератор звездных кластеров",
        "defaults.star_parameter_name": "Значение",
        "text.ready_status": "Готово к генерации.",
        "text.reset_positions_status": "Позиции кластеров сброшены.",
        "text.save_dialog_title": "Сохранить координаты звезд",
        "text.shape_interaction_hint": "Используйте панель инструментов или клавиши V/C/R/P/F для выбора инструмента. Круги, прямоугольники и функциональные кластеры ставятся щелчком. В режиме полигона каждый щелчок добавляет вершину; щелкните по первой вершине, чтобы завершить полигон, и нажмите Escape для отмены. Протягивание по пустому месту создает рамку выделения, Ctrl+щелчок переключает выделение, Delete удаляет текущее выделение, а панорамирование выполняется либо средней кнопкой мыши, либо Space+ЛКМ.",
        "text.select_tool_description": "Инструмент выделения: щелкните по кластеру, чтобы выделить его, Ctrl+щелчок переключает выделение, протягивание по пустому месту выделяет рамкой, перетаскивание выделенных кластеров перемещает их, а панорамирование выполняется либо средней кнопкой мыши, либо Space+ЛКМ.",
        "text.circle_tool_description": "Инструмент круга: щелкните по холсту, чтобы поставить круглый кластер с текущим радиусом размещения. Вернитесь к выделению, чтобы перемещать или редактировать созданные круги.",
        "text.rectangle_tool_description": "Инструмент прямоугольника: щелкните по холсту, чтобы поставить прямоугольный кластер с текущими шириной и высотой размещения. Вернитесь к выделению, чтобы перемещать или редактировать созданные прямоугольники.",
        "text.polygon_tool_description": "Инструмент полигона: щелчки добавляют вершины, щелчок по первой вершине завершает полигон, а Escape отменяет черновик. Переключитесь на выделение, чтобы перемещать полигон или тянуть его вершины.",
        "text.function_tool_description": "Инструмент функции: щелкните по холсту, чтобы поставить кластер в форме функции с текущей формулой, диапазоном, ориентацией и толщиной. Вернитесь к выделению, чтобы перемещать или редактировать созданные функциональные кластеры.",
        "text.trash_note": "Мусорные звезды выбираются из автоматической ограничивающей области вокруг всех кластеров и остаются вне каждого кластера на заданном расстоянии от края.",
        "text.manual_counts_note": "Ручные значения звезд по кластерам автоматически обновляют общий итог.",
        "ui.toolbar.undo": "Отменить",
        "ui.toolbar.redo": "Повторить",
        "ui.toolbar.snap": "Привязка",
        "ui.tool.select": "Выделение",
        "ui.tool.circle": "Круг",
        "ui.tool.rectangle": "Прямоугольник",
        "ui.tool.polygon": "Полигон",
        "ui.tool.function": "Функция",
        "ui.help": "Справка",
        "ui.config": "Конфиг",
        "ui.generate": "Сгенерировать",
        "ui.save_configuration": "Сохранить конфигурацию",
        "ui.load_configuration": "Загрузить конфигурацию",
        "ui.panel.clusters": "Кластеры",
        "ui.panel.stars": "Звезды",
        "ui.panel.star_parameter": "Параметр звезды",
        "ui.panel.trash_stars": "Мусорные звезды",
        "ui.checkbox.enable_third_parameter": "Включить третий параметр",
        "ui.label.name": "Имя",
        "ui.label.min": "Мин",
        "ui.label.max": "Макс",
        "ui.label.radius": "Радиус",
        "ui.label.width": "Ширина",
        "ui.label.height": "Высота",
        "ui.label.shape": "Форма",
        "ui.label.scale": "Масштаб %",
        "ui.label.orientation": "Ориентация",
        "ui.label.expression": "Выражение",
        "ui.label.range_start": "Начало диапазона",
        "ui.label.range_end": "Конец диапазона",
        "ui.label.thickness": "Толщина",
        "ui.label.total_cluster_stars": "Всего звезд в кластерах",
        "ui.label.distribution": "Распределение",
        "ui.label.deviation_percent": "Отклонение %",
        "ui.label.trash_star_count": "Число мусорных звезд",
        "ui.label.min_edge_distance": "Мин. расстояние от края",
        "ui.option.equal": "Равномерно",
        "ui.option.deviation": "С отклонением",
        "ui.option.manual": "Вручную",
        "ui.option.y_of_x": "y = f(x)",
        "ui.option.x_of_y": "x = f(y)",
        "shape.circle": "Круг",
        "shape.rectangle": "Прямоугольник",
        "shape.polygon": "Полигон",
        "shape.function": "Функция",
        "controller.placement.none": "Выберите Круг, Прямоугольник, Полигон или Функцию на панели инструментов, чтобы размещать новые кластеры.",
        "controller.placement.polygon": "Щелчки добавляют вершины полигона. Щелкните по первой вершине, чтобы завершить фигуру, и нажмите Escape для отмены черновика.",
        "controller.placement.shape_defaults": "Новые кластеры формы «{shape_name}» используют эти параметры размещения.",
        "controller.selection.none": "Ни один кластер не выбран.",
        "controller.selection.one": "Выбран 1 кластер.",
        "controller.selection.many": "Выбрано кластеров: {count}.",
        "controller.selection.mixed_shape_hint": "Изменение формы применяется ко всем выделенным кластерам. Изменение размеров доступно только при одинаковой форме.",
        "controller.selection.polygon_single_hint": "Перетаскивайте вершины полигона на холсте, чтобы менять форму. Масштаб применяется относительно центра полигона.",
        "controller.selection.polygon_multi_hint": "Масштаб применяется ко всем выбранным полигонам относительно их собственных центров.",
        "controller.selection.function_single_hint": "Здесь можно менять формулу, ориентацию, диапазон и толщину функции. Функциональные кластеры нельзя преобразовать в другие формы.",
        "controller.selection.function_multi_hint": "Общие изменения ориентации, диапазона и толщины применяются ко всем выбранным функциональным кластерам. Формулу можно редактировать только при выборе одного кластера.",
        "controller.selection.function_mixed_hint": "Функциональные кластеры нельзя преобразовывать по форме. Для смешанного выделения с функциями специальные настройки скрыты.",
        "controller.selection.multi_size_hint": "Изменение размера применяется ко всем выделенным кластерам.",
        "controller.manual_cluster_label": "Кластер {index}",
        "status.copied_clusters": "Скопировано кластеров: {count}.",
        "status.nothing_selected_to_copy": "Нечего копировать.",
        "status.nothing_to_paste": "Нечего вставлять.",
        "status.pasted_clusters": "Вставлено кластеров: {count}.",
        "status.saved": "Сохранено {count} звезд в файл {filename}.",
        "status.configuration_saved": "Конфигурация кластеров сохранена в файл {filename}.",
        "status.configuration_loaded": "Загружено кластеров: {count} из файла {filename}.",
        "window.config_issues_header": "Некоторые значения конфигурации были проигнорированы, и вместо них использованы значения по умолчанию:\n\n",
        "window.choose_local_path": "Пожалуйста, выберите локальный путь к файлу.",
        "window.save_config_dialog_title": "Сохранить конфигурацию кластеров",
        "window.load_config_dialog_title": "Загрузить конфигурацию кластеров",
        "window.help_dialog_title": "Справка",
        "window.close_button": "_Закрыть",
        "window.help_intro": "Используйте эти элементы, чтобы быстро размещать и редактировать кластеры.",
        "window.help_tools_title": "Инструменты и горячие клавиши",
        "window.help_tools_body": "V - Выделение, C - Круг, R - Прямоугольник, P - Полигон, F - Функция. Также можно выбирать инструменты кнопками на панели.",
        "window.help_selection_title": "Выделение и перемещение",
        "window.help_selection_body": "Щелчок по кластеру выделяет его, Ctrl+щелчок переключает выделение, протягивание по пустому месту делает рамку выделения, перетаскивание выделенных кластеров перемещает их.",
        "window.help_panning_title": "Панорамирование",
        "window.help_panning_body": "Панорамируйте через Space+ЛКМ или перетаскиванием средней кнопкой мыши.",
        "window.help_polygon_title": "Инструмент полигона",
        "window.help_polygon_body": "Каждый щелчок добавляет вершину. Чтобы завершить, щелкните по первой вершине. Escape отменяет черновик полигона.",
        "window.help_function_title": "Инструмент функции",
        "window.help_function_body": "Щелкните по холсту, чтобы поставить функциональный кластер с текущими выражением, ориентацией (y = f(x) или x = f(y)), диапазоном и толщиной. Переключитесь на Выделение, чтобы перемещать кластер или редактировать параметры функции слева.",
        "window.open_button": "_Открыть",
        "window.save_button": "_Сохранить",
        "window.cancel_button": "_Отмена",
        "canvas.hover.cluster": "Кластер {index}",
        "canvas.hover.center": "Центр: {x}, {y}",
        "canvas.hover.radius": "Радиус: {value}",
        "canvas.hover.width": "Ширина: {value}",
        "canvas.hover.height": "Высота: {value}",
        "canvas.hover.vertices": "Вершины: {count}",
        "canvas.hover.orientation": "Ориентация: {value}",
        "canvas.hover.range": "Диапазон: {start} .. {end}",
        "canvas.hover.thickness": "Толщина: {value}",
        "canvas.hover.stars": "Звезд: {count}",
        "canvas.hover.randomized": "Звезды: случайно",
        "error.circle_placement": "Размещение круга",
        "error.rectangle_placement": "Размещение прямоугольника",
        "error.function_placement": "Размещение функции",
        "error.cluster": "Кластер {index}",
        "error.radius_positive": "Радиус для «{label}» должен быть больше нуля.",
        "error.width_positive": "Ширина для «{label}» должна быть больше нуля.",
        "error.height_positive": "Высота для «{label}» должна быть больше нуля.",
        "error.cluster_total_negative": "Общее число звезд в кластерах не может быть отрицательным.",
        "error.trash_count_negative": "Число мусорных звезд не может быть отрицательным.",
        "error.trash_distance_negative": "Минимальное расстояние мусорных звезд не может быть отрицательным.",
        "error.cluster_required": "Для звезд в кластерах нужен хотя бы один кластер.",
        "error.deviation_negative": "Процент отклонения не может быть отрицательным.",
        "error.parameter_name_empty": "Имя параметра звезды не может быть пустым.",
        "error.parameter_range_invalid": "Максимум параметра звезды должен быть больше или равен минимуму.",
        "error.manual_counts_negative": "Ручные количества звезд по кластерам не могут быть отрицательными.",
        "error.manual_counts_total": "Сумма ручных количеств звезд по кластерам должна совпадать с общим числом звезд в кластерах.",
        "error.manual_counts_sync": "Ручные количества звезд не соответствуют числу кластеров.",
        "error.trash_placement_failed": "Не удалось разместить все мусорные звезды с заданным минимальным расстоянием. Уменьшите число мусорных звезд или минимальное расстояние.",
        "error.parameter_export_requires_value": "Для экспорта параметра значение должно быть задано для каждой звезды.",
        "error.configuration_invalid": "Файл конфигурации кластеров имеет неверный формат.",
        "error.polygon_vertex_count": "Полигон должен содержать не менее 3 различных вершин.",
        "error.polygon_simple": "Полигон должен быть простым и не самопересекающимся.",
        "error.function_expression_invalid": "Выражение функции некорректно.",
        "error.function_range_invalid": "Конец диапазона функции должен быть больше начала.",
        "error.function_thickness_positive": "Толщина функции должна быть больше нуля.",
        "error.function_geometry_invalid": "Геометрия полосы функции некорректна. Уменьшите толщину или измените диапазон или формулу.",
    },
}

_CACHED_LOCALIZER: Localizer | None = None


class Localizer:
    def __init__(self, language: str) -> None:
        self.language = language if language in TRANSLATIONS else "en"

    def text(self, key: str, **kwargs) -> str:
        template = TRANSLATIONS.get(self.language, {}).get(key)
        if template is None:
            template = TRANSLATIONS["en"].get(key, key)
        return template.format(**kwargs) if kwargs else template

    def shape_name(self, shape_kind: ShapeKind) -> str:
        return self.text(f"shape.{shape_kind.value}")

    def distribution_name(self, distribution_mode: DistributionMode) -> str:
        return self.text(f"ui.option.{distribution_mode.value}")

    def function_orientation_name(self, orientation: FunctionOrientation) -> str:
        return self.text(f"ui.option.{orientation.value}")

    def localize_config(self, config: AppConfig) -> AppConfig:
        app = replace(
            config.app,
            title=self._localize_if_default("app.title", config.app.title),
        )
        defaults = replace(
            config.defaults,
            star_parameter_name=self._localize_if_default(
                "defaults.star_parameter_name",
                config.defaults.star_parameter_name,
            ),
        )
        text = replace(
            config.text,
            ready_status=self._localize_if_default("text.ready_status", config.text.ready_status),
            reset_positions_status=self._localize_if_default("text.reset_positions_status", config.text.reset_positions_status),
            save_dialog_title=self._localize_if_default("text.save_dialog_title", config.text.save_dialog_title),
            shape_interaction_hint=self._localize_if_default("text.shape_interaction_hint", config.text.shape_interaction_hint),
            select_tool_description=self._localize_if_default("text.select_tool_description", config.text.select_tool_description),
            circle_tool_description=self._localize_if_default("text.circle_tool_description", config.text.circle_tool_description),
            rectangle_tool_description=self._localize_if_default("text.rectangle_tool_description", config.text.rectangle_tool_description),
            polygon_tool_description=self._localize_if_default("text.polygon_tool_description", config.text.polygon_tool_description),
            function_tool_description=self._localize_if_default("text.function_tool_description", config.text.function_tool_description),
            trash_note=self._localize_if_default("text.trash_note", config.text.trash_note),
            manual_counts_note=self._localize_if_default("text.manual_counts_note", config.text.manual_counts_note),
        )
        return replace(config, app=app, defaults=defaults, text=text)

    def _localize_if_default(self, key: str, value: str) -> str:
        if self.language == "en":
            return value
        if value == ENGLISH_DEFAULT_TEXTS.get(key):
            return self.text(key)
        return value


def _normalize_language(value: str | None) -> str:
    if not value:
        return "en"
    lowered = value.lower()
    if lowered.startswith("ru"):
        return "ru"
    return "en"


def _detect_system_language() -> str:
    for variable in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        raw = os.environ.get(variable)
        if raw:
            return _normalize_language(raw.split(":")[0])

    try:
        system_locale = locale.getlocale(locale.LC_MESSAGES)[0]
    except Exception:
        system_locale = None

    if not system_locale:
        try:
            system_locale = locale.getlocale()[0]
        except Exception:
            system_locale = None

    return _normalize_language(system_locale)


def initialize_localizer(config: AppConfig) -> AppConfig:
    global _CACHED_LOCALIZER
    requested = config.app.language.strip().lower()
    language = _detect_system_language() if requested == "auto" else _normalize_language(requested)
    _CACHED_LOCALIZER = Localizer(language)
    return _CACHED_LOCALIZER.localize_config(config)


def get_localizer() -> Localizer:
    global _CACHED_LOCALIZER
    if _CACHED_LOCALIZER is None:
        _CACHED_LOCALIZER = Localizer("en")
    return _CACHED_LOCALIZER

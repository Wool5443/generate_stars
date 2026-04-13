from __future__ import annotations

from dataclasses import replace
import tempfile
import unittest
from pathlib import Path

from generate_stars.config import load_app_config, set_app_config
from generate_stars.controllers.editor_controller import EditorController
from generate_stars.generator import validate_state
from generate_stars.localization import get_localizer, initialize_localizer
from generate_stars.models import AppState


class LocalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        config_path = Path(self.temp_dir.name) / "config.toml"
        self.raw_config, _issues = load_app_config(config_path, create_missing=True)
        self.config = self.raw_config

    def tearDown(self) -> None:
        english = replace(self.raw_config, app=replace(self.raw_config.app, language="en"))
        localized = initialize_localizer(english)
        set_app_config(localized, [])
        self.temp_dir.cleanup()

    def _activate_language(self, language: str) -> None:
        config = replace(self.raw_config, app=replace(self.raw_config.app, language=language))
        localized = initialize_localizer(config)
        set_app_config(localized, [])
        self.config = localized

    def test_russian_localizes_default_config_texts(self) -> None:
        self._activate_language("ru")

        self.assertEqual(self.config.app.title, "Генератор звездных кластеров")
        self.assertEqual(self.config.defaults.star_parameter_name, "Значение")
        self.assertEqual(get_localizer().text("text.ready_status"), "Готово к генерации.")

    def test_controller_view_model_uses_russian_strings(self) -> None:
        self._activate_language("ru")

        controller = EditorController(self.config)
        view_model = controller.build_window_view_model()

        self.assertEqual(view_model.cluster_panel.selection.info_text, "Ни один кластер не выбран.")
        self.assertEqual(view_model.toolbar.active_tool_description, get_localizer().text("text.select_tool_description"))

    def test_validation_errors_switch_to_russian(self) -> None:
        self._activate_language("ru")

        state = AppState(total_cluster_stars=1)

        self.assertIn("Для звезд в кластерах нужен хотя бы один кластер.", validate_state(state))
        self.assertEqual(get_localizer().text("error.polygon_simple"), "Полигон должен быть простым и не самопересекающимся.")
        self.assertEqual(get_localizer().text("window.help_function_title"), "Инструмент функции")
        self.assertEqual(get_localizer().text("ui.option.parameter_function"), "Функция")
        self.assertEqual(get_localizer().text("ui.label.parameter_preview"), "Предпросмотр:")
        self.assertEqual(get_localizer().text("ui.label.max_edge_distance"), "Макс. расстояние от края")
        self.assertEqual(
            get_localizer().text("error.trash_distance_range_invalid"),
            "Максимальное расстояние мусорных звезд должно быть больше или равно минимальному.",
        )


if __name__ == "__main__":
    unittest.main()

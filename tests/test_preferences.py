from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from generate_stars.preferences import load_last_save_path, save_last_save_path


class PreferenceTests(unittest.TestCase):
    def test_last_save_path_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.json"
            expected = Path(temp_dir) / "exports" / "stars.txt"

            save_last_save_path(expected, settings_path)

            self.assertEqual(load_last_save_path(settings_path), expected)

    def test_invalid_preferences_payload_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.json"
            settings_path.write_text("{not json", encoding="utf-8")

            self.assertIsNone(load_last_save_path(settings_path))

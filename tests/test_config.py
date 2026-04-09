from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from generate_stars.config import load_app_config, packaged_default_config_text


class ConfigTests(unittest.TestCase):
    def test_missing_runtime_config_is_created_from_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"

            config, issues = load_app_config(config_path, create_missing=True)

            self.assertTrue(config_path.exists())
            self.assertEqual(config.defaults.cluster_radius, 10.0)
            self.assertEqual(config.defaults.cluster_width, 10.0)
            self.assertEqual(config.defaults.cluster_height, 10.0)
            self.assertEqual(config.defaults.function_expression, "0")
            self.assertEqual(config.defaults.function_orientation, "y_of_x")
            self.assertEqual(config.defaults.function_range_start, -10.0)
            self.assertEqual(config.defaults.function_range_end, 10.0)
            self.assertEqual(config.defaults.function_thickness, 4.0)
            self.assertFalse(config.defaults.star_parameter_enabled)
            self.assertEqual(config.defaults.star_parameter_name, "Value")
            self.assertEqual(config.defaults.star_parameter_min_value, 0.0)
            self.assertEqual(config.defaults.star_parameter_max_value, 1.0)
            self.assertEqual(issues, [])

    def test_partial_runtime_config_merges_with_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                (
                    "[defaults]\n"
                    "cluster_count = 7\n"
                    "\n"
                    "[canvas]\n"
                    "zoom_factor = 1.5\n"
                ),
                encoding="utf-8",
            )

            config, issues = load_app_config(config_path)

            self.assertEqual(config.defaults.cluster_count, 7)
            self.assertEqual(config.canvas.zoom_factor, 1.5)
            self.assertEqual(config.defaults.cluster_radius, 10.0)
            self.assertEqual(issues, [])

    def test_invalid_and_unknown_values_fall_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                (
                    "[defaults]\n"
                    'cluster_radius = "bad"\n'
                    'star_parameter_enabled = "bad"\n'
                    "star_parameter_min_value = 3.0\n"
                    "star_parameter_max_value = 1.0\n"
                    "unknown = 1\n"
                    "\n"
                    "[colors]\n"
                    "grid = [2.0, 0.1, 0.1, 0.5]\n"
                ),
                encoding="utf-8",
            )

            config, issues = load_app_config(config_path)
            issue_paths = {issue.path for issue in issues}

            self.assertEqual(config.defaults.cluster_radius, 10.0)
            self.assertFalse(config.defaults.star_parameter_enabled)
            self.assertEqual(config.defaults.star_parameter_min_value, 0.0)
            self.assertEqual(config.defaults.star_parameter_max_value, 1.0)
            self.assertEqual(config.colors.grid, (0.7, 0.72, 0.78, 0.08))
            self.assertIn("defaults.cluster_radius", issue_paths)
            self.assertIn("defaults.star_parameter_enabled", issue_paths)
            self.assertIn("defaults.star_parameter_max_value", issue_paths)
            self.assertIn("defaults.unknown", issue_paths)
            self.assertIn("colors.grid", issue_paths)

    def test_packaged_default_config_is_available(self) -> None:
        text = packaged_default_config_text()
        self.assertIn('application_id = "com.twenty.generate-stars"', text)

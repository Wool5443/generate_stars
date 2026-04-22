from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from generate_stars.project_state import (
    PROJECT_STATE_FILENAME,
    LoadedProjectState,
    load_project_state,
    save_project_state,
)


class ProjectStateTests(unittest.TestCase):
    def test_project_state_round_trips_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            config_path = (project_dir / "scene.gstars.json").resolve()
            export_path = (project_dir / "exports" / "stars.txt").resolve()

            save_project_state(
                project_dir,
                last_active_config=config_path,
                per_config_last_export_path={config_path: export_path},
            )

            loaded = load_project_state(project_dir)
            self.assertEqual(loaded.last_active_config, config_path)
            self.assertEqual(loaded.per_config_last_export_path, {config_path: export_path})

    def test_invalid_project_state_payload_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            state_path = project_dir / PROJECT_STATE_FILENAME
            state_path.write_text("{bad json", encoding="utf-8")

            loaded = load_project_state(project_dir)
            self.assertEqual(loaded, LoadedProjectState())


if __name__ == "__main__":
    unittest.main()

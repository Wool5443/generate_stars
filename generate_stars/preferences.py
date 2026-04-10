from __future__ import annotations

import json
from pathlib import Path

from gi.repository import GLib

from .config import LAST_CONFIG_SAVE_PATH_KEY, LAST_SAVE_PATH_KEY, PREFERENCES_DIR_NAME, PREFERENCES_FILENAME


def preferences_path() -> Path:
    return Path(GLib.get_user_config_dir()) / PREFERENCES_DIR_NAME / PREFERENCES_FILENAME


def _load_path_preference(key: str, path: Path | None = None) -> Path | None:
    source_path = path or preferences_path()
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None

    raw_path = payload.get(key)
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    return Path(raw_path).expanduser()


def _save_path_preference(key: str, value: Path, path: Path | None = None) -> None:
    target_path = path or preferences_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        payload = json.loads(target_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            payload = {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        payload = {}
    payload[key] = str(value)
    target_path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def load_last_save_path(path: Path | None = None) -> Path | None:
    return _load_path_preference(LAST_SAVE_PATH_KEY, path)


def save_last_save_path(last_save_path: Path, path: Path | None = None) -> None:
    _save_path_preference(LAST_SAVE_PATH_KEY, last_save_path, path)


def load_last_config_save_path(path: Path | None = None) -> Path | None:
    return _load_path_preference(LAST_CONFIG_SAVE_PATH_KEY, path)


def save_last_config_save_path(last_config_save_path: Path, path: Path | None = None) -> None:
    _save_path_preference(LAST_CONFIG_SAVE_PATH_KEY, last_config_save_path, path)

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_STATE_FORMAT = "generate_stars_project_state"
PROJECT_STATE_VERSION = 1
PROJECT_STATE_FILENAME = ".generate-stars.project.json"
PROJECT_CONFIG_EXTENSION = ".gstars.json"


@dataclass(slots=True)
class LoadedProjectState:
    last_active_config: Path | None = None
    per_config_last_export_path: dict[Path, Path] = field(default_factory=dict)


def project_state_path(project_dir: Path) -> Path:
    return project_dir / PROJECT_STATE_FILENAME


def project_config_key(project_dir: Path, config_path: Path) -> str:
    project_root = project_dir.resolve()
    candidate = config_path.resolve()
    try:
        return candidate.relative_to(project_root).as_posix()
    except ValueError:
        return str(candidate)


def resolve_project_config_key(project_dir: Path, key: str) -> Path:
    key_path = Path(key).expanduser()
    if key_path.is_absolute():
        return key_path.resolve()
    return (project_dir / key_path).resolve()


def load_project_state(project_dir: Path) -> LoadedProjectState:
    source_path = project_state_path(project_dir)
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return LoadedProjectState()
    except (OSError, json.JSONDecodeError):
        return LoadedProjectState()

    if not isinstance(payload, dict):
        return LoadedProjectState()
    if payload.get("format") != PROJECT_STATE_FORMAT:
        return LoadedProjectState()
    if payload.get("version") != PROJECT_STATE_VERSION:
        return LoadedProjectState()

    last_active_raw = payload.get("last_active_config")
    last_active_config: Path | None = None
    if isinstance(last_active_raw, str) and last_active_raw.strip():
        last_active_config = resolve_project_config_key(project_dir, last_active_raw)

    per_config_last_export_path: dict[Path, Path] = {}
    export_payload = payload.get("per_config_last_export_path")
    if isinstance(export_payload, dict):
        for raw_config_key, raw_export_path in export_payload.items():
            if not isinstance(raw_config_key, str) or not raw_config_key.strip():
                continue
            if not isinstance(raw_export_path, str) or not raw_export_path.strip():
                continue
            config_path = resolve_project_config_key(project_dir, raw_config_key)
            export_path = Path(raw_export_path).expanduser()
            if not export_path.is_absolute():
                export_path = (project_dir / export_path).resolve()
            else:
                export_path = export_path.resolve()
            per_config_last_export_path[config_path] = export_path

    return LoadedProjectState(
        last_active_config=last_active_config,
        per_config_last_export_path=per_config_last_export_path,
    )


def save_project_state(
    project_dir: Path,
    *,
    last_active_config: Path | None,
    per_config_last_export_path: dict[Path, Path],
) -> None:
    payload: dict[str, object] = {
        "format": PROJECT_STATE_FORMAT,
        "version": PROJECT_STATE_VERSION,
        "last_active_config": project_config_key(project_dir, last_active_config) if last_active_config is not None else None,
        "per_config_last_export_path": {
            project_config_key(project_dir, config_path): str(export_path)
            for config_path, export_path in sorted(
                per_config_last_export_path.items(),
                key=lambda item: project_config_key(project_dir, item[0]),
            )
        },
    }
    target_path = project_state_path(project_dir)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(f"{json.dumps(payload, indent=2, ensure_ascii=False)}\n", encoding="utf-8")

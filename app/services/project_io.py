"""Version-aware JSON project persistence."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.models.project import Project, ProjectError


class ProjectIOError(RuntimeError):
    """Raised when a project cannot be saved or loaded."""


def save_project(project: Project, path: str | Path) -> Path:
    """Atomically save a project as UTF-8 JSON."""
    destination = Path(path)
    if not destination.name.endswith(".peffect.json"):
        destination = destination.with_name(destination.name + ".peffect.json")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=destination.parent, delete=False, suffix=".tmp"
        ) as temporary:
            json.dump(project.to_dict(), temporary, ensure_ascii=False, indent=2)
            temp_path = Path(temporary.name)
        temp_path.replace(destination)
    except (OSError, TypeError, ValueError) as exc:
        try:
            if "temp_path" in locals():
                temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise ProjectIOError(f"could not save project: {exc}") from exc
    return destination


def load_project(path: str | Path) -> Project:
    """Load and validate a project JSON file."""
    source = Path(path)
    try:
        with source.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return Project.from_dict(data)
    except (OSError, json.JSONDecodeError, ProjectError) as exc:
        raise ProjectIOError(f"could not load project: {exc}") from exc

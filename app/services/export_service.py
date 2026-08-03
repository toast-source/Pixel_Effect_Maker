"""Transparent PNG animation-frame export."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.models.project import Project


class ExportError(RuntimeError):
    """Raised when PNG frame export fails."""


def export_png_frames(project: Project, directory: str | Path) -> list[Path]:
    """Export all composed frames as transparent, sequentially named PNG files."""
    target = Path(directory)
    safe_name = "".join(
        char if char.isalnum() or char in "-_" else "_" for char in project.name
    ).strip("_") or "effect"
    written: list[Path] = []
    try:
        target.mkdir(parents=True, exist_ok=True)
        digits = max(3, len(str(len(project.frames))))
        for index in range(len(project.frames)):
            path = target / f"{safe_name}_{index + 1:0{digits}d}.png"
            Image.fromarray(project.compose_frame(index)).save(path)
            written.append(path)
    except (OSError, ValueError) as exc:
        raise ExportError(f"could not export PNG frames: {exc}") from exc
    return written

"""Export an unapplied preview as a transparent numbered PNG sequence."""
from __future__ import annotations
from pathlib import Path
import numpy as np
from PIL import Image

def export_preview_sequence(frames: list[np.ndarray], directory: str | Path, base_name: str, *, overwrite: bool = False) -> list[Path]:
    if not frames: raise ValueError("no current preview is available")
    target = Path(directory); target.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in base_name).strip("_") or "effect"
    paths = [target / f"{safe}_{index:04d}.png" for index in range(1, len(frames) + 1)]
    if not overwrite and any(path.exists() for path in paths): raise FileExistsError("preview sequence would overwrite existing files")
    for frame, path in zip(frames, paths, strict=True):
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 4: raise ValueError("invalid RGBA preview frame")
        Image.fromarray(frame, "RGBA").save(path)
    return paths

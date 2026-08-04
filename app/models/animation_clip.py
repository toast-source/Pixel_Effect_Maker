"""Embedded reusable RGBA animation clips."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import numpy as np


@dataclass
class AnimationClipAsset:
    name: str
    frames: list[np.ndarray]
    fps: int = 12
    pivot_x: float | None = None
    pivot_y: float | None = None
    playback_mode: str = "loop"
    source_generator_id: str | None = None
    frame_durations_ms: list[int] | None = None
    loop: bool = True
    source_format: str = "generated"
    source_path: str | None = None
    tags: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("an animation clip requires at least one frame")
        copied: list[np.ndarray] = []
        shape = None
        for frame in self.frames:
            pixels = np.asarray(frame)
            if pixels.dtype != np.uint8 or pixels.ndim != 3 or pixels.shape[2] != 4:
                raise ValueError("clip frames must be H x W x 4 uint8 arrays")
            if shape is None:
                shape = pixels.shape
            elif pixels.shape != shape:
                raise ValueError("all clip frames must have the same size")
            copied.append(np.ascontiguousarray(pixels).copy())
        if not 1 <= int(self.fps) <= 120:
            raise ValueError("clip FPS must be between 1 and 120")
        if self.playback_mode not in {"once", "loop", "hold"}:
            raise ValueError("playback_mode must be once, loop, or hold")
        self.frames = copied
        default_duration = max(1, round(1000 / self.fps))
        self.frame_durations_ms = [default_duration] * len(copied) if self.frame_durations_ms is None else [max(1, int(v or default_duration)) for v in self.frame_durations_ms]
        if len(self.frame_durations_ms) != len(copied): raise ValueError("frame duration count must match frames")
        if self.pivot_x is None:
            self.pivot_x = self.width / 2.0
        if self.pivot_y is None:
            self.pivot_y = self.height / 2.0

    @property
    def width(self) -> int:
        return int(self.frames[0].shape[1])

    @property
    def height(self) -> int:
        return int(self.frames[0].shape[0])

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "fps": self.fps,
                "pivot": {"x": self.pivot_x, "y": self.pivot_y},
                "playback_mode": self.playback_mode,
                "source_generator_id": self.source_generator_id,
                "frame_durations_ms": self.frame_durations_ms, "loop": self.loop,
                "source_format": self.source_format, "source_path": self.source_path, "tags": self.tags,
                "width": self.width, "height": self.height,
                "frames": [frame.tolist() for frame in self.frames]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimationClipAsset":
        width, height = int(data["width"]), int(data["height"])
        frames = [np.asarray(item, dtype=np.uint8) for item in data["frames"]]
        if any(frame.shape != (height, width, 4) for frame in frames):
            raise ValueError("invalid animation clip frame shape")
        pivot = data.get("pivot", {})
        return cls(id=str(data["id"]), name=str(data.get("name", "Animation Clip")),
                   frames=frames, fps=int(data.get("fps", 12)),
                   pivot_x=float(pivot.get("x", width / 2)),
                   pivot_y=float(pivot.get("y", height / 2)),
                   playback_mode=str(data.get("playback_mode", "loop")),
                   source_generator_id=None if data.get("source_generator_id") is None else str(data["source_generator_id"]),
                   frame_durations_ms=data.get("frame_durations_ms"), loop=bool(data.get("loop",True)),
                   source_format=str(data.get("source_format","generated")),
                   source_path=None if data.get("source_path") is None else str(data["source_path"]), tags=dict(data.get("tags",{})))

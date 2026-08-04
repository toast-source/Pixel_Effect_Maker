"""Immutable source images embedded in a project."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import numpy as np


@dataclass
class SourceAsset:
    """An imported RGBA image used as non-destructive generator input."""

    name: str
    pixels: np.ndarray
    pivot_x: float | None = None
    pivot_y: float | None = None
    source_path: str | None = None
    id: str = field(default_factory=lambda: uuid4().hex)
    source_format: str = "png"

    def __post_init__(self) -> None:
        pixels = np.asarray(self.pixels)
        if pixels.dtype != np.uint8 or pixels.ndim != 3 or pixels.shape[2] != 4:
            raise ValueError("source asset pixels must be an H x W x 4 uint8 array")
        if pixels.shape[0] < 1 or pixels.shape[1] < 1:
            raise ValueError("source asset dimensions must be positive")
        self.pixels = np.ascontiguousarray(pixels).copy()
        if self.pivot_x is None:
            self.pivot_x = self.width / 2.0
        if self.pivot_y is None:
            self.pivot_y = self.height / 2.0

    @property
    def width(self) -> int:
        return int(self.pixels.shape[1])

    @property
    def height(self) -> int:
        return int(self.pixels.shape[0])

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "pixels": self.pixels.tolist(),
            "pivot": {"x": self.pivot_x, "y": self.pivot_y},
            "source_path": self.source_path,
            "source_format": self.source_format,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceAsset":
        width = int(data["width"])
        height = int(data["height"])
        pixels = np.asarray(data["pixels"], dtype=np.uint8)
        if pixels.shape != (height, width, 4):
            raise ValueError(f"invalid source asset pixel shape: {pixels.shape}")
        pivot = data.get("pivot", {})
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", "Source Asset")),
            pixels=pixels,
            pivot_x=float(pivot.get("x", width / 2.0)),
            pivot_y=float(pivot.get("y", height / 2.0)),
            source_path=(
                None if data.get("source_path") is None else str(data["source_path"])
            ),
            source_format=str(data.get("source_format", "png")),
        )

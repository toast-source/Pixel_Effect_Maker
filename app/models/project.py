"""Core project model and frame/layer operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .frame import Frame, empty_pixels
from .layer import Layer

FORMAT_VERSION = 1


class ProjectError(ValueError):
    """Raised when project data is invalid or unsupported."""


@dataclass
class Project:
    """UI-independent pixel animation project."""

    name: str = "Untitled"
    width: int = 64
    height: int = 64
    fps: int = 12
    loop: bool = True
    layers: list[Layer] = field(default_factory=list)
    frames: list[Frame] = field(default_factory=list)
    format_version: int = FORMAT_VERSION

    def __post_init__(self) -> None:
        self._validate_dimensions()

    @classmethod
    def create_default(
        cls,
        name: str = "Untitled",
        width: int = 64,
        height: int = 64,
        fps: int = 12,
        loop: bool = True,
    ) -> "Project":
        project = cls(name=name, width=width, height=height, fps=fps, loop=loop)
        project.add_layer("Layer 1")
        project.add_frame()
        return project

    def _validate_dimensions(self) -> None:
        if not (1 <= int(self.width) <= 1024 and 1 <= int(self.height) <= 1024):
            raise ProjectError("canvas dimensions must be between 1 and 1024 pixels")
        if not (1 <= int(self.fps) <= 120):
            raise ProjectError("FPS must be between 1 and 120")

    def add_layer(self, name: str | None = None) -> Layer:
        layer = Layer(name=name or self.next_layer_name())
        self.layers.append(layer)
        for frame in self.frames:
            frame.layer_pixels[layer.id] = empty_pixels(self.width, self.height)
        return layer

    def next_layer_name(self) -> str:
        """Return the first available default layer name."""
        existing = {layer.name for layer in self.layers}
        number = 1
        while f"Layer {number}" in existing:
            number += 1
        return f"Layer {number}"

    def delete_layer(self, index: int) -> None:
        if len(self.layers) <= 1:
            raise ProjectError("a project must contain at least one layer")
        layer = self.layers.pop(index)
        for frame in self.frames:
            frame.layer_pixels.pop(layer.id, None)

    def add_frame(self) -> Frame:
        frame = Frame(name=f"Frame {len(self.frames) + 1}")
        frame.layer_pixels = {
            layer.id: empty_pixels(self.width, self.height) for layer in self.layers
        }
        self.frames.append(frame)
        return frame

    def insert_empty_frame(self, index: int) -> Frame:
        """Insert a transparent frame immediately after the given frame."""
        frame = Frame(name=f"Frame {len(self.frames) + 1}")
        frame.layer_pixels = {
            layer.id: empty_pixels(self.width, self.height) for layer in self.layers
        }
        self.frames.insert(index + 1, frame)
        return frame

    def duplicate_frame(self, index: int) -> Frame:
        source = self.frames[index]
        duplicate = Frame(
            # Keep the compatibility field without accumulating display suffixes.
            # Timeline labels are derived from the current list position.
            name=source.name,
            layer_pixels={key: value.copy() for key, value in source.layer_pixels.items()},
        )
        self.frames.insert(index + 1, duplicate)
        return duplicate

    def delete_frame(self, index: int) -> None:
        if len(self.frames) <= 1:
            raise ProjectError("a project must contain at least one frame")
        self.frames.pop(index)

    def compose_frame(self, index: int) -> np.ndarray:
        """Alpha-composite visible layers and return an RGBA buffer."""
        output = np.zeros((self.height, self.width, 4), dtype=np.float32)
        frame = self.frames[index]
        for layer in self.layers:
            if not layer.visible:
                continue
            source = frame.layer_pixels.get(layer.id)
            if source is None:
                continue
            src = source.astype(np.float32) / 255.0
            src_alpha = src[..., 3:4] * max(0.0, min(1.0, layer.opacity))
            dst_alpha = output[..., 3:4]
            combined_alpha = src_alpha + dst_alpha * (1.0 - src_alpha)
            safe_alpha = np.where(combined_alpha == 0, 1.0, combined_alpha)
            output[..., :3] = (
                src[..., :3] * src_alpha
                + output[..., :3] * dst_alpha * (1.0 - src_alpha)
            ) / safe_alpha
            output[..., 3:4] = combined_alpha
        return np.clip(output * 255.0, 0, 255).astype(np.uint8)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "name": self.name,
            "canvas": {"width": self.width, "height": self.height},
            "animation": {"fps": self.fps, "loop": self.loop},
            "layers": [layer.to_dict() for layer in self.layers],
            "frames": [frame.to_dict() for frame in self.frames],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        if not isinstance(data, dict):
            raise ProjectError("project root must be a JSON object")
        version = data.get("format_version")
        if version != FORMAT_VERSION:
            raise ProjectError(f"unsupported format_version: {version!r}")
        try:
            canvas = data["canvas"]
            animation = data["animation"]
            project = cls(
                format_version=int(version),
                name=str(data.get("name", "Untitled")),
                width=int(canvas["width"]),
                height=int(canvas["height"]),
                fps=int(animation.get("fps", 12)),
                loop=bool(animation.get("loop", True)),
            )
            project.layers = [Layer.from_dict(item) for item in data.get("layers", [])]
            project.frames = [
                Frame.from_dict(item, project.width, project.height)
                for item in data.get("frames", [])
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectError(f"invalid project data: {exc}") from exc
        if not project.layers or not project.frames:
            raise ProjectError("project must contain at least one layer and one frame")
        layer_ids = {layer.id for layer in project.layers}
        if len(layer_ids) != len(project.layers):
            raise ProjectError("layer IDs must be unique")
        for frame in project.frames:
            unknown = set(frame.layer_pixels) - layer_ids
            if unknown:
                raise ProjectError("frame contains unknown layer IDs")
            for layer in project.layers:
                frame.layer_pixels.setdefault(
                    layer.id, empty_pixels(project.width, project.height)
                )
        return project

"""Core project model and frame/layer operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .frame import Frame, empty_pixels
from .layer import Layer
from .source_asset import SourceAsset
from .effect_generator import TransformEmitter
from .animation_clip import AnimationClipAsset
from .particle_emitter import ParticleEmitter
from .resource_composition import ResourceComposition

FORMAT_VERSION = 5


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
    source_assets: list[SourceAsset] = field(default_factory=list)
    generators: list[TransformEmitter] = field(default_factory=list)
    animation_clips: list[AnimationClipAsset] = field(default_factory=list)
    particle_emitters: list[ParticleEmitter] = field(default_factory=list)
    resource_compositions: list[ResourceComposition] = field(default_factory=list)
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
        for generator in self.generators:
            if generator.generated_layer_id == layer.id:
                generator.generated_layer_id = None
        for emitter in self.particle_emitters:
            if emitter.generated_layer_id == layer.id:
                emitter.generated_layer_id = None
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
            "format_version": FORMAT_VERSION,
            "name": self.name,
            "canvas": {"width": self.width, "height": self.height},
            "animation": {"fps": self.fps, "loop": self.loop},
            "layers": [layer.to_dict() for layer in self.layers],
            "frames": [frame.to_dict() for frame in self.frames],
            "source_assets": [asset.to_dict() for asset in self.source_assets],
            "generators": [generator.to_dict() for generator in self.generators],
            "animation_clips": [clip.to_dict() for clip in self.animation_clips],
            "particle_emitters": [emitter.to_dict() for emitter in self.particle_emitters],
            "resource_compositions": [composition.to_dict() for composition in self.resource_compositions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        if not isinstance(data, dict):
            raise ProjectError("project root must be a JSON object")
        version = data.get("format_version")
        if version not in (1, 2, 3, 4, FORMAT_VERSION):
            raise ProjectError(f"unsupported format_version: {version!r}")
        try:
            canvas = data["canvas"]
            animation = data["animation"]
            project = cls(
                format_version=FORMAT_VERSION,
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
            if int(version) >= 2:
                project.source_assets = [
                    SourceAsset.from_dict(item)
                    for item in data.get("source_assets", [])
                ]
                project.generators = [
                    TransformEmitter.from_dict(item)
                    for item in data.get("generators", [])
                ]
            if int(version) >= 3:
                project.animation_clips = [AnimationClipAsset.from_dict(item) for item in data.get("animation_clips", [])]
                project.particle_emitters = [ParticleEmitter.from_dict(item) for item in data.get("particle_emitters", [])]
            if int(version) >= 5:
                project.resource_compositions = [ResourceComposition.from_dict(item) for item in data.get("resource_compositions", [])]
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
        asset_ids = {asset.id for asset in project.source_assets}
        if len(asset_ids) != len(project.source_assets):
            raise ProjectError("source asset IDs must be unique")
        generator_ids = {generator.id for generator in project.generators}
        if len(generator_ids) != len(project.generators):
            raise ProjectError("generator IDs must be unique")
        for generator in project.generators:
            if generator.settings.source_asset_id not in asset_ids:
                raise ProjectError("generator references an unknown source asset")
            if (
                generator.generated_layer_id is not None
                and generator.generated_layer_id not in layer_ids
            ):
                raise ProjectError("generator references an unknown generated layer")
        clip_ids = {clip.id for clip in project.animation_clips}
        if len(clip_ids) != len(project.animation_clips):
            raise ProjectError("animation clip IDs must be unique")
        emitter_ids = {emitter.id for emitter in project.particle_emitters}
        if len(emitter_ids) != len(project.particle_emitters):
            raise ProjectError("particle emitter IDs must be unique")
        composition_ids={composition.id for composition in project.resource_compositions}
        for emitter in project.particle_emitters:
            valid_ids = clip_ids if emitter.settings.resource_type == "animation_clip" else composition_ids if emitter.settings.resource_type == "resource_composition" else asset_ids
            if emitter.settings.clip_asset_id not in valid_ids:
                raise ProjectError("particle emitter references an unknown animation clip")
            if emitter.generated_layer_id is not None and emitter.generated_layer_id not in layer_ids:
                raise ProjectError("particle emitter references an unknown generated layer")
        if len({c.id for c in project.resource_compositions})!=len(project.resource_compositions):raise ProjectError("resource composition IDs must be unique")
        for composition in project.resource_compositions:
            for layer in composition.layers:
                valid=asset_ids if layer.source_type=="source_asset" else clip_ids
                if layer.source_id not in valid:raise ProjectError("composition layer references an unknown asset")
                if layer.end_frame>=composition.frame_count or layer.source_start_frame<0:raise ProjectError("composition layer range is outside the composition")
                for property_id,track in layer.tracks.items():
                    if property_id!=track.property_id:raise ProjectError("composition track ID does not match its property")
                    if any(key.frame>=composition.frame_count for key in track.keyframes):raise ProjectError("composition keyframe is outside the composition")
        return project

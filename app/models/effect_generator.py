"""Generic transform emitter data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class Distribution(str, Enum):
    POINT = "Point"
    LINE = "Line"
    CIRCLE = "Circle"


class Easing(str, Enum):
    LINEAR = "Linear"
    EASE_IN = "Ease In"
    EASE_OUT = "Ease Out"


@dataclass
class DeformationSettings:
    """Reserved extension point; only no deformation is currently rendered."""

    deformation_type: str = "none"
    amount_start: float = 0.0
    amount_end: float = 0.0

    def validate(self) -> None:
        if self.deformation_type != "none":
            raise ValueError("only deformation_type 'none' is currently supported")


@dataclass
class TransformEmitterSettings:
    source_asset_id: str
    output_frames: int = 8
    instance_count: int = 1
    emission_interval: int = 1
    lifetime: int = 8
    start_frame: int = 0
    distribution: str = Distribution.POINT.value
    origin_x: float = 32.0
    origin_y: float = 32.0
    line_end_x: float = 48.0
    line_end_y: float = 32.0
    radius: float = 16.0
    angle_start: float = 0.0
    angle_end: float = 360.0
    offset_x_start: float = 0.0
    offset_y_start: float = 0.0
    offset_x_end: float = 0.0
    offset_y_end: float = 0.0
    rotation_start: float = 0.0
    rotation_end: float = 0.0
    scale_x_start: float = 1.0
    scale_x_end: float = 1.0
    scale_y_start: float = 1.0
    scale_y_end: float = 1.0
    horizontal_tilt_start: float = 0.0
    horizontal_tilt_end: float = 0.0
    vertical_tilt_start: float = 0.0
    vertical_tilt_end: float = 0.0
    perspective_start: float = 0.0
    perspective_end: float = 0.0
    opacity_start: float = 1.0
    opacity_end: float = 1.0
    easing: str = Easing.LINEAR.value
    seed: int = 0
    deformation: DeformationSettings = field(default_factory=DeformationSettings)

    def validate(self) -> None:
        if not self.source_asset_id:
            raise ValueError("a source asset is required")
        if not 1 <= self.output_frames <= 512:
            raise ValueError("output_frames must be between 1 and 512")
        if not 1 <= self.instance_count <= 256:
            raise ValueError("instance_count must be between 1 and 256")
        if not 0 <= self.emission_interval <= 512:
            raise ValueError("emission_interval must be between 0 and 512")
        if not 1 <= self.lifetime <= 512:
            raise ValueError("lifetime must be between 1 and 512")
        if not 0 <= self.start_frame <= 511:
            raise ValueError("start_frame must be between 0 and 511")
        Distribution(self.distribution)
        Easing(self.easing)
        for value in (
            self.scale_x_start,
            self.scale_x_end,
            self.scale_y_start,
            self.scale_y_end,
        ):
            if not -16.0 <= value <= 16.0:
                raise ValueError("scale values must be between -16 and 16")
        for value in (
            self.horizontal_tilt_start,
            self.horizontal_tilt_end,
            self.vertical_tilt_start,
            self.vertical_tilt_end,
            self.perspective_start,
            self.perspective_end,
        ):
            if not -1.0 <= value <= 1.0:
                raise ValueError("tilt and perspective values must be between -1 and 1")
        for value in (self.opacity_start, self.opacity_end):
            if not 0.0 <= value <= 1.0:
                raise ValueError("opacity values must be between 0 and 1")
        self.deformation.validate()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransformEmitterSettings":
        values = dict(data)
        values["deformation"] = DeformationSettings(**values.get("deformation", {}))
        settings = cls(**values)
        settings.validate()
        return settings


@dataclass
class EffectInstance:
    source_asset_id: str
    birth_frame: int
    lifetime: int
    distribution_index: int
    random_seed: int
    origin_x: float
    origin_y: float


@dataclass
class TransformEmitter:
    name: str
    settings: TransformEmitterSettings
    generated_layer_id: str | None = None
    id: str = field(default_factory=lambda: uuid4().hex)
    generator_type: str = "transform_emitter"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "generator_type": self.generator_type,
            "generated_layer_id": self.generated_layer_id,
            "settings": self.settings.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransformEmitter":
        if data.get("generator_type", "transform_emitter") != "transform_emitter":
            raise ValueError(f"unsupported generator type: {data.get('generator_type')!r}")
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", "Transform Emitter")),
            generator_type="transform_emitter",
            generated_layer_id=(
                None
                if data.get("generated_layer_id") is None
                else str(data["generated_layer_id"])
            ),
            settings=TransformEmitterSettings.from_dict(data["settings"]),
        )

"""Deterministic animation-clip particle emitter models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class ParticleEmitterSettings:
    clip_asset_id: str
    resource_type: str = "animation_clip"
    output_frame_count: int = 24
    start_frame: int = 0
    emission_mode: str = "burst"
    particle_count_min: int = 8
    particle_count_max: int = 8
    emission_duration: int = 12
    spawn_shape: str = "point"
    origin_x: float = 32.0
    origin_y: float = 32.0
    line_end_x: float = 48.0
    line_end_y: float = 32.0
    radius: float = 16.0
    start_angle: float = 0.0
    end_angle: float = 360.0
    box_width: float = 32.0
    box_height: float = 32.0
    direction_mode: str = "fixed"
    direction_degrees: float = -90.0
    direction_spread_degrees: float = 20.0
    speed_min: float = 1.0
    speed_max: float = 2.0
    lifetime_min: int = 12
    lifetime_max: int = 20
    scale_min: float = 1.0
    scale_max: float = 1.0
    rotation_min: float = 0.0
    rotation_max: float = 0.0
    angular_velocity_min: float = 0.0
    angular_velocity_max: float = 0.0
    start_delay_min: int = 0
    start_delay_max: int = 0
    clip_speed_min: float = 1.0
    clip_speed_max: float = 1.0
    random_start_frame: bool = False
    opacity_start: float = 1.0
    opacity_end: float = 0.0
    easing: str = "Linear"
    seed: int = 0

    def validate(self) -> None:
        if not self.clip_asset_id: raise ValueError("an animation clip is required")
        if self.resource_type not in {"animation_clip", "source_asset", "resource_composition"}: raise ValueError("unsupported particle resource type")
        if not 1 <= self.output_frame_count <= 512: raise ValueError("output frame count must be 1..512")
        if self.emission_mode not in {"burst", "over_time"}: raise ValueError("unsupported emission mode")
        if self.spawn_shape not in {"point", "line", "circle", "box"}: raise ValueError("unsupported spawn shape")
        if self.direction_mode not in {"fixed", "radial_outward"}: raise ValueError("unsupported direction mode")
        ranges = ((self.particle_count_min, self.particle_count_max), (self.speed_min, self.speed_max),
                  (self.lifetime_min, self.lifetime_max), (self.scale_min, self.scale_max),
                  (self.rotation_min, self.rotation_max), (self.angular_velocity_min, self.angular_velocity_max),
                  (self.start_delay_min, self.start_delay_max), (self.clip_speed_min, self.clip_speed_max))
        if any(low > high for low, high in ranges): raise ValueError("random range minimum must not exceed maximum")
        if self.particle_count_min < 0 or self.particle_count_max > 4096: raise ValueError("particle count must be 0..4096")
        if self.lifetime_min < 1 or self.start_delay_min < 0: raise ValueError("invalid lifetime or start delay")
        if self.scale_min <= 0 or self.clip_speed_min <= 0: raise ValueError("scale and clip speed must be positive")
        if not (0 <= self.opacity_start <= 1 and 0 <= self.opacity_end <= 1): raise ValueError("opacity must be 0..1")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def resource_id(self) -> str:
        return self.clip_asset_id

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParticleEmitterSettings":
        values = dict(data)
        if "resource_id" in values and "clip_asset_id" not in values:
            values["clip_asset_id"] = values.pop("resource_id")
        value = cls(**values); value.validate(); return value


@dataclass(frozen=True)
class ParticleInstance:
    birth_frame: int
    lifetime: int
    start_x: float
    start_y: float
    velocity_x: float
    velocity_y: float
    scale: float
    rotation: float
    angular_velocity: float
    clip_start_frame: int
    clip_playback_speed: float
    random_seed: int


@dataclass
class ParticleEmitter:
    name: str
    settings: ParticleEmitterSettings
    generated_layer_id: str | None = None
    id: str = field(default_factory=lambda: uuid4().hex)
    generator_type: str = "particle_emitter"

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "generator_type": self.generator_type,
                "generated_layer_id": self.generated_layer_id, "settings": self.settings.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParticleEmitter":
        if data.get("generator_type") != "particle_emitter": raise ValueError("unsupported particle emitter type")
        return cls(id=str(data["id"]), name=str(data.get("name", "Particle Emitter")),
                   generated_layer_id=None if data.get("generated_layer_id") is None else str(data["generated_layer_id"]),
                   settings=ParticleEmitterSettings.from_dict(data["settings"]))

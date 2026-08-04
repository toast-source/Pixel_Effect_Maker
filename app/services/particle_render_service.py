"""Deterministic CPU renderer for animation-clip particles."""

from __future__ import annotations

import math
import random
from uuid import uuid4

import numpy as np

from app.models.animation_clip import AnimationClipAsset
from app.models.frame import empty_pixels
from app.models.layer import Layer
from app.models.particle_emitter import ParticleEmitter, ParticleEmitterSettings, ParticleInstance
from app.models.project import Project
from app.models.source_asset import SourceAsset
from app.services.effect_render_service import EffectRenderError, render_transformed_source
from app.services.emitter_service import ease
from app.services.resource_composition_render_service import composition_as_clip


def build_particle_instances(settings: ParticleEmitterSettings, clip_length: int) -> list[ParticleInstance]:
    """Resolve all randomness once; equal settings and seed produce equal instances."""
    settings.validate()
    rng = random.Random(settings.seed)
    count = rng.randint(settings.particle_count_min, settings.particle_count_max)
    result: list[ParticleInstance] = []
    for index in range(count):
        delay = rng.randint(settings.start_delay_min, settings.start_delay_max)
        spread_birth = 0 if settings.emission_mode == "burst" or count <= 1 else round(index * max(0, settings.emission_duration - 1) / (count - 1))
        x, y = _spawn_position(settings, rng)
        direction = settings.direction_degrees
        if settings.direction_mode == "radial_outward":
            dx, dy = x - settings.origin_x, y - settings.origin_y
            direction = math.degrees(math.atan2(dy, dx)) if abs(dx) + abs(dy) > 1e-9 else rng.uniform(0, 360)
        direction += rng.uniform(-settings.direction_spread_degrees, settings.direction_spread_degrees)
        speed = rng.uniform(settings.speed_min, settings.speed_max)
        radians = math.radians(direction)
        result.append(ParticleInstance(
            birth_frame=settings.start_frame + spread_birth + delay,
            lifetime=rng.randint(settings.lifetime_min, settings.lifetime_max),
            start_x=x, start_y=y, velocity_x=math.cos(radians) * speed,
            velocity_y=math.sin(radians) * speed,
            scale=rng.uniform(settings.scale_min, settings.scale_max),
            rotation=rng.uniform(settings.rotation_min, settings.rotation_max),
            angular_velocity=rng.uniform(settings.angular_velocity_min, settings.angular_velocity_max),
            clip_start_frame=rng.randrange(clip_length) if settings.random_start_frame else 0,
            clip_playback_speed=rng.uniform(settings.clip_speed_min, settings.clip_speed_max),
            random_seed=rng.getrandbits(31)))
    return result


def _spawn_position(settings: ParticleEmitterSettings, rng: random.Random) -> tuple[float, float]:
    if settings.spawn_shape == "line":
        amount = rng.random(); return (settings.origin_x + (settings.line_end_x - settings.origin_x) * amount,
                                       settings.origin_y + (settings.line_end_y - settings.origin_y) * amount)
    if settings.spawn_shape == "circle":
        angle = math.radians(rng.uniform(settings.start_angle, settings.end_angle))
        return settings.origin_x + math.cos(angle) * settings.radius, settings.origin_y + math.sin(angle) * settings.radius
    if settings.spawn_shape == "box":
        return (settings.origin_x + rng.uniform(-settings.box_width / 2, settings.box_width / 2),
                settings.origin_y + rng.uniform(-settings.box_height / 2, settings.box_height / 2))
    return settings.origin_x, settings.origin_y


def particle_clip_frame(clip: AnimationClipAsset, instance: ParticleInstance, age: int, effect_fps: int | None = None) -> np.ndarray | None:
    if clip.source_format == "composition":
        index = math.floor(age / max(1, effect_fps or clip.fps) * clip.fps * instance.clip_playback_speed) + instance.clip_start_frame
        if clip.playback_mode == "loop": index %= len(clip.frames)
        elif index >= len(clip.frames):
            if clip.playback_mode == "once": return None
            index = len(clip.frames)-1
        return clip.frames[max(0,index)]
    durations = clip.frame_durations_ms or [max(1, round(1000 / clip.fps))] * len(clip.frames)
    elapsed = age * (1000.0 / max(1, effect_fps or clip.fps)) * instance.clip_playback_speed + sum(durations[:instance.clip_start_frame])
    total = sum(durations)
    if clip.playback_mode == "loop": elapsed %= total
    elif elapsed >= total:
        if clip.playback_mode == "once": return None
        elapsed = total - 1
    cumulative = 0
    for index, duration in enumerate(durations):
        cumulative += duration
        if elapsed < cumulative: break
    return clip.frames[index]


def render_particle_frames(project: Project, emitter: ParticleEmitter) -> list[np.ndarray]:
    settings = emitter.settings; settings.validate()
    clip = next((item for item in project.animation_clips if item.id == settings.clip_asset_id), None)
    if settings.resource_type == "source_asset":
        source = next((item for item in project.source_assets if item.id == settings.clip_asset_id), None)
        clip = None if source is None else AnimationClipAsset(source.name, [source.pixels], fps=project.fps,
            pivot_x=source.pivot_x, pivot_y=source.pivot_y, playback_mode="hold",
            source_format=source.source_format, source_path=source.source_path)
    elif settings.resource_type == "resource_composition":
        composition=next((item for item in project.resource_compositions if item.id==settings.resource_id),None)
        clip=None if composition is None else composition_as_clip(project,composition)
    if clip is None: raise EffectRenderError("the particle animation clip does not exist")
    outputs = [empty_pixels(project.width, project.height) for _ in range(settings.output_frame_count)]
    instances = build_particle_instances(settings, len(clip.frames))
    for frame_index, output in enumerate(outputs):
        for instance in instances:
            age = frame_index - instance.birth_frame
            if age < 0 or age >= instance.lifetime: continue
            pixels = particle_clip_frame(clip, instance, age, project.fps)
            if pixels is None: continue
            amount = 1.0 if instance.lifetime <= 1 else ease(age / (instance.lifetime - 1), settings.easing)
            asset = SourceAsset(name="particle", pixels=pixels, pivot_x=clip.pivot_x, pivot_y=clip.pivot_y)
            render_transformed_source(output, asset,
                position_x=instance.start_x + instance.velocity_x * age,
                position_y=instance.start_y + instance.velocity_y * age,
                rotation=instance.rotation + instance.angular_velocity * age,
                scale_x=instance.scale, scale_y=instance.scale,
                horizontal_tilt=0, vertical_tilt=0, perspective=0,
                opacity=settings.opacity_start + (settings.opacity_end - settings.opacity_start) * amount)
    return outputs


def apply_particle_frames(project: Project, emitter: ParticleEmitter, outputs: list[np.ndarray]) -> Layer:
    if not outputs: raise EffectRenderError("particle output contains no frames")
    expected = (project.height, project.width, 4)
    if any(item.dtype != np.uint8 or item.shape != expected for item in outputs): raise EffectRenderError("invalid particle RGBA output")
    layer = next((item for item in project.layers if item.id == emitter.generated_layer_id), None)
    new = layer is None
    if new: layer = Layer(id=uuid4().hex, name=f"Particle: {emitter.name}", kind="generated", generator_id=emitter.id)
    while len(project.frames) < len(outputs): project.add_frame()
    if new: project.layers.append(layer)
    assert layer is not None
    for index, frame in enumerate(project.frames):
        frame.layer_pixels[layer.id] = outputs[index].copy() if index < len(outputs) else empty_pixels(project.width, project.height)
    layer.name = f"Particle: {emitter.name}"; layer.kind = "generated"; layer.generator_id = emitter.id
    emitter.generated_layer_id = layer.id
    return layer

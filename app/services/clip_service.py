"""Explicit animation clip creation and update operations."""
from __future__ import annotations
from app.models.animation_clip import AnimationClipAsset
from app.models.effect_generator import TransformEmitter
from app.models.project import Project

def create_clip_from_generator(project: Project, generator: TransformEmitter, name: str | None = None) -> AnimationClipAsset:
    if generator.generated_layer_id is None: raise ValueError("Apply to Frames before creating an animation clip")
    frames = [frame.layer_pixels[generator.generated_layer_id].copy() for frame in project.frames]
    clip = AnimationClipAsset(name=name or f"{generator.name} Clip", frames=frames, fps=project.fps,
                              pivot_x=project.width / 2, pivot_y=project.height / 2,
                              playback_mode="loop", source_generator_id=generator.id)
    project.animation_clips.append(clip); return clip

def update_clip_from_generator(project: Project, clip: AnimationClipAsset, generator: TransformEmitter) -> None:
    if generator.generated_layer_id is None: raise ValueError("Apply to Frames before updating an animation clip")
    clip.frames = [frame.layer_pixels[generator.generated_layer_id].copy() for frame in project.frames]
    clip.fps = project.fps; clip.source_generator_id = generator.id

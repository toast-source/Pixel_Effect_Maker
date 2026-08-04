"""Nearest-neighbor rendering and atomic Generated Layer replacement."""

from __future__ import annotations

import math
from uuid import uuid4

import numpy as np

from app.models.effect_generator import TransformEmitter
from app.models.frame import empty_pixels
from app.models.layer import Layer
from app.models.project import Project
from app.models.source_asset import SourceAsset
from app.services.emitter_service import (
    build_instances,
    ease,
    interpolate,
    normalized_lifetime,
)


class EffectRenderError(ValueError):
    """Raised when a generator cannot be rendered without partial mutation."""


def _homography_from_unit_square(destination: np.ndarray) -> np.ndarray:
    source = np.array(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))
    matrix: list[list[float]] = []
    values: list[float] = []
    for (u, v), (x, y) in zip(source, destination, strict=True):
        matrix.append([u, v, 1.0, 0.0, 0.0, 0.0, -u * x, -v * x])
        matrix.append([0.0, 0.0, 0.0, u, v, 1.0, -u * y, -v * y])
        values.extend((x, y))
    coefficients = np.linalg.solve(
        np.asarray(matrix, dtype=np.float64), np.asarray(values, dtype=np.float64)
    )
    return np.append(coefficients, 1.0).reshape(3, 3)


def _destination_corners(
    asset: SourceAsset,
    position_x: float,
    position_y: float,
    rotation: float,
    scale_x: float,
    scale_y: float,
    horizontal_tilt: float,
    vertical_tilt: float,
    perspective: float,
) -> np.ndarray:
    corners = np.array(
        [
            [-asset.pivot_x, -asset.pivot_y],
            [asset.width - asset.pivot_x, -asset.pivot_y],
            [asset.width - asset.pivot_x, asset.height - asset.pivot_y],
            [-asset.pivot_x, asset.height - asset.pivot_y],
        ],
        dtype=np.float64,
    )
    corners[:, 0] *= scale_x
    corners[:, 1] *= scale_y
    signs_x = np.array((-1.0, 1.0, 1.0, -1.0))
    signs_y = np.array((-1.0, -1.0, 1.0, 1.0))

    # Tilts alter opposing edge lengths as a quadrilateral warp, not aliases for scale.
    corners[:, 0] *= max(0.05, math.cos(abs(horizontal_tilt) * math.pi / 2.0))
    corners[:, 1] *= 1.0 - 0.45 * horizontal_tilt * signs_x
    corners[:, 1] *= max(0.05, math.cos(abs(vertical_tilt) * math.pi / 2.0))
    corners[:, 0] *= 1.0 - 0.45 * vertical_tilt * signs_y
    corners[:, 1] *= 1.0 - 0.45 * perspective * signs_x
    corners[:, 0] += perspective * signs_y * max(1.0, asset.width) * 0.2

    radians = math.radians(rotation)
    rotation_matrix = np.array(
        ((math.cos(radians), -math.sin(radians)),
         (math.sin(radians), math.cos(radians)))
    )
    corners = corners @ rotation_matrix.T
    corners[:, 0] += position_x
    corners[:, 1] += position_y
    return corners


def _source_over(destination: np.ndarray, source: np.ndarray) -> None:
    """Composite straight-alpha uint8 source over destination in place."""
    source_f = source.astype(np.float64) / 255.0
    destination_f = destination.astype(np.float64) / 255.0
    source_alpha = source_f[..., 3:4]
    destination_alpha = destination_f[..., 3:4]
    output_alpha = source_alpha + destination_alpha * (1.0 - source_alpha)
    safe = np.where(output_alpha > 0.0, output_alpha, 1.0)
    rgb = (
        source_f[..., :3] * source_alpha
        + destination_f[..., :3] * destination_alpha * (1.0 - source_alpha)
    ) / safe
    output = np.concatenate((rgb, output_alpha), axis=2)
    destination[:] = np.clip(np.rint(output * 255.0), 0, 255).astype(np.uint8)


def render_transformed_source(
    canvas: np.ndarray,
    asset: SourceAsset,
    *,
    position_x: float,
    position_y: float,
    rotation: float,
    scale_x: float,
    scale_y: float,
    horizontal_tilt: float,
    vertical_tilt: float,
    perspective: float,
    opacity: float,
) -> None:
    """Warp one source into an RGBA canvas using inverse nearest sampling."""
    if abs(scale_x) < 1e-6 or abs(scale_y) < 1e-6 or opacity <= 0.0:
        return
    destination = _destination_corners(
        asset,
        position_x,
        position_y,
        rotation,
        scale_x,
        scale_y,
        horizontal_tilt,
        vertical_tilt,
        perspective,
    )
    try:
        inverse = np.linalg.inv(_homography_from_unit_square(destination))
    except np.linalg.LinAlgError:
        return
    height, width = canvas.shape[:2]
    left = max(0, int(math.floor(float(destination[:, 0].min()))))
    right = min(width - 1, int(math.ceil(float(destination[:, 0].max()))))
    top = max(0, int(math.floor(float(destination[:, 1].min()))))
    bottom = min(height - 1, int(math.ceil(float(destination[:, 1].max()))))
    if right < left or bottom < top:
        return
    grid_x, grid_y = np.meshgrid(
        np.arange(left, right + 1, dtype=np.float64),
        np.arange(top, bottom + 1, dtype=np.float64),
    )
    points = np.stack((grid_x, grid_y, np.ones_like(grid_x)), axis=-1)
    mapped = points @ inverse.T
    denominator = mapped[..., 2]
    valid_denominator = np.abs(denominator) > 1e-10
    safe_denominator = np.where(valid_denominator, denominator, 1.0)
    u = mapped[..., 0] / safe_denominator
    v = mapped[..., 1] / safe_denominator
    valid = (
        valid_denominator
        & (u >= 0.0)
        & (u <= 1.0)
        & (v >= 0.0)
        & (v <= 1.0)
    )
    source_x = np.clip(np.rint(u * (asset.width - 1)), 0, asset.width - 1).astype(int)
    source_y = np.clip(np.rint(v * (asset.height - 1)), 0, asset.height - 1).astype(int)
    sampled = asset.pixels[source_y, source_x].copy()
    sampled[~valid] = 0
    if opacity < 1.0:
        sampled[..., 3] = np.rint(sampled[..., 3].astype(float) * opacity).astype(
            np.uint8
        )
    region = canvas[top : bottom + 1, left : right + 1]
    _source_over(region, sampled)


def render_generator_frames(
    project: Project, generator: TransformEmitter
) -> list[np.ndarray]:
    """Calculate all output buffers without mutating the project."""
    settings = generator.settings
    settings.validate()
    asset = next(
        (item for item in project.source_assets if item.id == settings.source_asset_id),
        None,
    )
    if asset is None:
        raise EffectRenderError("the generator source asset does not exist")
    frame_total = max(len(project.frames), settings.output_frames)
    outputs = [empty_pixels(project.width, project.height) for _ in range(frame_total)]
    instances = build_instances(settings)
    for frame_index in range(settings.output_frames):
        for instance in instances:
            lifetime = normalized_lifetime(instance, frame_index)
            if lifetime is None:
                continue
            amount = ease(lifetime, settings.easing)
            render_transformed_source(
                outputs[frame_index],
                asset,
                position_x=instance.origin_x
                + interpolate(settings.offset_x_start, settings.offset_x_end, amount),
                position_y=instance.origin_y
                + interpolate(settings.offset_y_start, settings.offset_y_end, amount),
                rotation=interpolate(
                    settings.rotation_start, settings.rotation_end, amount
                ),
                scale_x=interpolate(
                    settings.scale_x_start, settings.scale_x_end, amount
                ),
                scale_y=interpolate(
                    settings.scale_y_start, settings.scale_y_end, amount
                ),
                horizontal_tilt=interpolate(
                    settings.horizontal_tilt_start,
                    settings.horizontal_tilt_end,
                    amount,
                ),
                vertical_tilt=interpolate(
                    settings.vertical_tilt_start,
                    settings.vertical_tilt_end,
                    amount,
                ),
                perspective=interpolate(
                    settings.perspective_start, settings.perspective_end, amount
                ),
                opacity=interpolate(
                    settings.opacity_start, settings.opacity_end, amount
                ),
            )
    return outputs


def generate_emitter(project: Project, generator: TransformEmitter) -> Layer:
    """Atomically replace only this generator's dedicated layer."""
    outputs = render_generator_frames(project, generator)
    return apply_rendered_frames(project, generator, outputs)


def apply_rendered_frames(
    project: Project, generator: TransformEmitter, outputs: list[np.ndarray]
) -> Layer:
    """Commit already-rendered buffers to one generator layer."""
    if not outputs:
        raise EffectRenderError("the rendered output contains no frames")
    expected = (project.height, project.width, 4)
    if any(frame.shape != expected or frame.dtype != np.uint8 for frame in outputs):
        raise EffectRenderError("the rendered output contains an invalid RGBA buffer")
    if len(outputs) < len(project.frames):
        outputs = list(outputs) + [
            empty_pixels(project.width, project.height)
            for _ in range(len(project.frames) - len(outputs))
        ]
    layer = next(
        (item for item in project.layers if item.id == generator.generated_layer_id),
        None,
    )
    new_layer = layer is None
    if new_layer:
        layer = Layer(
            id=uuid4().hex,
            name=f"Generated: {generator.name}",
            kind="generated",
            generator_id=generator.id,
        )
    assert layer is not None
    while len(project.frames) < len(outputs):
        project.add_frame()
    if new_layer:
        project.layers.append(layer)
    for frame, pixels in zip(project.frames, outputs, strict=True):
        frame.layer_pixels[layer.id] = pixels
    layer.name = f"Generated: {generator.name}"
    layer.kind = "generated"
    layer.generator_id = generator.id
    generator.generated_layer_id = layer.id
    return layer

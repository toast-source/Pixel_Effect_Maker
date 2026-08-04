"""Deterministic emitter, transform, and Generated Layer tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.models.effect_generator import (
    Distribution,
    Easing,
    TransformEmitter,
    TransformEmitterSettings,
)
from app.models.project import Project
from app.models.source_asset import SourceAsset
from app.services.effect_render_service import (
    generate_emitter,
    render_generator_frames,
    render_transformed_source,
)
from app.services.emitter_service import build_instances, ease, normalized_lifetime


def patterned_asset(name: str = "Pattern") -> SourceAsset:
    pixels = np.zeros((3, 4, 4), dtype=np.uint8)
    pixels[0, 0] = [255, 0, 0, 255]
    pixels[0, -1] = [0, 255, 0, 255]
    pixels[-1, -1] = [0, 0, 255, 255]
    pixels[-1, 0] = [255, 255, 0, 255]
    pixels[1, 1:3] = [255, 0, 255, 255]
    return SourceAsset(name, pixels)


def project_with_emitter(**overrides):
    project = Project.create_default("Effect", 24, 24)
    asset = patterned_asset()
    project.source_assets.append(asset)
    values = dict(
        source_asset_id=asset.id,
        output_frames=6,
        instance_count=3,
        emission_interval=2,
        lifetime=3,
        origin_x=8,
        origin_y=8,
    )
    values.update(overrides)
    emitter = TransformEmitter("Transform Emitter 1", TransformEmitterSettings(**values))
    project.generators.append(emitter)
    return project, asset, emitter


def test_point_line_and_circle_distribution() -> None:
    point = TransformEmitterSettings("asset", instance_count=3, origin_x=2, origin_y=4)
    assert [(item.origin_x, item.origin_y) for item in build_instances(point)] == [(2, 4)] * 3
    point.distribution = Distribution.LINE.value
    point.line_end_x, point.line_end_y = 8, 10
    assert [(item.origin_x, item.origin_y) for item in build_instances(point)] == [(2, 4), (5, 7), (8, 10)]
    point.distribution = Distribution.CIRCLE.value
    point.origin_x = point.origin_y = 10
    point.radius = 4
    point.angle_start, point.angle_end = 0, 180
    origins = [(round(item.origin_x), round(item.origin_y)) for item in build_instances(point)]
    assert origins == [(14, 10), (10, 14), (6, 10)]


def test_emission_interval_lifetime_and_seed_are_deterministic() -> None:
    settings = TransformEmitterSettings(
        "asset", instance_count=3, start_frame=2, emission_interval=4, lifetime=3, seed=99
    )
    first = build_instances(settings)
    second = build_instances(settings)
    assert first == second
    assert [item.birth_frame for item in first] == [2, 6, 10]
    assert [item.random_seed for item in first] == [99, 100, 101]
    assert normalized_lifetime(first[0], 1) is None
    assert normalized_lifetime(first[0], 2) == 0.0
    assert normalized_lifetime(first[0], 4) == 1.0
    assert normalized_lifetime(first[0], 5) is None


def test_easing_curves() -> None:
    assert ease(0.5, Easing.LINEAR.value) == 0.5
    assert ease(0.5, Easing.EASE_IN.value) == 0.25
    assert ease(0.5, Easing.EASE_OUT.value) == 0.75


def test_position_rotation_scale_opacity_and_pivot_render() -> None:
    project, asset, emitter = project_with_emitter(
        instance_count=1,
        emission_interval=0,
        lifetime=3,
        output_frames=3,
        offset_x_end=8,
        rotation_end=90,
        scale_x_end=-1,
        scale_y_end=2,
        opacity_end=0.5,
    )
    before = asset.pixels.copy()
    frames = render_generator_frames(project, emitter)
    assert frames[0].shape == (24, 24, 4)
    assert frames[0][..., 3].max() == 255
    assert 126 <= frames[2][..., 3].max() <= 128
    x0 = np.argwhere(frames[0][..., 3] > 0)[:, 1].mean()
    x2 = np.argwhere(frames[2][..., 3] > 0)[:, 1].mean()
    assert x2 > x0 + 4
    assert not np.array_equal(frames[0], frames[2])
    assert np.array_equal(asset.pixels, before)


def test_rendered_frames_respect_start_emission_and_lifetime() -> None:
    project, asset, emitter = project_with_emitter(
        output_frames=7,
        instance_count=2,
        start_frame=1,
        emission_interval=2,
        lifetime=2,
    )
    frames = render_generator_frames(project, emitter)
    active = [index for index, frame in enumerate(frames) if frame[..., 3].any()]
    assert active == [1, 2, 3, 4]


def test_different_source_silhouettes_use_the_same_renderer() -> None:
    silhouettes = []
    square = np.zeros((5, 5, 4), dtype=np.uint8)
    square[1:4, 1:4] = [255, 40, 20, 255]
    silhouettes.append(square)
    ring = np.zeros((7, 7, 4), dtype=np.uint8)
    ring[[1, 5], 1:6] = [20, 255, 80, 255]
    ring[1:6, [1, 5]] = [20, 255, 80, 255]
    silhouettes.append(ring)
    line = np.zeros((3, 9, 4), dtype=np.uint8)
    line[1, :] = [30, 100, 255, 255]
    silhouettes.append(line)
    irregular = np.zeros((6, 6, 4), dtype=np.uint8)
    irregular[0, 1] = [220, 80, 255, 255]
    irregular[1:5, 2:4] = [220, 80, 255, 180]
    irregular[5, 4] = [220, 80, 255, 255]
    silhouettes.append(irregular)

    for index, pixels in enumerate(silhouettes):
        project = Project.create_default(f"Shape {index}", 24, 24)
        asset = SourceAsset(f"Shape {index}", pixels)
        project.source_assets.append(asset)
        emitter = TransformEmitter(
            f"Emitter {index}",
            TransformEmitterSettings(
                source_asset_id=asset.id,
                output_frames=2,
                lifetime=2,
                origin_x=12,
                origin_y=12,
                rotation_end=30,
            ),
        )
        project.generators.append(emitter)
        assert render_generator_frames(project, emitter)[0][..., 3].any()


@pytest.mark.parametrize(
    "field,value",
    [("horizontal_tilt", 0.8), ("vertical_tilt", -0.8), ("perspective", 0.8)],
)
def test_pseudo_3d_warps_corners_with_nearest_colors(field: str, value: float) -> None:
    asset = patterned_asset()
    baseline = np.zeros((24, 24, 4), dtype=np.uint8)
    warped = np.zeros_like(baseline)
    common = dict(
        position_x=12,
        position_y=12,
        rotation=0,
        scale_x=2,
        scale_y=2,
        horizontal_tilt=0,
        vertical_tilt=0,
        perspective=0,
        opacity=1,
    )
    render_transformed_source(baseline, asset, **common)
    common[field] = value
    render_transformed_source(warped, asset, **common)
    assert warped[..., 3].any()
    assert not np.array_equal(baseline, warped)
    source_colors = {tuple(color) for color in asset.pixels.reshape(-1, 4)}
    output_colors = {tuple(color) for color in warped.reshape(-1, 4)}
    assert output_colors <= source_colors


def test_extreme_warp_and_off_canvas_are_safe() -> None:
    canvas = np.zeros((8, 8, 4), dtype=np.uint8)
    render_transformed_source(
        canvas,
        patterned_asset(),
        position_x=-10000,
        position_y=10000,
        rotation=720,
        scale_x=-16,
        scale_y=16,
        horizontal_tilt=1,
        vertical_tilt=-1,
        perspective=1,
        opacity=1,
    )
    assert not canvas.any()


def test_generated_layer_replaces_only_its_own_pixels_and_extends_frames() -> None:
    project, asset, emitter = project_with_emitter(output_frames=6)
    manual_id = project.layers[0].id
    project.frames[0].layer_pixels[manual_id][0, 0] = [1, 2, 3, 255]
    original_source = asset.pixels.copy()
    layer = generate_emitter(project, emitter)
    assert layer.kind == "generated"
    assert layer.generator_id == emitter.id
    assert len(project.frames) == 6
    assert project.frames[0].layer_pixels[manual_id][0, 0].tolist() == [1, 2, 3, 255]
    first_result = [frame.layer_pixels[layer.id].copy() for frame in project.frames]

    other = project.add_layer("Generated: Other")
    project.frames[0].layer_pixels[other.id][0, 1] = [9, 9, 9, 255]
    emitter.settings.offset_x_start = emitter.settings.offset_x_end = 4
    regenerated = generate_emitter(project, emitter)
    assert regenerated.id == layer.id
    assert not np.array_equal(first_result[0], project.frames[0].layer_pixels[layer.id])
    assert project.frames[0].layer_pixels[other.id][0, 1].tolist() == [9, 9, 9, 255]
    assert np.array_equal(asset.pixels, original_source)


def test_generation_failure_preserves_previous_result(monkeypatch) -> None:
    project, asset, emitter = project_with_emitter(output_frames=2)
    layer = generate_emitter(project, emitter)
    before = [frame.layer_pixels[layer.id].copy() for frame in project.frames]

    def fail(*args, **kwargs):
        raise ValueError("render failed")

    monkeypatch.setattr(
        "app.services.effect_render_service.render_generator_frames", fail
    )
    with pytest.raises(ValueError, match="render failed"):
        generate_emitter(project, emitter)
    assert all(
        np.array_equal(frame.layer_pixels[layer.id], pixels)
        for frame, pixels in zip(project.frames, before, strict=True)
    )


def test_deleting_generated_layer_clears_generator_link() -> None:
    project, asset, emitter = project_with_emitter(output_frames=2)
    layer = generate_emitter(project, emitter)
    project.delete_layer(project.layers.index(layer))
    assert emitter.generated_layer_id is None
    regenerated = generate_emitter(project, emitter)
    assert regenerated.id != layer.id

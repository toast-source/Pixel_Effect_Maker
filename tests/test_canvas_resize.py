"""Tests for atomic canvas-only resizing and nearest-neighbor scaling."""

from __future__ import annotations

import numpy as np
import pytest

from app.models.project import Project
from app.services.canvas_resize_service import (
    CanvasAnchor,
    CanvasResizeError,
    resize_canvas,
    scale_project,
)
from app.services.project_io import load_project, save_project


def colored_project(width: int = 2, height: int = 2) -> tuple[Project, str]:
    project = Project.create_default("Colors", width, height)
    layer_id = project.layers[0].id
    pixels = project.frames[0].layer_pixels[layer_id]
    pixels[0, 0] = [255, 0, 0, 255]
    pixels[0, width - 1] = [0, 255, 0, 255]
    pixels[height - 1, 0] = [0, 0, 255, 255]
    pixels[height - 1, width - 1] = [255, 255, 0, 128]
    return project, layer_id


@pytest.mark.parametrize(
    ("anchor", "expected_y", "expected_x"),
    [
        (CanvasAnchor.TOP_LEFT, 0, 0),
        (CanvasAnchor.CENTER, 1, 1),
        (CanvasAnchor.BOTTOM_RIGHT, 3, 3),
    ],
)
def test_canvas_resize_expansion_anchors(anchor, expected_y, expected_x) -> None:
    project, layer_id = colored_project()
    source = project.frames[0].layer_pixels[layer_id].copy()
    resize_canvas(project, 5, 5, anchor)
    output = project.frames[0].layer_pixels[layer_id]
    assert output.shape == (5, 5, 4)
    assert np.array_equal(
        output[expected_y : expected_y + 2, expected_x : expected_x + 2], source
    )
    assert np.count_nonzero(output[..., 3]) == 4


def test_canvas_resize_odd_center_rule_and_non_square_size() -> None:
    project, layer_id = colored_project(3, 3)
    source = project.frames[0].layer_pixels[layer_id].copy()
    resize_canvas(project, 6, 4, CanvasAnchor.CENTER)
    output = project.frames[0].layer_pixels[layer_id]
    # (6-3)//2 == 1 and (4-3)//2 == 0: extra pixels go right/bottom.
    assert np.array_equal(output[0:3, 1:4], source)
    assert (project.width, project.height) == (6, 4)


def test_canvas_resize_shrink_crops_from_anchor() -> None:
    project = Project.create_default(width=5, height=3)
    layer_id = project.layers[0].id
    pixels = project.frames[0].layer_pixels[layer_id]
    for x in range(5):
        pixels[:, x] = [x, x + 10, x + 20, 255]
    resize_canvas(project, 2, 3, CanvasAnchor.CENTER)
    output = project.frames[0].layer_pixels[layer_id]
    # (2-5)//2 == -2, so source columns 2 and 3 are retained.
    assert output[0, :, 0].tolist() == [2, 3]


def test_canvas_resize_applies_to_every_frame_and_layer_without_sharing() -> None:
    project = Project.create_default(width=2, height=2)
    second_layer = project.add_layer()
    project.add_frame()
    originals: list[np.ndarray] = []
    for frame_index, frame in enumerate(project.frames):
        for layer_index, layer in enumerate(project.layers):
            pixels = frame.layer_pixels[layer.id]
            pixels[0, 0] = [frame_index, layer_index, 99, 255]
            originals.append(pixels)
    resize_canvas(project, 4, 3, CanvasAnchor.TOP_LEFT)
    outputs = [
        frame.layer_pixels[layer.id]
        for frame in project.frames
        for layer in project.layers
    ]
    assert all(output.shape == (3, 4, 4) for output in outputs)
    assert all(not np.shares_memory(old, new) for old, new in zip(originals, outputs))
    assert not np.shares_memory(
        project.frames[0].layer_pixels[second_layer.id],
        project.frames[1].layer_pixels[second_layer.id],
    )


def test_nearest_neighbor_scale_two_by_two_to_four_by_four() -> None:
    project, layer_id = colored_project()
    source = project.frames[0].layer_pixels[layer_id].copy()
    scale_project(project, 4, 4)
    output = project.frames[0].layer_pixels[layer_id]
    expected = source.repeat(2, axis=0).repeat(2, axis=1)
    assert np.array_equal(output, expected)
    assert set(np.unique(output[..., 3])).issubset({128, 255})


def test_nearest_neighbor_scale_non_uniform_and_transparent() -> None:
    project = Project.create_default(width=2, height=2)
    layer_id = project.layers[0].id
    pixels = project.frames[0].layer_pixels[layer_id]
    pixels[0, 0] = [10, 20, 30, 255]
    original = pixels
    scale_project(project, 4, 2)
    output = project.frames[0].layer_pixels[layer_id]
    assert output.shape == (2, 4, 4)
    assert output[0, :2].tolist() == [[10, 20, 30, 255]] * 2
    assert not output[1].any()
    assert not np.shares_memory(original, output)


def test_resize_failure_is_atomic() -> None:
    project, layer_id = colored_project()
    project.add_frame()
    valid_before = project.frames[0].layer_pixels[layer_id].copy()
    project.frames[1].layer_pixels[layer_id] = np.zeros((1, 1, 4), dtype=np.uint8)
    with pytest.raises(CanvasResizeError, match="invalid pixels"):
        resize_canvas(project, 8, 8, CanvasAnchor.CENTER)
    assert (project.width, project.height) == (2, 2)
    assert np.array_equal(project.frames[0].layer_pixels[layer_id], valid_before)
    assert project.frames[1].layer_pixels[layer_id].shape == (1, 1, 4)


@pytest.mark.parametrize("operation", [resize_canvas, scale_project])
def test_invalid_dimensions_do_not_change_project(operation) -> None:
    project, layer_id = colored_project()
    before = project.frames[0].layer_pixels[layer_id].copy()
    if operation is resize_canvas:
        with pytest.raises(CanvasResizeError):
            operation(project, 0, 4, CanvasAnchor.CENTER)
    else:
        with pytest.raises(CanvasResizeError):
            operation(project, 0, 4)
    assert (project.width, project.height) == (2, 2)
    assert np.array_equal(project.frames[0].layer_pixels[layer_id], before)


def test_resized_project_round_trip(tmp_path) -> None:
    project, layer_id = colored_project()
    resize_canvas(project, 5, 4, CanvasAnchor.BOTTOM_RIGHT)
    path = save_project(project, tmp_path / "resized.peffect.json")
    loaded = load_project(path)
    assert (loaded.width, loaded.height) == (5, 4)
    assert np.array_equal(
        loaded.frames[0].layer_pixels[loaded.layers[0].id],
        project.frames[0].layer_pixels[layer_id],
    )


def test_scaled_project_round_trip(tmp_path) -> None:
    project, layer_id = colored_project()
    scale_project(project, 5, 3)
    path = save_project(project, tmp_path / "scaled.peffect.json")
    loaded = load_project(path)
    assert (loaded.width, loaded.height) == (5, 3)
    assert np.array_equal(
        loaded.frames[0].layer_pixels[loaded.layers[0].id],
        project.frames[0].layer_pixels[layer_id],
    )

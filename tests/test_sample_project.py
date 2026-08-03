"""Tests for the built-in playback diagnostic project."""

from __future__ import annotations

import numpy as np

from app.services.export_service import export_png_frames
from app.services.project_io import load_project, save_project
from app.services.sample_project_service import create_playback_test_project


def test_playback_project_structure_and_motion() -> None:
    project = create_playback_test_project()
    assert project.name == "Playback Test"
    assert (project.width, project.height, project.fps, project.loop) == (64, 64, 12, True)
    assert len(project.layers) == 1
    assert project.layers[0].name == "Playback Test"
    assert len(project.frames) == 8
    layer_id = project.layers[0].id
    positions: list[tuple[int, int]] = []
    arrays = []
    for frame in project.frames:
        pixels = frame.layer_pixels[layer_id]
        arrays.append(pixels)
        opaque_y, opaque_x = np.nonzero(pixels[..., 3])
        assert len(opaque_x) == 64
        assert opaque_x.min() >= 0 and opaque_x.max() < 64
        assert opaque_y.min() >= 0 and opaque_y.max() < 64
        positions.append((int(opaque_x.min()), int(opaque_y.min())))
    assert len(set(positions)) == 8
    assert all(not np.shares_memory(a, b) for a, b in zip(arrays, arrays[1:]))


def test_playback_project_uses_normal_save_and_export(tmp_path) -> None:
    project = create_playback_test_project()
    loaded = load_project(save_project(project, tmp_path / "playback.peffect.json"))
    assert len(loaded.frames) == 8
    exported = export_png_frames(loaded, tmp_path / "png")
    assert len(exported) == 8
    assert all(path.exists() for path in exported)

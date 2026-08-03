"""Tests for the UI-independent project model."""

import numpy as np
import pytest

from app.models.project import Project, ProjectError


def test_default_project_creation() -> None:
    project = Project.create_default()
    assert project.name == "Untitled"
    assert (project.width, project.height) == (64, 64)
    assert project.fps == 12
    assert len(project.layers) == 1
    assert len(project.frames) == 1


def test_canvas_size_and_fps_are_serialized() -> None:
    project = Project.create_default(width=32, height=48)
    project.fps = 24
    data = project.to_dict()
    assert data["canvas"] == {"width": 32, "height": 48}
    assert data["animation"]["fps"] == 24


def test_add_and_delete_layer() -> None:
    project = Project.create_default()
    layer = project.add_layer("Glow")
    assert layer.id in project.frames[0].layer_pixels
    project.delete_layer(1)
    assert [item.name for item in project.layers] == ["Layer 1"]
    assert layer.id not in project.frames[0].layer_pixels


def test_cannot_delete_only_layer() -> None:
    project = Project.create_default()
    with pytest.raises(ProjectError, match="at least one layer"):
        project.delete_layer(0)


def test_add_duplicate_and_delete_frame() -> None:
    project = Project.create_default(width=4, height=4)
    layer_id = project.layers[0].id
    project.frames[0].layer_pixels[layer_id][1, 2] = [255, 20, 5, 255]
    project.duplicate_frame(0)
    assert len(project.frames) == 2
    assert project.frames[1].name == project.frames[0].name
    assert "Copy" not in project.frames[1].name
    assert np.array_equal(
        project.frames[0].layer_pixels[layer_id],
        project.frames[1].layer_pixels[layer_id],
    )
    project.frames[1].layer_pixels[layer_id][1, 2] = [0, 0, 0, 0]
    assert project.frames[0].layer_pixels[layer_id][1, 2, 3] == 255
    project.add_frame()
    project.delete_frame(2)
    assert len(project.frames) == 2


def test_repeated_frame_duplication_never_accumulates_copy() -> None:
    project = Project.create_default()
    for index in range(4):
        project.duplicate_frame(index)
    assert len(project.frames) == 5
    assert all("Copy" not in frame.name for frame in project.frames)


def test_default_layer_names_remain_unique_after_deletion() -> None:
    project = Project.create_default()
    project.add_layer()
    project.add_layer()
    project.delete_layer(1)
    new_layer = project.add_layer()
    assert new_layer.name == "Layer 2"
    assert len({layer.name for layer in project.layers}) == len(project.layers)


def test_custom_layer_names_are_not_rewritten() -> None:
    project = Project.create_default()
    custom = project.add_layer("Manual Edit")
    project.add_layer()
    assert custom.name == "Manual Edit"


def test_cannot_delete_only_frame() -> None:
    project = Project.create_default()
    with pytest.raises(ProjectError, match="at least one frame"):
        project.delete_frame(0)


def test_insert_empty_frame_after_current() -> None:
    project = Project.create_default(width=2, height=2)
    project.add_frame()
    layer_id = project.layers[0].id
    project.frames[0].layer_pixels[layer_id][0, 0] = [1, 2, 3, 255]
    inserted = project.insert_empty_frame(0)
    assert project.frames[1] is inserted
    assert len(project.frames) == 3
    assert not inserted.layer_pixels[layer_id].any()

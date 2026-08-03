"""Tests for project JSON persistence and validation."""

import json

import numpy as np
import pytest

from app.models.project import Project
from app.services.project_io import ProjectIOError, load_project, save_project
from app.services.export_service import export_png_frames


def test_json_round_trip(tmp_path) -> None:
    project = Project.create_default("Spark", 8, 12)
    project.fps = 30
    project.add_layer("Glow")
    pixels = project.frames[0].layer_pixels[project.layers[1].id]
    pixels[2, 3] = [10, 20, 30, 200]
    destination = save_project(project, tmp_path / "spark.peffect.json")
    loaded = load_project(destination)
    assert loaded.name == "Spark"
    assert (loaded.width, loaded.height, loaded.fps) == (8, 12, 30)
    assert [layer.name for layer in loaded.layers] == ["Layer 1", "Glow"]
    assert np.array_equal(
        loaded.frames[0].layer_pixels[loaded.layers[1].id], pixels
    )


def test_save_adds_project_extension(tmp_path) -> None:
    destination = save_project(Project.create_default(), tmp_path / "effect")
    assert destination.name == "effect.peffect.json"


@pytest.mark.parametrize("contents", ["not json", "[]", '{"format_version": 1}'])
def test_invalid_project_file(tmp_path, contents: str) -> None:
    path = tmp_path / "bad.peffect.json"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ProjectIOError, match="could not load project"):
        load_project(path)


def test_unsupported_format_version(tmp_path) -> None:
    data = Project.create_default().to_dict()
    data["format_version"] = 99
    path = tmp_path / "future.peffect.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProjectIOError, match="unsupported format_version"):
        load_project(path)


def test_transparent_png_export(tmp_path) -> None:
    project = Project.create_default("Empty", 3, 2)
    written = export_png_frames(project, tmp_path / "png")
    assert [path.name for path in written] == ["Empty_001.png"]
    from PIL import Image

    with Image.open(written[0]) as image:
        assert image.mode == "RGBA"
        assert image.size == (3, 2)
        assert image.getpixel((0, 0)) == (0, 0, 0, 0)


def test_duplicated_frame_order_and_pixels_survive_round_trip(tmp_path) -> None:
    project = Project.create_default("Ordered", 4, 4)
    layer_id = project.layers[0].id
    project.add_frame()
    project.frames[1].layer_pixels[layer_id][0, 0] = [1, 2, 3, 255]
    duplicate = project.duplicate_frame(1)
    duplicate.layer_pixels[layer_id][1, 1] = [9, 8, 7, 255]

    loaded = load_project(save_project(project, tmp_path / "ordered.peffect.json"))

    assert len(loaded.frames) == 3
    loaded_layer_id = loaded.layers[0].id
    assert loaded.frames[1].layer_pixels[loaded_layer_id][0, 0].tolist() == [1, 2, 3, 255]
    assert loaded.frames[2].layer_pixels[loaded_layer_id][1, 1].tolist() == [9, 8, 7, 255]

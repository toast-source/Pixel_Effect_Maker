"""Source import and format-v1 migration regressions."""

from __future__ import annotations

import json

import numpy as np
import pytest
from PIL import Image

from app.models.effect_generator import TransformEmitter, TransformEmitterSettings
from app.models.project import FORMAT_VERSION, Project
from app.services.project_io import ProjectIOError, load_project, save_project
from app.services.source_import_service import SourceImportError, import_source_asset


@pytest.mark.parametrize("mode", ["RGBA", "RGB", "P", "L"])
def test_png_modes_import_as_independent_rgba(tmp_path, mode: str) -> None:
    path = tmp_path / f"source_{mode}.png"
    if mode == "P":
        image = Image.new("P", (3, 2))
        image.putpalette([255, 0, 0, 0, 255, 0] + [0] * 762)
        image.putdata([0, 1, 0, 1, 0, 1])
        image.info["transparency"] = 0
    elif mode == "L":
        image = Image.new("L", (3, 2), 127)
    else:
        color = (10, 20, 30, 90) if mode == "RGBA" else (10, 20, 30)
        image = Image.new(mode, (3, 2), color)
    image.save(path)
    asset = import_source_asset(path)
    assert asset.pixels.shape == (2, 3, 4)
    assert asset.pixels.dtype == np.uint8
    assert (asset.pivot_x, asset.pivot_y) == (1.5, 1.0)
    assert asset.source_path == str(path.resolve())
    if mode == "RGBA":
        assert asset.pixels[0, 0].tolist() == [10, 20, 30, 90]
    imported = asset.pixels.copy()
    image.close()
    path.unlink()
    assert np.array_equal(asset.pixels, imported)


def test_invalid_or_non_png_source_is_rejected(tmp_path) -> None:
    bad = tmp_path / "bad.png"
    bad.write_text("not an image", encoding="utf-8")
    with pytest.raises(SourceImportError, match="could not import PNG"):
        import_source_asset(bad)
    wrong = tmp_path / "source.jpg"
    Image.new("RGB", (2, 2)).save(wrong)
    with pytest.raises(SourceImportError, match="only PNG"):
        import_source_asset(wrong)


def test_format_one_migrates_without_changing_frames_or_layers(tmp_path) -> None:
    project = Project.create_default("Legacy", 3, 2)
    layer_id = project.layers[0].id
    project.frames[0].layer_pixels[layer_id][1, 2] = [7, 8, 9, 255]
    legacy = project.to_dict()
    legacy["format_version"] = 1
    legacy.pop("source_assets")
    legacy.pop("generators")
    for layer in legacy["layers"]:
        layer.pop("kind")
        layer.pop("generator_id")
    path = tmp_path / "legacy.peffect.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")
    loaded = load_project(path)
    assert loaded.format_version == FORMAT_VERSION == 5
    assert loaded.source_assets == []
    assert loaded.generators == []
    assert loaded.layers[0].name == "Layer 1"
    assert loaded.frames[0].layer_pixels[layer_id][1, 2].tolist() == [7, 8, 9, 255]


def test_v2_embeds_source_and_generator_after_external_file_deletion(tmp_path) -> None:
    source_path = tmp_path / "ring.png"
    pixels = np.zeros((5, 5, 4), dtype=np.uint8)
    pixels[[0, -1], :, :] = [200, 30, 10, 255]
    pixels[:, [0, -1], :] = [200, 30, 10, 255]
    Image.fromarray(pixels, "RGBA").save(source_path)
    asset = import_source_asset(source_path)
    project = Project.create_default("Embedded", 16, 16)
    project.source_assets.append(asset)
    emitter = TransformEmitter(
        "Transform Emitter 1",
        TransformEmitterSettings(source_asset_id=asset.id, output_frames=3),
    )
    project.generators.append(emitter)
    destination = save_project(project, tmp_path / "embedded.peffect.json")
    source_path.unlink()
    loaded = load_project(destination)
    assert np.array_equal(loaded.source_assets[0].pixels, pixels)
    assert loaded.generators[0].settings.source_asset_id == asset.id
    loaded.source_assets[0].pixels[0, 0] = 0
    assert pixels[0, 0, 3] == 255


def test_future_project_format_is_still_rejected(tmp_path) -> None:
    data = Project.create_default().to_dict()
    data["format_version"] = FORMAT_VERSION + 1
    path = tmp_path / "future.peffect.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProjectIOError, match="unsupported format_version"):
        load_project(path)

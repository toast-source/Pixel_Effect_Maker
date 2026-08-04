"""Offscreen Source Asset to Generated Layer UI flow."""

from __future__ import annotations

import os

import numpy as np
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from app.models.effect_generator import Distribution
from app.services.project_io import load_project, save_project
from app.services.settings_service import ShortcutSettingsService
from app.ui.main_window import MainWindow


APPLICATION = QApplication.instance() or QApplication([])


def service_for(tmp_path) -> ShortcutSettingsService:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("ui/language", "en")
    return ShortcutSettingsService(settings)


def test_full_ui_pipeline_import_emit_generate_and_round_trip(tmp_path) -> None:
    path = tmp_path / "irregular.png"
    pixels = np.zeros((4, 5, 4), dtype=np.uint8)
    pixels[0, 1] = [255, 100, 20, 255]
    pixels[1:4, 2:5] = [30, 180, 255, 200]
    Image.fromarray(pixels, "RGBA").save(path)
    window = MainWindow(service_for(tmp_path))
    assert window.effect_library is not None
    assert window.effect_properties is not None
    assert window.import_source_action.text() == "Import Source Asset…"
    asset = window.import_source_asset_path(path)
    assert asset is not None
    assert window.effect_library.asset_list.count() == 1
    assert window.effect_library.source_preview.pixmap() is not None
    emitter = window.add_transform_emitter()
    assert emitter is not None
    assert window.effect_library.generator_list.count() == 1
    assert window.effect_properties.generator_id == emitter.id
    window.effect_properties.distribution_combo.setCurrentText(Distribution.LINE.value)
    assert window.effect_properties.line_end_x.isVisibleTo(window.effect_properties.widget())
    settings = window.effect_properties.current_settings()
    settings.output_frames = 4
    settings.instance_count = 2
    settings.lifetime = 4
    assert window.generate_effect(emitter.id, settings)
    assert len(window.project.frames) == 4
    generated = next(layer for layer in window.project.layers if layer.kind == "generated")
    assert any(frame.layer_pixels[generated.id][..., 3].any() for frame in window.project.frames)
    saved = save_project(window.project, tmp_path / "ui-flow.peffect.json")
    loaded = load_project(saved)
    assert len(loaded.source_assets) == 1
    assert len(loaded.generators) == 1
    assert loaded.generators[0].generated_layer_id == generated.id
    assert any(frame.layer_pixels[generated.id][..., 3].any() for frame in loaded.frames)
    window.dirty = False
    window.close()


def test_no_source_disables_transform_emitter_creation(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    assert not window.effect_library.add_emitter_button.isEnabled()
    assert window.project.generators == []
    window.close()


def test_in_use_source_is_protected_and_generator_delete_removes_its_layer(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "source.png"
    Image.new("RGBA", (3, 3), (255, 255, 255, 255)).save(path)
    window = MainWindow(service_for(tmp_path))
    asset = window.import_source_asset_path(path)
    assert asset is not None
    emitter = window.add_transform_emitter()
    assert emitter is not None
    settings = window.effect_properties.current_settings()
    settings.output_frames = 2
    assert window.generate_effect(emitter.id, settings)
    layer_id = emitter.generated_layer_id
    warnings = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: warnings.append(args[2]),
    )
    window.delete_source_asset(asset.id)
    assert warnings
    assert asset in window.project.source_assets

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    window.delete_generator(emitter.id)
    assert emitter not in window.project.generators
    assert all(layer.id != layer_id for layer in window.project.layers)
    window.dirty = False
    window.close()


def test_reset_settings_restores_safe_defaults_without_regenerating(tmp_path) -> None:
    path = tmp_path / "source.png"
    Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(path)
    window = MainWindow(service_for(tmp_path))
    window.import_source_asset_path(path)
    emitter = window.add_transform_emitter()
    assert emitter is not None
    emitter.settings.scale_x_start = 4.0
    window.reset_generator_settings(emitter.id)
    assert emitter.settings.scale_x_start == 4.0
    assert window.preview_manager.drafts[emitter.id].settings.scale_x_start == 1.0
    assert emitter.generated_layer_id is None
    assert "Apply to Frames" in window.effect_properties.settings_status.text()
    window.dirty = False
    window.close()

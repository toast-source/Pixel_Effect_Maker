from __future__ import annotations

import os

import numpy as np
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.services.localization_service import LocalizationService
from app.services.particle_render_service import apply_particle_frames, render_particle_frames
from app.services.preview_export_service import export_preview_sequence
from app.services.project_io import load_project, save_project
from app.services.settings_service import ShortcutSettingsService
from app.ui.main_window import MainWindow
from app.ui.resource_editor_widget import AddPropertyDialog


APPLICATION = QApplication.instance() or QApplication([])


def service(tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("ui/language", "en")
    return ShortcutSettingsService(settings)


def test_required_png_composition_particle_bake_export_round_trip(tmp_path):
    path = tmp_path / "a.png"
    pixels = np.zeros((5, 3, 4), dtype=np.uint8)
    pixels[0, 1] = [255, 80, 20, 255]
    pixels[2:5, 1] = [20, 180, 255, 255]
    Image.fromarray(pixels, "RGBA").save(path)

    window = MainWindow(service(tmp_path))
    asset = window.import_resources([path])[0]
    editor = window.resource_editor
    composition = editor.create_composition("A", 64, 64, 12, 12, True)
    layer = editor.add_selected_asset()
    assert layer.source_id == asset.id and layer.end_frame == 11

    editor.add_property_to_layer("rotation")
    editor.set_frame(0)
    editor.set_keyframe("rotation", 0, "Linear")
    editor.set_frame(11)
    editor.set_keyframe("rotation", 360, "Linear")
    assert [key.value for key in layer.tracks["rotation"].keyframes] == [0, 360]

    editor.toggle_play()
    assert editor.timer.interval() == 83
    editor.stop()

    emitter = window.create_particle_from_resource("resource_composition", composition.id)
    window.select_particle_emitter(emitter.id)
    assert tuple(window.particle_properties.clip.currentData()) == ("resource_composition", composition.id)
    output = render_particle_frames(window.project, emitter)
    assert output and any(frame[..., 3].any() for frame in output)
    layer_out = apply_particle_frames(window.project, emitter, output)
    assert layer_out.generator_id == emitter.id
    exported = export_preview_sequence(output[:2], tmp_path / "sequence", "A Particle")
    assert [item.name for item in exported] == ["A_Particle_0001.png", "A_Particle_0002.png"]

    saved = save_project(window.project, tmp_path / "composition.peffect.json")
    loaded = load_project(saved)
    loaded_track = loaded.resource_compositions[0].layers[0].tracks["rotation"]
    assert loaded_track.keyframes[-1].value == 360
    window.dirty = False
    window.close()


def test_property_search_is_bilingual_and_full_rotation_directions(tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    localization = LocalizationService(settings, system_locale="en_US")
    dialog = AddPropertyDialog({}, localization)
    dialog.search.setText("spin")
    assert dialog.results.count() == 1 and dialog.results.item(0).data(256) == "rotation"
    localization.set_language("ko")
    dialog.search.setText("회전")
    assert dialog.results.count() == 1

    window = MainWindow(service(tmp_path))
    path = tmp_path / "pixel.png"
    Image.new("RGBA", (1, 1), (255, 255, 255, 255)).save(path)
    window.import_resources([path])
    editor = window.resource_editor
    editor.create_composition("Spin", 16, 16, 12, 12, True)
    layer = editor.add_selected_asset()
    editor.add_full_rotation(clockwise=False, turns=2)
    assert [key.value for key in layer.tracks["rotation"].keyframes] == [0, -720]
    window.dirty = False
    window.close()


def test_gizmo_auto_track_and_cancel_restore(tmp_path):
    window = MainWindow(service(tmp_path))
    path = tmp_path / "pixel.png"
    Image.new("RGBA", (2, 2), (255, 255, 255, 255)).save(path)
    window.import_resources([path])
    editor = window.resource_editor
    editor.create_composition("Gizmo", 16, 16, 12, 12, True)
    layer = editor.add_selected_asset()

    editor._gizmo_change("rotation", 45.0, False)
    assert layer.tracks["rotation"].evaluate(0) == 45.0
    editor._gizmo_cancel("rotation", 0.0)
    assert "rotation" not in layer.tracks
    editor._gizmo_change("position", [3.0, -2.0], True)
    assert layer.tracks["position"].evaluate(0) == [3.0, -2.0]
    window.dirty = False
    window.close()

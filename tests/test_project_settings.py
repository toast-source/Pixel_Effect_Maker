"""Offscreen tests for editable project settings and safe application."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.services.canvas_resize_service import CanvasAnchor, CanvasResizeMode
from app.services.settings_service import ShortcutSettingsService
from app.ui.main_window import MainWindow
from app.ui.project_settings_dialog import (
    ProjectSettingsDialog,
    ProjectSettingsValues,
)

APPLICATION = QApplication.instance() or QApplication([])


def service_for(tmp_path) -> ShortcutSettingsService:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    return ShortcutSettingsService(settings)


def values_for(window: MainWindow, **changes) -> ProjectSettingsValues:
    values = {
        "name": window.project.name,
        "fps": window.project.fps,
        "loop": window.project.loop,
        "width": window.project.width,
        "height": window.project.height,
        "resize_mode": CanvasResizeMode.CANVAS_ONLY,
        "anchor": CanvasAnchor.CENTER,
    }
    values.update(changes)
    return ProjectSettingsValues(**values)


def test_project_settings_dialog_defaults(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    dialog = window.create_project_settings_dialog()
    settings = dialog.settings()
    assert settings == values_for(window)
    assert dialog.anchor_buttons.checkedButton().toolTip() == "Center"
    assert dialog.canvas_only_radio.isChecked()
    assert dialog.apply_button.isEnabled()
    window.close()


def test_project_settings_dialog_apply_stays_open_and_cancel_discards_pending() -> None:
    calls: list[ProjectSettingsValues] = []
    from app.models.project import Project

    project = Project.create_default()
    dialog = ProjectSettingsDialog(project, None, lambda values: calls.append(values) or True)
    dialog.name_edit.setText("  Changed  ")
    dialog.width_spin.setValue(96)
    dialog.fps_spin.setValue(24)
    dialog.loop_check.setChecked(False)
    assert dialog.apply_changes()
    assert calls[-1].name == "Changed"
    assert calls[-1].width == 96
    assert calls[-1].fps == 24
    assert not calls[-1].loop
    assert dialog.result() == 0
    assert dialog.current_size_label.text() == "96 × 64"

    pending = ProjectSettingsDialog(project, None, lambda values: calls.append(values) or True)
    count = len(calls)
    pending.name_edit.setText("Not Applied")
    pending.reject()
    assert len(calls) == count
    assert project.name == "Untitled"


def test_no_change_does_not_mark_project_modified(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    assert window.apply_project_settings(values_for(window))
    assert not window.dirty
    window.close()


def test_general_settings_apply_and_update_running_timer(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    window.set_playing(True)
    assert window.apply_project_settings(
        values_for(window, name="Burst", fps=20, loop=False)
    )
    assert (window.project.name, window.project.fps, window.project.loop) == (
        "Burst",
        20,
        False,
    )
    assert window.play_timer.interval() == 50
    assert "Burst*" in window.windowTitle()
    window.set_playing(False)
    window.dirty = False
    window.close()


def test_canvas_expansion_applies_without_warning_when_clean(tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    layer_id = window.project.layers[0].id
    window.project.frames[0].layer_pixels[layer_id][0, 0] = [1, 2, 3, 255]
    assert window.apply_project_settings(
        values_for(window, width=66, height=65, anchor=CanvasAnchor.TOP_LEFT)
    )
    assert (window.project.width, window.project.height) == (66, 65)
    assert window.project.frames[0].layer_pixels[layer_id][0, 0].tolist() == [1, 2, 3, 255]
    assert window.dirty
    window.dirty = False
    window.close()


def test_dangerous_canvas_change_cancel_is_atomic(tmp_path, monkeypatch) -> None:
    window = MainWindow(service_for(tmp_path))
    layer_id = window.project.layers[0].id
    before = window.project.frames[0].layer_pixels[layer_id]
    monkeypatch.setattr(window, "_confirm_canvas_change", lambda values: False)
    applied = window.apply_project_settings(
        values_for(
            window,
            width=32,
            height=32,
            resize_mode=CanvasResizeMode.SCALE,
        )
    )
    assert not applied
    assert (window.project.width, window.project.height) == (64, 64)
    assert window.project.frames[0].layer_pixels[layer_id] is before
    assert not window.dirty
    window.close()


def test_confirmed_scale_applies_through_project_settings(tmp_path, monkeypatch) -> None:
    window = MainWindow(service_for(tmp_path))
    layer_id = window.project.layers[0].id
    pixels = window.project.frames[0].layer_pixels[layer_id]
    pixels[0:32, 0:32] = [11, 22, 33, 255]
    monkeypatch.setattr(window, "_confirm_canvas_change", lambda values: True)
    assert window.apply_project_settings(
        values_for(
            window,
            width=32,
            height=32,
            resize_mode=CanvasResizeMode.SCALE,
        )
    )
    assert window.project.frames[0].layer_pixels[layer_id].shape == (32, 32, 4)
    assert window.project.frames[0].layer_pixels[layer_id][0, 0].tolist() == [11, 22, 33, 255]
    window.dirty = False
    window.close()

"""Offscreen tests for shortcuts, compact layout, and project information."""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.services.settings_service import ShortcutSettingsService
from app.shortcuts import (
    DEFAULT_SHORTCUTS,
    ShortcutConfigurationError,
)
from app.ui.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
from app.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def application() -> QApplication:
    return QApplication.instance() or QApplication([])


def service_for(tmp_path) -> ShortcutSettingsService:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("ui/language", "en")
    return ShortcutSettingsService(settings)


def portable(sequence: QKeySequence) -> str:
    return sequence.toString(QKeySequence.SequenceFormat.PortableText)


def test_shortcut_defaults_and_persistence(tmp_path) -> None:
    service = service_for(tmp_path)
    assert service.load() == DEFAULT_SHORTCUTS
    changed = {
        "new_layer": "Ctrl+Shift+L",
        "new_frame": "Ctrl+Alt+N",
        "new_empty_frame": "",
        "play_stop_animation": "Space",
    }
    normalized = service.save(changed)
    assert normalized["new_layer"] == ["Ctrl+Shift+L"]
    assert normalized["new_frame"] == ["Ctrl+Alt+N"]
    assert normalized["new_empty_frame"] == []
    assert normalized["play_stop_animation"] == ["Space"]
    assert normalized["previous_frame"] == ["Left", "<"]
    assert service_for(tmp_path).load() == normalized


def test_duplicate_shortcuts_are_not_saved(tmp_path) -> None:
    service = service_for(tmp_path)
    with pytest.raises(ShortcutConfigurationError, match="assigned to both"):
        service.save(
            {
                "new_layer": "Shift+N",
                "new_frame": "Shift+N",
                "new_empty_frame": "Alt+B",
                "play_stop_animation": "Enter",
            }
        )
    assert service.load() == DEFAULT_SHORTCUTS


def test_alternate_shortcut_conflicts_are_rejected(tmp_path) -> None:
    service = service_for(tmp_path)
    changed = {key: list(value) for key, value in DEFAULT_SHORTCUTS.items()}
    changed["previous_frame"] = ["Left", "Space"]
    changed["play_stop_animation"] = ["Space"]
    with pytest.raises(ShortcutConfigurationError, match="assigned to both"):
        service.save(changed)


def test_corrupt_or_conflicting_settings_recover_to_defaults(tmp_path) -> None:
    service = service_for(tmp_path)
    service.settings.setValue("keyboard_shortcuts/new_layer", "Alt+N")
    service.settings.setValue("keyboard_shortcuts/new_frame", "Alt+N")
    service.settings.sync()
    assert service.load() == DEFAULT_SHORTCUTS
    assert service_for(tmp_path).load() == DEFAULT_SHORTCUTS


def test_existing_shortcuts_gain_playback_default_without_reset(tmp_path) -> None:
    service = service_for(tmp_path)
    existing = {
        "new_layer": "Ctrl+Shift+L",
        "new_frame": "Ctrl+Alt+N",
        "new_empty_frame": "Space",
    }
    for key, value in existing.items():
        service.settings.setValue(f"keyboard_shortcuts/{key}", value)
    service.settings.sync()
    loaded = service.load()
    assert {key: loaded[key] for key in existing} == {
        key: [value] for key, value in existing.items()
    }
    assert loaded["play_stop_animation"] == ["Enter"]
    assert service.settings.contains("keyboard_shortcuts/play_stop_animation")


def test_shortcut_dialog_blocks_conflicts_and_restores_defaults(application) -> None:
    dialog = KeyboardShortcutsDialog(dict(DEFAULT_SHORTCUTS))
    dialog.editors["new_frame"].setKeySequence(QKeySequence("Shift+N"))
    assert not dialog.apply_changes()
    assert "assigned to both" in dialog.error_label.text()
    dialog.editors["new_layer"].clear()
    dialog.restore_defaults()
    assert dialog.current_shortcuts() == DEFAULT_SHORTCUTS


def test_main_window_has_compact_canvas_timeline_layout(application, tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    assert not hasattr(window, "layer_panel")
    assert not hasattr(window, "properties")
    assert window.centralWidget().layout().count() == 2
    assert window.project_settings_action.text() == "Project Settings…"
    assert not hasattr(window, "project_info_action")
    assert window.keyboard_shortcuts_action.text() == "Keyboard Shortcuts…"
    window.close()


def test_default_shortcuts_are_shown_on_single_actions(application, tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    assert portable(window.new_layer_action.shortcut()) == "Shift+N"
    assert portable(window.new_frame_action.shortcut()) == "Alt+N"
    assert portable(window.new_empty_frame_action.shortcut()) == "Alt+B"
    assert window.play_action.shortcut().isEmpty()
    assert window.playback_shortcut_controller.sequence_text == "Enter"
    assert window.playback_shortcut_controller.active_shortcut_count() == 2
    playback_shortcuts = window.findChildren(QShortcut)
    assert len(playback_shortcuts) == 6
    assert {portable(shortcut.key()) for shortcut in playback_shortcuts} == {
        "Return",
        "Enter",
        "Left",
        "Shift+,",
        "Right",
        "Shift+.",
    }
    window.close()


def test_actions_add_layer_duplicate_and_add_empty_frame(application, tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    original_layers = len(window.project.layers)
    window.new_layer_action.trigger()
    assert len(window.project.layers) == original_layers + 1
    assert window.project.layers[-1].name == "Layer 2"

    layer_id = window.project.layers[0].id
    window.project.frames[0].layer_pixels[layer_id][0, 0] = [5, 6, 7, 255]
    source = window.project.frames[0].layer_pixels[layer_id]
    window.frame_index = 0
    window.new_frame_action.trigger()
    duplicate = window.project.frames[1].layer_pixels[layer_id]
    assert np.array_equal(source, duplicate)
    assert source is not duplicate
    assert window.frame_index == 1

    window.frame_index = 0
    window.new_empty_frame_action.trigger()
    assert window.frame_index == 1
    assert not window.project.frames[1].layer_pixels[layer_id].any()
    window.dirty = False
    window.close()


def test_layer_actions_refresh_timeline_and_canvas_selection(application, tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    window.new_layer_action.trigger()
    assert window.timeline.table.rowCount() == 2
    assert window.layer_index == 1
    assert window.canvas.layer_index == 1
    window.delete_layer_action.trigger()
    assert window.timeline.table.rowCount() == 1
    assert window.layer_index == 0
    assert window.canvas.layer_index == 0
    window.dirty = False
    window.close()


def test_keyboard_shortcut_invokes_command_once(application, tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    window.show()
    window.activateWindow()
    window.setFocus()
    application.processEvents()
    before = len(window.project.layers)
    QTest.keyClick(window, Qt.Key.Key_N, Qt.KeyboardModifier.ShiftModifier)
    application.processEvents()
    assert len(window.project.layers) == before + 1

    frame_count = len(window.project.frames)
    QTest.keyClick(window, Qt.Key.Key_N, Qt.KeyboardModifier.AltModifier)
    application.processEvents()
    assert len(window.project.frames) == frame_count + 1
    frame_count = len(window.project.frames)
    QTest.keyClick(window, Qt.Key.Key_B, Qt.KeyboardModifier.AltModifier)
    application.processEvents()
    assert len(window.project.frames) == frame_count + 1
    window.dirty = False
    window.close()


def test_changed_shortcuts_update_actions_and_persist(application, tmp_path) -> None:
    service = service_for(tmp_path)
    window = MainWindow(service)
    changed = {
        "new_layer": "Ctrl+Shift+L",
        "new_frame": "Ctrl+Alt+N",
        "new_empty_frame": "",
        "play_stop_animation": "Space",
    }
    assert window.apply_shortcuts(changed)
    assert portable(window.new_layer_action.shortcut()) == "Ctrl+Shift+L"
    assert window.new_empty_frame_action.shortcut().isEmpty()
    restored = service_for(tmp_path).load()
    assert restored["new_layer"] == ["Ctrl+Shift+L"]
    assert restored["new_frame"] == ["Ctrl+Alt+N"]
    assert restored["new_empty_frame"] == []
    assert restored["play_stop_animation"] == ["Space"]
    window.close()


def test_project_settings_uses_latest_project_state(application, tmp_path) -> None:
    window = MainWindow(service_for(tmp_path))
    first = window.create_project_settings_dialog()
    assert first.name_edit.text() == "Untitled"
    assert first.current_size_label.text() == "64 × 64"
    assert "File: Not Saved" in first.info_label.text()
    assert "Frames: 1" in first.info_label.text()
    assert "Layers: 1" in first.info_label.text()
    assert "Format: 5" in first.info_label.text()

    window.project.name = "Burst"
    window.project.add_frame()
    window.project.add_layer()
    window.project.fps = 24
    window.project.loop = False
    window.dirty = True
    latest = window.create_project_settings_dialog()
    assert latest.name_edit.text() == "Burst"
    assert latest.fps_spin.value() == 24
    assert not latest.loop_check.isChecked()
    assert "Frames: 2" in latest.info_label.text()
    assert "Layers: 2" in latest.info_label.text()
    window.dirty = False
    window.close()
